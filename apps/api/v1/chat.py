"""
Layer 1: Ingress & Policy Guardrails Chat API.

Coordinates the 6-Layer Architecture:
- Layer 1: Ingress & Policy Guardrails (Rate Limiting, Tenant Quota, Prompt Injection)
- Layer 2: Intent Classification & 4-Way Routing (agent_runtime.py)
- Layer 3: Query Reformulation (query_rewrite.py)
- Layer 4: Hybrid RAG Engine (rag_engine.py & embedding_service.py)
- Layer 5: Anti-Hallucination Guardrail Decision Gate (rag_engine.py)
- Layer 6: LLM Gateway & Synthesis (llm_service.py)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from uuid import UUID

from packages.security.guardrails import guardrails
from packages.agents.agent_runtime import agent_runtime, AgentRuntimeResponse
from packages.agents.memory import memory_manager
from packages.auth.dependencies import CurrentUser
from packages.database.tenant_context import TenantDB

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = "default-session"
    scope: Optional[str] = None


@router.post("")
async def chat_with_agent(
    request: ChatRequest,
    current_user: CurrentUser,
    db: TenantDB,
):
    """
    6-Layer Agent & RAG Ingress Orchestrator:
    Ingress Guardrails -> Intent Routing -> Query Rewrite -> Hybrid RAG -> Groundedness Gate -> LLM Gateway
    """
    if not request.messages:
        return {"response": "Hello! I am your Enterprise ERP Orchestrator. How can I assist with your operations today?"}

    last_user_message = request.messages[-1].content
    session_id = request.session_id or "default-session"
    org_id = current_user.org_id

    from packages.billing.plan_limits import PlanLimitEnforcer
    await PlanLimitEnforcer.check_token_budget(db, org_id, tokens_requested=100)

    # -------------------------------------------------------------------------
    # LAYER 1: Ingress & Policy Guardrails (Anti-Spam, Rate Limit, Injection Scrub)
    # -------------------------------------------------------------------------
    is_safe, sanitized_query, rejection = guardrails.validate_input_query(last_user_message)
    if not is_safe:
        return {
            "branch": "guardrail_blocked",
            "response": f"⚠️ {rejection}",
            "is_grounded": False,
            "citations": []
        }

    # Format multi-turn history for contextual query rewriter
    chat_history = [{"role": m.role, "content": m.content} for m in request.messages[:-1]]

    from packages.config.settings import settings
    if not settings.openai_api_key and not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Service Unavailable: No valid LLM or embedding provider credentials configured on server."
        )

    # -------------------------------------------------------------------------
    # LAYER 2 - 6: Dispatch across 4-Way Router & Hybrid RAG Engine
    # -------------------------------------------------------------------------
    try:
        runtime_res: AgentRuntimeResponse = await agent_runtime.dispatch(
            query=sanitized_query,
            organization_id=org_id,
            chat_history=chat_history,
            scope=request.scope
        )
    except Exception as e:
        from packages.rag.embedding_service import EmbeddingServiceError
        if isinstance(e, EmbeddingServiceError) or "EmbeddingServiceError" in type(e).__name__:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"AI Service Unavailable: {str(e)}"
            )
        raise

    # Sanitize outgoing response text to guarantee no PII, credit cards, or secrets leak
    clean_response = guardrails.sanitize_output(runtime_res.response_text)

    # Persist turns to memory buffer with strict tenant and session isolation
    memory = memory_manager.get_memory_for_agent("Master ERP Orchestrator", organization_id=org_id)
    memory.add_conversation_turn(
        role="user",
        message=sanitized_query,
        session_id=session_id,
        metadata={"session_id": session_id, "user_id": str(current_user.user_id)}
    )
    memory.add_conversation_turn(
        role="assistant",
        message=clean_response,
        session_id=session_id,
        metadata={"branch": runtime_res.branch}
    )

    return {
        "branch": runtime_res.branch,
        "intent_description": runtime_res.intent_description,
        "response": clean_response,
        "latency_ms": runtime_res.latency_ms,
        "citations": runtime_res.citations,
        "groundedness_score": runtime_res.groundedness_score,
        "data": runtime_res.data
    }
