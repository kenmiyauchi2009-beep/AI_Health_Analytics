"""The signed-in sidebar: logo, grouped navigation, and the user's profile summary with Logout."""

from __future__ import annotations

import streamlit as st

from app_pages.practitioner_service import format_person_name

LOGO = "assets/logo.svg"
LOGO_ICON = "assets/logo_icon.svg"


def logout() -> None:
    st.session_state.clear()


def render_sidebar(groups: list[tuple[str, list[str]]], pages: dict[str, st.Page], user: dict, role: str) -> None:
    """Grouped page links (Streamlit highlights the current page) and a profile summary."""
    st.logo(LOGO, icon_image=LOGO_ICON, size="large")
    with st.sidebar:
        for label, keys in groups:
            st.caption(label)
            for key in keys:
                st.page_link(pages[key])

        st.divider()
        name = format_person_name(user, doctor=role == "Doctor")
        st.markdown(f"**{name}**  \n:gray[{role} account]")
        st.caption(user.get("email", ""))
        st.button("Log out", icon=":material/logout:", on_click=logout, key="sidebar_logout", width="stretch")
