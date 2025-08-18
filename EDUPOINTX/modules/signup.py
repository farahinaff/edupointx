import streamlit as st
from sqlalchemy import create_engine, text

from modules.db import engine


def show_signup_form():
    role = st.session_state.get("signup_role")

    if not role:
        st.error("No role selected. Please go back to the welcome screen.")
        return

    # --- Title ---
    st.markdown(
        f"<h3 style='text-align:center;'>📝 Sign Up as {role.title()}</h3>",
        unsafe_allow_html=True,
    )
    success = False

    # Pull class list for students
    with engine.connect() as conn:
        class_names = conn.execute(
            text("SELECT DISTINCT class_name FROM students ORDER BY class_name")
        ).fetchall()
        class_options = [c[0] for c in class_names]

    with st.form("signup_form"):
        # --- User info ---
        username = st.text_input("👤 Username")
        full_name = st.text_input("🧑 Full Name")

        # --- Gender (icon-only, horizontal) ---
        st.markdown("**Gender**")
        gender = st.radio(
            label="Gender",
            options=["male", "female"],
            format_func=lambda x: "♂️" if x == "male" else "♀️",
            horizontal=True,
            label_visibility="collapsed",  # hide the label text
        )

        password = st.text_input("🔑 Password", type="password")
        confirm = st.text_input("🔑 Confirm Password", type="password")

        # Only show class selector for student
        selected_class = None
        if role == "student":
            selected_class = st.selectbox("🏫 Select Class", class_options)

        submitted = st.form_submit_button("✅ Create Account", use_container_width=True)

    if submitted:
        if not username or not password or not full_name:
            st.warning("Please fill in all required fields.")
        elif password != confirm:
            st.error("Passwords do not match.")
        elif gender not in ("male", "female"):
            st.error("Please select a gender.")
        else:
            try:
                with engine.begin() as conn:
                    # Check username exists
                    result = conn.execute(
                        text("SELECT COUNT(*) FROM users WHERE username = :u"),
                        {"u": username},
                    ).scalar()
                    if result > 0:
                        st.error("Username already exists.")
                        return

                    student_id = None
                    teacher_id = None

                    if role == "student":
                        conn.execute(
                            text(
                                """
                                INSERT INTO students (name, class_name, gender, total_points)
                                VALUES (:n, :c, :g, 0)
                                """
                            ),
                            {"n": full_name, "c": selected_class, "g": gender},
                        )
                        student_id = conn.execute(
                            text("SELECT LAST_INSERT_ID()")
                        ).scalar()

                    elif role == "teacher":
                        conn.execute(
                            text("INSERT INTO teachers (name, gender) VALUES (:n, :g)"),
                            {"n": full_name, "g": gender},
                        )
                        teacher_id = conn.execute(
                            text("SELECT LAST_INSERT_ID()")
                        ).scalar()

                    # Save user account (⚠️ consider hashing password)
                    # hashed = hash_password(password)
                    conn.execute(
                        text(
                            """
                            INSERT INTO users (username, password_hash, role, student_id, teacher_id)
                            VALUES (:u, :p, :r, :sid, :tid)
                            """
                        ),
                        {
                            "u": username,
                            "p": password,  # replace with hashed if using hash_password
                            "r": role,
                            "sid": student_id,
                            "tid": teacher_id,
                        },
                    )

                    st.success("🎉 Account created successfully!")
                    success = True

            except Exception as e:
                st.error(f"Signup failed: {str(e)}")
                success = False

    if success:
        st.session_state.page = (
            "login_student" if role == "student" else "login_teacher"
        )
        st.session_state.signup_role = None
        st.rerun()

    # Back button (full width on mobile)
    st.button("⬅ Back", use_container_width=True, on_click=lambda: _go_back())


def _go_back():
    st.session_state.page = "select_role_signup"
    st.rerun()
