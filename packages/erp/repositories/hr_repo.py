"""
HR repository.

Handles data access for Departments, Employees, AttendanceRecords, LeaveRequests.
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.erp.hr import (
    Department, Employee, AttendanceRecord, LeaveRequest, LeaveStatus, LeaveType
)


class HRRepository:

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── Departments ───────────────────────────────────────────

    async def create_department(
        self,
        organization_id: UUID,
        name: str,
        code: str,
        description: Optional[str] = None,
        manager_id: Optional[UUID] = None,
    ) -> Department:
        dept = Department(
            organization_id=organization_id,
            name=name,
            code=code,
            description=description,
            manager_id=manager_id,
        )
        self._session.add(dept)
        await self._session.flush()
        return dept

    async def list_departments(self, organization_id: UUID) -> List[Department]:
        result = await self._session.execute(
            select(Department)
            .where(Department.organization_id == organization_id, Department.is_deleted == False)
            .order_by(Department.name)
        )
        return list(result.scalars().all())

    # ── Employees ─────────────────────────────────────────────

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
        emp = Employee(
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
        self._session.add(emp)
        await self._session.flush()
        return emp

    async def get_employee(self, employee_id: UUID) -> Optional[Employee]:
        result = await self._session.execute(
            select(Employee).where(Employee.id == employee_id, Employee.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list_employees(
        self, organization_id: UUID, department_id: Optional[UUID] = None, page: int = 1, page_size: int = 20
    ) -> List[Employee]:
        offset = (page - 1) * page_size
        q = select(Employee).where(Employee.organization_id == organization_id, Employee.is_deleted == False)
        if department_id:
            q = q.where(Employee.department_id == department_id)
        q = q.offset(offset).limit(page_size).order_by(Employee.last_name, Employee.first_name)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    # ── Attendance ────────────────────────────────────────────

    async def record_attendance(
        self,
        organization_id: UUID,
        employee_id: UUID,
        record_date: date,
        check_in: datetime,
        check_out: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> AttendanceRecord:
        hours_worked = None
        if check_out and check_out > check_in:
            diff_seconds = (check_out - check_in).total_seconds()
            hours_worked = Decimal(str(round(diff_seconds / 3600.0, 2)))

        att = AttendanceRecord(
            organization_id=organization_id,
            employee_id=employee_id,
            date=record_date,
            check_in=check_in,
            check_out=check_out,
            hours_worked=hours_worked,
            notes=notes,
        )
        self._session.add(att)
        await self._session.flush()
        return att

    # ── Leave Requests ────────────────────────────────────────

    async def create_leave_request(
        self,
        organization_id: UUID,
        employee_id: UUID,
        leave_type: LeaveType,
        start_date: date,
        end_date: date,
        reason: Optional[str] = None,
    ) -> LeaveRequest:
        req = LeaveRequest(
            organization_id=organization_id,
            employee_id=employee_id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status=LeaveStatus.PENDING,
        )
        self._session.add(req)
        await self._session.flush()
        return req

    async def update_leave_status(
        self,
        leave_id: UUID,
        status: LeaveStatus,
        approved_by_id: Optional[UUID] = None,
        rejection_reason: Optional[str] = None,
    ) -> Optional[LeaveRequest]:
        result = await self._session.execute(
            select(LeaveRequest).where(LeaveRequest.id == leave_id)
        )
        req = result.scalar_one_or_none()
        if not req:
            return None
        req.status = status
        req.approved_by_id = approved_by_id
        if status == LeaveStatus.APPROVED:
            req.approved_at = datetime.now(timezone.utc)
        elif status == LeaveStatus.REJECTED:
            req.rejection_reason = rejection_reason
        await self._session.flush()
        return req

    async def list_leave_requests(
        self, organization_id: UUID, status: Optional[LeaveStatus] = None, page: int = 1, page_size: int = 20
    ) -> List[LeaveRequest]:
        offset = (page - 1) * page_size
        q = select(LeaveRequest).where(LeaveRequest.organization_id == organization_id)
        if status:
            q = q.where(LeaveRequest.status == status)
        q = q.offset(offset).limit(page_size).order_by(LeaveRequest.start_date.desc())
        result = await self._session.execute(q)
        return list(result.scalars().all())
