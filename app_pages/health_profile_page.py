"""Patient health profile: the details doctors see, with known conditions editable by the patient."""

from __future__ import annotations

import streamlit as st

from app_pages.patient_navigation import MY_DOCTORS, page
from app_pages.patient_overview_service import calculate_age, parse_known_conditions, update_known_conditions
from app_pages.practitioner_service import format_person_name, get_primary_practitioner
from app_pages.registration_page import get_requests_collection, get_users_collection
from ui.components import card, field_grid, flash, form_section, page_header, show_errors, show_flash

COMMON_CONDITIONS = [
    "Allergies", "Arthritis", "Asthma", "Chronic kidney disease", "COPD", "Depression", "Heart disease",
    "High blood pressure", "High cholesterol", "Hypothyroidism", "Migraine", "Type 1 diabetes", "Type 2 diabetes",
]


def render() -> None:
    session_user = st.session_state.get("authenticated_user") or {}
    users = get_users_collection()
    user = (users.find_one({"email": session_user.get("email")}) if users is not None else None) or session_user

    page_header("Health profile", "Shared with your doctor alongside your analyses")
    show_flash("health-profile")

    with card("health-summary"):
        age = calculate_age(user.get("date_of_birth"))
        doctor = get_primary_practitioner(users, get_requests_collection(), user.get("email"))
        field_grid(
            [
                ("Name", format_person_name(user)),
                ("Date of birth", user.get("date_of_birth")),
                ("Age", age),
                ("Primary health practitioner", format_person_name(doctor, doctor=True) if doctor else "Not connected"),
            ],
            columns=4,
        )
        if doctor is None:
            st.page_link(page(MY_DOCTORS), label="Find a doctor", icon=":material/arrow_forward:")

    current = parse_known_conditions(user.get("known_conditions"))
    with form_section("Known conditions", "Long-term conditions your doctor should know about. "
                      "Pick from the list or type your own and press Enter.", key="conditions"):
        selected = st.multiselect(
            "Known conditions",
            options=sorted(set(COMMON_CONDITIONS) | set(current)),
            default=current,
            accept_new_options=True,
            placeholder="Add a condition",
            label_visibility="collapsed",
            key="known_conditions_editor",
        )
        if st.button("Save conditions", type="primary", icon=":material/save:", disabled=selected == current):
            saved, errors = update_known_conditions(users, user.get("email"), selected)
            if not show_errors(errors):
                st.session_state["authenticated_user"] = {**session_user, "known_conditions": saved}
                flash("Known conditions saved.", key="health-profile")
                st.rerun()
