"""
Integration tests for Universal LiteLLM Multi-Model Gateway.

Tests:
- Multi-model routing and completion
- Automated fallback execution on model failures
- Cost calculation and token usage accounting
- RAG synthesis integration
- LangSmith callback integration
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pydantic import BaseModel

from packages.config.settings import settings
from packages.ai.litellm_gateway import LiteLLMGateway, litellm_gateway
from packages.rag.llm_service import LLMGateway


class MockChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str
    tool_calls: list = []


class MockChoice(BaseModel):
    message: MockChoiceMessage


class MockUsage(BaseModel):
    prompt_tokens: int = 15
    completion_tokens: int = 25
    total_tokens: int = 40


class MockCompletionResponse:
    def __init__(self, content: str, model: str = "gpt-4o-mini"):
        self.id = "mock-cmpl-123"
        self.model = model
        self.choices = [MockChoice(message=MockChoiceMessage(content=content))]
        self.usage = MockUsage()


def test_litellm_gateway_diagnostics():
    """Verifies LiteLLM gateway diagnostics and default model configurations."""
    gateway = LiteLLMGateway()
    diag = gateway.test_connection()
    assert diag["gateway"] == "LiteLLM Universal Gateway"
    assert diag["primary_model"] == settings.litellm_model
    assert diag["status"] == "ready"


def test_litellm_fallback_list_logic():
    """Verifies fallback list filtering removes primary model to avoid redundant retries."""
    gateway = LiteLLMGateway()
    fallbacks = gateway._get_fallback_list(
        primary_model="gpt-4o-mini",
        custom_fallbacks=["gpt-4o-mini", "claude-3-5-sonnet", "gemini-1.5-flash"]
    )
    assert "gpt-4o-mini" not in fallbacks
    assert "claude-3-5-sonnet" in fallbacks
    assert "gemini-1.5-flash" in fallbacks


@pytest.mark.asyncio
async def test_litellm_acompletion_mock():
    """Tests async multi-model completion with usage and cost accounting."""
    gateway = LiteLLMGateway()
    mock_resp = MockCompletionResponse("The current inventory for SKU-ALUM-8020 is 42 units.")

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
        mock_acompletion.return_value = mock_resp

        messages = [
            {"role": "system", "content": "You are an ERP Assistant."},
            {"role": "user", "content": "Check stock for SKU-ALUM-8020"}
        ]

        resp = await gateway.acompletion(
            messages=messages,
            model="gpt-4o-mini",
            temperature=0.0
        )

        assert resp.choices[0].message.content == "The current inventory for SKU-ALUM-8020 is 42 units."
        assert resp.usage.total_tokens == 40
        mock_acompletion.assert_called_once()


@pytest.mark.asyncio
async def test_litellm_automatic_fallback_routing():
    """Tests that a failure in the primary model automatically fails over to the fallback model."""
    gateway = LiteLLMGateway()
    fallback_resp = MockCompletionResponse("Response from Claude fallback model", model="claude-3-5-sonnet")

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
        # First call (primary gpt-4o-mini) raises RateLimitError / 429
        # Second call (fallback claude-3-5-sonnet) succeeds
        mock_acompletion.side_effect = [
            Exception("429 RateLimitError: TPM quota exceeded"),
            fallback_resp
        ]

        messages = [{"role": "user", "content": "Synthesize report"}]
        resp = await gateway.acompletion(
            messages=messages,
            model="gpt-4o-mini",
            fallbacks=["claude-3-5-sonnet"]
        )

        assert resp.choices[0].message.content == "Response from Claude fallback model"
        assert mock_acompletion.call_count == 2


def test_litellm_rag_synthesis_service():
    """Tests RAG LLMGateway.synthesize using LiteLLM gateway with extractive fallback safety."""
    rag_llm = LLMGateway()
    prompt = "What is the delivery timeline for PO-9921?"
    context = "Purchase Order PO-9921 is scheduled for expedited delivery on Friday."

    # When no real API key is set, ensures graceful deterministic fallback
    result = rag_llm.synthesize(prompt, context)
    assert len(result) > 0
    assert "PO-9921" in result or "expedited delivery" in result


def test_litellm_langsmith_callback_wiring():
    """Verifies LiteLLM connects to LangSmith when tracing is enabled."""
    with patch.object(settings, "langchain_tracing_v2", True), \
         patch.object(settings, "langchain_api_key", "lsv2_test_key_12345"):
        
        import litellm
        gateway = LiteLLMGateway()
        gateway._setup_litellm()

        assert "langsmith" in litellm.success_callback
        assert "langsmith" in litellm.failure_callback
