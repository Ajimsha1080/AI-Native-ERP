"""
Accounting repository.

Key business rule (CRITICAL):
  post_journal_entry() validates that sum(debit lines) == sum(credit lines)
  before updating the entry status to POSTED. Raises JournalImbalanceError
  if the entry does not balance. This is a hard requirement of double-entry
  bookkeeping — a journal entry that doesn't balance is always an error.
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.erp.accounting import (
    Account, JournalEntry, JournalLine, AccountType, EntryStatus
)


class JournalImbalanceError(Exception):
    """Raised when a journal entry's debits do not equal its credits."""
    def __init__(self, entry_id: UUID, total_debit: Decimal, total_credit: Decimal):
        self.entry_id = entry_id
        self.total_debit = total_debit
        self.total_credit = total_credit
        super().__init__(
            f"Journal entry {entry_id} does not balance: "
            f"debit={total_debit}, credit={total_credit}, "
            f"difference={abs(total_debit - total_credit)}"
        )


class AccountingRepository:

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── Accounts ──────────────────────────────────────────────

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
        account = Account(
            organization_id=organization_id,
            code=code,
            name=name,
            account_type=account_type,
            currency=currency,
            description=description,
            parent_id=parent_id,
        )
        self._session.add(account)
        await self._session.flush()
        return account

    async def get_account(self, account_id: UUID) -> Optional[Account]:
        result = await self._session.execute(
            select(Account).where(Account.id == account_id, Account.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_account_by_code(self, organization_id: UUID, code: str) -> Optional[Account]:
        result = await self._session.execute(
            select(Account).where(
                Account.organization_id == organization_id,
                Account.code == code,
                Account.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def list_accounts(
        self,
        organization_id: UUID,
        account_type: Optional[AccountType] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> list[Account]:
        q = select(Account).where(
            Account.organization_id == organization_id,
            Account.is_deleted == False,
        )
        if account_type:
            q = q.where(Account.account_type == account_type)
        q = q.order_by(Account.code).offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    # ── Journal Entries ────────────────────────────────────────

    async def create_journal_entry(
        self,
        organization_id: UUID,
        entry_date,
        description: str,
        lines: list[dict],  # [{"account_id": UUID, "debit": Decimal, "credit": Decimal}]
        reference: Optional[str] = None,
        created_by_id: Optional[UUID] = None,
    ) -> JournalEntry:
        """
        Create a draft journal entry with all its lines.

        Args:
            lines: List of dicts with keys: account_id, debit, credit.
                   Each line must have either debit > 0 or credit > 0 (not both).

        Returns:
            New JournalEntry in DRAFT status.
        """
        entry = JournalEntry(
            organization_id=organization_id,
            entry_date=entry_date,
            description=description,
            reference=reference,
            status=EntryStatus.DRAFT,
            created_by_id=created_by_id,
        )
        self._session.add(entry)
        await self._session.flush()

        for line_data in lines:
            line = JournalLine(
                organization_id=organization_id,
                entry_id=entry.id,
                account_id=line_data["account_id"],
                debit=line_data.get("debit", Decimal("0")),
                credit=line_data.get("credit", Decimal("0")),
                description=line_data.get("description"),
            )
            self._session.add(line)

        await self._session.flush()
        return entry

    async def get_journal_entry(self, entry_id: UUID) -> Optional[JournalEntry]:
        result = await self._session.execute(
            select(JournalEntry).where(JournalEntry.id == entry_id)
        )
        return result.scalar_one_or_none()

    async def get_journal_entry_with_lines(self, entry_id: UUID) -> Optional[JournalEntry]:
        """Load entry with all lines eagerly."""
        from sqlalchemy.orm import selectinload
        result = await self._session.execute(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(JournalEntry.id == entry_id)
        )
        return result.scalar_one_or_none()

    async def post_journal_entry(self, entry_id: UUID) -> JournalEntry:
        """
        Post a draft journal entry, enforcing the double-entry balance invariant.

        The total debits MUST equal the total credits. Any difference — even
        a single cent — is an accounting error and must be corrected before posting.

        Raises:
            JournalImbalanceError: If sum(debit) != sum(credit).
            ValueError: If the entry is already posted or voided.
        """
        entry = await self.get_journal_entry_with_lines(entry_id)
        if entry is None:
            raise ValueError(f"Journal entry {entry_id} not found")
        if entry.status != EntryStatus.DRAFT:
            raise ValueError(f"Cannot post entry in status '{entry.status}'")

        total_debit = sum(line.debit for line in entry.lines)
        total_credit = sum(line.credit for line in entry.lines)

        if total_debit != total_credit:
            raise JournalImbalanceError(entry_id, total_debit, total_credit)

        entry.status = EntryStatus.POSTED
        await self._session.flush()
        return entry

    async def list_journal_entries(
        self,
        organization_id: UUID,
        status: Optional[EntryStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[JournalEntry]:
        q = select(JournalEntry).where(JournalEntry.organization_id == organization_id)
        if status:
            q = q.where(JournalEntry.status == status)
        q = q.order_by(JournalEntry.entry_date.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(q)
        return list(result.scalars().all())
