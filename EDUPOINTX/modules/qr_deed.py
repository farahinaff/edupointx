# modules/qr_deed.py
import streamlit as st
from sqlalchemy import create_engine, text
from modules.db import DB_URL
from datetime import datetime

engine = create_engine(DB_URL)


def show_qr_deed_submission(student_id):
    st.title("➕ Add Points to Student")

    with engine.connect() as conn:
        student = conn.execute(
            text("SELECT id, name, class_name FROM students WHERE id = :sid"),
            {"sid": student_id},
        ).fetchone()

        if not student:
            st.error("❌ Student not found.")
            return

        st.success(f"Student: {student.name} (Class: {student.class_name})")

        teacher_username = st.text_input("Enter Your Username (Teacher)")
        teacher_password = st.text_input("Password", type="password")
        from modules.auth import login_user

        auth_user = login_user(teacher_username, teacher_password)

        if not auth_user or auth_user.get("role") != "teacher":
            st.warning("Please login as teacher to proceed.")
            return

        with st.form("deed_form"):
            category = st.selectbox(
                "Category", ["Discipline", "Academics", "Sports", "Leadership", "Other"]
            )
            reason = st.text_input("Reason")
            points = st.number_input("Points", min_value=1, max_value=100)
            submitted = st.form_submit_button("✅ Add Deed")

        if submitted:
            try:
                with engine.begin() as tx:
                    tx.execute(
                        text(
                            """
                            INSERT INTO activities (student_id, teacher_id, category, reason, points, created_at)
                            VALUES (:sid, :tid, :cat, :reason, :pts, :ts)
                        """
                        ),
                        {
                            "sid": student_id,
                            "tid": auth_user["teacher_id"],
                            "cat": category,
                            "reason": reason,
                            "pts": points,
                            "ts": datetime.now(),
                        },
                    )
                    tx.execute(
                        text(
                            "UPDATE students SET total_points = total_points + :pts WHERE id = :sid"
                        ),
                        {"pts": points, "sid": student_id},
                    )
                st.success(f"{points} points added to {student.name} for {category}.")
            except Exception as e:
                st.error(f"Error: {e}")
