import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from modules.auth import hash_password
from modules.db import DB_URL

engine = create_engine(DB_URL)


def show_admin_dashboard(user):
    st.markdown("## 🛠 Admin Dashboard")

    tabs = st.tabs(
        ["📚 Class View", "👨‍🏫 Teacher Assignment", "🎁 Rewards", "🔐 Reset Password"]
    )

    with engine.connect() as conn:
        class_names = conn.execute(
            text("SELECT DISTINCT class_name FROM students ORDER BY class_name")
        ).fetchall()
        class_list = [c[0] for c in class_names]

        # --- 📚 TAB 1 ---
        with tabs[0]:
            selected_class1 = st.selectbox(
                "🎓 Select Class", class_list, key="class_tab1"
            )

            st.subheader("👥 Students in Class")
            students = conn.execute(
                text(
                    "SELECT id, name, total_points FROM students WHERE class_name = :cls ORDER BY name"
                ),
                {"cls": selected_class1},
            ).fetchall()
            st.dataframe(
                pd.DataFrame(students, columns=["ID", "Name", "Points"]),
                use_container_width=True,
            )

            st.markdown("**👨‍🏫 Teachers assigned to this class:**")
            teachers = conn.execute(
                text(
                    """
                    SELECT t.name FROM teachers t
                    JOIN teacher_class tc ON t.id = tc.teacher_id
                    WHERE tc.class_name = :cls
                """
                ),
                {"cls": selected_class1},
            ).fetchall()
            st.dataframe(pd.DataFrame(teachers, columns=["Teacher Name"]))

        # --- 👨‍🏫 TAB 2 ---
        with tabs[1]:
            selected_class2 = st.selectbox(
                "🎓 Select Class", class_list, key="class_tab2"
            )

            st.subheader("Assign / Unassign Teachers")
            filter_option = st.radio(
                "Filter Teachers", ["Assigned", "Not Assigned"], horizontal=True
            )
            search = st.text_input("Search Teacher Name", key="teacher_search")

            if filter_option == "Assigned":
                t_query = """
                    SELECT t.id, t.name FROM teachers t
                    JOIN teacher_class tc ON t.id = tc.teacher_id
                    WHERE tc.class_name = :cls AND LOWER(t.name) LIKE LOWER(:q)
                    GROUP BY t.id, t.name
                    ORDER BY t.name
                """
            else:
                t_query = """
                    SELECT t.id, t.name FROM teachers t
                    WHERE t.id NOT IN (
                        SELECT teacher_id FROM teacher_class WHERE class_name = :cls
                    )
                    AND LOWER(t.name) LIKE LOWER(:q)
                    ORDER BY t.name
                """
            teachers = conn.execute(
                text(t_query), {"cls": selected_class2, "q": f"%{search}%"}
            ).fetchall()

            if not teachers:
                st.info("No teachers match the filter.")
            else:
                for tid, tname in teachers:
                    assigned = conn.execute(
                        text(
                            "SELECT 1 FROM teacher_class WHERE teacher_id = :tid AND class_name = :cls"
                        ),
                        {"tid": tid, "cls": selected_class2},
                    ).fetchone()

                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.markdown(f"**{tname}**")
                        class_rows = conn.execute(
                            text(
                                "SELECT class_name FROM teacher_class WHERE teacher_id = :tid"
                            ),
                            {"tid": tid},
                        ).fetchall()
                        class_str = (
                            ", ".join([row[0] for row in class_rows])
                            if class_rows
                            else "❌ None"
                        )
                        st.caption(f"Classes: {class_str}")

                    with col2:
                        if assigned:
                            if st.button("🗑 Unassign", key=f"unassign_{tid}"):
                                with engine.begin() as tx:
                                    tx.execute(
                                        text(
                                            "DELETE FROM teacher_class WHERE teacher_id = :tid AND class_name = :cls"
                                        ),
                                        {"tid": tid, "cls": selected_class2},
                                    )
                                st.success(f"{tname} unassigned from {selected_class2}")
                                st.rerun()
                        else:
                            if st.button("➕ Assign", key=f"assign_{tid}"):
                                with engine.begin() as tx:
                                    tx.execute(
                                        text(
                                            "INSERT INTO teacher_class (teacher_id, class_name) VALUES (:tid, :cls)"
                                        ),
                                        {"tid": tid, "cls": selected_class2},
                                    )
                                st.success(f"{tname} assigned to {selected_class2}")
                                st.rerun()

        # --- 🎁 TAB 3 ---
        with tabs[2]:
            st.subheader("🎁 Manage Rewards")

            r_search = st.text_input("Search Rewards", key="reward_search")
            rewards = conn.execute(
                text("SELECT id, name, cost, stock FROM rewards WHERE name LIKE :q"),
                {"q": f"%{r_search}%"},
            ).fetchall()
            r_df = pd.DataFrame(rewards, columns=["ID", "Name", "Cost", "Stock"])
            st.dataframe(r_df, use_container_width=True)

            with st.expander("➕ Add New Reward"):
                r_name = st.text_input("Reward Name")
                r_desc = st.text_area("Description")
                r_cost = st.number_input("Cost", min_value=1)
                r_stock = st.number_input("Stock", min_value=0)
                if st.button("✅ Add Reward"):
                    with engine.begin() as tx:
                        tx.execute(
                            text(
                                "INSERT INTO rewards (name, description, cost, stock) VALUES (:n, :d, :c, :s)"
                            ),
                            {"n": r_name, "d": r_desc, "c": r_cost, "s": r_stock},
                        )
                    st.success(f"Added reward '{r_name}'")
                    st.rerun()

            if not r_df.empty:
                selected_reward = st.selectbox(
                    "Select Reward to Edit", r_df["Name"].tolist()
                )
                r_row = r_df[r_df["Name"] == selected_reward].iloc[0]

                with st.expander("✏️ Edit Reward"):
                    new_cost = st.number_input("New Cost", value=int(r_row["Cost"]))
                    new_stock = st.number_input("New Stock", value=int(r_row["Stock"]))
                    if st.button("💾 Update"):
                        with engine.begin() as tx:
                            tx.execute(
                                text(
                                    "UPDATE rewards SET cost = :c, stock = :s WHERE id = :rid"
                                ),
                                {
                                    "c": new_cost,
                                    "s": new_stock,
                                    "rid": int(r_row["ID"]),
                                },
                            )
                        st.success("Reward updated.")
                        st.rerun()

                if st.button("🗑 Delete Reward"):
                    with engine.begin() as tx:
                        tx.execute(
                            text("DELETE FROM rewards WHERE id = :rid"),
                            {"rid": int(r_row["ID"])},
                        )
                    st.warning("Reward deleted.")
                    st.rerun()

        # --- 🔐 TAB 4 ---
        with tabs[3]:
            st.subheader("Reset User Password")
            role = st.radio("Select Role", ["student", "teacher"], horizontal=True)
            name_filter = st.text_input("Search Name", key="pw_reset_name")

            if role == "student":
                selected_pw_class = st.selectbox(
                    "Select Class", class_list, key="pw_reset_class"
                )
                users = conn.execute(
                    text(
                        """
                    SELECT u.username, s.name
                    FROM users u
                    JOIN students s ON u.student_id = s.id
                    WHERE u.role = 'student' AND s.class_name = :cls AND s.name LIKE :q
                """
                    ),
                    {"cls": selected_pw_class, "q": f"%{name_filter}%"},
                ).fetchall()
            else:
                users = conn.execute(
                    text(
                        """
                    SELECT u.username, t.name
                    FROM users u
                    JOIN teachers t ON u.teacher_id = t.id
                    WHERE u.role = 'teacher' AND t.name LIKE :q
                """
                    ),
                    {"q": f"%{name_filter}%"},
                ).fetchall()

            if not users:
                st.info("No users found.")
            else:
                u_map = {f"{n} ({u})": u for u, n in users}
                selected_u = st.selectbox("Select User to Reset", list(u_map.keys()))
                if st.button("🔁 Reset to 'password123'"):
                    new_pw = hash_password("password123")
                    with engine.begin() as tx:
                        tx.execute(
                            text(
                                "UPDATE users SET password_hash = :p WHERE username = :u"
                            ),
                            {"p": new_pw, "u": u_map[selected_u]},
                        )
                    st.success(f"{selected_u} password reset to 'password123'.")
