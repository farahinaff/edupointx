# modules/qr_redeem.py
import streamlit as st
from sqlalchemy import text
from datetime import datetime
from modules.db import engine


def show_qr_redemption(sid):
    st.markdown("## 🧾 Student Reward Redemption")

    try:
        sid = int(sid)
    except:
        st.error("Invalid QR link.")
        return

    with engine.connect() as conn:
        student = conn.execute(
            text("SELECT id, name, total_points FROM students WHERE id = :id"),
            {"id": sid},
        ).fetchone()

        if not student:
            st.error("Student not found.")
            return

        st.subheader(f"🎓 {student.name} – {student.total_points} pts")

        rewards = conn.execute(
            text(
                "SELECT id, name, cost, stock FROM rewards WHERE stock > 0 ORDER BY cost"
            )
        ).fetchall()

        if not rewards:
            st.info("No rewards available right now.")
            return

        st.info(
            "Select an item to request redemption. Your request will be sent to admin for approval."
        )

        for reward_id, name, cost, stock in rewards:
            with st.form(key=f"form_{reward_id}"):
                st.write(f"🎁 {name} – **{cost} pts** (Stock: {stock})")
                submit = st.form_submit_button("Request Redemption")

                if submit:
                    try:
                        with engine.begin() as tx:
                            # Create redemption record as PENDING (do NOT deduct yet)
                            tx.execute(
                                text(
                                    """
                                    INSERT INTO redemptions (student_id, reward_id, status, created_at)
                                    VALUES (:sid, :rid, 'pending', :ts)
                                    """
                                ),
                                {"sid": sid, "rid": reward_id, "ts": datetime.now()},
                            )
                        st.success(
                            f"Request submitted for '{name}'. An admin will review it shortly."
                        )
                        st.rerun()
                    except Exception as e:
                        st.error("Something went wrong submitting your request.")
                        st.code(str(e))
