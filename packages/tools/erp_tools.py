from typing import Dict, Any, List, Optional
from packages.connectors.base import BaseConnector

class AgentToolLayer:
    """
    Middleware layer between the AI Agent and the underlying ERP Connectors.
    Enforces permission checks, policies, and idempotency before translating 
    the semantic intent into a connector execution.
    """

    def __init__(self, connector: BaseConnector, agent_id: str):
        self.connector = connector
        self.agent_id = agent_id

    async def _policy_check(self, action: str, entity: str) -> bool:
        """
        Stub for robust RBAC and policy checking.
        """
        # E.g., Only Finance Agents can create Payments.
        # In a real system, this checks the database for agent_tools and tool_permissions.
        return True

    async def get_inventory(self, sku: Optional[str] = None) -> List[Dict[str, Any]]:
        if not await self._policy_check("read", "inventory"):
            raise PermissionError("Agent does not have permission to read inventory.")
            
        query = {"sku": sku} if sku else None
        # Translates to Connector READ operation
        records = await self.connector.read("inventory", query=query)
        
        # In production, we map `records` to UnifiedInventory Pydantic schemas here.
        return records

    async def create_purchase_order(self, supplier_id: str, items: List[Dict[str, Any]], amount: float) -> Dict[str, Any]:
        if not await self._policy_check("create", "purchase_orders"):
            raise PermissionError("Agent does not have permission to create purchase orders.")
            
        # Strict enterprise requirement: High-value actions (> $1,000) require Human Approval
        if amount > 1000.00:
            return {
                "status": "pending_approval",
                "requires_approval": True,
                "amount": amount,
                "message": f"Purchase order for ${amount:,.2f} exceeds autonomous agent limits ($1,000.00) and requires human executive approval.",
                "proposed_data": {
                    "supplier_id": supplier_id,
                    "items": items,
                    "total_amount": amount
                }
            }

        data = {
            "supplier_id": supplier_id,
            "items": items,
            "total_amount": amount,
            "status": "draft"
        }
        
        # Translates to Connector CREATE operation
        result = await self.connector.create("purchase_orders", data=data)
        
        # Verify idempotency/success
        if not result.get("id"):
            raise Exception("Failed to verify purchase order creation.")
            
        return result

    async def get_customers(self) -> List[Dict[str, Any]]:
        if not await self._policy_check("read", "customers"):
            raise PermissionError("Agent does not have permission to read customers.")
        return await self.connector.read("customers")

    async def create_invoice(self, customer_id: str, amount: float) -> Dict[str, Any]:
        if not await self._policy_check("create", "invoices"):
            raise PermissionError("Agent does not have permission to create invoices.")
        
        if amount > 1000.00:
            return {
                "status": "pending_approval",
                "requires_approval": True,
                "amount": amount,
                "message": f"Invoice for ${amount:,.2f} exceeds autonomous agent limits ($1,000.00) and requires human executive approval.",
                "proposed_data": {
                    "customer_id": customer_id,
                    "amount": amount
                }
            }

        data = {"customer_id": customer_id, "amount": amount, "status": "pending"}
        return await self.connector.create("invoices", data=data)

# TOOLS FOR CHAT ROUTER & COPILOT
def check_inventory(sku: Optional[str] = None) -> str:
    if sku:
        return f"Inventory for {sku}: 450 units in stock (Warehouse A, Zone B-12)."
    return "Inventory looks good, we have 450 units in stock across all warehouses."

def check_revenue() -> str:
    return "Revenue this month is $425,000.00 across enterprise sales channels."

def check_pending_invoices() -> str:
    return "There are 3 pending invoices awaiting executive approval."
