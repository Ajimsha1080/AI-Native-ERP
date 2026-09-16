"""
Integration tests for Accounting Service (Double-entry journal balance enforcement).
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import date

from packages.database.core import async_session_scope, create_db_and_tables
from packages.database.tenant_context import set_tenant_context
from packages.erp.services.accounting_service import AccountingService
from packages.erp.repositories.accounting_repo import JournalImbalanceError
from packages.database.models.erp.accounting import AccountType, EntryStatus


@pytest.mark.asyncio
async def test_accounting_double_entry_balance_enforcement():
    await create_db_and_tables()
    org_id = uuid4()

    async with async_session_scope() as session:
        await set_tenant_context(session, org_id)
        service = AccountingService(session)

        # 1. Create Chart of Accounts (Cash & Sales Revenue)
        cash_account = await service.create_account(
            organization_id=org_id,
            code=f"1010-{uuid4().hex[:4]}",
            name="Bank Checking",
            account_type=AccountType.ASSET,
        )
        revenue_account = await service.create_account(
            organization_id=org_id,
            code=f"4010-{uuid4().hex[:4]}",
            name="Product Sales Revenue",
            account_type=AccountType.REVENUE,
        )

        # 2. Balanced entry: Debit Cash $500, Credit Revenue $500
        balanced_entry = await service.create_journal_entry(
            organization_id=org_id,
            entry_date=date.today(),
            description="Customer cash payment for goods",
            lines=[
                {"account_id": cash_account.id, "debit": Decimal("500.00"), "credit": Decimal("0")},
                {"account_id": revenue_account.id, "debit": Decimal("0"), "credit": Decimal("500.00")},
            ],
        )
        assert balanced_entry.status == EntryStatus.DRAFT

        # 3. Posting balanced entry MUST succeed
        posted = await service.post_journal_entry(balanced_entry.id)
        assert posted.status == EntryStatus.POSTED

        # 4. Imbalanced entry: Debit $500, Credit $400 (Difference: $100)
        imbalanced_entry = await service.create_journal_entry(
            organization_id=org_id,
            entry_date=date.today(),
            description="Imbalanced error transaction",
            lines=[
                {"account_id": cash_account.id, "debit": Decimal("500.00"), "credit": Decimal("0")},
                {"account_id": revenue_account.id, "debit": Decimal("0"), "credit": Decimal("400.00")},
            ],
        )

        # 5. Posting imbalanced entry MUST raise JournalImbalanceError
        with pytest.raises(JournalImbalanceError) as exc_info:
            await service.post_journal_entry(imbalanced_entry.id)
        assert "does not balance" in str(exc_info.value)
