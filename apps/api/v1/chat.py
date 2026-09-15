"""
Chat API Endpoint

Handles communication between the Frontend Copilot UI and the Backend Agents.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
import asyncio

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
    Parses user input and routes to the appropriate tool, returning a natural language response.
    """
    if not request.messages:
        return {"response": "Hello! How can I help you today?"}
    
    last_message = request.messages[-1].content.lower()
    
    # Non-blocking slight delay for async responsiveness
    await asyncio.sleep(0.05)

    # Simple keyword-based intent routing (Mocking an LLM)
    if "revenue" in last_message:
        tool_result = check_revenue()
        return {"response": f"I checked the financial systems for you. {tool_result} Is there anything else you'd like to analyze?"}
    
    elif "inventory" in last_message or "stock" in last_message or "sku" in last_message:
        # Hardcoding the SKU extraction for the mock
        if "sku-9921" in last_message:
            tool_result = check_inventory("SKU-9921")
        else:
            tool_result = check_inventory("SKU-8840")
        
        return {"response": f"I've accessed the warehouse management system. {tool_result}"}
        
    elif "invoice" in last_message or "approval" in last_message:
        tool_result = check_pending_invoices()
        return {"response": f"{tool_result} You can review and approve them in the Approvals tab."}
    
    else:
        return {"response": "I'm your Agentic ERP Copilot. I can help you check revenue, monitor inventory levels (e.g., SKU-8840), or verify pending invoices. What would you like to do?"}
