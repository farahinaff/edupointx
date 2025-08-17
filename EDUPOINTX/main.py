import streamlit as st
import base64
from modules.auth import login_user
from modules.student import show_student_dashboard
from modules.teacher import show_teacher_dashboard
from modules.admin import show_admin_dashboard
from modules.signup import show_signup_form
from modules.qr_deed import show_qr_deed_submission


# --- Helper to encode images as base64 ---
def get_base64(file_path):
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# --- Load assets (JPG) ---
bg_base64 = get_base64("assets/background_main.jpg")
kpm_base64 = get_base64("assets/kpm.jpg")
jata_base64 = get_base64("assets/jata.jpg")
smapk_base64 = get_base64("assets/edupointx_logo.jpg")

# --- CONFIG ---
st.set_page_config(page_title="EduPointX", layout="wide")

# --- CUSTOM CSS ---
st.markdown(
    f"""
    <style>
    /* Background with dark blue overlay */
    [data-testid="stAppViewContainer"] {{
        background: linear-gradient(rgba(0,0,50,0.75), rgba(0,0,50,0.75)),
                    url("data:image/jpg;base64,{bg_base64}");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
    }}

    /* Dark blue & gold theme */
    h1, h2, h3, h4, h5, h6, p, span, label {{
        color: #FFD700 !important; /* Gold */
    }}
    .stButton button {{
        background-color: #002147 !important; /* Dark navy */
        color: #FFD700 !important;
        border-radius: 10px;
        border: 1px solid #FFD700;
    }}
    .stButton button:hover {{
        background-color: #003366 !important;
        border: 1px solid #FFD700;
    }}

    /* Top corner logos */
    .top-left-logo, .top-right-logo {{
        position: absolute;
        top: 15px;
        width: 70px;
        height: auto;
        z-index: 1000; /* keep above background, below text */
    }}
    .top-left-logo {{ left: 20px; }}
    .top-right-logo {{ right: 20px; }}
    
    @media (max-width: 768px) {{
        .top-left-logo, .top-right-logo {{
            width: 50px;
            top: 60px;   /* push them lower, so they don't overlap the title */
        }}
    }}
    /* Center school logo */
    .center-logo {{
        display: block;
        margin-left: auto;
        margin-right: auto;
        margin-top: -10px;
        margin-bottom: 20px;
        width: 120px;
        height: 120px;
        border-radius: 50%;
        border: 3px solid #FFD700;
        object-fit: cover;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Place logos & title ---
st.markdown(
    f"""
    <img src="data:image/jpg;base64,{kpm_base64}" class="top-left-logo">
    <img src="data:image/jpg;base64,{jata_base64}" class="top-right-logo">
    <h1 style='text-align:center; color:#FFD700;'>EduPointX – School Points & Redemption System</h1>
    <img src="data:image/jpg;base64,{smapk_base64}" class="center-logo">
    """,
    unsafe_allow_html=True,
)

# --- QR MODE HANDLING ---
if "sid" in st.query_params and "action" in st.query_params:
    if st.query_params["action"] == "addpoints":
        show_qr_deed_submission(st.query_params["sid"])
    elif st.query_params["action"] == "redeem":
        from modules.qr_redeem import show_qr_redemption

        show_qr_redemption(st.query_params["sid"])
    st.stop()

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
    st.markdown(
        "<p style='text-align:center;'>“Do More, Earn More”</p>", unsafe_allow_html=True
    )

    if st.button("🔐 Login", use_container_width=True):
        st.session_state.page = "select_role_login"
        st.rerun()

    if st.button("📝 Sign Up", use_container_width=True):
        st.session_state.page = "select_role_signup"
        st.rerun()
    st.stop()

# --- 3. ROLE SELECTION FOR LOGIN ---
if st.session_state.page == "select_role_login":
    st.subheader("Login as...")
    if st.button("🎓 Student", use_container_width=True):
        st.session_state.page = "login_student"
        st.rerun()
    if st.button("👨‍🏫 Teacher", use_container_width=True):
        st.session_state.page = "login_teacher"
        st.rerun()
    if st.button("⬅ Back", use_container_width=True):
        st.session_state.page = "welcome"
        st.rerun()
    st.stop()

# --- 4. ROLE SELECTION FOR SIGNUP ---
if st.session_state.page == "select_role_signup":
    st.subheader("Sign Up as...")
    if st.button("🎓 Student", use_container_width=True):
        st.session_state.signup_role = "student"
        st.session_state.page = "signup"
        st.rerun()
    if st.button("👨‍🏫 Teacher", use_container_width=True):
        st.session_state.signup_role = "teacher"
        st.session_state.page = "signup"
        st.rerun()
    if st.button("⬅ Back", use_container_width=True):
        st.session_state.page = "welcome"
        st.rerun()
    st.stop()

# --- 5. LOGIN: STUDENT ---
if st.session_state.page == "login_student" and not st.session_state.user:
    st.subheader("🔐 Login as Student")
    with st.form("login_student_form"):
        username = st.text_input("👤 Username")
        password = st.text_input("🔑 Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            user = login_user(username, password)
            if user and user.get("role") == "student":
                st.session_state.user = user
                st.success(f"Welcome, {user['username']}!")
                st.rerun()
            else:
                st.error("Invalid student credentials.")

    if st.button("⬅ Back", use_container_width=True):
        st.session_state.page = "welcome"
        st.rerun()
    st.stop()

# --- 6. LOGIN: TEACHER + ADMIN ---
if st.session_state.page == "login_teacher" and not st.session_state.user:
    st.subheader("🔐 Login as Teacher")
    with st.form("login_teacher_form"):
        username = st.text_input("👤 Username")
        password = st.text_input("🔑 Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            user = login_user(username, password)
            if user and user.get("role") in ["teacher", "admin"]:
                st.session_state.user = user
                st.success(f"Welcome, {user['username']}!")
                st.rerun()
            else:
                st.error("Invalid teacher/admin credentials.")

    if st.button("⬅ Back", use_container_width=True):
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
        show_admin_dashboard(user)
    elif role == "teacher":
        show_teacher_dashboard(user, is_admin=False)
    else:
        st.error("Unauthorized role.")
        st.session_state.user = None
        st.session_state.page = "welcome"
        st.rerun()

    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.user = None
        st.session_state.page = "welcome"
        st.session_state.signup_role = None
        st.rerun()
