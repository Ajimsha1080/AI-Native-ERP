"""
Accounting REST API routes.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query

from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser, require_role
from packages.erp.services.accounting_service import AccountingService
from packages.erp.repositories.accounting_repo import JournalImbalanceError
from packages.database.models.erp.accounting import AccountType, EntryStatus
from packages.schemas.erp import (
    AccountCreate, AccountResponse,
    JournalEntryCreate, JournalEntryResponse,
)

router = APIRouter(prefix="/accounting", tags=["Accounting"])


@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: AccountCreate,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = AccountingService(db)
    return await service.create_account(
        organization_id=current_user.org_id,
        code=body.code,
        name=body.name,
        account_type=body.account_type,
        currency=body.currency,
        description=body.description,
        parent_id=body.parent_id,
    )


@router.get("/accounts", response_model=List[AccountResponse])
async def list_accounts(
    current_user: CurrentUser,
    db: TenantDB,
    account_type: Optional[AccountType] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    service = AccountingService(db)
    return await service.list_accounts(current_user.org_id, account_type=account_type, page=page, page_size=page_size)


@router.post("/journal-entries", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    body: JournalEntryCreate,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = AccountingService(db)
    return await service.create_journal_entry(
        organization_id=current_user.org_id,
        entry_date=body.entry_date,
        description=body.description,
        lines=[l.model_dump() for l in body.lines],
        reference=body.reference,
        created_by_id=current_user.user_id,
    )


@router.post("/journal-entries/{entry_id}/post", response_model=JournalEntryResponse)
async def post_journal_entry(
    entry_id: UUID,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = AccountingService(db)
    try:
        return await service.post_journal_entry(entry_id)
    except JournalImbalanceError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/journal-entries", response_model=List[JournalEntryResponse])
async def list_journal_entries(
    current_user: CurrentUser,
    db: TenantDB,
    status: Optional[EntryStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = AccountingService(db)
    return await service.list_journal_entries(current_user.org_id, status=status, page=page, page_size=page_size)
