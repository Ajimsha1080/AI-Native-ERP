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
    current_user: Optional[CurrentUser] = None
):
    """
    6-Layer Agent & RAG Ingress Orchestrator:
    Ingress Guardrails -> Intent Routing -> Query Rewrite -> Hybrid RAG -> Groundedness Gate -> LLM Gateway
    """
    if not request.messages:
        return {"response": "Hello! I am your Enterprise ERP Orchestrator. How can I assist with your operations today?"}

    last_user_message = request.messages[-1].content
    session_id = request.session_id or "default-session"
    org_id = getattr(current_user, "org_id", None) or UUID("00000000-0000-0000-0000-000000000001")

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

    # -------------------------------------------------------------------------
    # LAYER 2 - 6: Dispatch across 4-Way Router & Hybrid RAG Engine
    # -------------------------------------------------------------------------
    runtime_res: AgentRuntimeResponse = await agent_runtime.dispatch(
        query=sanitized_query,
        organization_id=org_id,
        chat_history=chat_history,
        scope=request.scope
    )

    # Persist turns to memory buffer
    memory = memory_manager.get_memory_for_agent("Master ERP Orchestrator")
    memory.add_conversation_turn(role="user", message=last_user_message, metadata={"session_id": session_id})
    memory.add_conversation_turn(role="assistant", message=runtime_res.response_text, metadata={"branch": runtime_res.branch})

    return {
        "branch": runtime_res.branch,
        "intent_description": runtime_res.intent_description,
        "response": runtime_res.response_text,
        "latency_ms": runtime_res.latency_ms,
        "citations": runtime_res.citations,
        "groundedness_score": runtime_res.groundedness_score,
        "data": runtime_res.data
    }
