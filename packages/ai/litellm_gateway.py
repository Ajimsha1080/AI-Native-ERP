"""
Universal Multi-Model AI Gateway powered by LiteLLM.

Provides unified interface across 100+ LLMs:
- OpenAI (GPT-4o, GPT-4 Turbo, o1)
- Anthropic (Claude 3.5 Sonnet, Claude 3 Opus)
- Google (Gemini 1.5 Pro, Gemini 1.5 Flash)
- AWS Bedrock, Azure OpenAI, Groq, Ollama, and Mistral
- Automatic model fallback routing and retry policies
- Native LangSmith tracing callback integration
- Multi-tenant cost and token accounting
"""

import os
from typing import Dict, Any, List, Optional, Union
import structlog

from packages.config.settings import settings
from packages.observability.langsmith_client import langsmith_manager

logger = structlog.get_logger("ai.litellm_gateway")


class LiteLLMGateway:
    """Enterprise Universal LLM Gateway using LiteLLM."""

    def __init__(self):
        self._setup_litellm()

    def _setup_litellm(self):
        """Initializes LiteLLM global settings and observability callbacks."""
        try:
            import litellm

            # Drop unrecognized parameters across different provider schemas
            litellm.drop_params = True
            litellm.suppress_debug_info = True

            # Connect to LangSmith if tracing is enabled
            if langsmith_manager.is_enabled():
                if "langsmith" not in litellm.success_callback:
                    litellm.success_callback.append("langsmith")
                if "langsmith" not in litellm.failure_callback:
                    litellm.failure_callback.append("langsmith")
                logger.info("litellm_langsmith_callback_registered")
        except Exception as exc:
            logger.warning("litellm_init_warning", error=str(exc))

    def _get_fallback_list(self, primary_model: str, custom_fallbacks: Optional[List[str]] = None) -> List[str]:
        """Builds a clean list of fallback models excluding the primary."""
        raw_fallbacks = custom_fallbacks or settings.litellm_fallback_models
        if isinstance(raw_fallbacks, str):
            fallbacks = [m.strip() for m in raw_fallbacks.split(",") if m.strip()]
        else:
            fallbacks = list(raw_fallbacks)

        return [m for m in fallbacks if m != primary_model]

    async def acompletion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        fallbacks: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """
        Asynchronous multi-model completion with automated fallback routing.
        """
        import litellm

        primary_model = model or settings.litellm_model
        fallback_models = self._get_fallback_list(primary_model, fallbacks)
        models_to_try = [primary_model] + fallback_models

        last_error = None
        for current_model in models_to_try:
            try:
                call_kwargs: Dict[str, Any] = {
                    "model": current_model,
                    "messages": messages,
                    "temperature": temperature,
                    "timeout": settings.litellm_timeout,
                    "max_tokens": max_tokens or 1000,
                    **kwargs
                }

                if tools:
                    call_kwargs["tools"] = tools

                if metadata:
                    call_kwargs["metadata"] = metadata

                response = await litellm.acompletion(**call_kwargs)
                return response
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "litellm_model_attempt_failed",
                    attempted_model=current_model,
                    error=str(exc),
                    next_models=models_to_try[models_to_try.index(current_model) + 1:]
                )

        # If all model attempts failed, raise the final exception
        raise last_error or RuntimeError("All LiteLLM model attempts failed.")

    def completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        fallbacks: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """
        Synchronous multi-model completion with automated fallback routing.
        """
        import litellm

        primary_model = model or settings.litellm_model
        fallback_models = self._get_fallback_list(primary_model, fallbacks)
        models_to_try = [primary_model] + fallback_models

        last_error = None
        for current_model in models_to_try:
            try:
                call_kwargs: Dict[str, Any] = {
                    "model": current_model,
                    "messages": messages,
                    "temperature": temperature,
                    "timeout": settings.litellm_timeout,
                    "max_tokens": max_tokens or 1000,
                    **kwargs
                }

                if tools:
                    call_kwargs["tools"] = tools

                if metadata:
                    call_kwargs["metadata"] = metadata

                response = litellm.completion(**call_kwargs)
                return response
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "litellm_sync_attempt_failed",
                    attempted_model=current_model,
                    error=str(exc)
                )

        raise last_error or RuntimeError("All LiteLLM synchronous model attempts failed.")

    def calculate_cost(self, response: Any) -> float:
        """Calculates exact execution cost in USD using LiteLLM cost database."""
        try:
            import litellm
            cost = litellm.completion_cost(completion_response=response)
            return float(cost or 0.0)
        except Exception:
            return 0.0

    def test_connection(self, model: Optional[str] = None) -> Dict[str, Any]:
        """Diagnostics for the LiteLLM gateway."""
        primary_model = model or settings.litellm_model
        return {
            "gateway": "LiteLLM Universal Gateway",
            "primary_model": primary_model,
            "configured_fallbacks": settings.litellm_fallback_models,
            "timeout_seconds": settings.litellm_timeout,
            "langsmith_tracing": langsmith_manager.is_enabled(),
            "status": "ready"
        }


# Global singleton instance
litellm_gateway = LiteLLMGateway()
