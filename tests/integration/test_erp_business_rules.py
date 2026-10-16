"""
Integration tests for ERP Business Rules & Approval Workflow Thresholds.

Verifies Phase 4 requirements:
1. Inventory negative stock prevention (InsufficientStockError).
2. Accounting double-entry bookkeeping balance check (JournalImbalanceError).
3. Approval workflow thresholds (auto-approval <$1,000, human approval >$1,000).
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.database.models import Organization
from packages.database.models.erp.accounting import Account, AccountType, EntryStatus, JournalEntry, JournalLine
from packages.database.models.erp.inventory import MovementType, Product, StockLevel, Warehouse
from packages.database.tenant_context import set_tenant_context
from packages.erp.repositories.accounting_repo import AccountingRepository, JournalImbalanceError
from packages.erp.repositories.inventory_repo import InsufficientStockError, InventoryRepository
from packages.security.guardrails import guardrails
from tests.conftest import ASYNC_TEST_DB_URL


@pytest.mark.asyncio
async def test_inventory_negative_stock_prevention():
    """Asserts that attempting to deduct stock below zero raises InsufficientStockError."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    async with session_factory() as session:
        await set_tenant_context(session, org_id)
        org = Organization(id=org_id, name="Stock Org", slug=f"stock-{org_id.hex[:6]}", plan="pro")
        session.add(org)
        await session.commit()

        repo = InventoryRepository(session)
        # Create product
        prod = await repo.create_product(
            organization_id=org_id,
            sku=f"SKU-TEST-{uuid4().hex[:6]}",
            name="Stock Prevention Test Item",
            unit_price=Decimal("100.00"),
            cost_price=Decimal("50.00"),
        )

        # Create warehouse
        wh = await repo.create_warehouse(
            organization_id=org_id,
            code=f"WH-{uuid4().hex[:4]}",
            name="Main Warehouse",
        )
        await session.commit()

        # Add initial stock of 10 units
        await repo.adjust_stock(
            organization_id=org_id,
            product_id=prod.id,
            warehouse_id=wh.id,
            delta=Decimal("10"),
            movement_type=MovementType.RECEIPT,
            notes="Initial stock delivery",
        )
        await session.commit()

        # Verify on-hand is 10
        stock = await repo.get_stock_level(prod.id, wh.id)
        assert stock.quantity_on_hand == Decimal("10")

        # Attempt to deduct 15 units (would result in -5 units) -> Must raise InsufficientStockError
        with pytest.raises(InsufficientStockError) as exc_info:
            await repo.adjust_stock(
                organization_id=org_id,
                product_id=prod.id,
                warehouse_id=wh.id,
                delta=Decimal("-15"),
                movement_type=MovementType.ADJUSTMENT,
                notes="Over-deduction attempt",
            )
        assert exc_info.value.available == Decimal("10")
        assert exc_info.value.requested == Decimal("15")

    await engine.dispose()


@pytest.mark.asyncio
async def test_accounting_double_entry_balance_check():
    """Asserts that journal entries must balance (sum debits == sum credits) before posting."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    async with session_factory() as session:
        await set_tenant_context(session, org_id)
        org = Organization(id=org_id, name="Accounting Org", slug=f"acct-{org_id.hex[:6]}", plan="enterprise")
        session.add(org)
        await session.commit()

        repo = AccountingRepository(session)
        # Create cash and revenue accounts
        cash_acc = await repo.create_account(
            organization_id=org_id,
            code="1010",
            name="Operating Cash",
            account_type=AccountType.ASSET,
        )
        rev_acc = await repo.create_account(
            organization_id=org_id,
            code="4010",
            name="Product Revenue",
            account_type=AccountType.REVENUE,
        )
        await session.commit()

        now_date = datetime.now(timezone.utc).date()

        # 1. Unbalanced Journal Entry: $500 Debit vs $400 Credit
        unbalanced_entry = await repo.create_journal_entry(
            organization_id=org_id,
            entry_date=now_date,
            description="Unbalanced sale recording",
            lines=[
                {"account_id": cash_acc.id, "debit": Decimal("500.00"), "credit": Decimal("0.00")},
                {"account_id": rev_acc.id, "debit": Decimal("0.00"), "credit": Decimal("400.00")},
            ],
        )
        await session.commit()

        # Posting must be rejected with JournalImbalanceError
        with pytest.raises(JournalImbalanceError) as exc_info:
            await repo.post_journal_entry(unbalanced_entry.id)
        assert exc_info.value.total_debit == Decimal("500.00")
        assert exc_info.value.total_credit == Decimal("400.00")

        # 2. Balanced Journal Entry: $500 Debit == $500 Credit
        balanced_entry = await repo.create_journal_entry(
            organization_id=org_id,
            entry_date=now_date,
            description="Balanced sale recording",
            lines=[
                {"account_id": cash_acc.id, "debit": Decimal("500.00"), "credit": Decimal("0.00")},
                {"account_id": rev_acc.id, "debit": Decimal("0.00"), "credit": Decimal("500.00")},
            ],
        )
        await session.commit()

        # Posting balanced entry succeeds
        posted = await repo.post_journal_entry(balanced_entry.id)
        assert posted.status == EntryStatus.POSTED

    await engine.dispose()


def test_approval_workflow_financial_thresholds():
    """Asserts AI guardrails enforce human-in-the-loop review threshold for transactions exceeding $1,000."""
    # Under $1,000 auto-approved
    low_risk_action = {"action": "purchase_order", "amount": 450.00}
    res_low = guardrails.enforce_action_boundaries(low_risk_action)
    assert res_low["requires_human_approval"] is False
    assert "Passed Auto-Approval" in res_low["guardrail_status"]

    # Exactly $1,000 auto-approved
    boundary_action = {"action": "invoice_payment", "amount": "$1,000.00"}
    res_bound = guardrails.enforce_action_boundaries(boundary_action)
    assert res_bound["requires_human_approval"] is False

    # Over $1,000 requires human manager review
    high_risk_action = {"action": "wire_transfer", "amount": 25000.00}
    res_high = guardrails.enforce_action_boundaries(high_risk_action)
    assert res_high["requires_human_approval"] is True
    assert "Requires Manager Review" in res_high["guardrail_status"]
