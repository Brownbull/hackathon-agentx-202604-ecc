"""Triage agent — the core brain of the SRE system.

Takes an incident description (+ optional attachments), loads relevant codebase
context from the Solidus index, and calls Claude to produce a structured triage.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from typing import Literal

if TYPE_CHECKING:
    from app.pipeline.knowledge.loader import KnowledgeLoader

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


class RelatedFile(BaseModel):
    """A codebase file relevant to the incident."""
    path: str = Field(description="File path relative to repo root")
    relevance: str = Field(description="Why this file is relevant to the incident")


class TriageResult(BaseModel):
    """Structured triage output — produced by all engines.

    Pydantic BaseModel (not frozen dataclass) so LangChain can use
    `with_structured_output(TriageResult)` for schema-enforced responses.
    """

    severity: Literal["P1", "P2", "P3", "P4"]
    category: Literal[
        "payment-processing", "checkout", "inventory", "shipping",
        "authentication", "admin", "storefront", "api", "infrastructure", "other",
    ]
    affected_component: str
    technical_summary: str
    root_cause_hypothesis: str
    suggested_assignee: Literal[
        "payments-team", "platform-team", "frontend-team",
        "infrastructure-team", "security-team", "fulfillment-team",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_actions: list[str]
    related_files: list[RelatedFile]
    tokens_in: int = 0
    tokens_out: int = 0
    engine: str = "anthropic"


def verify_files(related_files: list[RelatedFile], codebase_dir: str) -> list[RelatedFile]:
    """Verify each related file exists in the mounted codebase.

    Marks unverified files in the relevance field.
    """
    verified = []
    for f in related_files:
        clean_path = f.path.split("#")[0]  # strip line references
        full_path = os.path.join(codebase_dir, clean_path)
        if not os.path.exists(full_path):
            f = RelatedFile(path=f.path, relevance=f"[UNVERIFIED] {f.relevance}")
        verified.append(f)
    return verified


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
    provider_override: str = "",
    knowledge_loader: "KnowledgeLoader | None" = None,
) -> TriageResult:
    """Run the triage agent on an incident description.

    This is a thin facade that delegates to the configured provider
    (Anthropic, LangChain, or Managed).

    Args:
        description: The incident description from the reporter.
        codebase_index: Pre-built index of the target codebase.
        attachment_descriptions: Optional text descriptions of attached files.
        provider_override: If set, use this provider instead of the default.
        knowledge_loader: Progressive disclosure knowledge (L0-L3). Falls back to codebase_index.

    Returns:
        TriageResult with the structured triage assessment.
    """
    from app.pipeline.triage.provider import get_provider

    provider_name = provider_override or getattr(settings, "triage_provider", "anthropic")
    provider = get_provider(provider_name)

    # Prefer progressive disclosure knowledge over raw codebase dump
    if knowledge_loader:
        codebase_context = knowledge_loader.get_context(description)
        logger.info("Using progressive disclosure knowledge (L0+L1+L2)")
    else:
        codebase_context = _build_codebase_context(codebase_index, description)
        logger.info("Using raw codebase index (no knowledge loader)")

    logger.info(
        "Running triage via %s provider (description: %d chars, context: %d chars)",
        provider_name,
        len(description),
        len(codebase_context),
    )

    result = await provider.triage(
        description=description,
        codebase_context=codebase_context,
        attachment_descriptions=attachment_descriptions,
    )

    # Post-triage: verify related files exist in the codebase
    result.related_files = verify_files(result.related_files, settings.ecommerce_repo_path)

    # Post-triage: sanitize PII from output fields
    from app.pipeline.guardrail.pii import detect_pii, sanitize_text

    pii = detect_pii(description)
    if pii.has_pii:
        logger.info("PII detected in input (%s) — sanitizing output", ", ".join(pii.types))
        result.technical_summary = sanitize_text(result.technical_summary)
        result.root_cause_hypothesis = sanitize_text(result.root_cause_hypothesis)
        result.affected_component = sanitize_text(result.affected_component)
        result.recommended_actions = [sanitize_text(a) for a in result.recommended_actions]
        result.related_files = [
            RelatedFile(path=f.path, relevance=sanitize_text(f.relevance))
            for f in result.related_files
        ]

    return result