"""
Accounting domain models.

Tables: accounts, journal_entries, journal_lines

Business rules (CRITICAL):
  - Every posted JournalEntry must have sum(debit) == sum(credit).
    This is enforced in accounting_service.post_journal_entry() BEFORE commit.
    A JournalImbalanceError is raised if the entry does not balance to zero.
  - JournalLine: each line has EITHER a debit OR a credit, never both.
    Enforced by CHECK constraint.
  - Double-entry bookkeeping: debits increase assets/expenses,
    credits increase liabilities/equity/revenue.

Account types follow standard chart of accounts conventions:
  asset, liability, equity, revenue, expense
"""

from enum import Enum as PyEnum
from sqlalchemy import (
    Column, String, Text, Numeric, Date, ForeignKey,
    CheckConstraint, Index, UniqueConstraint, Enum as SAEnum, Boolean,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from packages.database.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin


class AccountType(str, PyEnum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class EntryStatus(str, PyEnum):
    DRAFT = "draft"
    POSTED = "posted"
    VOID = "void"


class Account(SoftDeleteMixin, Base):
    """
    A single account in the chart of accounts.

    Accounts are hierarchical — a parent_id allows sub-accounts
    (e.g., 1000 Cash → 1001 Petty Cash, 1002 Bank).
    """
    __tablename__ = "accounts"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    code = Column(String(20), nullable=False)     # e.g., "1000", "4100"
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    account_type = Column(
        SAEnum(AccountType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    currency = Column(String(3), nullable=False, default="USD")
    is_active = Column(Boolean, nullable=False, default=True)

    parent_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parent = relationship("Account", remote_side="Account.id", backref="children")

    # Relationships
    journal_lines = relationship("JournalLine", back_populates="account")

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uix_account_org_code"),
        Index("ix_account_organization", "organization_id"),
        Index("ix_account_type", "account_type"),
    )


class JournalEntry(Base):
    """
    A double-entry journal entry header.

    INVARIANT: For any POSTED entry, sum(lines.debit) == sum(lines.credit).
    This is enforced by accounting_service.post_journal_entry() using
    Python-level validation before commit. The DB does not have a trigger
    for this (cross-row constraints are not natively supported in SQL).
    """
    __tablename__ = "journal_entries"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    entry_date = Column(Date, nullable=False)
    description = Column(Text, nullable=False)
    reference = Column(String(255), nullable=True)  # External reference (invoice, PO, etc.)
    status = Column(
        SAEnum(EntryStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=EntryStatus.DRAFT,
    )
    created_by_id = Column(PG_UUID(as_uuid=True), nullable=True)

    # Relationships
    lines = relationship("JournalLine", back_populates="entry", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_journal_entry_organization", "organization_id"),
        Index("ix_journal_entry_date", "entry_date"),
        Index("ix_journal_entry_status", "status"),
    )


class JournalLine(Base):
    """
    A single debit or credit line within a journal entry.

    Rules:
      - debit and credit are both non-negative (CHECK).
      - Exactly one of debit or credit must be non-zero (CHECK).
        A line cannot have both debit > 0 and credit > 0 simultaneously.
    """
    __tablename__ = "journal_lines"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    entry_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    debit = Column(Numeric(15, 4), nullable=False, default=0)
    credit = Column(Numeric(15, 4), nullable=False, default=0)
    description = Column(Text, nullable=True)

    # Relationships
    entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("Account", back_populates="journal_lines")

    __table_args__ = (
        # Both must be non-negative
        CheckConstraint("debit >= 0", name="chk_jl_debit_non_negative"),
        CheckConstraint("credit >= 0", name="chk_jl_credit_non_negative"),
        # Exactly one side must be non-zero — prevents invalid "both sides" entries
        CheckConstraint(
            "(debit = 0 AND credit > 0) OR (debit > 0 AND credit = 0)",
            name="chk_jl_single_side",
        ),
        Index("ix_journal_line_entry", "entry_id"),
        Index("ix_journal_line_account", "account_id"),
    )
