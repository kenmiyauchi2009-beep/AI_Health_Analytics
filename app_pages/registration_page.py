from __future__ import annotations

import os
from datetime import date, datetime
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


def normalize_registration_role(role_value: str | None, *, doctor_fields: dict | None = None) -> str:
    """Normalize the selected registration role before storing it in MongoDB."""
    if doctor_fields and any(
        str(doctor_fields.get(field) or "").strip()
        for field in ("medical_license_number", "speciality", "clinic_or_hospital")
    ):
        return "Doctor"

    role_text = str(role_value or "").strip()
    normalized = role_text.lower()

    if normalized in {"doctor", "dr", "physician", "clinician", "medical_doctor"}:
        return "Doctor"
    if normalized in {"patient", "user", "member"}:
        return "Patient"

    return "Patient"


def validate_registration(form_data: dict, email_exists) -> list[str]:
    """Return validation errors for the user registration form."""
    errors: list[str] = []
    role = normalize_registration_role(form_data.get("role"), doctor_fields={
        "medical_license_number": form_data.get("medical_license_number"),
        "speciality": form_data.get("speciality"),
        "clinic_or_hospital": form_data.get("clinic_or_hospital"),
    })

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
        degree = str(form_data.get("degree") or "").strip()
        clinic_or_hospital = str(form_data.get("clinic_or_hospital") or "").strip()
        if not medical_license_number:
            errors.append("Medical License Number is required.")
        if not speciality:
            errors.append("Speciality is required.")
        if not degree:
            errors.append("Degree is required.")
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


def get_requests_collection():
    """Create the MongoDB collection that stores patient-to-doctor access requests."""
    users_collection = get_users_collection()
    if users_collection is None:
        return None

    requests_collection = users_collection.database["doctor_requests"]
    requests_collection.create_index([("doctor_email", 1), ("status", 1)])
    requests_collection.create_index([("patient_email", 1), ("created_at", -1)])
    return requests_collection


def get_analyses_collection():
    """Create the MongoDB collection that stores patients' saved disease predictions."""
    users_collection = get_users_collection()
    if users_collection is None:
        return None

    analyses_collection = users_collection.database["patient_analyses"]
    analyses_collection.create_index([("patient_email", 1), ("created_at", -1)])
    return analyses_collection


def get_doctor_notes_collection():
    """Create the MongoDB collection that stores doctors' notes about their patients."""
    users_collection = get_users_collection()
    if users_collection is None:
        return None

    notes_collection = users_collection.database["doctor_notes"]
    notes_collection.create_index([("patient_id", 1), ("created_at", -1)])
    notes_collection.create_index([("doctor_email", 1), ("created_at", -1)])
    return notes_collection


def get_prescriptions_collection():
    """Create the MongoDB collection that stores simulated prescriptions."""
    users_collection = get_users_collection()
    if users_collection is None:
        return None

    prescriptions_collection = users_collection.database["prescriptions"]
    prescriptions_collection.create_index("prescription_id", unique=True)
    prescriptions_collection.create_index([("patient_email", 1), ("created_at", -1)])
    return prescriptions_collection


def get_availability_collection():
    """Create the MongoDB collection that stores each doctor's working hours and blocked periods."""
    users_collection = get_users_collection()
    if users_collection is None:
        return None

    availability_collection = users_collection.database["doctor_availability"]
    availability_collection.create_index("doctor_email", unique=True)
    return availability_collection


def get_appointments_collection():
    """Create the MongoDB collection that stores patient-doctor appointments."""
    users_collection = get_users_collection()
    if users_collection is None:
        return None

    appointments_collection = users_collection.database["appointments"]
    appointments_collection.create_index([("doctor_email", 1), ("status", 1), ("start_at", 1)])
    appointments_collection.create_index([("patient_email", 1), ("start_at", -1)])
    return appointments_collection


