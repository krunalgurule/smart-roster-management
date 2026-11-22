
from datetime import date

from sqlalchemy import select

from database.models import Employee, EmployeeAvailability


VALID_STATUSES = {
    "LEAVE",
    "COMP_OFF",
    "UNAVAILABLE",
    "AVAILABLE",
}


def record_availability(
    session,
    employee_id: int,
    availability_date: date,
    status: str,
    note: str = "",
    approved: bool = False,
):
    """
    Create or update an employee availability record.

    Pending requests do not block scheduling.
    Approved LEAVE, COMP_OFF and UNAVAILABLE
    records block scheduling.
    """

    status = status.upper().strip()

    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status: {status}. "
            f"Allowed values: {sorted(VALID_STATUSES)}"
        )

    employee = session.get(Employee, employee_id)

    if employee is None or not employee.is_active:
        raise ValueError("Employee does not exist or is inactive.")

    record = session.scalar(
        select(EmployeeAvailability).where(
            EmployeeAvailability.employee_id == employee_id,
            EmployeeAvailability.availability_date == availability_date,
        )
    )

    if record is None:
        record = EmployeeAvailability(
            employee_id=employee_id,
            availability_date=availability_date,
            status=status,
            is_approved=approved,
            note=note,
        )
        session.add(record)

    else:
        record.status = status
        record.is_approved = approved
        record.note = note

    session.flush()

    return record


def approve_availability(session, employee_id, availability_date):
    record = session.scalar(
        select(EmployeeAvailability).where(
            EmployeeAvailability.employee_id == employee_id,
            EmployeeAvailability.availability_date == availability_date,
        )
    )

    if record is None:
        raise ValueError("Availability request not found.")

    record.is_approved = True
    session.flush()

    return record


def reject_availability(session, employee_id, availability_date):
    record = session.scalar(
        select(EmployeeAvailability).where(
            EmployeeAvailability.employee_id == employee_id,
            EmployeeAvailability.availability_date == availability_date,
        )
    )

    if record is None:
        raise ValueError("Availability request not found.")

    session.delete(record)
    session.flush()

    return True
