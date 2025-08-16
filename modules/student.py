import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import altair as alt

from modules.db import DB_URL

engine = create_engine(DB_URL)


def show_student_dashboard(user):
    student_id = user["student_id"]

    st.header("🎓 Student Dashboard")
    col1, col2 = st.columns(2)

    with engine.connect() as conn:
        # Fetch current point balance
        student = conn.execute(
            text("SELECT name, class_name, total_points FROM students WHERE id = :id"),
            {"id": student_id},
        ).fetchone()
        if not student:
            st.error("Student not found.")
            return

        with col1:
            st.metric("Total Points", student.total_points)
            st.markdown(
                f"*Name:* {student.name}<br>*Class:* {student.class_name}",
                unsafe_allow_html=True,
            )

        # List available rewards
        rewards = conn.execute(
            text(
                "SELECT name, cost, stock FROM rewards WHERE stock > 0 ORDER BY cost ASC"
            )
        ).fetchall()
        rewards_df = pd.DataFrame(rewards, columns=["Item", "Point Cost", "Stock"])
        with col2:
            st.subheader("🎁 Available Rewards")
            st.dataframe(rewards_df, use_container_width=True)

        # Show list of deeds
        st.subheader("📋 Your Activities")
        activities = conn.execute(
            text(
                """
            SELECT category, reason, points, created_at 
            FROM activities 
            WHERE student_id = :sid ORDER BY created_at DESC
        """
            ),
            {"sid": student_id},
        ).fetchall()

        deeds_df = pd.DataFrame(
            activities, columns=["Category", "Reason", "Points", "Date"]
        )
        st.dataframe(deeds_df, use_container_width=True)

        # Self trend: points per week/month
        trend_data = conn.execute(
            text(
                """
            SELECT DATE(created_at) AS date, SUM(points) AS daily_points
            FROM activities WHERE student_id = :sid
            GROUP BY DATE(created_at) ORDER BY date
        """
            ),
            {"sid": student_id},
        ).fetchall()

        if trend_data:
            trend_df = pd.DataFrame(trend_data, columns=["Date", "Points"])
            chart = (
                alt.Chart(trend_df)
                .mark_line(point=True)
                .encode(x="Date:T", y="Points:Q")
                .properties(title="📈 Weekly/Monthly Point Trend")
            )
            st.altair_chart(chart, use_container_width=True)

        # Leaderboard - top 3 in class
        st.subheader("🏆 Top 3 in Your Class")
        leaderboard = conn.execute(
            text(
                """
            SELECT name, total_points FROM students
            WHERE class_name = :class_name
            ORDER BY total_points DESC LIMIT 3
        """
            ),
            {"class_name": student.class_name},
        ).fetchall()

        top_df = pd.DataFrame(leaderboard, columns=["Student", "Points"])
        st.dataframe(top_df, use_container_width=True)