def create_patient_doctor_request(patient_user: dict | None, doctor_email: str, note: str = "") -> dict | None:
    """Persist a real patient request against a doctor in MongoDB."""
    if not isinstance(patient_user, dict):
        return None

    collection = get_requests_collection()
    if collection is None:
        return None

    normalized_patient_email = str(patient_user.get("email") or "").strip().lower()
    normalized_doctor_email = str(doctor_email or "").strip().lower()
    if not normalized_patient_email or not normalized_doctor_email:
        return None

    if collection.find_one({
        "patient_email": normalized_patient_email,
        "doctor_email": normalized_doctor_email,
        "status": {"$in": ["pending", "accepted"]},
    }):
        return None

    patient_name = (
        f"{str(patient_user.get('first_name') or '').strip()} {str(patient_user.get('last_name') or '').strip()}"
    ).strip() or normalized_patient_email

    request = {
        "patient_email": normalized_patient_email,
        "patient_name": patient_name,
        "doctor_email": normalized_doctor_email,
        "note": (note or "").strip(),
        "status": "pending",
        "created_at": datetime.utcnow(),
    }
    result = collection.insert_one(request)
    request["_id"] = result.inserted_id
    return request


def get_pending_doctor_requests(doctor_email: str) -> list[dict]:
    """Return pending requests for a specific doctor."""
    collection = get_requests_collection()
    normalized_doctor_email = str(doctor_email or "").strip().lower()
    if collection is None or not normalized_doctor_email:
        return []
    return list(collection.find({"doctor_email": normalized_doctor_email, "status": "pending"}).sort("created_at", -1))


def get_accepted_doctor_requests(doctor_email: str) -> list[dict]:
    """Return accepted patient connections for a specific doctor."""
    collection = get_requests_collection()
    normalized_doctor_email = str(doctor_email or "").strip().lower()
    if collection is None or not normalized_doctor_email:
        return []
    return list(collection.find({"doctor_email": normalized_doctor_email, "status": "accepted"}).sort("created_at", -1))


def update_doctor_request_status(request_id, status: str) -> bool:
    """Set the status for a patient request."""
    collection = get_requests_collection()
    if collection is None or status not in {"pending", "accepted", "declined"}:
        return False
    result = collection.update_one({"_id": request_id}, {"$set": {"status": status, "updated_at": datetime.utcnow()}})
    return result.matched_count > 0


def normalize_user_record(user: dict | None) -> dict | None:
    """Ensure every authenticated record has a normalized role string for routing and UI checks."""
    if not isinstance(user, dict):
        return user

    role_value = str(user.get("role") or user.get("user_type") or "").strip()
    role_key = role_value.lower()
    has_doctor_fields = bool(
        user.get("speciality") or user.get("medical_license_number") or user.get("clinic_or_hospital")
    )

    if role_key in {"doctor", "dr", "physician", "clinician", "medical_doctor"} or has_doctor_fields:
        normalized_role = "Doctor"
    elif role_key in {"patient", "user", "member"}:
        normalized_role = "Patient"
    elif role_value:
        normalized_role = role_value.capitalize()
    else:
        normalized_role = "Patient"

    user["role"] = normalized_role
    return user


def reconcile_user_role_in_db(users_collection, user: dict | None) -> dict | None:
    """Persist a corrected role back to the database when a document was created with the wrong role."""
    if users_collection is None or not isinstance(user, dict):
        return user

    normalized_user = normalize_user_record(dict(user))
    if not normalized_user:
        return user

    current_role = str(user.get("role") or "").strip()
    if current_role != normalized_user.get("role") and hasattr(users_collection, "update_one"):
        users_collection.update_one({"_id": user.get("_id")}, {"$set": {"role": normalized_user["role"]}})

    return normalized_user


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
            return reconcile_user_role_in_db(users_collection, user)
    except (TypeError, ValueError):
        return None

    return None


def get_registration_wizard_state() -> dict[str, str]:
    """Return the active registration wizard step and selected role."""
    step = st.session_state.get("registration_step", "role")
    role = st.session_state.get("registration_role", "Patient")
    if step not in {"role", "details"}:
        step = "role"
    return {"step": step, "role": role}


