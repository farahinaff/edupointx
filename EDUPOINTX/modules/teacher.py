import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import altair as alt

DB_URL = "mysql+pymysql://root:@localhost/edupointx"
engine = create_engine(DB_URL)


def show_teacher_dashboard(user, is_admin=False):
    teacher_id = user["teacher_id"] if not is_admin else None
    st.header("📊 Teacher Dashboard")

    with engine.connect() as conn:
        # Load classes that this teacher teaches
        if is_admin:
            classes = conn.execute(
                text("SELECT DISTINCT class_name FROM students")
            ).fetchall()
        else:
            classes = conn.execute(
                text(
                    """
                SELECT DISTINCT s.class_name FROM students s
                JOIN activities a ON s.id = a.student_id
                WHERE a.teacher_id = :tid
            """
                ),
                {"tid": teacher_id},
            ).fetchall()

        class_list = [c[0] for c in classes]

        selected_class = st.selectbox("Select a Class", class_list)

        # Display student points for the selected class
        st.subheader(f"Students in {selected_class}")
        students = conn.execute(
            text(
                """
            SELECT name, total_points FROM students
            WHERE class_name = :cname ORDER BY total_points DESC
        """
            ),
            {"cname": selected_class},
        ).fetchall()

        st.dataframe(
            pd.DataFrame(students, columns=["Name", "Points"]), use_container_width=True
        )

        # Top 3 deeds/categories for the class
        st.subheader("🔥 Top 3 Deed Categories in Class")
        top_categories = conn.execute(
            text(
                """
            SELECT category, COUNT(*) AS count FROM activities a
            JOIN students s ON a.student_id = s.id
            WHERE s.class_name = :cname
            GROUP BY category ORDER BY count DESC LIMIT 3
        """
            ),
            {"cname": selected_class},
        ).fetchall()

        st.table(pd.DataFrame(top_categories, columns=["Category", "Count"]))

        # Top 3 students by points in the class
        st.subheader("🏅 Top 3 Students in Class")
        top_students = conn.execute(
            text(
                """
            SELECT id, name, total_points FROM students
            WHERE class_name = :cname
            ORDER BY total_points DESC LIMIT 3
        """
            ),
            {"cname": selected_class},
        ).fetchall()

        for stu_id, stu_name, stu_points in top_students:
            st.markdown(f"### {stu_name} – {stu_points} pts")
            st.markdown("Top 3 Deed Categories:")
            deeds = conn.execute(
                text(
                    """
                SELECT category, COUNT(*) AS count FROM activities
                WHERE student_id = :sid
                GROUP BY category ORDER BY count DESC LIMIT 3
            """
                ),
                {"sid": stu_id},
            ).fetchall()
            st.table(pd.DataFrame(deeds, columns=["Category", "Count"]))
