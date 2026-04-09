"""LangChain triage provider — Google Gemini or Groq free tier.

Uses LangChain with_structured_output(TriageResult) for schema-enforced responses.
Fallback chain: Gemini Flash → Groq Llama (both free tier, no credit card).
"""

import logging

from app.config import settings
from app.pipeline.triage.agent import TRIAGE_SYSTEM_PROMPT, TriageResult

logger = logging.getLogger(__name__)


class LangChainProvider:
    """Triage provider using LangChain with structured output + model fallbacks."""

    async def triage(
        self,
        description: str,
        codebase_context: str,
        attachment_descriptions: list[str] | None = None,
    ) -> TriageResult:
        chain = self._build_chain()

        user_parts = [
            "## Incident Report\n",
            description,
        ]
        if attachment_descriptions:
            user_parts.append("\n## Attached Files")
            for desc in attachment_descriptions:
                user_parts.append(f"- {desc}")
        user_parts.append(f"\n## Target Codebase Context\n{codebase_context}")
        user_parts.append("\nAnalyze this incident and submit your structured triage assessment.")

        user_message = "\n".join(user_parts)

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=TRIAGE_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]

        logger.info("LangChainProvider: running structured triage (description: %d chars)", len(description))

        result = await chain.ainvoke(messages)

        # with_structured_output returns a TriageResult directly (or dict depending on provider)
        if isinstance(result, TriageResult):
            result.engine = "basic"
            return result

        # Some providers return a dict — convert
        if isinstance(result, dict):
            return TriageResult(engine="basic", **result)

        raise ValueError(f"LangChain provider returned unexpected type: {type(result)}")

    def _build_chain(self):
        """Build a structured output chain with model fallbacks."""
        google_key = getattr(settings, "google_api_key", "")
        groq_key = getattr(settings, "groq_api_key", "")

        primary = None
        fallbacks = []

        if google_key:
            from langchain_google_genai import ChatGoogleGenerativeAI
            gemini = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=google_key,
                temperature=0.1,
            )
            primary = gemini.with_structured_output(TriageResult)

        if groq_key:
            from langchain_groq import ChatGroq
            groq = ChatGroq(
                model="llama-3.3-70b-versatile",
                groq_api_key=groq_key,
                temperature=0.1,
            )
            groq_structured = groq.with_structured_output(TriageResult)
            if primary is None:
                primary = groq_structured
            else:
                fallbacks.append(groq_structured)

        if primary is None:
            raise ValueError(
                "LangChain provider requires GOOGLE_API_KEY or GROQ_API_KEY. "
                "Set one in your .env file."
            )

        if fallbacks:
            return primary.with_fallbacks(fallbacks)
        return primary
