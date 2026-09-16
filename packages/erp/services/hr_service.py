"""
HR Service.

Enforces business logic for departments, employees, attendance tracking, and leave request management.
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.erp.hr import (
    Department, Employee, AttendanceRecord, LeaveRequest, LeaveStatus, LeaveType
)
from packages.erp.repositories.hr_repo import HRRepository


class HRService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = HRRepository(session)

    async def create_department(
        self,
        organization_id: UUID,
        name: str,
        code: str,
        description: Optional[str] = None,
        manager_id: Optional[UUID] = None,
    ) -> Department:
        dept = await self.repo.create_department(
            organization_id=organization_id,
            name=name,
            code=code,
            description=description,
            manager_id=manager_id,
        )
        await self.session.commit()
        return dept

    async def list_departments(self, organization_id: UUID) -> List[Department]:
        return await self.repo.list_departments(organization_id)

    async def create_employee(
        self,
        organization_id: UUID,
        first_name: str,
        last_name: str,
        hire_date: date,
        department_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        job_title: Optional[str] = None,
        employee_number: Optional[str] = None,
        salary: Optional[Decimal] = None,
        salary_currency: str = "USD",
    ) -> Employee:
        emp = await self.repo.create_employee(
            organization_id=organization_id,
            first_name=first_name,
            last_name=last_name,
            hire_date=hire_date,
            department_id=department_id,
            user_id=user_id,
            email=email,
            phone=phone,
            job_title=job_title,
            employee_number=employee_number,
            salary=salary,
            salary_currency=salary_currency,
        )
        await self.session.commit()
        return emp

    async def list_employees(
        self, organization_id: UUID, department_id: Optional[UUID] = None, page: int = 1, page_size: int = 20
    ) -> List[Employee]:
        return await self.repo.list_employees(
            organization_id, department_id=department_id, page=page, page_size=page_size
        )

    async def record_attendance(
        self,
        organization_id: UUID,
        employee_id: UUID,
        record_date: date,
        check_in: datetime,
        check_out: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> AttendanceRecord:
        att = await self.repo.record_attendance(
            organization_id=organization_id,
            employee_id=employee_id,
            record_date=record_date,
            check_in=check_in,
            check_out=check_out,
            notes=notes,
        )
        await self.session.commit()
        return att

    async def create_leave_request(
        self,
        organization_id: UUID,
        employee_id: UUID,
        leave_type: LeaveType,
        start_date: date,
        end_date: date,
        reason: Optional[str] = None,
    ) -> LeaveRequest:
        req = await self.repo.create_leave_request(
            organization_id=organization_id,
            employee_id=employee_id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
        )
        await self.session.commit()
        return req

    async def approve_leave_request(
        self,
        leave_id: UUID,
        approved_by_id: UUID,
    ) -> LeaveRequest:
        req = await self.repo.update_leave_status(
            leave_id=leave_id,
            status=LeaveStatus.APPROVED,
            approved_by_id=approved_by_id,
        )
        if not req:
            raise ValueError(f"Leave request {leave_id} not found")
        await self.session.commit()
        return req

    async def reject_leave_request(
        self,
        leave_id: UUID,
        approved_by_id: UUID,
        rejection_reason: str,
    ) -> LeaveRequest:
        req = await self.repo.update_leave_status(
            leave_id=leave_id,
            status=LeaveStatus.REJECTED,
            approved_by_id=approved_by_id,
            rejection_reason=rejection_reason,
        )
        if not req:
            raise ValueError(f"Leave request {leave_id} not found")
        await self.session.commit()
        return req

    async def list_leave_requests(
        self, organization_id: UUID, status: Optional[LeaveStatus] = None, page: int = 1, page_size: int = 20
    ) -> List[LeaveRequest]:
        return await self.repo.list_leave_requests(
            organization_id, status=status, page=page, page_size=page_size
        )
