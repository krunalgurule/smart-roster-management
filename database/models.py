from datetime import date, datetime
from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String,
    UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db import Base

class Pod(Base):
    __tablename__ = "pods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    lead_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", use_alter=True, name="fk_pod_lead_employee"),
        nullable=True
    )
    employees: Mapped[list["Employee"]] = relationship(
        back_populates="pod", foreign_keys="Employee.pod_id"
    )

class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint("max_workdays_per_week BETWEEN 1 AND 7",
                        name="ck_employee_max_workdays"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    pod_id: Mapped[int] = mapped_column(ForeignKey("pods.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_workdays_per_week: Mapped[int] = mapped_column(Integer, default=6, nullable=False)

    pod: Mapped["Pod"] = relationship(back_populates="employees", foreign_keys=[pod_id])
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="employee")
    weekly_offs: Mapped[list["WeeklyOff"]] = relationship(back_populates="employee")
    availability: Mapped[list["EmployeeAvailability"]] = relationship(back_populates="employee")

class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="brand")

class Process(Base):
    __tablename__ = "processes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="process")

class Assignment(Base):
    """Many-to-many bridge: one employee can serve many brand/process pairs."""
    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("employee_id", "brand_id", "process_id",
                         name="uq_employee_brand_process"),
        Index("ix_assignment_brand_process", "brand_id", "process_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), nullable=False)
    process_id: Mapped[int] = mapped_column(ForeignKey("processes.id"), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    employee: Mapped["Employee"] = relationship(back_populates="assignments")
    brand: Mapped["Brand"] = relationship(back_populates="assignments")
    process: Mapped["Process"] = relationship(back_populates="assignments")

class OperatingRule(Base):
    """Operating calendar and minimum staffing for one brand/process pair."""
    __tablename__ = "operating_rules"
    __table_args__ = (
        UniqueConstraint("brand_id", "process_id", name="uq_rule_brand_process"),
        CheckConstraint("min_staff >= 1", name="ck_rule_min_staff"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), nullable=False)
    process_id: Mapped[int] = mapped_column(ForeignKey("processes.id"), nullable=False)
    # Calendar mode: EVERY_DAY, NO_PUBLIC_HOLIDAYS, or NO_SUNDAYS_OR_HOLIDAYS
    calendar_mode: Mapped[str] = mapped_column(String(40), default="EVERY_DAY", nullable=False)
    min_staff: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

class WeeklyOff(Base):
    __tablename__ = "weekly_offs"
    __table_args__ = (
        UniqueConstraint("employee_id", "weekday", name="uq_employee_weekly_off"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_weekly_off_weekday"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    # Python weekday: Monday=0 ... Sunday=6
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    employee: Mapped["Employee"] = relationship(back_populates="weekly_offs")

class PublicHoliday(Base):
    __tablename__ = "public_holidays"
    __table_args__ = (UniqueConstraint("holiday_date", name="uq_public_holiday_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    region: Mapped[str] = mapped_column(String(80), default="India", nullable=False)

class EmployeeAvailability(Base):
    __tablename__ = "employee_availability"
    __table_args__ = (
        UniqueConstraint("employee_id", "availability_date",
                         name="uq_employee_availability_date"),
        Index("ix_availability_date", "availability_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    availability_date: Mapped[date] = mapped_column(Date, nullable=False)
    # LEAVE, COMP_OFF, UNAVAILABLE, AVAILABLE
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    note: Mapped[str] = mapped_column(String(255), default="")
    employee: Mapped["Employee"] = relationship(back_populates="availability")

class RosterRun(Base):
    __tablename__ = "roster_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str] = mapped_column(String(255), default="")

class RosterEntry(Base):
    __tablename__ = "roster_entries"
    __table_args__ = (
        UniqueConstraint("roster_run_id", "employee_id", "brand_id", "process_id",
                         "work_date", name="uq_roster_assignment_day"),
        Index("ix_roster_entry_date", "work_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    roster_run_id: Mapped[int] = mapped_column(ForeignKey("roster_runs.id"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), nullable=False)
    process_id: Mapped[int] = mapped_column(ForeignKey("processes.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="WORK", nullable=False)
