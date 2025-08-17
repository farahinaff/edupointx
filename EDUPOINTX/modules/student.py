import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import altair as alt
from modules.db import DB_URL  # assuming you use a central db.py for connection

from modules.db import DB_URL

engine = create_engine(DB_URL)


def show_student_dashboard(user):
    student_id = user["student_id"]

    st.header("🎓 Student Dashboard")

    tabs = st.tabs(
        ["🧍 Info", "🎁 Rewards", "💳 Transactions", "📋 Activities", "🏅 Leaderboard"]
    )

    with engine.connect() as conn:
        # Fetch student info
        student = conn.execute(
            text(
                "SELECT name, class_name, gender, total_points FROM students WHERE id = :id"
            ),
            {"id": student_id},
        ).fetchone()

        # Fetch rewards
        rewards = conn.execute(
            text(
                "SELECT name, cost, stock FROM rewards WHERE stock > 0 ORDER BY cost ASC"
            )
        ).fetchall()
        rewards_df = pd.DataFrame(rewards, columns=["Item", "Point Cost", "Stock"])

        # Fetch activities
        activities = conn.execute(
            text(
                """
                SELECT category, reason, points, created_at 
                FROM activities 
                WHERE student_id = :sid 
                ORDER BY created_at DESC
            """
            ),
            {"sid": student_id},
        ).fetchall()
        deeds_df = pd.DataFrame(
            activities, columns=["Category", "Reason", "Points", "Date"]
        )

        # Fetch redemptions
        redemptions = conn.execute(
            text(
                """
                SELECT r.name, rd.status, rd.created_at
                FROM redemptions rd
                JOIN rewards r ON rd.reward_id = r.id
                WHERE rd.student_id = :sid
                ORDER BY rd.created_at DESC
            """
            ),
            {"sid": student_id},
        ).fetchall()
        redemption_df = pd.DataFrame(redemptions, columns=["Reward", "Status", "Date"])

        # Leaderboard
        leaderboard = conn.execute(
            text(
                """
                SELECT name, total_points FROM students
                WHERE class_name = :cls
                ORDER BY total_points DESC
            """
            ),
            {"cls": student.class_name},
        ).fetchall()
        top_df = pd.DataFrame(leaderboard, columns=["Student", "Points"])

    # --- 🧍 INFO TAB ---
    with tabs[0]:
        st.subheader("🧍 Student Info")
        st.markdown(
            f"""
        - **Name**: {student.name}
        - **Gender**: {student.gender}
        - **Class**: {student.class_name}
        - **Total Points**: {student.total_points}
        """
        )

    # --- 🎁 REWARDS TAB ---
    with tabs[1]:
        st.subheader("🎁 Available Rewards")
        st.dataframe(rewards_df, use_container_width=True)

    # --- 💳 TRANSACTIONS TAB ---
    with tabs[2]:
        st.subheader("💳 Redemption History")
        if not redemption_df.empty:
            st.dataframe(redemption_df, use_container_width=True)
        else:
            st.info("No redemptions yet.")

    # --- 📋 ACTIVITIES TAB ---
    with tabs[3]:
        st.subheader("📋 Activity Log")
        if not deeds_df.empty:
            st.dataframe(deeds_df, use_container_width=True)

            # Chart: Trend over time
            trend_chart = (
                alt.Chart(deeds_df)
                .mark_line(point=True)
                .encode(x="Date:T", y="Points:Q", tooltip=["Date", "Points"])
                .properties(title="📈 Point Trend")
            )
            st.altair_chart(trend_chart, use_container_width=True)
        else:
            st.info("No activity records yet.")

    # --- 🏅 LEADERBOARD TAB ---
    with tabs[4]:
        st.subheader(f"🏅 Leaderboard: {student.class_name}")
        if not top_df.empty:
            st.dataframe(top_df, use_container_width=True)
        else:
            st.info("No other students in your class yet.")
