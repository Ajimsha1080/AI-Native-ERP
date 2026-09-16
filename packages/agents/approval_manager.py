"""
Human-in-the-loop approval manager for high-risk agent write tools.
"""

from typing import Dict, Any, Optional
from uuid import UUID
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.erp.agent_runs import PendingApproval, ApprovalStatus


class ApprovalManager:

    @staticmethod
    def is_high_risk_tool(tool_name: str, inputs: Dict[str, Any]) -> bool:
        """
        Determines if a tool call requires human-in-the-loop approval.
        Read-only tools always auto-execute.
        Financial / stock alteration / payment write tools require approval
        if amount/delta exceeds threshold or if tagged critical.
        """
        # Read tools: safe to auto-execute
        if tool_name.startswith("list_") or tool_name.startswith("get_") or tool_name.startswith("check_"):
            return False

        # Financial actions with threshold > $1,000 require approval
        if tool_name in ["record_payment", "post_journal_entry"]:
            return True

        if tool_name == "adjust_stock":
            delta = abs(Decimal(str(inputs.get("delta", 0))))
            return delta > Decimal("100")  # Adjusting > 100 units requires approval

        if tool_name == "create_invoice":
            total = Decimal(str(inputs.get("total_amount", 0)))
            return total > Decimal("5000")  # Invoices > $5k require approval

        return False

    @staticmethod
    async def create_pending_approval(
        session: AsyncSession,
        organization_id: UUID,
        tool_name: str,
        inputs: Dict[str, Any],
        run_id: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> PendingApproval:
        approval = PendingApproval(
            organization_id=organization_id,
            run_id=run_id,
            tool_name=tool_name,
            inputs=inputs,
            status=ApprovalStatus.PENDING,
            risk_level="high",
            reason=reason or f"Action '{tool_name}' requires human approval before execution.",
        )
        session.add(approval)
        await session.commit()
        return approval
