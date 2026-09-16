"""
Agent state definitions for LangGraph ERP orchestration.
"""

from typing import Annotated, Sequence, TypedDict, Optional, List, Dict, Any
from uuid import UUID
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ERPAgentState(TypedDict):
    """Global state across supervisor and specialist agents in LangGraph."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    organization_id: UUID
    user_id: UUID
    user_role: str
    next_agent: Optional[str]
    pending_approvals: List[Dict[str, Any]]
    total_tokens: int
    cost_usd: float
    session_id: Optional[str]
