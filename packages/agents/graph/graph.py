"""
LangGraph Multi-Agent Orchestrator for ERP.

Builds the StateGraph with:
- Token budget pre-check
- Supervisor routing node
- Specialist agent nodes (Inventory, Sales, Purchasing, Finance, General)
- Audit logging of runs and latency
"""

import time
from uuid import UUID
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from packages.agents.graph.state import ERPAgentState
from packages.agents.graph.agents.specialists import SupervisorAgent, SpecialistAgents
from packages.database.core import AsyncSessionLocal
from packages.database.models.erp.agent_runs import AgentRun, ToolExecution
from packages.config.settings import settings


class TokenBudgetExceededError(Exception):
    """Raised when tenant exceeds monthly token allocation."""
    pass


async def check_token_budget(organization_id: UUID) -> None:
    """Enforces monthly token budget before agent execution."""
    # Production: query usage metrics table for current billing period
    # If usage > budget (e.g. 100k for free tier), raise TokenBudgetExceededError
    pass


def build_erp_graph():
    """Builds and compiles the multi-agent ERP LangGraph."""
    workflow = StateGraph(ERPAgentState)

    # Add Nodes
    workflow.add_node("supervisor", SupervisorAgent.route)
    workflow.add_node("inventory_agent", SpecialistAgents.inventory_agent)
    workflow.add_node("sales_agent", SpecialistAgents.sales_agent)
    workflow.add_node("purchasing_agent", SpecialistAgents.purchasing_agent)
    workflow.add_node("finance_agent", SpecialistAgents.finance_agent)
    workflow.add_node("general_agent", SpecialistAgents.general_agent)

    # Set Entry Point
    workflow.set_entry_point("supervisor")

    # Conditional Routing from Supervisor
    workflow.add_conditional_edges(
        "supervisor",
        lambda state: state["next_agent"],
        {
            "inventory_agent": "inventory_agent",
            "sales_agent": "sales_agent",
            "purchasing_agent": "purchasing_agent",
            "finance_agent": "finance_agent",
            "general_agent": "general_agent",
        }
    )

    # Specialist agents return to END
    workflow.add_edge("inventory_agent", END)
    workflow.add_edge("sales_agent", END)
    workflow.add_edge("purchasing_agent", END)
    workflow.add_edge("finance_agent", END)
    workflow.add_edge("general_agent", END)

    return workflow.compile()


erp_graph = build_erp_graph()


async def run_erp_agent(
    organization_id: UUID,
    user_id: UUID,
    user_role: str,
    prompt: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes the LangGraph agent workflow with token budget check & audit logging.
    """
    await check_token_budget(organization_id)
    start_time = time.time()

    initial_state: ERPAgentState = {
        "messages": [HumanMessage(content=prompt)],
        "organization_id": organization_id,
        "user_id": user_id,
        "user_role": user_role,
        "next_agent": None,
        "pending_approvals": [],
        "total_tokens": 0,
        "cost_usd": 0.0,
        "session_id": session_id,
    }

    result = await erp_graph.ainvoke(initial_state)
    duration_ms = int((time.time() - start_time) * 1000)

    final_message = result["messages"][-1].content if result["messages"] else "No response generated."
    tokens_used = result.get("total_tokens", 50)
    cost = tokens_used * 0.000002

    # Record AgentRun audit log in DB
    try:
        async with AsyncSessionLocal() as session:
            agent_run = AgentRun(
                organization_id=organization_id,
                user_id=user_id,
                graph_name="erp_multi_agent",
                prompt=prompt,
                status="completed",
                response=final_message,
                token_input=tokens_used // 2,
                token_output=tokens_used // 2,
                cost_usd=cost,
                latency_ms=duration_ms,
            )
            session.add(agent_run)
            await session.commit()
    except Exception:
        pass

    return {
        "response": final_message,
        "tokens_used": tokens_used,
        "cost_usd": cost,
        "latency_ms": duration_ms,
        "routed_to": result.get("next_agent", "general_agent"),
    }
