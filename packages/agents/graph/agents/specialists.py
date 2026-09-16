"""
LangGraph Specialist agents and Supervisor router.
"""

from typing import Dict, Any, List
import time
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from packages.agents.graph.state import ERPAgentState
from packages.agents.approval_manager import ApprovalManager
from packages.agents.graph.tools.erp_tools import (
    tool_list_products, tool_check_stock, tool_adjust_stock,
    tool_list_customers, tool_list_invoices,
    tool_list_vendors,
    tool_list_accounts, tool_create_journal_entry,
)


class SupervisorAgent:

    @staticmethod
    def route(state: ERPAgentState) -> Dict[str, Any]:
        """Routes user intent to the appropriate specialist agent."""
        messages = state["messages"]
        last_message = messages[-1].content.lower() if messages else ""

        if any(w in last_message for w in ["stock", "inventory", "product", "warehouse"]):
            return {"next_agent": "inventory_agent"}
        elif any(w in last_message for w in ["sales", "customer", "invoice", "order"]):
            return {"next_agent": "sales_agent"}
        elif any(w in last_message for w in ["purchase", "po", "vendor", "supplier"]):
            return {"next_agent": "purchasing_agent"}
        elif any(w in last_message for w in ["account", "journal", "finance", "ledger", "balance"]):
            return {"next_agent": "finance_agent"}
        else:
            return {"next_agent": "general_agent"}


class SpecialistAgents:

    @staticmethod
    async def inventory_agent(state: ERPAgentState) -> Dict[str, Any]:
        org_id = state["organization_id"]
        messages = state["messages"]
        content = messages[-1].content.lower()

        if "list" in content or "show" in content or "product" in content:
            products = await tool_list_products(org_id)
            response_text = f"Retrieved {len(products)} products: " + ", ".join(f"{p['name']} (${p['unit_price']})" for p in products[:5])
            return {"messages": [AIMessage(content=response_text)], "total_tokens": 120}
        else:
            levels = await tool_check_stock(org_id)
            response_text = f"Stock checked across {len(levels)} product-warehouse records."
            return {"messages": [AIMessage(content=response_text)], "total_tokens": 100}

    @staticmethod
    async def sales_agent(state: ERPAgentState) -> Dict[str, Any]:
        org_id = state["organization_id"]
        messages = state["messages"]
        content = messages[-1].content.lower()

        if "invoice" in content:
            invoices = await tool_list_invoices(org_id)
            response_text = f"Found {len(invoices)} invoices in the system."
            return {"messages": [AIMessage(content=response_text)], "total_tokens": 110}
        else:
            customers = await tool_list_customers(org_id)
            response_text = f"Found {len(customers)} active customer accounts."
            return {"messages": [AIMessage(content=response_text)], "total_tokens": 95}

    @staticmethod
    async def purchasing_agent(state: ERPAgentState) -> Dict[str, Any]:
        org_id = state["organization_id"]
        vendors = await tool_list_vendors(org_id)
        response_text = f"Found {len(vendors)} registered suppliers."
        return {"messages": [AIMessage(content=response_text)], "total_tokens": 90}

    @staticmethod
    async def finance_agent(state: ERPAgentState) -> Dict[str, Any]:
        org_id = state["organization_id"]
        accounts = await tool_list_accounts(org_id)
        response_text = f"Chart of Accounts contains {len(accounts)} configured accounts."
        return {"messages": [AIMessage(content=response_text)], "total_tokens": 130}

    @staticmethod
    async def general_agent(state: ERPAgentState) -> Dict[str, Any]:
        return {
            "messages": [AIMessage(content="I am the ERP Master Agent. I can assist with Inventory, Sales, Purchasing, and Accounting queries.")],
            "total_tokens": 50,
        }
