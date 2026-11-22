
import calendar
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import select, func

from database.db import init_db, SessionLocal

from database.models import (
    Employee,
    EmployeeAvailability,
    Brand,
    Pod,
    Process,
    Assignment,
    RosterRun,
    RosterEntry,
)

from engine.scheduler import generate_monthly_roster

from engine.leave_manager import (
    record_availability,
    approve_availability,
    reject_availability,
)

from engine.roster_manager import (
    get_roster_runs,
    approve_roster,
    publish_roster,
    reject_roster,
    RosterWorkflowError,
)

from engine.validator import validate_saved_roster


# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="Smart Roster Management",
    page_icon="📅",
    layout="wide",
)

init_db()

st.title("📅 Smart Roster Management System")
st.caption(
    "Automated scheduling | Leave management | "
    "Roster validation | Approval | Analytics"
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_roster_dataframe(session, roster_run_id):
    query = (
        select(
            RosterEntry.work_date,
            Employee.employee_code,
            Employee.full_name,
            Brand.name,
            Process.name,
            RosterEntry.status,
        )
        .join(Employee, RosterEntry.employee_id == Employee.id)
        .join(Brand, RosterEntry.brand_id == Brand.id)
        .join(Process, RosterEntry.process_id == Process.id)
        .where(RosterEntry.roster_run_id == roster_run_id)
        .order_by(
            RosterEntry.work_date,
            Brand.name,
            Process.name,
            Employee.full_name,
        )
    )

    rows = session.execute(query).all()

    return pd.DataFrame(
        rows,
        columns=[
            "Date",
            "Employee Code",
            "Employee",
            "Brand",
            "Process",
            "Status",
        ],
    )


def change_roster_status(roster_id, action):
    try:
        with SessionLocal() as session:
            if action == "approve":
                approve_roster(session, roster_id)
                message = f"Roster #{roster_id} is now APPROVED."

            elif action == "publish":
                publish_roster(session, roster_id)
                message = f"Roster #{roster_id} is now PUBLISHED."

            elif action == "reject":
                reject_roster(session, roster_id)
                message = f"Roster #{roster_id} is now REJECTED."

            else:
                raise ValueError("Unknown roster action.")

            session.commit()

        st.session_state["workflow_message"] = (
            "success",
            message,
        )
        st.session_state.pop("validation_result", None)
        st.rerun()

    except (RosterWorkflowError, ValueError) as error:
        st.session_state["workflow_message"] = (
            "error",
            str(error),
        )
        st.rerun()

    except Exception as error:
        st.session_state["workflow_message"] = (
            "error",
            f"Unexpected error: {error}",
        )
        st.rerun()


# ============================================================
# PHASE 1: DASHBOARD OVERVIEW
# ============================================================

st.header("📊 Dashboard Overview")

with SessionLocal() as session:
    employee_count = session.scalar(
        select(func.count(Employee.id)).where(
            Employee.is_active.is_(True)
        )
    ) or 0

    brand_count = session.scalar(
        select(func.count(Brand.id))
    ) or 0

    pod_count = session.scalar(
        select(func.count(Pod.id))
    ) or 0

    process_count = session.scalar(
        select(func.count(Process.id))
    ) or 0

    assignment_count = session.scalar(
        select(func.count(Assignment.id))
    ) or 0


c1, c2, c3, c4 = st.columns(4)

c1.metric("Active Employees", employee_count)
c2.metric("Brands", brand_count)
c3.metric("Pods", pod_count)
c4.metric("Processes", process_count)

st.divider()


# ============================================================
# PHASE 2: MONTHLY ROSTER GENERATOR
# ============================================================

st.header("🗓️ Monthly Roster Generator")

today = date.today()

col1, col2 = st.columns(2)

with col1:
    selected_month = st.selectbox(
        "Select Month",
        list(range(1, 13)),
        index=today.month - 1,
        format_func=lambda m: calendar.month_name[m],
        key="generator_month",
    )

with col2:
    selected_year = st.number_input(
        "Select Year",
        min_value=2024,
        max_value=2100,
        value=today.year,
        step=1,
        key="generator_year",
    )


if st.button(
    "🚀 Generate Monthly Roster",
    type="primary",
    use_container_width=True,
):
    try:
        with st.spinner("Generating optimized roster..."):
            with SessionLocal() as session:
                result = generate_monthly_roster(
                    session,
                    int(selected_year),
                    int(selected_month),
                    time_limit_seconds=30,
                    save=True,
                )
                session.commit()

        st.session_state["roster_result"] = result
        st.session_state["roster_period"] = (
            int(selected_year),
            int(selected_month),
        )
        st.session_state.pop("validation_result", None)

    except Exception as error:
        st.error(f"Roster generation failed: {error}")


roster_result = st.session_state.get("roster_result")
roster_period = st.session_state.get("roster_period")

if (
    roster_result is not None
    and roster_period == (
        int(selected_year),
        int(selected_month),
    )
):
    st.subheader("Generation Result")

    st.write(
        "**Solver Status:**",
        roster_result.get("status", "UNKNOWN"),
    )

    st.write(roster_result.get("message", ""))

    generated_id = roster_result.get("roster_run_id")

    if generated_id is not None:
        st.success(f"Roster #{generated_id} saved as DRAFT.")

        with SessionLocal() as session:
            generated_df = get_roster_dataframe(
                session,
                generated_id,
            )

        st.write(
            f"**Total Assignments:** {len(generated_df)}"
        )

        st.dataframe(
            generated_df,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "📥 Download Generated Roster CSV",
            data=generated_df.to_csv(index=False).encode("utf-8"),
            file_name=(
                f"roster_{selected_year}_"
                f"{selected_month:02d}.csv"
            ),
            mime="text/csv",
        )

    result_errors = roster_result.get("errors", [])
    result_warnings = roster_result.get("warnings", [])

    if result_errors:
        with st.expander(
            f"Generation Errors ({len(result_errors)})"
        ):
            for error in result_errors:
                st.error(str(error))

    if result_warnings:
        with st.expander(
            f"Generation Warnings ({len(result_warnings)})"
        ):
            for warning in result_warnings:
                st.warning(str(warning))

st.divider()


# ============================================================
# PHASE 3: LEAVE MANAGEMENT
# ============================================================

st.header("🏖️ Employee Leave Management")

with SessionLocal() as session:
    active_employees = session.scalars(
        select(Employee)
        .where(Employee.is_active.is_(True))
        .order_by(Employee.employee_code)
    ).all()

    employee_options = {
        employee.id: (
            f"{employee.employee_code} - {employee.full_name}"
        )
        for employee in active_employees
    }


st.subheader("Submit Availability Request")

if not employee_options:
    st.warning("No active employees available.")

else:
    with st.form("availability_request_form"):
        selected_employee_id = st.selectbox(
            "Select Employee",
            options=list(employee_options.keys()),
            format_func=lambda eid: employee_options[eid],
        )

        leave_date = st.date_input(
            "Select Date",
            value=today,
        )

        availability_status = st.selectbox(
            "Request Type",
            ["LEAVE", "COMP_OFF", "UNAVAILABLE"],
        )

        leave_note = st.text_area(
            "Reason / Notes",
            placeholder="Enter a reason...",
        )

        submit_leave = st.form_submit_button(
            "Submit Request",
            use_container_width=True,
        )

    if submit_leave:
        try:
            with SessionLocal() as session:
                record_availability(
                    session,
                    employee_id=selected_employee_id,
                    availability_date=leave_date,
                    status=availability_status,
                    note=leave_note,
                    approved=False,
                )
                session.commit()

            st.success("Availability request submitted.")

        except Exception as error:
            st.error(f"Could not submit request: {error}")


# ============================================================
# PENDING LEAVE REQUESTS
# ============================================================

st.subheader("Pending Leave / Availability Requests")

with SessionLocal() as session:
    pending_requests = session.scalars(
        select(EmployeeAvailability)
        .where(EmployeeAvailability.is_approved.is_(False))
        .order_by(
            EmployeeAvailability.availability_date,
            EmployeeAvailability.employee_id,
        )
    ).all()

    pending_data = [
        {
            "employee_id": request.employee_id,
            "date": request.availability_date,
            "status": request.status,
            "note": request.note,
        }
        for request in pending_requests
    ]


if not pending_data:
    st.info("No pending availability requests.")

else:
    for index, request in enumerate(pending_data):
        employee_label = employee_options.get(
            request["employee_id"],
            f"Employee #{request['employee_id']}",
        )

        with st.container(border=True):
            st.write(f"**{employee_label}**")
            st.write(
                f"Date: {request['date']} | "
                f"Type: {request['status']}"
            )

            if request["note"]:
                st.caption(request["note"])

            approve_col, reject_col = st.columns(2)

            with approve_col:
                if st.button(
                    "✅ Approve",
                    key=(
                        f"approve_leave_{index}_"
                        f"{request['employee_id']}_"
                        f"{request['date']}"
                    ),
                    use_container_width=True,
                ):
                    try:
                        with SessionLocal() as session:
                            approve_availability(
                                session,
                                request["employee_id"],
                                request["date"],
                            )
                            session.commit()

                        st.success("Request approved.")
                        st.rerun()

                    except Exception as error:
                        st.error(f"Approval failed: {error}")

            with reject_col:
                if st.button(
                    "❌ Reject",
                    key=(
                        f"reject_leave_{index}_"
                        f"{request['employee_id']}_"
                        f"{request['date']}"
                    ),
                    use_container_width=True,
                ):
                    try:
                        with SessionLocal() as session:
                            reject_availability(
                                session,
                                request["employee_id"],
                                request["date"],
                            )
                            session.commit()

                        st.success("Request rejected.")
                        st.rerun()

                    except Exception as error:
                        st.error(f"Rejection failed: {error}")


# ============================================================
# APPROVED LEAVE
# ============================================================

st.subheader("Approved Leave / Availability")

with SessionLocal() as session:
    approved_rows = session.execute(
        select(
            Employee.employee_code,
            Employee.full_name,
            EmployeeAvailability.availability_date,
            EmployeeAvailability.status,
            EmployeeAvailability.note,
        )
        .join(
            Employee,
            EmployeeAvailability.employee_id == Employee.id,
        )
        .where(EmployeeAvailability.is_approved.is_(True))
        .order_by(EmployeeAvailability.availability_date)
    ).all()


if approved_rows:
    approved_df = pd.DataFrame(
        approved_rows,
        columns=[
            "Employee Code",
            "Employee",
            "Date",
            "Status",
            "Notes",
        ],
    )

    st.dataframe(
        approved_df,
        use_container_width=True,
        hide_index=True,
    )

else:
    st.info("No approved availability records.")


st.info(
    "After approving leave, validate any existing roster. "
    "If conflicts are found, generate a new draft roster."
)

st.divider()


# ============================================================
# PHASE 4 + 5: ROSTER WORKFLOW AND VALIDATION
# ============================================================

st.header("📋 Roster Approval & Publishing")

workflow_message = st.session_state.pop(
    "workflow_message",
    None,
)

if workflow_message:
    message_type, message_text = workflow_message

    if message_type == "success":
        st.success(message_text)
    else:
        st.error(message_text)


review_col1, review_col2 = st.columns(2)

with review_col1:
    review_month = st.selectbox(
        "Review Month",
        list(range(1, 13)),
        index=today.month - 1,
        format_func=lambda m: calendar.month_name[m],
        key="review_month",
    )

with review_col2:
    review_year = st.number_input(
        "Review Year",
        min_value=2024,
        max_value=2100,
        value=today.year,
        step=1,
        key="review_year",
    )


with SessionLocal() as session:
    roster_runs = get_roster_runs(
        session,
        year=int(review_year),
        month=int(review_month),
    )

    roster_options = [
        {
            "id": roster.id,
            "status": roster.status,
            "generated_at": roster.generated_at,
        }
        for roster in roster_runs
    ]


if not roster_options:
    st.info("No saved rosters for the selected month.")

else:
    roster_ids = [r["id"] for r in roster_options]

    roster_labels = {
        r["id"]: (
            f"Roster #{r['id']} | "
            f"{r['status']} | "
            f"{r['generated_at']}"
        )
        for r in roster_options
    }

    selected_roster_id = st.selectbox(
        "Select Saved Roster",
        options=roster_ids,
        format_func=lambda rid: roster_labels[rid],
        key="selected_review_roster",
    )

    selected_roster_info = next(
        r for r in roster_options
        if r["id"] == selected_roster_id
    )

    selected_status = selected_roster_info["status"]

    with SessionLocal() as session:
        roster_df = get_roster_dataframe(
            session,
            selected_roster_id,
        )

    info1, info2, info3 = st.columns(3)

    info1.metric("Roster ID", selected_roster_id)
    info2.metric("Status", selected_status)
    info3.metric("Assignments", len(roster_df))

    st.subheader("Roster Preview")

    st.dataframe(
        roster_df,
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "📥 Download Selected Roster CSV",
        data=roster_df.to_csv(index=False).encode("utf-8"),
        file_name=(
            f"roster_{selected_roster_id}_"
            f"{review_year}_{review_month:02d}.csv"
        ),
        mime="text/csv",
        key=f"download_roster_{selected_roster_id}",
    )

    st.divider()

    # ========================================================
    # ROSTER VALIDATION
    # ========================================================

    st.subheader("🛡️ Roster Validation")

    st.write(
        "Check the selected roster against current "
        "availability and operating rules."
    )

    if st.button(
        "🔍 Validate Selected Roster",
        use_container_width=True,
        key=f"validate_roster_{selected_roster_id}",
    ):
        try:
            with st.spinner("Checking roster constraints..."):
                with SessionLocal() as session:
                    selected_roster = session.get(
                        RosterRun,
                        selected_roster_id,
                    )

                    if selected_roster is None:
                        raise ValueError("Roster not found.")

                    validation_result = validate_saved_roster(
                        session,
                        selected_roster,
                    )

            st.session_state["validation_result"] = {
                "roster_id": selected_roster_id,
                "result": validation_result,
            }

        except Exception as error:
            st.error(f"Validation failed to run: {error}")

    saved_validation = st.session_state.get(
        "validation_result"
    )

    if (
        saved_validation is not None
        and saved_validation["roster_id"] == selected_roster_id
    ):
        validation = saved_validation["result"]

        errors = validation.get("errors", [])
        warnings = validation.get("warnings", [])

        v1, v2, v3 = st.columns(3)

        v1.metric(
            "Validation",
            "PASS" if validation["valid"] else "FAIL",
        )
        v2.metric("Conflicts", len(errors))
        v3.metric("Warnings", len(warnings))

        if validation["valid"]:
            st.success(
                "Validation passed! No hard scheduling "
                "conflicts detected."
            )
        else:
            st.error(
                f"Validation failed: {len(errors)} conflicts."
            )

            with st.expander(
                "🚨 View Scheduling Conflicts",
                expanded=True,
            ):
                error_df = pd.DataFrame(
                    {"Conflict": errors}
                )

                st.dataframe(
                    error_df,
                    use_container_width=True,
                    hide_index=True,
                )

                st.download_button(
                    "📥 Download Conflict Report",
                    data=error_df.to_csv(
                        index=False
                    ).encode("utf-8"),
                    file_name=(
                        f"roster_{selected_roster_id}_"
                        "conflicts.csv"
                    ),
                    mime="text/csv",
                    key=f"conflicts_{selected_roster_id}",
                )

        if warnings:
            st.warning(
                f"{len(warnings)} scheduling warnings."
            )

            with st.expander("⚠️ View Warnings"):
                st.dataframe(
                    pd.DataFrame({"Warning": warnings}),
                    use_container_width=True,
                    hide_index=True,
                )

    else:
        st.info(
            "Click 'Validate Selected Roster' "
            "to check for conflicts."
        )

    st.caption(
        "This is the last validation result. "
        "Approval and publishing always revalidate."
    )

    st.divider()

    # ========================================================
    # ROSTER ACTIONS
    # ========================================================

    st.subheader("Roster Actions")

    if selected_status == "DRAFT":
        action1, action2 = st.columns(2)

        with action1:
            if st.button(
                "✅ Approve Roster",
                type="primary",
                use_container_width=True,
                key=f"approve_roster_{selected_roster_id}",
            ):
                change_roster_status(
                    selected_roster_id,
                    "approve",
                )

        with action2:
            if st.button(
                "❌ Reject Roster",
                use_container_width=True,
                key=f"reject_draft_{selected_roster_id}",
            ):
                change_roster_status(
                    selected_roster_id,
                    "reject",
                )

    elif selected_status == "APPROVED":
        action1, action2 = st.columns(2)

        with action1:
            if st.button(
                "📢 Publish Roster",
                type="primary",
                use_container_width=True,
                key=f"publish_roster_{selected_roster_id}",
            ):
                change_roster_status(
                    selected_roster_id,
                    "publish",
                )

        with action2:
            if st.button(
                "❌ Reject Approved Roster",
                use_container_width=True,
                key=f"reject_approved_{selected_roster_id}",
            ):
                change_roster_status(
                    selected_roster_id,
                    "reject",
                )

    elif selected_status == "PUBLISHED":
        st.success("This is a published roster.")
        st.info(
            "Published rosters cannot be rejected "
            "or published again."
        )

    elif selected_status == "REJECTED":
        st.warning("This roster has been rejected.")
        st.info("Generate a new draft if needed.")


st.divider()


# ============================================================
# PHASE 6: ANALYTICS DASHBOARD
# ============================================================

st.header("📈 Workforce Analytics Dashboard")

st.caption(
    "Analyze employee workload, staffing assignments, "
    "brand distribution, and approved leave."
)

analytics_col1, analytics_col2 = st.columns(2)

with analytics_col1:
    analytics_month = st.selectbox(
        "Analytics Month",
        options=list(range(1, 13)),
        index=today.month - 1,
        format_func=lambda m: calendar.month_name[m],
        key="analytics_month",
    )

with analytics_col2:
    analytics_year = st.number_input(
        "Analytics Year",
        min_value=2024,
        max_value=2100,
        value=today.year,
        step=1,
        key="analytics_year",
    )


with SessionLocal() as session:
    analytics_runs = get_roster_runs(
        session,
        year=int(analytics_year),
        month=int(analytics_month),
    )

    analytics_roster_options = [
        {
            "id": run.id,
            "status": run.status,
        }
        for run in analytics_runs
    ]


if not analytics_roster_options:
    st.info(
        "No saved roster available for this month. "
        "Generate a roster first."
    )

else:
    analytics_ids = [
        r["id"] for r in analytics_roster_options
    ]

    analytics_labels = {
        r["id"]: f"Roster #{r['id']} | {r['status']}"
        for r in analytics_roster_options
    }

    published_ids = [
        r["id"]
        for r in analytics_roster_options
        if r["status"] == "PUBLISHED"
    ]

    default_analytics_id = (
        published_ids[0]
        if published_ids
        else analytics_ids[0]
    )

    analytics_roster_id = st.selectbox(
        "Select Roster for Analytics",
        options=analytics_ids,
        index=analytics_ids.index(default_analytics_id),
        format_func=lambda rid: analytics_labels[rid],
        key="analytics_roster",
    )

    with SessionLocal() as session:
        analytics_df = get_roster_dataframe(
            session,
            analytics_roster_id,
        )

        month_start = date(
            int(analytics_year),
            int(analytics_month),
            1,
        )

        month_end = date(
            int(analytics_year),
            int(analytics_month),
            calendar.monthrange(
                int(analytics_year),
                int(analytics_month),
            )[1],
        )

        leave_rows = session.execute(
            select(
                Employee.employee_code,
                Employee.full_name,
                EmployeeAvailability.availability_date,
                EmployeeAvailability.status,
            )
            .join(
                Employee,
                EmployeeAvailability.employee_id == Employee.id,
            )
            .where(
                EmployeeAvailability.is_approved.is_(True),
                EmployeeAvailability.availability_date >= month_start,
                EmployeeAvailability.availability_date <= month_end,
                EmployeeAvailability.status.in_(
                    ["LEAVE", "COMP_OFF", "UNAVAILABLE"]
                ),
            )
        ).all()

    if analytics_df.empty:
        st.warning(
            "The selected roster contains no assignments."
        )

    else:
        analytics_df["Date"] = pd.to_datetime(
            analytics_df["Date"]
        )

        # ====================================================
        # ANALYTICS FILTERS
        # ====================================================

        st.subheader("Analytics Filters")

        filter1, filter2 = st.columns(2)

        all_brands = sorted(
            analytics_df["Brand"].unique().tolist()
        )

        all_processes = sorted(
            analytics_df["Process"].unique().tolist()
        )

        with filter1:
            selected_brands = st.multiselect(
                "Filter Brands",
                options=all_brands,
                default=all_brands,
                key=f"analytics_brands_{analytics_roster_id}",
            )

        with filter2:
            selected_processes = st.multiselect(
                "Filter Processes",
                options=all_processes,
                default=all_processes,
                key=f"analytics_processes_{analytics_roster_id}",
            )

        filtered_df = analytics_df[
            analytics_df["Brand"].isin(selected_brands)
            & analytics_df["Process"].isin(selected_processes)
        ].copy()

        work_df = filtered_df[
            filtered_df["Status"] == "WORK"
        ].copy()

        # ====================================================
        # ANALYTICS SUMMARY
        # ====================================================

        st.subheader("Roster Statistics")

        unique_employees = work_df[
            "Employee Code"
        ].nunique()

        total_assignments = len(work_df)

        unique_workdays = work_df[
            ["Employee Code", "Date"]
        ].drop_duplicates()

        total_employee_days = len(unique_workdays)

        operating_dates = work_df[
            "Date"
        ].nunique()

        stat1, stat2, stat3, stat4 = st.columns(4)

        stat1.metric(
            "Work Assignments",
            total_assignments,
        )

        stat2.metric(
            "Scheduled Employees",
            unique_employees,
        )

        stat3.metric(
            "Employee Workdays",
            total_employee_days,
        )

        stat4.metric(
            "Dates With Assignments",
            operating_dates,
        )

        st.caption(
            "One employee may have multiple process "
            "assignments on the same date. "
            "Employee Workdays counts each employee/date once. "
            "Statistics follow the selected filters."
        )

        if work_df.empty:
            st.info(
                "No work assignments match the selected filters."
            )

        else:
            # ================================================
            # EMPLOYEE WORKLOAD
            # ================================================

            st.subheader("👥 Employee Workload Analysis")

            employee_workload = (
                work_df.groupby(
                    ["Employee Code", "Employee"]
                )["Date"]
                .nunique()
                .reset_index(name="Working Days")
                .sort_values(
                    "Working Days",
                    ascending=False,
                )
            )

            st.bar_chart(
                employee_workload.set_index(
                    "Employee Code"
                )["Working Days"],
                use_container_width=True,
            )

            st.dataframe(
                employee_workload,
                use_container_width=True,
                hide_index=True,
            )

            st.caption(
                "Working days are unique dates per employee, "
                "not the number of process assignments."
            )

            # ================================================
            # DAILY STAFFING TREND
            # ================================================

            st.subheader("📅 Daily Staffing Trend")

            daily_staffing = (
                work_df.groupby("Date")[
                    "Employee Code"
                ]
                .nunique()
                .reset_index(name="Employees Scheduled")
                .sort_values("Date")
            )

            st.line_chart(
                daily_staffing.set_index(
                    "Date"
                )["Employees Scheduled"],
                use_container_width=True,
            )

            # ================================================
            # BRAND ASSIGNMENT DISTRIBUTION
            # ================================================

            st.subheader("🏢 Brand Assignment Distribution")

            brand_distribution = (
                work_df.groupby("Brand")
                .size()
                .reset_index(name="Assignments")
                .sort_values(
                    "Assignments",
                    ascending=False,
                )
            )

            st.bar_chart(
                brand_distribution.set_index(
                    "Brand"
                )["Assignments"],
                use_container_width=True,
            )

            st.caption(
                "Shows assignment volume by brand, "
                "not whether minimum staffing requirements "
                "were satisfied."
            )

            # ================================================
            # PROCESS DISTRIBUTION
            # ================================================

            st.subheader("⚙️ Process Distribution")

            process_distribution = (
                work_df.groupby("Process")
                .size()
                .reset_index(name="Assignments")
                .sort_values(
                    "Assignments",
                    ascending=False,
                )
            )

            st.bar_chart(
                process_distribution.set_index(
                    "Process"
                )["Assignments"],
                use_container_width=True,
            )

            # ================================================
            # BRAND / PROCESS MATRIX
            # ================================================

            st.subheader("📊 Brand and Process Matrix")

            brand_process_matrix = pd.crosstab(
                work_df["Brand"],
                work_df["Process"],
            )

            st.dataframe(
                brand_process_matrix,
                use_container_width=True,
            )

            st.caption(
                "Each cell shows the number of assignments "
                "for that brand and process in the "
                "selected roster and filters."
            )

        # ====================================================
        # APPROVED LEAVE ANALYTICS
        # ====================================================

        st.subheader("🏖️ Approved Leave Analytics")

        leave_df = pd.DataFrame(
            leave_rows,
            columns=[
                "Employee Code",
                "Employee",
                "Date",
                "Status",
            ],
        )

        if leave_df.empty:
            st.info(
                "No approved leave or unavailability "
                "records for this month."
            )

        else:
            leave_summary = (
                leave_df.groupby("Status")
                .size()
                .reset_index(name="Approved Days")
            )

            leave1, leave2 = st.columns(2)

            leave1.metric(
                "Approved Availability Records",
                len(leave_df),
            )

            leave2.metric(
                "Employees With Approved Records",
                leave_df["Employee Code"].nunique(),
            )

            st.bar_chart(
                leave_summary.set_index(
                    "Status"
                )["Approved Days"],
                use_container_width=True,
            )

            st.dataframe(
                leave_df,
                use_container_width=True,
                hide_index=True,
            )

            st.caption(
                "Leave analytics cover the selected month "
                "across all employees and do not change "
                "with brand/process filters."
            )

        # ====================================================
        # ANALYTICS CSV EXPORT
        # ====================================================

        st.subheader("📥 Export Analytics")

        st.download_button(
            "Download Filtered Roster Data",
            data=filtered_df.to_csv(
                index=False
            ).encode("utf-8"),
            file_name=(
                f"analytics_roster_{analytics_roster_id}.csv"
            ),
            mime="text/csv",
            use_container_width=True,
            key=f"analytics_export_{analytics_roster_id}",
        )


# ============================================================
# RESOURCE CONFIGURATION
# ============================================================

st.divider()

st.header("⚙️ Resource Configuration")

st.write(
    "**Total Employee-Process Assignments:**",
    assignment_count,
)

st.caption(
    "Smart Roster Management System | "
    "Automated Scheduling & Workforce Optimization"
)
