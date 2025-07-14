import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from modules.auth import hash_password

DB_URL = "mysql+pymysql://root:@localhost/edupointx"
engine = create_engine(DB_URL)


def show_admin_dashboard(user):
    st.header("🛠 Admin Controls")
    with engine.connect() as conn:
        # Manage Students
        st.subheader("👨‍🎓 Student List")
        students = conn.execute(
            text(
                "SELECT id, name, class_name, total_points FROM students ORDER BY class_name, name"
            )
        ).fetchall()
        st.dataframe(pd.DataFrame(students, columns=["ID", "Name", "Class", "Points"]))

        # Manage Teachers
        st.subheader("👩‍🏫 Teacher List")
        teachers = conn.execute(
            text("SELECT id, name FROM teachers ORDER BY name")
        ).fetchall()
        st.dataframe(pd.DataFrame(teachers, columns=["ID", "Name"]))

    # Reset Passwords
    st.subheader("🔑 Reset User Password")
    with engine.connect() as conn:
        usernames = conn.execute(
            text("SELECT username FROM users ORDER BY username")
        ).fetchall()
    selected_user = st.selectbox("Select user", [u[0] for u in usernames])
    new_password = st.text_input("New Password", type="password")
    if st.button("Reset Password"):
        if selected_user and new_password:
            hashed = new_password
            # hashed = hash_password(new_password)
            with engine.begin() as conn:  # Use transaction-safe block
                conn.execute(
                    text("UPDATE users SET password_hash = :pw WHERE username = :u"),
                    {"pw": hashed, "u": selected_user},
                )
            st.success("Password updated!")

    # Manage Rewards
    st.subheader("🏱 Manage Rewards")
    with engine.connect() as conn:
        rewards = conn.execute(
            text("SELECT id, name, cost, stock FROM rewards ORDER BY name")
        ).fetchall()
        rewards_df = pd.DataFrame(rewards, columns=["ID", "Item", "Cost", "Stock"])
        st.dataframe(rewards_df, use_container_width=True)

    with st.expander("Add/Edit Reward"):
        reward_id = st.number_input("Reward ID (0 to add new)", min_value=0, step=1)
        name = st.text_input("Item Name")
        cost = st.number_input("Point Cost", min_value=0)
        stock = st.number_input("Stock Quantity", min_value=0)
        desc = st.text_area("Description")
        if st.button("Save Reward"):
            with engine.begin() as conn:
                if reward_id == 0:
                    conn.execute(
                        text(
                            """
                            INSERT INTO rewards (name, cost, stock, description)
                            VALUES (:n, :c, :s, :d)
                            """
                        ),
                        {"n": name, "c": cost, "s": stock, "d": desc},
                    )
                    st.success("Reward added!")
                else:
                    conn.execute(
                        text(
                            """
                            UPDATE rewards SET name = :n, cost = :c, stock = :s, description = :d
                            WHERE id = :id
                            """
                        ),
                        {"n": name, "c": cost, "s": stock, "d": desc, "id": reward_id},
                    )
                    st.success("Reward updated!")

    with st.expander("🗑 Delete Reward"):
        reward_ids = [r[0] for r in rewards]
        delete_id = st.selectbox("Select reward to delete", reward_ids)
        if st.button("Delete Selected Reward"):
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM rewards WHERE id = :id"), {"id": delete_id}
                )
            st.success("Reward deleted!")
