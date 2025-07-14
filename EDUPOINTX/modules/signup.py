# modules/signup.py
import streamlit as st
from sqlalchemy import create_engine, text
from .auth import hash_password

DB_URL = "mysql+pymysql://root:@localhost/edupointx"
engine = create_engine(DB_URL)


def show_signup_form():
    st.header("📝 Create New Account")
    success = False

    with engine.connect() as conn:
        class_names = conn.execute(
            text("SELECT DISTINCT class_name FROM students ORDER BY class_name")
        ).fetchall()
        class_options = [c[0] for c in class_names]

    with st.form("signup_form"):
        username = st.text_input("Username")
        full_name = st.text_input("Full Name")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        role = st.selectbox("Select Role", ["student", "teacher"])
        selected_class = (
            st.selectbox("Select Class", class_options) if role == "student" else None
        )
        submitted = st.form_submit_button("Create Account")

    if submitted:
        st.write("Form submitted.")
        if not username or not password or not full_name:
            st.warning("Please fill in all required fields.")
        elif password != confirm:
            st.error("Passwords do not match.")
        else:
            st.write("Proceeding with DB operations...")
            # hashed = hash_password(password)
            hashed = password
            try:
                with engine.begin() as conn:
                    result = conn.execute(
                        text("SELECT COUNT(*) FROM users WHERE username = :u"),
                        {"u": username},
                    ).scalar()
                    st.write(f"User count with this username: {result}")
                    if result > 0:
                        st.error("Username already exists.")
                        return

                    student_id = None
                    teacher_id = None

                    if role == "student":
                        st.write(f"Inserting student: {full_name} ({selected_class})")
                        conn.execute(
                            text(
                                "INSERT INTO students (name, class_name, total_points) VALUES (:n, :c, 0)"
                            ),
                            {"n": full_name, "c": selected_class},
                        )
                        student_id = conn.execute(
                            text("SELECT LAST_INSERT_ID()")
                        ).scalar()
                        st.write(f"Fetched student_id: {student_id}")

                    elif role == "teacher":
                        st.write(f"Inserting teacher: {full_name}")
                        conn.execute(
                            text("INSERT INTO teachers (name) VALUES (:n)"),
                            {"n": full_name},
                        )
                        teacher_id = conn.execute(
                            text("SELECT LAST_INSERT_ID()")
                        ).scalar()
                        st.write(f"Fetched teacher_id: {teacher_id}")

                    if role == "student" and not student_id:
                        st.error("Could not fetch student_id. Check DB constraints.")
                        return
                    if role == "teacher" and not teacher_id:
                        st.error("Could not fetch teacher_id. Check DB constraints.")
                        return

                    st.write("Inserting into users...")
                    conn.execute(
                        text(
                            """
                            INSERT INTO users (username, password_hash, role, student_id, teacher_id)
                            VALUES (:u, :p, :r, :sid, :tid)
                        """
                        ),
                        {
                            "u": username,
                            "p": hashed,
                            "r": role,
                            "sid": student_id,
                            "tid": teacher_id,
                        },
                    )
                    st.success("Account created successfully!")
                    success = True
            except Exception as e:
                st.error(f"Signup failed: {str(e)}")
                success = False

    if success:
        st.session_state.page = "login"
        st.rerun()

    if st.button("Back to Login"):
        st.session_state.page = "login"
        st.rerun()
