# modules/qr_redeem.py
import streamlit as st
from sqlalchemy import text
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

        for reward_id, name, cost, stock in rewards:
            with st.form(key=f"form_{reward_id}"):
                st.write(f"🎁 {name} – {cost} pts (Stock: {stock})")
                submit = st.form_submit_button("Redeem")

                if submit:
                    if student.total_points < cost:
                        st.warning("Not enough points.")
                    else:
                        try:
                            with engine.begin() as tx:
                                # Create redemption record
                                tx.execute(
                                    text(
                                        """
                                    INSERT INTO redemptions (student_id, reward_id, status)
                                    VALUES (:sid, :rid, 'approved')
                                """
                                    ),
                                    {"sid": sid, "rid": reward_id},
                                )

                                # Deduct points
                                tx.execute(
                                    text(
                                        """
                                    UPDATE students SET total_points = total_points - :pts
                                    WHERE id = :sid
                                """
                                    ),
                                    {"pts": cost, "sid": sid},
                                )

                                # Reduce stock
                                tx.execute(
                                    text(
                                        """
                                    UPDATE rewards SET stock = stock - 1 WHERE id = :rid
                                """
                                    ),
                                    {"rid": reward_id},
                                )

                            st.success(f"Redeemed {name}!")
                            st.experimental_rerun()

                        except Exception as e:
                            st.error("Something went wrong.")
                            st.code(str(e))
