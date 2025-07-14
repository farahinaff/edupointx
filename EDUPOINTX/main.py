# main.py
import streamlit as st
from modules.auth import login_user
from modules.student import show_student_dashboard
from modules.teacher import show_teacher_dashboard
from modules.admin import show_admin_dashboard
from modules.signup import show_signup_form

st.set_page_config(page_title="EduPointX", layout="wide")
st.title("EduPointX – School Points & Redemption System")

# Initialize session state
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "login"

# --- SIGNUP FORM ---
if st.session_state.page == "signup":
    show_signup_form()
    st.stop()

# --- LOGIN FORM ---
if not st.session_state.user:
    with st.form("login_form"):
        st.subheader("🔐 Login to EduPointX")
        username = st.text_input(
            "Username", help="Students, Teachers, and Admins share this portal"
        )
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            user = login_user(username, password)
            if user:
                st.session_state.user = user
                st.success(f"Welcome, {user['username']}!")
                st.rerun()
            else:
                st.error("Invalid username or password.")

    if st.button("Sign Up"):
        st.session_state.page = "signup"
        st.rerun()

# --- DASHBOARD ROUTING ---
else:
    user = st.session_state.user

    if user and "role" in user:
        role = user["role"].strip().lower()
        st.sidebar.success(f"Logged in as: {user['username']} ({role})")

        if role == "student":
            show_student_dashboard(user)

        elif role == "teacher":
            show_teacher_dashboard(user, is_admin=False)

        elif role == "admin":
            show_teacher_dashboard(user, is_admin=True)
            show_admin_dashboard(user)

        else:
            st.error("Unauthorized role. Please contact administrator.")
            st.session_state.user = None
            st.rerun()
    else:
        st.error("Session error: Role missing or user invalid.")
        st.session_state.user = None
        st.rerun()

    # --- LOGOUT BUTTON ---
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.session_state.page = "login"
        st.rerun()
