import streamlit as st
import pandas as pd
import altair as alt
from sqlalchemy import create_engine, text
from datetime import datetime
import time
from modules.db import DB_URL


engine = create_engine(DB_URL)


def show_teacher_dashboard(user, is_admin=False):
    teacher_id = user.get("teacher_id")
    st.header("📊 Teacher Dashboard" if not is_admin else "📊 Admin View: Class Deeds")

    with engine.connect() as conn:
        # --- 1. Load Class List ---
        if is_admin:
            classes = conn.execute(
                text("SELECT DISTINCT class_name FROM students ORDER BY class_name")
            ).fetchall()
        else:
            classes = conn.execute(
                text(
                    "SELECT class_name FROM teacher_class WHERE teacher_id = :tid ORDER BY class_name"
                ),
                {"tid": teacher_id},
            ).fetchall()

        class_list = [c[0] for c in classes]
        selected_class = st.selectbox(
            "🎓 Select Class", ["Please select..."] + class_list
        )

        if selected_class == "Please select...":
            st.info("Please select a class to view and manage data.")
            return

        # --- 2. Load Students in Selected Class ---
        students = conn.execute(
            text("SELECT id, name FROM students WHERE class_name = :cls ORDER BY name"),
            {"cls": selected_class},
        ).fetchall()
        student_map = {name: sid for sid, name in students}
        if not student_map:
            st.info("No students found in this class.")
            return

        # --- 3. Add Student Deed Form (Auto-clear) ---
        st.subheader("📝 Add Student Deed")
        form_key = f"form_{int(time.time())}"  # forces refresh after submit

        with st.form(form_key):
            selected_student_name = st.selectbox(
                "Select Student", list(student_map.keys())
            )
            deed_category = st.selectbox(
                "Deed Category",
                ["Discipline", "Academics", "Sports", "Leadership", "Other"],
            )
            deed_reason = st.text_input("Reason / Description")
            deed_points = st.number_input(
                "Point Reward", min_value=1, max_value=100, step=1
            )
            submitted = st.form_submit_button("✅ Submit")

        if submitted:
            student_id = student_map[selected_student_name]
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
                            "tid": teacher_id,
                            "cat": deed_category,
                            "reason": deed_reason,
                            "pts": deed_points,
                            "ts": datetime.now(),
                        },
                    )
                    tx.execute(
                        text(
                            "UPDATE students SET total_points = total_points + :pts WHERE id = :sid"
                        ),
                        {"pts": deed_points, "sid": student_id},
                    )
                st.success(
                    f"{deed_points} points added to {selected_student_name} for '{deed_category}'"
                )
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error adding deed: {e}")

        # --- 4. Class Insights (Bar Chart) ---
        st.subheader("📊 Class Performance Insights")

        student_points = conn.execute(
            text(
                "SELECT name, total_points FROM students WHERE class_name = :cls ORDER BY total_points DESC"
            ),
            {"cls": selected_class},
        ).fetchall()

        df_points = pd.DataFrame(student_points, columns=["Name", "Points"])
        if not df_points.empty:
            st.markdown("**Total Points by Student**")
            chart = (
                alt.Chart(df_points)
                .mark_bar()
                .encode(x=alt.X("Name", sort="-y"), y="Points")
                .properties(height=300)
            )
            st.altair_chart(chart, use_container_width=True)

        # --- 5. Category Distribution (Pie Chart) ---
        category_data = conn.execute(
            text(
                """
                SELECT category, COUNT(*) as count
                FROM activities a
                JOIN students s ON a.student_id = s.id
                WHERE s.class_name = :cls
                GROUP BY category
            """
            ),
            {"cls": selected_class},
        ).fetchall()

        if category_data:
            cat_df = pd.DataFrame(category_data, columns=["Category", "Count"])
            st.markdown("**Deed Category Distribution**")
            pie = (
                alt.Chart(cat_df)
                .mark_arc()
                .encode(theta="Count", color="Category", tooltip=["Category", "Count"])
                .properties(width=400)
            )
            st.altair_chart(pie, use_container_width=True)

        # --- 6. Top 3 Deed Categories ---
        st.subheader("🔥 Top 3 Deed Categories")
        top_categories = conn.execute(
            text(
                """
                SELECT category, COUNT(*) as count
                FROM activities a
                JOIN students s ON a.student_id = s.id
                WHERE s.class_name = :cls
                GROUP BY category
                ORDER BY count DESC
                LIMIT 3
            """
            ),
            {"cls": selected_class},
        ).fetchall()
        st.table(pd.DataFrame(top_categories, columns=["Category", "Count"]))

        # --- 7. Top 3 Students + Their Top Categories ---
        st.subheader("🏅 Top 3 Students & Their Top Deeds")
        top_students = conn.execute(
            text(
                """
                SELECT id, name, total_points
                FROM students
                WHERE class_name = :cls
                ORDER BY total_points DESC
                LIMIT 3
            """
            ),
            {"cls": selected_class},
        ).fetchall()

        for sid, sname, pts in top_students:
            st.markdown(f"### 🧑‍🎓 {sname} – {pts} pts")
            deeds = conn.execute(
                text(
                    """
                    SELECT category, COUNT(*) as count
                    FROM activities
                    WHERE student_id = :sid
                    GROUP BY category
                    ORDER BY count DESC
                    LIMIT 3
                """
                ),
                {"sid": sid},
            ).fetchall()
            st.table(pd.DataFrame(deeds, columns=["Category", "Count"]))
