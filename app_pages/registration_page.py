from __future__ import annotations

import os
from pathlib import Path
import tomllib

import bcrypt
import streamlit as st
from pymongo import MongoClient, errors

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_secret_config() -> dict:
    """Read config values from app-level secrets files with sensible fallbacks."""
    config: dict = {}
    for candidate in (
        REPO_ROOT / "secrets.toml",
        REPO_ROOT / ".streamlit" / "secrets.toml",
    ):
        if not candidate.exists():
            continue
        with candidate.open("rb") as handle:
            try:
                loaded = tomllib.load(handle)
            except tomllib.TOMLDecodeError:
                loaded = {}
        if isinstance(loaded, dict):
            config.update(loaded)
    return config


def get_mongo_uri() -> str | None:
    """Return a MongoDB URI from secrets or environment variables."""
    config = _load_secret_config()
    mongo_section = config.get("mongo", {})
    mongo_uri = (
        config.get("MONGO_URI")
        or config.get("MONGODB_URI")
        or mongo_section.get("uri")
        or os.getenv("MONGO_URI")
        or os.getenv("MONGODB_URI")
    )
    if mongo_uri is None:
        return None
    return str(mongo_uri).strip() or None


def hash_password(password: str) -> str:
    """Hash a password using bcrypt so plaintext is never stored."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def validate_registration(form_data: dict, email_exists) -> list[str]:
    """Return validation errors for the user registration form."""
    errors: list[str] = []
    role = str(form_data.get("role") or "Patient")

    first_name = str(form_data.get("first_name") or "").strip()
    last_name = str(form_data.get("last_name") or "").strip()
    email = str(form_data.get("email") or "").strip().lower()
    password = str(form_data.get("password") or "")
    confirm_password = str(form_data.get("confirm_password") or "")

    if not first_name:
        errors.append("First name cannot be empty.")
    if not last_name:
        errors.append("Last name cannot be empty.")
    if not email:
        errors.append("Email is required.")
    elif email_exists(email):
        errors.append("Email must be unique.")
    if not password:
        errors.append("Password is required.")
    if not confirm_password:
        errors.append("Confirm Password is required.")
    if password and confirm_password and password != confirm_password:
        errors.append("Password and Confirm Password should match.")

    if role == "Patient":
        dob = str(form_data.get("date_of_birth") or "").strip()
        address = str(form_data.get("address") or "").strip()
        if not dob:
            errors.append("Date of Birth is required.")
        if not address:
            errors.append("Address is required.")
    elif role == "Doctor":
        medical_license_number = str(form_data.get("medical_license_number") or "").strip()
        speciality = str(form_data.get("speciality") or "").strip()
        clinic_or_hospital = str(form_data.get("clinic_or_hospital") or "").strip()
        if not medical_license_number:
            errors.append("Medical License Number is required.")
        if not speciality:
            errors.append("Speciality is required.")
        if not clinic_or_hospital:
            errors.append("Clinic / Hospital is required.")

    return errors


def get_users_collection():
    """Create the MongoDB client and users collection if the URI is configured."""
    mongo_uri = get_mongo_uri()
    if not mongo_uri:
        return None

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
    except errors.PyMongoError:
        return None

    db = client["deltaai"]
    db.users.create_index("email", unique=True)
    return db.users


def authenticate_user(email: str, password: str, users_collection) -> dict | None:
    """Authenticate a user by email and bcrypt-hashed password."""
    if users_collection is None:
        return None

    normalized_email = (email or "").strip().lower()
    if not normalized_email or not password:
        return None

    user = users_collection.find_one({"email": normalized_email})
    if user is None:
        return None

    stored_hash = user.get("password_hash")
    if not stored_hash:
        return None

    try:
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
            return user
    except (TypeError, ValueError):
        return None

    return None


def render_signup_form() -> None:
    """Render the sign-up form used as the app landing registration page."""
    st.title("Create your account")
    st.caption("This registration page acts as the signup form for new users.")

    users_collection = get_users_collection()
    if users_collection is None:
        st.warning(
            "MongoDB is not configured yet. Add a `MONGO_URI` value to `secrets.toml` or `.streamlit/secrets.toml` to enable sign-up."
        )
        return

    role = st.selectbox("User type", ["Patient", "Doctor"], index=0)

    first_name = st.text_input("First Name")
    last_name = st.text_input("Last Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")
    phone_number = st.text_input("Phone Number (Optional)")

    if role == "Patient":
        date_of_birth = st.date_input("Date of Birth")
        address = st.text_area("Address")
        medical_license_number = ""
        speciality = ""
        yoe = 0
        clinic_or_hospital = ""
    else:
        date_of_birth = None
        address = ""
        medical_license_number = st.text_input("Medical License Number")
        speciality = st.text_input("Speciality")
        yoe = st.number_input("YOE", min_value=0, max_value=80, step=1)
        clinic_or_hospital = st.text_input("Clinic / Hospital")

    if st.button("Create account"):
        payload = {
            "role": role,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": password,
            "confirm_password": confirm_password,
            "phone_number": phone_number,
            "date_of_birth": str(date_of_birth) if date_of_birth is not None else "",
            "address": address,
            "medical_license_number": medical_license_number,
            "speciality": speciality,
            "yoe": int(yoe),
            "clinic_or_hospital": clinic_or_hospital,
        }

        def email_exists(normalized_email: str) -> bool:
            return users_collection.find_one({"email": normalized_email}) is not None

        errors = validate_registration(payload, email_exists)
        if errors:
            for error in errors:
                st.error(error)
            return

        password_hash = hash_password(password)
        document = {
            "role": role,
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "email": email.strip().lower(),
            "phone_number": phone_number.strip() if phone_number.strip() else None,
            "password_hash": password_hash,
        }

        if role == "Patient":
            document.update({"date_of_birth": str(date_of_birth), "address": address.strip()})
        else:
            document.update(
                {
                    "medical_license_number": medical_license_number.strip(),
                    "speciality": speciality.strip(),
                    "yoe": int(yoe),
                    "clinic_or_hospital": clinic_or_hospital.strip(),
                }
            )

        try:
            users_collection.insert_one(document)
            st.success(f"{role} account created successfully. You can now log in.")
            st.session_state["auth_mode"] = "login"
        except errors.DuplicateKeyError:
            st.error("Email must be unique.")
        except Exception as exc:  # pragma: no cover - UI safeguard only
            st.error(f"Registration failed: {exc}")


def render_auth_gate() -> None:
    """Show the landing auth screen before the app unlocks the main pages."""
    st.set_page_config(page_title="DeltaAI Health Portal", layout="wide")
    st.title("DeltaAI Health Portal")
    st.caption("Sign in to access the dashboard and disease prediction tools.")

    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"

    users_collection = get_users_collection()

    if users_collection is None:
        st.warning(
            "MongoDB is not configured yet. Add a `MONGO_URI` value to `secrets.toml` or `.streamlit/secrets.toml` before logging in or signing up."
        )
        return

    if st.session_state.auth_mode == "login":
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login"):
            user = authenticate_user(email, password, users_collection)
            if user is None:
                st.error("Invalid email or password.")
                return

            st.session_state["authenticated_user"] = user
            st.session_state["active_page"] = "Dashboard"
            st.rerun()

        st.markdown("---")
        if st.button("Register if you do not have an account"):
            st.session_state.auth_mode = "signup"
            st.rerun()
        return

    render_signup_form()
    st.markdown("---")
    if st.button("Back to Login"):
        st.session_state.auth_mode = "login"
        st.rerun()


def render() -> None:
    """Compatibility wrapper: the signup form is the app's registration flow."""
    render_signup_form()
