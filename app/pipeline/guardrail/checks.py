"""Guardrail checks — validates incident input safety before LLM triage.

Runs pattern-based injection detection, PII flagging, and input validation.
Designed as defense-in-depth: flags suspicious content but only blocks
clear injection attempts.
"""

import re
from dataclasses import dataclass

# --- Prompt injection patterns ---
# Known injection templates and jailbreak attempts
INJECTION_PATTERNS: list[tuple[str, float]] = [
    # Direct instruction override
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)", 0.95),
    (r"disregard\s+(all\s+)?(previous|prior|above)", 0.90),
    (r"forget\s+(everything|all|your)\s+(you|instructions|rules)", 0.90),
    # Role hijacking
    (r"you\s+are\s+now\s+(a|an|the)\s+", 0.80),
    (r"act\s+as\s+(a|an|the)\s+", 0.60),
    (r"pretend\s+(you|to)\s+(are|be)\s+", 0.85),
    (r"from\s+now\s+on\s+you\s+(will|must|should)", 0.80),
    # System prompt extraction
    (r"(show|print|reveal|output|display)\s+(your|the)\s+(system|initial)\s+prompt", 0.95),
    (r"what\s+(are|is)\s+your\s+(instructions|system\s+prompt|rules)", 0.85),
    (r"repeat\s+(your|the)\s+(system|initial)\s+(prompt|instructions)", 0.95),
    # Encoded/obfuscated attacks
    (r"base64\s*(decode|encode)", 0.70),
    (r"\\x[0-9a-fA-F]{2}", 0.50),
    # Output manipulation
    (r"respond\s+only\s+with", 0.70),
    (r"output\s+(only|just)\s+(the|a)", 0.60),
    (r"do\s+not\s+(mention|include|add)\s+(any|the)", 0.50),
    # SQL injection patterns (matched against lowercased text)
    (r";\s*(drop|delete|update|insert|alter|truncate)\s+", 0.95),
    (r"union\s+select\s+", 0.90),
    (r"'\s*(or|and)\s+'?\d*'?\s*=\s*'?\d*", 0.85),
    (r"--\s*$", 0.40),  # SQL comment at end (low weight — common in text)
    # XSS / template injection
    (r"<script[\s>]", 0.90),
    (r"javascript\s*:", 0.85),
    (r"on(error|load|click|mouseover)\s*=", 0.85),
    (r"\{\{.*constructor", 0.90),
    (r"\$\{.*(runtime|process|exec)", 0.90),
]

# --- PII patterns ---
# High-confidence PII (always flag)
PII_PATTERNS: dict[str, str] = {
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    "api_key": r"(?:sk|pk|api|key|token|secret)[-_]?[a-zA-Z0-9]{16,}",
    "phone": r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
}

# Low-confidence PII (expected in SRE incident reports — flag separately)
PII_PATTERNS_LOW: dict[str, str] = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
}

# Max description length (bytes)
MAX_DESCRIPTION_BYTES = 10_000


@dataclass(frozen=True)
class GuardrailResult:
    """Result of guardrail validation."""
    passed: bool
    flags: list[str]
    injection_score: float
    rejected: bool
    rejection_reason: str | None


def check_injection(text: str) -> tuple[float, list[str]]:
    """Scan text for prompt injection patterns.

    Returns (score, matched_patterns) where score is 0.0-1.0.
    Uses max pattern score boosted by number of distinct matches:
    each additional match adds 10% of the remaining gap to 1.0.
    """
    text_lower = text.lower()
    max_score = 0.0
    matches: list[str] = []

    for pattern, weight in INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            max_score = max(max_score, weight)
            matches.append(pattern[:40])

    # Boost score when multiple patterns match (combined signal)
    if len(matches) > 1:
        boost = (1.0 - max_score) * 0.10 * (len(matches) - 1)
        max_score = min(max_score + boost, 1.0)

    return max_score, matches


def check_pii(text: str) -> list[str]:
    """Scan text for PII patterns. Returns list of detected PII types.

    High-confidence PII (SSN, credit card, API key, phone) is always flagged.
    Low-confidence PII (email, IP) is common in SRE reports and tagged with
    a '_low' suffix so callers can treat it differently.
    """
    found: list[str] = []
    for pii_type, pattern in PII_PATTERNS.items():
        if re.search(pattern, text):
            found.append(pii_type)
    for pii_type, pattern in PII_PATTERNS_LOW.items():
        if re.search(pattern, text):
            found.append(f"{pii_type}_low")
    return found


def validate_input(description: str) -> GuardrailResult:
    """Run all guardrail checks on an incident description.

    Returns a GuardrailResult with pass/fail, flags, and injection score.
    """
    flags: list[str] = []
    rejection_reason: str | None = None

    # --- Size check ---
    if len(description.encode("utf-8")) > MAX_DESCRIPTION_BYTES:
        flags.append("oversized_input")

    # --- Injection detection ---
    injection_score, injection_matches = check_injection(description)
    if injection_matches:
        flags.append("injection_patterns_detected")
    if injection_score >= 0.90:
        flags.append("high_injection_risk")

    # --- PII scan (flag, don't block) ---
    pii_types = check_pii(description)
    if pii_types:
        flags.append(f"contains_pii:{','.join(pii_types)}")

    # --- Decision ---
    rejected = injection_score >= 0.90
    if rejected:
        rejection_reason = (
            f"Input rejected: high prompt injection risk "
            f"(score: {injection_score:.2f}, patterns: {len(injection_matches)})"
        )

    return GuardrailResult(
        passed=not rejected,
        flags=flags,
        injection_score=injection_score,
        rejected=rejected,
        rejection_reason=rejection_reason,
    )
