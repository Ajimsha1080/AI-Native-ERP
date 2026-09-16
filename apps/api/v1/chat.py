"""
Chat API Endpoint

Master Agent Orchestrator handling communication between the Frontend Copilot UI
and Backend Domain Agents with persistent conversational memory buffer.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio

from packages.agents.base import BaseAgent
from packages.agents.memory import memory_manager
from packages.tools.erp_tools import check_inventory, check_revenue, check_pending_invoices

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = "default-session"

def route_master_agent(user_query: str) -> BaseAgent:
    """Classifies user intent and assigns the appropriate specialized domain agent."""
    q_lower = user_query.lower()

    if any(k in q_lower for k in ["revenue", "invoice", "finance", "arr", "billing", "payment", "balance", "credit"]):
        return BaseAgent(
            name="Finance Agent",
            role="Autonomous Financial Controller, AR/AP Auditing & Revenue Intelligence"
        )
    elif any(k in q_lower for k in ["inventory", "stock", "warehouse", "sku", "supply", "level"]):
        return BaseAgent(
            name="Inventory Agent",
            role="Autonomous Warehouse Logistics & Multi-Facility Stock Controller"
        )
    elif any(k in q_lower for k in ["purchase order", "po", "supplier", "vendor", "procure", "procurement", "sourcing"]):
        return BaseAgent(
            name="Procurement Agent",
            role="Autonomous Strategic Sourcing, Supplier Negotiation & PO Creation"
        )
    else:
        return BaseAgent(
            name="Master ERP Orchestrator",
            role="Enterprise Multi-Domain Autonomous Orchestration & Executive Decisioning"
        )

@router.post("")
async def chat_with_agent(request: ChatRequest):
    """
    Master Agent Copilot Chat Engine
    Routes query through domain-specific autonomous agent, persists conversational context,
    and executes tool calling with real enterprise grounding.
    """
    if not request.messages:
        return {"response": "Hello! I am your Enterprise ERP Orchestrator. How can I assist with your business operations today?"}
    
    last_user_message = request.messages[-1].content
    session_id = request.session_id or "default-session"
    
    # 1. Domain Agent Routing via Master Orchestrator
    assigned_agent = route_master_agent(last_user_message)
    
    # 2. Persist User Turn to Conversational Buffer
    memory = memory_manager.get_memory_for_agent(assigned_agent.name)
    memory.add_conversation_turn(
        role="user",
        message=last_user_message,
        metadata={"session_id": session_id}
    )

    # 3. Retrieve recent conversational context
    context_turns = memory.get_conversation_context(max_turns=4)
    
    # 4. Execute Autonomous Task through BaseAgent ReAct Loop
    result = await assigned_agent.execute_task(
        prompt=last_user_message,
        context={"history": context_turns, "session_id": session_id}
    )
    
    response_text = result.get("output") or "Task processed successfully."

    # 5. Persist Assistant Response to Conversational Buffer
    memory.add_conversation_turn(
        role="assistant",
        message=response_text,
        metadata={"tool_calls_count": len(result.get("tool_calls", []))}
    )
    
    return {
        "response": response_text,
        "agent": result.get("agent"),
        "role": result.get("role"),
        "tool_calls": result.get("tool_calls", []),
        "status": result.get("status", "completed"),
        "tokens_used": result.get("tokens_used", 0),
        "grounding": result.get("grounding"),
        "memory_turns_tracked": len(memory.short_term_buffer)
    }

