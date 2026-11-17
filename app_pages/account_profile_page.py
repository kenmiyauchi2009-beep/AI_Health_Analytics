"""Account profile for patients and doctors: the details on file, and logging out."""

from __future__ import annotations

import streamlit as st

from app_pages.dashboard_page import get_user_role
from app_pages.practitioner_service import format_person_name
from app_pages.registration_page import get_users_collection
from app_pages.sidebar import logout
from ui.components import field_grid, form_section, page_header


def render() -> None:
    session_user = st.session_state.get("authenticated_user") or {}
    users = get_users_collection()
    user = (users.find_one({"email": session_user.get("email")}) if users is not None else None) or session_user
    role = get_user_role(user)

    actions = page_header("Profile", "The account details on file")
    actions.button("Log out", icon=":material/logout:", on_click=logout, key="profile_logout")

    with form_section("Account", key="account"):
        field_grid(
            [
                ("Name", format_person_name(user, doctor=role == "Doctor")),
                ("Email", user.get("email")),
                ("Phone", user.get("phone_number")),
                ("Account type", role),
            ],
            columns=2,
        )

    if role == "Doctor":
        with form_section("Professional details", "Shown to patients choosing a doctor", key="professional"):
            field_grid(
                [
                    ("Speciality", user.get("speciality")),
                    ("Degree", user.get("degree")),
                    ("Years of experience", user.get("yoe")),
                    ("Clinic or hospital", user.get("clinic_or_hospital")),
                    ("Medical license number", user.get("medical_license_number")),
                ],
                columns=2,
            )
    else:
        with form_section("Personal details", key="personal"):
            field_grid([("Date of birth", user.get("date_of_birth")), ("Address", user.get("address"))], columns=2)