def _create_account(users_collection, role: str, fields: dict) -> list[str]:
    """Validate and insert a new user. Returns problems to show; empty means the account was created."""
    selected_role = normalize_registration_role(
        role,
        doctor_fields={key: fields.get(key, "") for key in ("medical_license_number", "speciality", "clinic_or_hospital")},
    )
    date_of_birth = fields.get("date_of_birth")
    payload = {
        **fields,
        "role": selected_role,
        "date_of_birth": str(date_of_birth) if date_of_birth is not None else "",
        "yoe": int(fields.get("yoe") or 0),
    }

    def email_exists(normalized_email: str) -> bool:
        return users_collection.find_one({"email": normalized_email}) is not None

    problems = validate_registration(payload, email_exists)
    if problems:
        return problems

    document = {
        "role": selected_role,
        "first_name": payload["first_name"].strip(),
        "last_name": payload["last_name"].strip(),
        "email": payload["email"].strip().lower(),
        "phone_number": payload["phone_number"].strip() or None,
        "password_hash": hash_password(payload["password"]),
    }
    if selected_role == "Patient":
        document.update(
            {
                "date_of_birth": str(date_of_birth),
                "address": payload["address"].strip(),
                "known_conditions": [item.strip() for item in payload["known_conditions"].split(",") if item.strip()],
            }
        )
    else:
        document.update(
            {
                "medical_license_number": payload["medical_license_number"].strip(),
                "speciality": payload["speciality"].strip(),
                "degree": payload["degree"].strip(),
                "yoe": payload["yoe"],
                "clinic_or_hospital": payload["clinic_or_hospital"].strip(),
            }
        )

    try:
        users_collection.insert_one(document)
    except errors.DuplicateKeyError:
        return ["An account with this email already exists. Sign in instead."]
    except Exception as exc:  # pragma: no cover - UI safeguard only
        return [f"Your account couldn't be created: {exc}"]
    return []


def render_signup_form() -> None:
    """Two-step sign-up: choose patient or doctor, then fill in the details for that account type."""
    from ui.components import form_section, show_errors

    if "registration_step" not in st.session_state:
        st.session_state.registration_step = "role"
    if "registration_role" not in st.session_state:
        st.session_state.registration_role = "Patient"

    users_collection = get_users_collection()
    if users_collection is None:
        st.warning("Sign-up is unavailable: the database isn't configured. Add `MONGO_URI` to "
                   "`.streamlit/secrets.toml`.", icon=":material/database:")
        return

    state = get_registration_wizard_state()
    role = state["role"]

    if state["step"] == "role":
        st.subheader("Create your account", anchor=False)
        st.markdown(":gray[Step 1 of 2: choose your account type]")
        # A separate widget key: Streamlit drops widget-owned keys once the widget stops
        # rendering, which would reset "registration_role" on the details step.
        choice = st.segmented_control(
            "I'm signing up as",
            ["Patient", "Doctor"],
            default=normalize_registration_role(role),
            key="registration_role_choice",
            width="stretch",
        )
        st.caption("Doctors can accept patients, manage appointments and write simulated prescriptions. "
                   "Patients can run health analyses, book appointments and view prescriptions.")
        if st.button("Continue", type="primary", width="stretch", disabled=choice is None,
                     icon=":material/arrow_forward:", icon_position="right"):
            st.session_state.registration_role = normalize_registration_role(choice)
            st.session_state.registration_step = "details"
            st.rerun()
        return

    st.subheader(f"Create your {role.lower()} account", anchor=False)
    st.markdown(":gray[Step 2 of 2: your details]")
    fields: dict = {}
    with form_section("Your details", key="signup-you"):
        first_col, last_col = st.columns(2)
        fields["first_name"] = first_col.text_input("First name")
        fields["last_name"] = last_col.text_input("Last name")
        fields["email"] = st.text_input("Email")
        fields["phone_number"] = st.text_input("Phone number (optional)")
    with form_section("Password", key="signup-password"):
        password_col, confirm_col = st.columns(2)
        fields["password"] = password_col.text_input("Password", type="password")
        fields["confirm_password"] = confirm_col.text_input("Confirm password", type="password")

    if normalize_registration_role(role) == "Patient":
        with form_section("Health details", "Shared with the doctor you connect with", key="signup-health"):
            fields["date_of_birth"] = st.date_input("Date of birth", value=None, min_value=date(1900, 1, 1),
                                                    max_value=date.today(), format="YYYY-MM-DD")
            fields["address"] = st.text_area("Address", height=80)
            fields["known_conditions"] = st.text_input("Known conditions (optional)",
                                                       placeholder="Comma-separated, e.g. Asthma, Type 2 diabetes")
        fields.update(medical_license_number="", speciality="", degree="", yoe=0, clinic_or_hospital="")
    else:
        with form_section("Professional details", "Shown to patients choosing a doctor", key="signup-professional"):
            fields["medical_license_number"] = st.text_input("Medical license number")
            speciality_col, degree_col = st.columns(2)
            fields["speciality"] = speciality_col.text_input("Speciality")
            fields["degree"] = degree_col.text_input("Degree", placeholder="e.g. MBBS, MD")
            years_col, clinic_col = st.columns([1, 2])
            fields["yoe"] = years_col.number_input("Years of experience", min_value=0, max_value=80, step=1)
            fields["clinic_or_hospital"] = clinic_col.text_input("Clinic or hospital")
        fields.update(date_of_birth=None, address="", known_conditions="")

    back_col, submit_col = st.columns([1, 2])
    if back_col.button("Back", icon=":material/arrow_back:", width="stretch"):
        st.session_state.registration_step = "role"
        st.rerun()
    if submit_col.button("Create account", type="primary", width="stretch"):
        problems = _create_account(users_collection, st.session_state.get("registration_role") or role, fields)
        if not show_errors(problems):
            st.session_state["auth_mode"] = "login"
            st.session_state.registration_step = "role"
            st.session_state.registration_role = "Patient"
            st.session_state["auth_flash"] = "Your account is ready. Sign in to continue."
            st.rerun()


