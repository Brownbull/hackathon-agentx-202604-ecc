"""Progressive disclosure knowledge loader.

Loads curated codebase knowledge in layers:
  L0 — Architecture Map (~500 tokens)     → always loaded
  L1 — Component Index (~1,500 tokens)    → always loaded
  L2 — Domain Deep-Dive (~900 tokens)     → on-demand per triage (keyword-matched)
  L3 — Source Code (variable)             → fallback to actual codebase files
"""

import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Domain keywords extracted from L1 component index
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "payment": [
        "payment", "charge", "gateway", "stripe", "refund", "credit card",
        "transaction", "authorize", "capture", "void", "checkout payment",
    ],
    "inventory": [
        "stock", "inventory", "out of stock", "oversell", "count_on_hand",
        "backorder", "warehouse", "stock location", "quantity",
    ],
    "orders": [
        "order", "checkout", "cart", "line item", "place order", "order stuck",
        "order state", "address", "delivery",
    ],
    "search": [
        "search", "autocomplete", "product search", "keyword search",
        "search index", "ransack", "filter", "sort",
    ],
    "auth": [
        "login", "authentication", "password", "session", "token", "permission",
        "role", "admin access", "403", "unauthorized", "forbidden",
    ],
    "shipping": [
        "shipping", "shipment", "carrier", "tracking", "delivery rate",
        "shipping method", "freight", "ship",
    ],
}


class KnowledgeLoader:
    """Progressive disclosure loader for codebase knowledge."""

    def __init__(self, knowledge_dir: str | Path):
        self.knowledge_dir = Path(knowledge_dir)
        self.codebase_dir = Path(settings.ecommerce_repo_path)

        # L0 + L1 loaded once at startup (always in context)
        self.l0 = self._load_file("codebase-L0-architecture.md")
        self.l1 = self._load_file("codebase-L1-component-index.md")

        domains = [f.stem.replace("codebase-L2-", "") for f in self.knowledge_dir.glob("codebase-L2-*.md")]
        logger.info(
            "KnowledgeLoader initialized: L0=%d chars, L1=%d chars, L2 domains=%s",
            len(self.l0), len(self.l1), domains,
        )

    def get_context(self, description: str) -> str:
        """Build triage context from progressive disclosure layers.

        1. Always includes L0 (architecture) + L1 (component index)
        2. Keyword-matches description to load the best L2 domain file
        3. Falls back to L3 (actual source files) if no L2 match
        """
        domain = self._match_domain(description)
        parts = [self.l0, self.l1]

        if domain:
            l2 = self._load_file(f"codebase-L2-{domain}.md")
            if l2:
                parts.append(l2)
                logger.info("KnowledgeLoader: matched domain '%s' for L2 context", domain)
        else:
            logger.info("KnowledgeLoader: no L2 domain match, using L0+L1 only")

        return "\n\n".join(parts)

    def get_l3_files(self, file_paths: list[str], max_files: int = 5, max_lines: int = 100) -> str:
        """Fallback: read actual codebase files from the mounted repo."""
        if not self.codebase_dir.exists():
            return ""

        parts: list[str] = []
        for path_str in file_paths[:max_files]:
            clean_path = path_str.split("#")[0]  # strip line references
            full_path = self.codebase_dir / clean_path
            if full_path.is_file():
                try:
                    lines = full_path.read_text(errors="replace").splitlines()[:max_lines]
                    ext = full_path.suffix.lstrip(".")
                    parts.append(f"### {clean_path}\n```{ext}\n" + "\n".join(lines) + "\n```")
                except OSError:
                    pass
        return "\n\n".join(parts)

    def _match_domain(self, description: str) -> str | None:
        """Match incident description keywords against domain index. Returns best domain or None."""
        desc_lower = description.lower()
        scores: dict[str, int] = {}

        for domain, keywords in DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in desc_lower)
            if score > 0:
                scores[domain] = score

        if not scores:
            return None

        return max(scores, key=scores.get)

    def _load_file(self, filename: str) -> str:
        """Load a knowledge file, return empty string if missing."""
        path = self.knowledge_dir / filename
        if path.is_file():
            return path.read_text(errors="replace").strip()
        return ""
