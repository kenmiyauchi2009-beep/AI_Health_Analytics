import streamlit as st

from app_pages.dashboard_page import get_user_role
from app_pages.doctor_navigation import DASHBOARD as DOCTOR_HOME
from app_pages.doctor_navigation import SIDEBAR_GROUPS as DOCTOR_GROUPS
from app_pages.doctor_navigation import doctor_pages
from app_pages.patient_navigation import HOME as PATIENT_HOME
from app_pages.patient_navigation import SIDEBAR_GROUPS as PATIENT_GROUPS
from app_pages.patient_navigation import patient_pages
from app_pages.registration_page import render_auth_gate
from app_pages.sidebar import render_sidebar
from ui.theme import apply_theme

# The URL someone asked for while signed out, so they land there (or on home) after signing in.
REQUESTED_PATH_KEY = "requested_path"


def _signed_out_pages() -> list:
    """Every app URL shows the sign-in screen while signed out, so links and reloads never hit "page not found";
    after signing in, the person lands on the page they asked for."""
    paths = {*patient_pages().keys(), *doctor_pages().keys()}
    return [st.Page(render_auth_gate, title="Sign in", url_path="sign-in", default=True)] + [
        st.Page(render_auth_gate, title="Sign in", url_path=path) for path in sorted(paths)
    ]


def main() -> None:
    """App-level controller: picks the pages available to the current user and runs the selected one."""
    st.set_page_config(page_title="DeltaAI Health", page_icon="assets/logo_icon.svg", layout="wide")
    apply_theme()

    user = st.session_state.get("authenticated_user")
    if user is None:
        pages = _signed_out_pages()
    else:
        role = get_user_role(user)
        if role == "Doctor":
            pages_by_key, groups, home = doctor_pages(), DOCTOR_GROUPS, DOCTOR_HOME
        else:
            pages_by_key, groups, home = patient_pages(), PATIENT_GROUPS, PATIENT_HOME
        requested = st.session_state.pop(REQUESTED_PATH_KEY, None)
        if requested is not None and requested not in pages_by_key:
            # Signed in on a URL this role doesn't have (e.g. a patient page link): start on the home page.
            st.switch_page(pages_by_key[home])
        render_sidebar(groups, pages_by_key, user, role)
        pages = list(pages_by_key.values())

    # Navigation is drawn by render_sidebar so it can be grouped and include a profile summary;
    # detail pages stay registered (reachable by st.switch_page) without appearing in the sidebar.
    current = st.navigation(pages, position="hidden")
    if user is None:
        st.session_state[REQUESTED_PATH_KEY] = current.url_path
    current.run()


if __name__ == "__main__":
    main()
