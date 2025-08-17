import streamlit as st
import pandas as pd
import altair as alt
from sqlalchemy import create_engine, text
from modules.auth import hash_password
from modules.db import DB_URL

engine = create_engine(DB_URL)


def show_admin_dashboard(user):
    st.markdown("## 🛠 Admin Dashboard")

    tabs = st.tabs(
        [
            "📚 Class View",
            "👨‍🏫 Teacher Assignment",
            "🎁 Rewards",
            "🧾 Approvals",
            "📊 Redemption Insights",
            "🔐 Reset Password",
        ]
    )

    # --- 📚 TAB 1: Class View ---
    with tabs[0]:
        with engine.connect() as conn:
            class_names = conn.execute(
                text("SELECT DISTINCT class_name FROM students ORDER BY class_name")
            ).fetchall()
        class_list = [c[0] for c in class_names]

        if not class_list:
            st.info("No classes found.")
        else:
            selected_class1 = st.selectbox(
                "🎓 Select Class", class_list, key="class_tab1"
            )
            st.subheader("👥 Students in Class")

            with engine.connect() as conn:
                students = conn.execute(
                    text(
                        "SELECT id, name, total_points FROM students WHERE class_name = :cls ORDER BY name"
                    ),
                    {"cls": selected_class1},
                ).fetchall()

            if not students:
                st.info("No students found in this class.")
            else:
                st.dataframe(
                    pd.DataFrame(students, columns=["ID", "Name", "Points"]),
                    use_container_width=True,
                )

            st.markdown("**👨‍🏫 Teachers assigned to this class:**")
            with engine.connect() as conn:
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
            if not teachers:
                st.info("No teachers assigned yet.")
            else:
                st.dataframe(pd.DataFrame(teachers, columns=["Teacher Name"]))

    # --- 👨‍🏫 TAB 2: Teacher Assignment ---
    with tabs[1]:
        with engine.connect() as conn:
            class_names = conn.execute(
                text("SELECT DISTINCT class_name FROM students ORDER BY class_name")
            ).fetchall()
        class_list = [c[0] for c in class_names]

        if not class_list:
            st.info("No classes found.")
        else:
            selected_class2 = st.selectbox(
                "🎓 Select Class", class_list, key="class_tab2"
            )

            st.subheader("Assign / Unassign Teachers")
            filter_option = st.radio(
                "Filter Teachers", ["Assigned", "Not Assigned"], horizontal=True
            )
            search = st.text_input("Search Teacher Name", key="teacher_search")

            with engine.connect() as conn:
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
                    with engine.connect() as conn:
                        assigned = conn.execute(
                            text(
                                "SELECT 1 FROM teacher_class WHERE teacher_id = :tid AND class_name = :cls"
                            ),
                            {"tid": tid, "cls": selected_class2},
                        ).fetchone()
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.markdown(f"**{tname}**")
                        with engine.connect() as conn:
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

    # --- 🎁 TAB 3: Rewards ---
    with tabs[2]:
        st.subheader("🎁 Manage Rewards")
        r_search = st.text_input("Search Rewards", key="reward_search")

        with engine.connect() as conn:
            rewards = conn.execute(
                text("SELECT id, name, cost, stock FROM rewards WHERE name LIKE :q"),
                {"q": f"%{r_search}%"},
            ).fetchall()

        if not rewards:
            st.info("No rewards found.")
        else:
            r_df = pd.DataFrame(rewards, columns=["ID", "Name", "Cost", "Stock"])
            st.dataframe(r_df, use_container_width=True)

            with st.expander("➕ Add New Reward"):
                r_name = st.text_input("Reward Name")
                r_desc = st.text_area("Description")
                r_cost = st.number_input("Cost", min_value=1)
                r_stock = st.number_input("Stock", min_value=0)
                r_source = st.selectbox("Source", ["coop", "canteen"])
                if st.button("✅ Add Reward"):
                    with engine.begin() as tx:
                        tx.execute(
                            text(
                                "INSERT INTO rewards (name, description, cost, stock, source) VALUES (:n, :d, :c, :s, :src)"
                            ),
                            {
                                "n": r_name,
                                "d": r_desc,
                                "c": r_cost,
                                "s": r_stock,
                                "src": r_source,
                            },
                        )
                    st.success(f"Added reward '{r_name}'")
                    st.rerun()

            selected_reward = st.selectbox(
                "Select Reward to Edit", [r[1] for r in rewards], key="edit_reward"
            )
            if selected_reward:
                r_row = next(r for r in rewards if r[1] == selected_reward)
                with st.expander("✏️ Edit Reward"):
                    new_cost = st.number_input("New Cost", value=int(r_row[2]))
                    new_stock = st.number_input("New Stock", value=int(r_row[3]))
                    if st.button("💾 Update"):
                        with engine.begin() as tx:
                            tx.execute(
                                text(
                                    "UPDATE rewards SET cost = :c, stock = :s WHERE id = :rid"
                                ),
                                {"c": new_cost, "s": new_stock, "rid": r_row[0]},
                            )
                        st.success("Reward updated.")
                        st.rerun()
                if st.button("🗑 Delete Reward"):
                    with engine.begin() as tx:
                        tx.execute(
                            text("DELETE FROM rewards WHERE id = :rid"),
                            {"rid": r_row[0]},
                        )
                    st.warning("Reward deleted.")
                    st.rerun()

    # --- 🧾 TAB 4: Approvals ---
    with tabs[3]:
        st.subheader("🧾 Pending Redemptions")
        with engine.connect() as conn:
            pending = conn.execute(
                text(
                    """
                    SELECT r.id, r.student_id, r.reward_id, r.created_at,
                           s.name AS student_name, s.total_points,
                           rw.name AS reward_name, rw.cost, rw.stock
                    FROM redemptions r
                    JOIN students s ON s.id = r.student_id
                    JOIN rewards  rw ON rw.id = r.reward_id
                    WHERE r.status = 'pending'
                    ORDER BY r.created_at
                    """
                )
            ).fetchall()

        if not pending:
            st.info("No pending requests.")
        else:
            for (
                rid,
                sid,
                rwid,
                created_at,
                sname,
                spts,
                rname,
                rcost,
                rstock,
            ) in pending:
                with st.container(border=True):
                    st.markdown(
                        f"**#{rid}** • 🎓 {sname} ({spts} pts) "
                        f"→ 🎁 {rname} (cost {rcost}, stock {rstock}) • 🕒 {created_at}"
                    )
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button("✅ Approve", key=f"approve_{rid}"):
                            try:
                                with engine.begin() as tx:
                                    row = tx.execute(
                                        text(
                                            "SELECT total_points FROM students WHERE id=:sid"
                                        ),
                                        {"sid": sid},
                                    ).fetchone()
                                    if row.total_points < rcost:
                                        st.warning("Not enough points.")
                                    elif rstock <= 0:
                                        st.warning("Out of stock.")
                                    else:
                                        tx.execute(
                                            text(
                                                "UPDATE redemptions SET status='approved' WHERE id=:rid"
                                            ),
                                            {"rid": rid},
                                        )
                                        tx.execute(
                                            text(
                                                "UPDATE students SET total_points = total_points - :c WHERE id=:sid"
                                            ),
                                            {"c": rcost, "sid": sid},
                                        )
                                        tx.execute(
                                            text(
                                                "UPDATE rewards SET stock = stock - 1 WHERE id=:rid2"
                                            ),
                                            {"rid2": rwid},
                                        )
                                    st.success("Approved!")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                    with col2:
                        if st.button("❌ Reject", key=f"reject_{rid}"):
                            with engine.begin() as tx:
                                tx.execute(
                                    text(
                                        "UPDATE redemptions SET status='rejected' WHERE id=:rid"
                                    ),
                                    {"rid": rid},
                                )
                            st.warning("Rejected.")
                            st.rerun()

    # --- 📊 TAB 5: Redemption Insights ---
    with tabs[4]:
        st.subheader("📊 Redemption Insights")
        with engine.connect() as conn:
            status_rows = conn.execute(
                text("SELECT status, COUNT(*) cnt FROM redemptions GROUP BY status")
            ).fetchall()
            total_points_row = conn.execute(
                text(
                    "SELECT COALESCE(SUM(rw.cost),0) pts FROM redemptions r JOIN rewards rw ON rw.id=r.reward_id WHERE r.status='approved'"
                )
            ).fetchone()
            top_rewards = conn.execute(
                text(
                    "SELECT rw.name, COUNT(*) cnt FROM redemptions r JOIN rewards rw ON rw.id=r.reward_id WHERE r.status='approved' GROUP BY rw.id, rw.name ORDER BY cnt DESC LIMIT 10"
                )
            ).fetchall()
            top_students = conn.execute(
                text(
                    "SELECT s.name, COUNT(*) cnt, SUM(rw.cost) spent FROM redemptions r JOIN students s ON s.id=r.student_id JOIN rewards rw ON rw.id=r.reward_id WHERE r.status='approved' GROUP BY s.id,s.name ORDER BY cnt DESC LIMIT 10"
                )
            ).fetchall()
            ts_rows = conn.execute(
                text(
                    "SELECT DATE(created_at) d, COUNT(*) cnt FROM redemptions WHERE status='approved' GROUP BY DATE(created_at) ORDER BY d"
                )
            ).fetchall()

        col1, col2 = st.columns(2)
        with col1:
            if status_rows:
                st.table(pd.DataFrame(status_rows, columns=["Status", "Count"]))
            else:
                st.info("No redemption data yet.")
        with col2:
            st.metric(
                "Total Points Spent (Approved)",
                total_points_row.pts if total_points_row else 0,
            )

        if top_rewards:
            st.markdown("**Top Rewards**")
            st.table(pd.DataFrame(top_rewards, columns=["Reward", "Count"]))
        if top_students:
            st.markdown("**Top Students**")
            st.table(
                pd.DataFrame(top_students, columns=["Student", "Count", "Points Spent"])
            )
        if ts_rows:
            st.markdown("**Approvals Over Time**")
            df_ts = pd.DataFrame(ts_rows, columns=["Date", "Approved Count"])
            chart = (
                alt.Chart(df_ts)
                .mark_line(point=True)
                .encode(x="Date:T", y="Approved Count:Q")
                .properties(height=300)
            )
            st.altair_chart(chart, use_container_width=True)

    # --- 🔐 TAB 6: Reset Password ---
    with tabs[5]:
        st.subheader("Reset User Password")
        role = st.radio("Select Role", ["student", "teacher"], horizontal=True)
        name_filter = st.text_input("Search Name", key="pw_reset_name")

        with engine.connect() as conn:
            if role == "student":
                users = conn.execute(
                    text(
                        "SELECT u.username, s.name FROM users u JOIN students s ON u.student_id=s.id WHERE u.role='student' AND s.name LIKE :q"
                    ),
                    {"q": f"%{name_filter}%"},
                ).fetchall()
            else:
                users = conn.execute(
                    text(
                        "SELECT u.username, t.name FROM users u JOIN teachers t ON u.teacher_id=t.id WHERE u.role='teacher' AND t.name LIKE :q"
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
                        text("UPDATE users SET password_hash=:p WHERE username=:u"),
                        {"p": new_pw, "u": u_map[selected_u]},
                    )
                st.success(f"{selected_u} password reset to 'password123'.")
