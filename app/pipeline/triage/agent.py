"""Triage agent — the core brain of the SRE system.

Takes an incident description (+ optional attachments), loads relevant codebase
context from the Solidus index, and calls Claude to produce a structured triage.
"""

import logging
from dataclasses import dataclass

import anthropic

from app.config import settings
from app.services.codebase_indexer import CodebaseIndex, search_files

logger = logging.getLogger(__name__)

TRIAGE_SYSTEM_PROMPT = """\
You are an expert SRE triage agent for a Solidus e-commerce platform.

Your job is to analyze incident reports and produce a structured triage assessment.
You have access to the codebase structure and relevant source files.

When triaging:
1. Assess severity based on user/business impact (P1=critical outage, P2=major degradation, P3=minor issue, P4=cosmetic/low-impact)
2. Identify the most likely affected component in the codebase
3. Provide a technical summary explaining the probable cause
4. Suggest specific files that are likely involved
5. Recommend concrete next actions for the on-call engineer

Be precise and actionable. Reference specific files and code patterns when possible.
"""

TRIAGE_TOOL = {
    "name": "submit_triage",
    "description": "Submit the structured triage assessment for this incident.",
    "input_schema": {
        "type": "object",
        "required": [
            "severity",
            "category",
            "affected_component",
            "technical_summary",
            "root_cause_hypothesis",
            "suggested_assignee",
            "confidence",
            "recommended_actions",
            "related_files",
        ],
        "properties": {
            "severity": {
                "type": "string",
                "enum": ["P1", "P2", "P3", "P4"],
                "description": "Incident severity. P1=critical outage affecting all users, P2=major feature broken, P3=minor issue, P4=cosmetic.",
            },
            "category": {
                "type": "string",
                "enum": [
                    "payment-processing",
                    "checkout",
                    "inventory",
                    "shipping",
                    "authentication",
                    "admin",
                    "storefront",
                    "api",
                    "infrastructure",
                    "other",
                ],
                "description": "Primary category of the incident.",
            },
            "affected_component": {
                "type": "string",
                "description": "Specific module, service, or component affected (e.g., 'Spree::Payment', 'checkout flow', 'admin/orders controller').",
            },
            "technical_summary": {
                "type": "string",
                "description": "2-3 paragraph technical analysis of the incident and probable cause.",
            },
            "root_cause_hypothesis": {
                "type": "string",
                "description": "Most likely root cause based on the incident description and codebase analysis.",
            },
            "suggested_assignee": {
                "type": "string",
                "enum": [
                    "payments-team",
                    "platform-team",
                    "frontend-team",
                    "infrastructure-team",
                    "security-team",
                    "fulfillment-team",
                ],
                "description": "Recommended team to handle this incident.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence in the triage assessment (0.0-1.0).",
            },
            "recommended_actions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Concrete next steps for the on-call engineer.",
            },
            "related_files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["path", "relevance"],
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path relative to repo root.",
                        },
                        "relevance": {
                            "type": "string",
                            "description": "Why this file is relevant to the incident.",
                        },
                    },
                },
                "description": "Codebase files relevant to this incident.",
            },
        },
    },
}


@dataclass(frozen=True)
class TriageResult:
    """Structured triage output from the agent."""

    severity: str
    category: str
    affected_component: str
    technical_summary: str
    root_cause_hypothesis: str
    suggested_assignee: str
    confidence: float
    recommended_actions: list[str]
    related_files: list[dict[str, str]]
    tokens_in: int
    tokens_out: int


def _build_codebase_context(index: CodebaseIndex, description: str) -> str:
    """Build the codebase context section for the prompt."""
    if not index.files:
        return "No codebase context available."

    parts: list[str] = []

    # Structure overview
    parts.append("## Codebase Overview")
    parts.append(index.structure_summary)
    parts.append("")

    # Relevant files
    relevant = search_files(index, description, max_results=5)
    if relevant:
        parts.append("## Relevant Source Files")
        for f in relevant:
            parts.append(f"### {f.path}")
            parts.append(f"```{f.extension.lstrip('.')}")
            parts.append(f.first_lines)
            parts.append("```")
            parts.append("")

    return "\n".join(parts)


async def run_triage(
    description: str,
    codebase_index: CodebaseIndex,
    attachment_descriptions: list[str] | None = None,
) -> TriageResult:
    """Run the triage agent on an incident description.

    Args:
        description: The incident description from the reporter.
        codebase_index: Pre-built index of the target codebase.
        attachment_descriptions: Optional text descriptions of attached files.

    Returns:
        TriageResult with the structured triage assessment.

    Raises:
        anthropic.APIError: If the Claude API call fails.
        ValueError: If the model response doesn't contain valid triage data.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Build context
    codebase_context = _build_codebase_context(codebase_index, description)

    # Build user message
    user_parts: list[str] = [
        "## Incident Report",
        "",
        description,
    ]

    if attachment_descriptions:
        user_parts.append("")
        user_parts.append("## Attached Files")
        for desc in attachment_descriptions:
            user_parts.append(f"- {desc}")

    user_parts.append("")
    user_parts.append("## Target Codebase Context")
    user_parts.append(codebase_context)
    user_parts.append("")
    user_parts.append(
        "Analyze this incident and submit your triage assessment using the submit_triage tool."
    )

    user_message = "\n".join(user_parts)

    logger.info("Running triage agent (description length: %d chars)", len(description))

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=TRIAGE_SYSTEM_PROMPT,
        tools=[TRIAGE_TOOL],
        tool_choice={"type": "tool", "name": "submit_triage"},
        messages=[{"role": "user", "content": user_message}],
    )

    # Extract tool use result
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_triage":
            data = block.input
            return TriageResult(
                severity=data["severity"],
                category=data["category"],
                affected_component=data["affected_component"],
                technical_summary=data["technical_summary"],
                root_cause_hypothesis=data["root_cause_hypothesis"],
                suggested_assignee=data["suggested_assignee"],
                confidence=data["confidence"],
                recommended_actions=data["recommended_actions"],
                related_files=data["related_files"],
                tokens_in=response.usage.input_tokens,
                tokens_out=response.usage.output_tokens,
            )

    raise ValueError("Triage agent did not return a valid tool_use response")