def render_auth_gate() -> None:
    """Sign-in and sign-up screen shown before anything else."""
    _, center, _ = st.columns([1, 1.6, 1])
    with center:
        st.image("assets/logo.svg", width=200)
        if "auth_mode" not in st.session_state:
            st.session_state.auth_mode = "login"

        users_collection = get_users_collection()
        if users_collection is None:
            st.warning("Sign-in is unavailable: the database isn't configured. Add `MONGO_URI` to "
                       "`.streamlit/secrets.toml`.", icon=":material/database:")
            return

        if st.session_state.auth_mode != "login":
            render_signup_form()
            st.divider()
            with st.container(horizontal=True, horizontal_alignment="center", vertical_alignment="center"):
                st.markdown(":gray[Already have an account?]", width="content")
                if st.button("Sign in", type="tertiary", key="to_login"):
                    st.session_state.auth_mode = "login"
                    st.rerun()
            return

        st.title("Sign in", anchor=False)
        st.markdown(":gray[Health analyses, appointments and prescriptions in one place]")
        message = st.session_state.pop("auth_flash", None)
        if message:
            st.success(message, icon=":material/check_circle:")
        with st.form("login_form", border=False):
            email = st.text_input("Email", key="login_email", autocomplete="email")
            password = st.text_input("Password", type="password", key="login_password",
                                     autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
        if submitted:
            user = authenticate_user(email, password, users_collection)
            if user is None:
                st.error("That email and password don't match an account. Check them and try again.",
                         icon=":material/error:")
            else:
                st.session_state["authenticated_user"] = normalize_user_record(user)
                st.rerun()

        st.divider()
        with st.container(horizontal=True, horizontal_alignment="center", vertical_alignment="center"):
            st.markdown(":gray[New to DeltaAI Health?]", width="content")
            if st.button("Create an account", type="tertiary", key="to_signup"):
                st.session_state.auth_mode = "signup"
                st.rerun()


def render() -> None:
    """Compatibility wrapper: the signup form is the app's registration flow."""
    render_signup_form()
