"""Patient "My Prescriptions" page: read-only history of finalized and voided simulated prescriptions."""

from __future__ import annotations

import streamlit as st

from app_pages.prescription_service import STATUS_FINALIZED, STATUS_VOIDED, list_prescriptions_for_patient
from app_pages.prescription_ui import (
    STATUS_LABELS,
    format_date,
    render_pdf_download,
    render_prescription_summary,
    render_simulation_notice,
    status_label,
)
from app_pages.registration_page import get_prescriptions_collection


def render() -> None:
    """Show the signed-in patient's own prescriptions. Drafts are never shown."""
    st.title("My Prescriptions")
    render_simulation_notice()

    user = st.session_state.get("authenticated_user") or {}
    prescriptions = list_prescriptions_for_patient(get_prescriptions_collection(), user.get("email"))
    if not prescriptions:
        st.info("You don't have any prescriptions yet.")
        return

    statuses = st.segmented_control(
        "Filter by status",
        options=[STATUS_FINALIZED, STATUS_VOIDED],
        selection_mode="multi",
        default=[STATUS_FINALIZED, STATUS_VOIDED],
        format_func=lambda status: STATUS_LABELS[status],
        key="my_rx_status_filter",
    )
    shown = [prescription for prescription in prescriptions if prescription.get("status") in (statuses or [])]
    if not shown:
        st.info("No prescriptions match the selected filters.")
        return

    for index, prescription in enumerate(shown):
        title = (
            f"{prescription.get('prescription_id')} · {status_label(prescription)} · "
            f"{prescription.get('doctor_name')} · {format_date(prescription.get('created_at'))}"
        )
        with st.expander(title, expanded=index == 0):
            render_prescription_summary(prescription)
            render_pdf_download(prescription, key=f"my_rx_pdf_{prescription['_id']}")
