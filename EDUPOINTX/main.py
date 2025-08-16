# main.py
import streamlit as st
from modules.auth import login_user
from modules.student import show_student_dashboard
from modules.teacher import show_teacher_dashboard
from modules.admin import show_admin_dashboard
from modules.signup import show_signup_form

# --- CONFIG ---
st.set_page_config(page_title="EduPointX", layout="wide")
st.markdown(
    "<h1 style='text-align:center;'>EduPointX - School Points & Redemption System</h1>",
    unsafe_allow_html=True,
)

# --- INIT SESSION STATE ---
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "welcome"
if "signup_role" not in st.session_state:
    st.session_state.signup_role = None

# --- 1. SIGNUP PAGE ---
if st.session_state.page == "signup":
    show_signup_form()
    st.stop()

# --- 2. WELCOME PAGE ---
if st.session_state.page == "welcome":
    st.subheader("“Do More, Earn More”")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔐 Login"):
            st.session_state.page = "select_role_login"
            st.rerun()
    with col2:
        if st.button("📝 Sign Up"):
            st.session_state.page = "select_role_signup"
            st.rerun()
    st.stop()

# --- 3. ROLE SELECTION FOR LOGIN ---
if st.session_state.page == "select_role_login":
    st.subheader("Login as...")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎓 Student"):
            st.session_state.page = "login_student"
            st.rerun()
    with col2:
        if st.button("👨‍🏫 Teacher"):
            st.session_state.page = "login_teacher"
            st.rerun()
    st.stop()

# --- 4. ROLE SELECTION FOR SIGNUP ---
if st.session_state.page == "select_role_signup":
    st.subheader("Sign Up as...")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎓 Student"):
            st.session_state.signup_role = "student"
            st.session_state.page = "signup"
            st.rerun()
    with col2:
        if st.button("👨‍🏫 Teacher"):
            st.session_state.signup_role = "teacher"
            st.session_state.page = "signup"
            st.rerun()
    if st.button("⬅ Back"):
        st.session_state.page = "welcome"
        st.rerun()
    st.stop()

# --- 5. LOGIN: STUDENT ---
if st.session_state.page == "login_student" and not st.session_state.user:
    st.subheader("🔐 Login as Student")
    with st.form("login_student_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            user = login_user(username, password)
            if user and user.get("role") == "student":
                st.session_state.user = user
                st.success(f"Welcome, {user['username']}!")
                st.rerun()
            else:
                st.error("Invalid student credentials.")

    if st.button("⬅ Back"):
        st.session_state.page = "welcome"
        st.rerun()
    st.stop()

# --- 6. LOGIN: TEACHER + ADMIN ---
if st.session_state.page == "login_teacher" and not st.session_state.user:
    st.subheader("🔐 Login as Teacher")
    with st.form("login_teacher_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            user = login_user(username, password)
            if user and user.get("role") in ["teacher", "admin"]:
                st.session_state.user = user
                st.success(f"Welcome, {user['username']}!")
                st.rerun()
            else:
                st.error("Invalid teacher/admin credentials.")

    if st.button("⬅ Back"):
        st.session_state.page = "welcome"
        st.rerun()
    st.stop()

# --- 7. DASHBOARD ROUTING ---
if st.session_state.user:
    user = st.session_state.user
    role = user.get("role", "").strip().lower()
    st.sidebar.success(f"Logged in as: {user['username']} ({role})")

    if role == "student":
        show_student_dashboard(user)
    elif role == "admin":
        show_admin_dashboard(user)  # ✅ Admin does NOT see teacher dashboard
    elif role == "teacher":
        show_teacher_dashboard(user, is_admin=False)
    else:
        st.error("Unauthorized role.")
        st.session_state.user = None
        st.session_state.page = "welcome"
        st.rerun()

    if st.sidebar.button("🚪 Logout"):
        st.session_state.user = None
        st.session_state.page = "welcome"
        st.session_state.signup_role = None
        st.rerun()
