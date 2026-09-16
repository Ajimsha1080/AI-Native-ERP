"""
HR REST API routes.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query

from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser, require_role
from packages.erp.services.hr_service import HRService
from packages.database.models.erp.hr import LeaveStatus
from packages.schemas.erp import (
    DepartmentCreate, DepartmentResponse,
    EmployeeCreate, EmployeeResponse,
    AttendanceCreate, AttendanceResponse,
    LeaveRequestCreate, LeaveRequestResponse,
)

router = APIRouter(prefix="/hr", tags=["HR"])


@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    body: DepartmentCreate,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = HRService(db)
    return await service.create_department(
        organization_id=current_user.org_id,
        name=body.name,
        code=body.code,
        description=body.description,
        manager_id=body.manager_id,
    )


@router.get("/departments", response_model=List[DepartmentResponse])
async def list_departments(
    current_user: CurrentUser,
    db: TenantDB,
):
    service = HRService(db)
    return await service.list_departments(current_user.org_id)


@router.post("/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    body: EmployeeCreate,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = HRService(db)
    return await service.create_employee(
        organization_id=current_user.org_id,
        first_name=body.first_name,
        last_name=body.last_name,
        hire_date=body.hire_date,
        department_id=body.department_id,
        user_id=body.user_id,
        email=body.email,
        phone=body.phone,
        job_title=body.job_title,
        employee_number=body.employee_number,
        salary=body.salary,
        salary_currency=body.salary_currency,
    )


@router.get("/employees", response_model=List[EmployeeResponse])
async def list_employees(
    current_user: CurrentUser,
    db: TenantDB,
    department_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = HRService(db)
    return await service.list_employees(
        current_user.org_id, department_id=department_id, page=page, page_size=page_size
    )


@router.post("/attendance", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
async def record_attendance(
    body: AttendanceCreate,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = HRService(db)
    return await service.record_attendance(
        organization_id=current_user.org_id,
        employee_id=body.employee_id,
        record_date=body.record_date,
        check_in=body.check_in,
        check_out=body.check_out,
        notes=body.notes,
    )


@router.post("/leave-requests", response_model=LeaveRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_leave_request(
    body: LeaveRequestCreate,
    current_user: CurrentUser,
    db: TenantDB,
):
    service = HRService(db)
    return await service.create_leave_request(
        organization_id=current_user.org_id,
        employee_id=body.employee_id,
        leave_type=body.leave_type,
        start_date=body.start_date,
        end_date=body.end_date,
        reason=body.reason,
    )


@router.post("/leave-requests/{leave_id}/approve", response_model=LeaveRequestResponse)
async def approve_leave_request(
    leave_id: UUID,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = HRService(db)
    try:
        return await service.approve_leave_request(leave_id, current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/leave-requests", response_model=List[LeaveRequestResponse])
async def list_leave_requests(
    current_user: CurrentUser,
    db: TenantDB,
    status: Optional[LeaveStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = HRService(db)
    return await service.list_leave_requests(
        current_user.org_id, status=status, page=page, page_size=page_size
    )
