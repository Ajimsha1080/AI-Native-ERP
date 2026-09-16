"""
Chat API Endpoint

Handles communication between the Frontend Copilot UI and the Backend Autonomous Agents.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
import asyncio

from packages.agents.base import BaseAgent
from packages.tools.erp_tools import check_inventory, check_revenue, check_pending_invoices

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

@router.post("")
async def chat_with_agent(request: ChatRequest):
    """
    Agentic Copilot Chat Engine
    Parses user input and routes through BaseAgent ReAct loop with function calling and tool execution.
    """
    if not request.messages:
        return {"response": "Hello! How can I help you with your enterprise operations today?"}
    
    last_message = request.messages[-1].content
    
    copilot_agent = BaseAgent(
        name="Enterprise ERP Copilot",
        role="Autonomous Enterprise Operations & Financial Orchestration"
    )
    
    result = await copilot_agent.execute_task(last_message)
    response_text = result.get("output") or "Task processed successfully."
    
    return {
        "response": response_text,
        "agent": result.get("agent"),
        "tool_calls": result.get("tool_calls", []),
        "status": result.get("status", "completed"),
        "tokens_used": result.get("tokens_used", 0)
    }
