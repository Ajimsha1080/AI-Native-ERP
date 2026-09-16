"""
Accounting Service.

Enforces double-entry bookkeeping, balanced journals validation, and ledger reporting.
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.erp.accounting import (
    Account, JournalEntry, AccountType, EntryStatus
)
from packages.erp.repositories.accounting_repo import (
    AccountingRepository, JournalImbalanceError
)


class AccountingService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AccountingRepository(session)

    async def create_account(
        self,
        organization_id: UUID,
        code: str,
        name: str,
        account_type: AccountType,
        currency: str = "USD",
        description: Optional[str] = None,
        parent_id: Optional[UUID] = None,
    ) -> Account:
        account = await self.repo.create_account(
            organization_id=organization_id,
            code=code,
            name=name,
            account_type=account_type,
            currency=currency,
            description=description,
            parent_id=parent_id,
        )
        await self.session.commit()
        return account

    async def list_accounts(
        self,
        organization_id: UUID,
        account_type: Optional[AccountType] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> List[Account]:
        return await self.repo.list_accounts(
            organization_id, account_type=account_type, page=page, page_size=page_size
        )

    async def create_journal_entry(
        self,
        organization_id: UUID,
        entry_date: date,
        description: str,
        lines: List[Dict[str, Any]],
        reference: Optional[str] = None,
        created_by_id: Optional[UUID] = None,
    ) -> JournalEntry:
        entry = await self.repo.create_journal_entry(
            organization_id=organization_id,
            entry_date=entry_date,
            description=description,
            lines=lines,
            reference=reference,
            created_by_id=created_by_id,
        )
        await self.session.commit()
        return entry

    async def post_journal_entry(self, entry_id: UUID) -> JournalEntry:
        """
        Validates double-entry debits == credits balance and posts entry.
        """
        entry = await self.repo.post_journal_entry(entry_id)
        await self.session.commit()
        return entry

    async def list_journal_entries(
        self,
        organization_id: UUID,
        status: Optional[EntryStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[JournalEntry]:
        return await self.repo.list_journal_entries(
            organization_id, status=status, page=page, page_size=page_size
        )
