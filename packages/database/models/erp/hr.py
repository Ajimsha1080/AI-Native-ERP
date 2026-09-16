"""
HR domain models.

Tables: departments, employees, attendance_records, leave_requests

Business rules:
  - AttendanceRecord.hours_worked is computed from check_in/check_out
    when the record is closed by the service.
  - LeaveRequest status: pending → approved | rejected
  - Employees reference an optional User account (for system access).
"""

from enum import Enum as PyEnum
from datetime import date
from sqlalchemy import (
    Column, String, Text, Numeric, Date, DateTime, ForeignKey,
    CheckConstraint, Index, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from packages.database.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin


class LeaveType(str, PyEnum):
    ANNUAL = "annual"
    SICK = "sick"
    MATERNITY = "maternity"
    PATERNITY = "paternity"
    UNPAID = "unpaid"
    OTHER = "other"


class LeaveStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class Department(SoftDeleteMixin, Base):
    """An organisational department."""
    __tablename__ = "departments"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)

    # Department head (optional — references an employee)
    manager_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    employees = relationship("Employee", back_populates="department", foreign_keys="Employee.department_id")
    manager = relationship("Employee", foreign_keys=[manager_id], post_update=True)

    __table_args__ = (
        Index("ix_department_organization", "organization_id"),
    )


class Employee(SoftDeleteMixin, Base):
    """
    An employee record.

    Employees may optionally be linked to a User account (for system login).
    An employee without a user_id is a record-only entry (e.g., non-system users).
    """
    __tablename__ = "employees"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Optional link to a system user account
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    job_title = Column(String(255), nullable=True)
    employee_number = Column(String(50), nullable=True)
    hire_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # null = currently employed

    # Salary stored as NUMERIC to avoid floating-point issues
    salary = Column(Numeric(15, 2), nullable=True)
    salary_currency = Column(String(3), nullable=False, default="USD")

    # Relationships
    department = relationship("Department", back_populates="employees", foreign_keys=[department_id])
    attendance_records = relationship("AttendanceRecord", back_populates="employee")
    leave_requests = relationship("LeaveRequest", back_populates="employee")

    __table_args__ = (
        CheckConstraint("salary IS NULL OR salary >= 0", name="chk_employee_salary"),
        Index("ix_employee_organization", "organization_id"),
        Index("ix_employee_department", "department_id"),
    )


class AttendanceRecord(Base):
    """
    A daily attendance log entry for an employee.

    hours_worked is computed when the record is closed (check_out is set).
    The service calculates: hours_worked = (check_out - check_in).seconds / 3600
    """
    __tablename__ = "attendance_records"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    date = Column(Date, nullable=False)
    check_in = Column(DateTime(timezone=True), nullable=False)
    check_out = Column(DateTime(timezone=True), nullable=True)
    hours_worked = Column(Numeric(5, 2), nullable=True)  # Set when check_out is recorded
    notes = Column(Text, nullable=True)

    # Relationships
    employee = relationship("Employee", back_populates="attendance_records")

    __table_args__ = (
        CheckConstraint(
            "check_out IS NULL OR check_out > check_in",
            name="chk_attendance_checkout_after_checkin",
        ),
        CheckConstraint(
            "hours_worked IS NULL OR hours_worked >= 0",
            name="chk_attendance_hours_non_negative",
        ),
        Index("ix_attendance_organization", "organization_id"),
        Index("ix_attendance_employee", "employee_id"),
        Index("ix_attendance_date", "date"),
    )


class LeaveRequest(Base):
    """
    An employee leave request.

    Status flow: pending → approved | rejected | cancelled
    Approved/rejected by a manager via /hr/leave-requests/{id}/approve
    """
    __tablename__ = "leave_requests"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    leave_type = Column(
        SAEnum(LeaveType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(
        SAEnum(LeaveStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=LeaveStatus.PENDING,
    )

    approved_by_id = Column(PG_UUID(as_uuid=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Relationships
    employee = relationship("Employee", back_populates="leave_requests")

    __table_args__ = (
        CheckConstraint(
            "end_date >= start_date",
            name="chk_leave_end_after_start",
        ),
        Index("ix_leave_organization", "organization_id"),
        Index("ix_leave_employee", "employee_id"),
        Index("ix_leave_status", "status"),
    )
