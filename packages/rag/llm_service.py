"""
Layer 6: LLM Gateway & Response Synthesis Service.

Supports multi-model synthesis gateways (Sarvam AI 105B, Custom Models, OpenAI, Anthropic),
response sanitization, and citation deduplication.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from packages.config.settings import settings

logger = logging.getLogger("rag.llm_service")


class LLMGateway:
    """Enterprise LLM Gateway with multi-provider routing & citation deduplication."""

    def __init__(self):
        self.provider = getattr(settings, "llm_provider", "openai")

    def synthesize(
        self,
        prompt: str,
        context: str,
        model_override: Optional[str] = None,
        temperature: float = 0.0
    ) -> str:
        """
        Executes zero-temperature synthesis via the configured LLM Gateway.
        """
        # 1. Universal LiteLLM Multi-Model Gateway (OpenAI, Anthropic, Gemini, Bedrock)
        api_key = getattr(settings, "openai_api_key", "")
        anthropic_key = getattr(settings, "anthropic_api_key", "")
        google_key = getattr(settings, "google_api_key", "")

        if (api_key and api_key.startswith("sk-")) or anthropic_key or google_key:
            try:
                from packages.ai import litellm_gateway
                model = model_override or getattr(settings, "litellm_model", "gpt-4o-mini")
                res = litellm_gateway.completion(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a precise enterprise ERP AI. Answer questions strictly from context. Do not speculate."},
                        {"role": "user", "content": f"Context:\n{context}\n\nQuestion:\n{prompt}\n\nAnswer:"}
                    ],
                    temperature=temperature,
                    max_tokens=600
                )
                raw_ans = res.choices[0].message.content.strip()
                if raw_ans:
                    return self.sanitize_response(raw_ans)
            except Exception as e:
                logger.warning(f"LiteLLM Gateway call failed, falling back to extractive synthesis: {e}")

        # 2. Deterministic Extractive Synthesis Fallback
        return self._extractive_synthesis(prompt, context)

    def _extractive_synthesis(self, question: str, context: str) -> str:
        """Extracts high-relevance declarative facts from context."""
        sentences = [s.strip() for s in context.split(".") if s.strip()]
        q_tokens = set(re.findall(r"\b\w+\b", question.lower()))

        matched = []
        for s in sentences:
            s_tokens = set(re.findall(r"\b\w+\b", s.lower()))
            if len(q_tokens & s_tokens) >= 2:
                matched.append(s)

        if matched:
            text = ". ".join(matched[:3]) + "."
        elif sentences:
            text = ". ".join(sentences[:2]) + "."
        else:
            text = "No verified data records found."

        return self.sanitize_response(text)

    def sanitize_response(self, text: str) -> str:
        """Sanitizes raw response text and cleans formatting anomalies."""
        cleaned = re.sub(r"\s+", " ", text).strip()
        return cleaned

    def deduplicate_citations(self, citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicates and standardizes citation records."""
        seen = set()
        unique_citations = []
        for c in citations:
            key = (c.get("document_title"), c.get("chunk_index"))
            if key not in seen:
                seen.add(key)
                unique_citations.append(c)
        return unique_citations


# Global LLM Gateway
llm_gateway = LLMGateway()
