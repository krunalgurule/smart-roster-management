
from sqlalchemy import select

from database.models import RosterRun, RosterEntry
from engine.validator import validate_saved_roster


class RosterWorkflowError(ValueError):
    """Raised when a roster action is not allowed."""


def get_roster_runs(session, year=None, month=None):
    """Return saved rosters, newest first."""

    query = select(RosterRun)

    if year is not None:
        query = query.where(RosterRun.year == year)

    if month is not None:
        query = query.where(RosterRun.month == month)

    query = query.order_by(RosterRun.id.desc())

    return session.scalars(query).all()


def check_roster_validity(session, roster):
    """
    Validate saved assignments against current
    employee availability and operating rules.

    Block the workflow if any hard errors exist.
    """

    result = validate_saved_roster(session, roster)

    if not result["valid"]:

        errors = result["errors"]

        error_message = (
            f"Roster #{roster.id} failed validation "
            f"with {len(errors)} error(s):\n"
            + "\n".join(errors[:10])
        )

        if len(errors) > 10:
            error_message += (
                f"\n...and {len(errors) - 10} more errors."
            )

        raise RosterWorkflowError(error_message)

    return result


def approve_roster(session, roster_run_id):
    """
    Allowed transition:
        DRAFT -> APPROVED

    Validation is mandatory.
    """

    roster = session.get(RosterRun, roster_run_id)

    if roster is None:
        raise RosterWorkflowError("Roster not found.")

    if roster.status != "DRAFT":
        raise RosterWorkflowError(
            f"Cannot approve roster with status {roster.status}."
        )

    has_entries = session.scalar(
        select(RosterEntry.id)
        .where(RosterEntry.roster_run_id == roster_run_id)
        .limit(1)
    )

    if has_entries is None:
        raise RosterWorkflowError(
            "Cannot approve an empty roster."
        )

    # Validate before approval
    check_roster_validity(session, roster)

    roster.status = "APPROVED"

    session.flush()

    return roster


def publish_roster(session, roster_run_id):
    """
    Allowed transition:
        APPROVED -> PUBLISHED

    Validation is mandatory.
    Only one published roster per month.
    """

    roster = session.get(RosterRun, roster_run_id)

    if roster is None:
        raise RosterWorkflowError("Roster not found.")

    if roster.status != "APPROVED":
        raise RosterWorkflowError(
            "Only an APPROVED roster can be published."
        )

    existing_published = session.scalar(
        select(RosterRun)
        .where(
            RosterRun.year == roster.year,
            RosterRun.month == roster.month,
            RosterRun.status == "PUBLISHED",
            RosterRun.id != roster.id,
        )
    )

    if existing_published is not None:
        raise RosterWorkflowError(
            "A roster is already published for this month."
        )

    # Revalidate before publishing
    check_roster_validity(session, roster)

    roster.status = "PUBLISHED"

    session.flush()

    return roster


def reject_roster(session, roster_run_id):
    """
    Allowed transitions:
        DRAFT -> REJECTED
        APPROVED -> REJECTED
    """

    roster = session.get(RosterRun, roster_run_id)

    if roster is None:
        raise RosterWorkflowError("Roster not found.")

    if roster.status not in ("DRAFT", "APPROVED"):
        raise RosterWorkflowError(
            f"Cannot reject roster with status {roster.status}."
        )

    roster.status = "REJECTED"

    session.flush()

    return roster
