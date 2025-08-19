# modules/admin.py
import streamlit as st
import pandas as pd
import altair as alt
from sqlalchemy import text
from modules.auth import hash_password
from modules.db import engine

# Try to import the global resync helper; provide a safe fallback if not present
try:
    from modules.db import recalc_all_students  # preferred
except Exception:

    def recalc_all_students(engine_):
        """Fallback: recompute students.total_points = sum(activities) - sum(approved redemptions)."""
        with engine_.begin() as tx:
            tx.execute(
                text(
                    """
                    UPDATE students s
                    LEFT JOIN (
                      SELECT a.student_id, COALESCE(SUM(a.points),0) AS earned
                      FROM activities a
                      GROUP BY a.student_id
                    ) e ON e.student_id = s.id
                    LEFT JOIN (
                      SELECT r.student_id, COALESCE(SUM(w.cost),0) AS spent
                      FROM redemptions r
                      JOIN rewards w ON w.id = r.reward_id
                      WHERE r.status = 'approved'
                      GROUP BY r.student_id
                    ) x ON x.student_id = s.id
                    SET s.total_points = COALESCE(e.earned,0) - COALESCE(x.spent,0);
                """
                )
            )


def show_admin_dashboard(user):
    st.markdown("## 🛠 Admin Dashboard")

    tabs = st.tabs(
        [
            "📚 Class View",
            "👨‍🏫 Teacher Assignment",
            "🎁 Manage Stocks",
            "🧾 Stock Approvals",
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
                # coerce points to int (avoid Decimal issues)
                df = pd.DataFrame(students, columns=["ID", "Name", "Points"])
                if "Points" in df.columns:
                    df["Points"] = df["Points"].apply(
                        lambda x: int(float(x)) if x is not None else 0
                    )
                st.dataframe(df, use_container_width=True)

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

    # --- 🎁 TAB 3: Manage Stocks (Rewards) ---
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
            # Coerce numeric types
            r_df["Cost"] = r_df["Cost"].apply(
                lambda x: int(float(x)) if x is not None else 0
            )
            r_df["Stock"] = r_df["Stock"].apply(
                lambda x: int(float(x)) if x is not None else 0
            )
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
                                "c": int(r_cost),
                                "s": int(r_stock),
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
                                {
                                    "c": int(new_cost),
                                    "s": int(new_stock),
                                    "rid": r_row[0],
                                },
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

    # --- 🧾 TAB 4: Manage Redemptions (mobile-friendly table) ---
    with tabs[3]:
        st.subheader("🧾 Manage Redemptions")

        # --- Filters ---
        status_filter = st.radio(
            "Filter by Status",
            ["pending", "approved", "rejected", "insufficient"],
            horizontal=True,
        )

        with engine.connect() as conn:
            classes = conn.execute(
                text("SELECT DISTINCT class_name FROM students ORDER BY class_name")
            ).fetchall()
        class_list = [c[0] for c in classes]
        class_filter = st.selectbox(
            "Filter by Class", ["All"] + class_list, key="redeem_class"
        )

        # --- Query (same logic as yours) ---
        base_sql = """
            SELECT r.id, r.student_id, r.reward_id, r.created_at, r.status,
                s.name AS student_name, s.class_name, s.total_points,
                rw.name AS reward_name, rw.cost, rw.stock
            FROM redemptions r
            JOIN students s ON s.id = r.student_id
            JOIN rewards  rw ON rw.id = r.reward_id
        """
        params = {}
        if status_filter == "insufficient":
            # pending where points < cost OR stock <= 0
            where_sql = " WHERE r.status = 'pending' AND (s.total_points < rw.cost OR rw.stock <= 0)"
        else:
            where_sql = " WHERE r.status = :status"
            params["status"] = status_filter

        if class_filter != "All":
            where_sql += " AND s.class_name = :cls"
            params["cls"] = class_filter

        order_sql = " ORDER BY r.created_at"

        with engine.connect() as conn:
            rows = (
                conn.execute(text(base_sql + where_sql + order_sql), params).fetchall()
                or []
            )

        if not rows:
            st.info(f"No {status_filter} requests.")
        else:
            # ---- Normalize into a DataFrame (Decimal-safe) ----
            # Also keep a meta lookup for IDs to (student_id, reward_id)
            id_to_meta = {}
            records = []
            for (
                rid,
                sid,
                rwid,
                created_at,
                rstatus,
                sname,
                sclass,
                spts,
                rname,
                rcost,
                rstock,
            ) in rows:
                id_to_meta[int(rid)] = (int(sid), int(rwid))
                records.append(
                    {
                        "ID": int(rid),
                        "Student": sname,
                        "Class": sclass,
                        "Pts": int(float(spts)) if spts is not None else 0,
                        "Reward": rname,
                        "Cost": int(float(rcost)) if rcost is not None else 0,
                        "Stock": int(float(rstock)) if rstock is not None else 0,
                        "Date": str(created_at),
                        "Status": rstatus,
                        "Decision": "",  # "", "Approve", "Reject"
                    }
                )

            df = pd.DataFrame(
                records,
                columns=[
                    "ID",
                    "Student",
                    "Class",
                    "Pts",
                    "Reward",
                    "Cost",
                    "Stock",
                    "Date",
                    "Status",
                    "Decision",
                ],
            )

            # ---- Bulk actions header (compact for mobile) ----
            h1, h2 = st.columns(2)
            with h1:
                if status_filter == "pending":
                    scope = (
                        f"for {class_filter}"
                        if class_filter != "All"
                        else "for ALL classes"
                    )
                    if st.button(f"✅ Approve All Pending {scope}"):
                        try:
                            with engine.begin() as tx:
                                for rec in records:
                                    if rec["Status"] != "pending":
                                        continue
                                    rid = rec["ID"]
                                    sid, rwid = id_to_meta[rid]
                                    # Validate latest points & stock
                                    pts = tx.execute(
                                        text(
                                            "SELECT total_points FROM students WHERE id=:sid"
                                        ),
                                        {"sid": sid},
                                    ).scalar()
                                    stock = tx.execute(
                                        text("SELECT stock FROM rewards WHERE id=:rw"),
                                        {"rw": rwid},
                                    ).scalar()
                                    if pts is None or stock is None:
                                        continue
                                    if int(pts) >= int(rec["Cost"]) and int(stock) > 0:
                                        tx.execute(
                                            text(
                                                "UPDATE redemptions SET status='approved' WHERE id=:rid"
                                            ),
                                            {"rid": rid},
                                        )
                                        # If your app still relies on students.total_points, deduct here:
                                        tx.execute(
                                            text(
                                                "UPDATE students SET total_points = total_points - :c WHERE id=:sid"
                                            ),
                                            {"c": int(rec["Cost"]), "sid": sid},
                                        )
                                        tx.execute(
                                            text(
                                                "UPDATE rewards SET stock = stock - 1 WHERE id=:rw"
                                            ),
                                            {"rw": rwid},
                                        )
                            # If parts of the app read students.total_points, keep this:
                            # recalc_all_students(engine)
                            st.success(
                                f"All valid pending redemptions {scope} approved."
                            )
                            # st.cache_data.clear()  # if any cached reads elsewhere
                            st.rerun()
                        except Exception as e:
                            st.error(f"Bulk approval failed: {e}")
            with h2:
                if status_filter == "insufficient":
                    if st.button("❌ Reject All (Insufficient)"):
                        try:
                            with engine.begin() as tx:
                                for rec in records:
                                    if rec["Status"] != "pending":
                                        continue
                                    tx.execute(
                                        text(
                                            "UPDATE redemptions SET status='rejected' WHERE id=:rid"
                                        ),
                                        {"rid": rec["ID"]},
                                    )
                            st.warning("All insufficient requests rejected.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Bulk reject failed: {e}")

            # ---- Editable table (only Decision is editable) ----
            edited = st.data_editor(
                df,
                hide_index=True,
                column_config={
                    "ID": st.column_config.NumberColumn("ID", width="small"),
                    "Student": st.column_config.TextColumn("Student", width="medium"),
                    "Class": st.column_config.TextColumn("Class", width="small"),
                    "Pts": st.column_config.NumberColumn("Pts", width="small"),
                    "Reward": st.column_config.TextColumn("Reward", width="medium"),
                    "Cost": st.column_config.NumberColumn("Cost", width="small"),
                    "Stock": st.column_config.NumberColumn("Stock", width="small"),
                    "Date": st.column_config.TextColumn("Date", width="medium"),
                    "Status": st.column_config.TextColumn("Status", width="small"),
                    "Decision": st.column_config.SelectboxColumn(
                        "Decision", options=["", "Approve", "Reject"], width="small"
                    ),
                },
                disabled=[c for c in df.columns if c != "Decision"],
                use_container_width=True,
            )

            # ---- Apply per-row decisions (Approve/Reject) ----
            if st.button("💾 Apply Decisions"):
                try:
                    approve_jobs = []  # (rid, sid, rwid, cost)
                    reject_jobs = []  # rid

                    for _, r in edited.iterrows():
                        decision = (r["Decision"] or "").strip()
                        if not decision:
                            continue
                        rid = int(r["ID"])
                        sid, rwid = id_to_meta[rid]
                        cost = int(r["Cost"])
                        if decision == "Reject":
                            reject_jobs.append(rid)
                        elif decision == "Approve":
                            approve_jobs.append((rid, sid, rwid, cost))

                    with engine.begin() as tx:
                        # Reject first
                        for rid in reject_jobs:
                            tx.execute(
                                text(
                                    "UPDATE redemptions SET status='rejected' WHERE id=:rid"
                                ),
                                {"rid": rid},
                            )

                        # Approve with validation
                        for rid, sid, rwid, cost in approve_jobs:
                            pts = tx.execute(
                                text("SELECT total_points FROM students WHERE id=:sid"),
                                {"sid": sid},
                            ).scalar()
                            stock = tx.execute(
                                text("SELECT stock FROM rewards WHERE id=:rw"),
                                {"rw": rwid},
                            ).scalar()
                            if pts is None or stock is None:
                                continue
                            if int(pts) >= int(cost) and int(stock) > 0:
                                tx.execute(
                                    text(
                                        "UPDATE redemptions SET status='approved' WHERE id=:rid"
                                    ),
                                    {"rid": rid},
                                )
                                # If your app still reads students.total_points:
                                tx.execute(
                                    text(
                                        "UPDATE students SET total_points = total_points - :c WHERE id=:sid"
                                    ),
                                    {"c": int(cost), "sid": sid},
                                )
                                tx.execute(
                                    text(
                                        "UPDATE rewards SET stock = stock - 1 WHERE id=:rw"
                                    ),
                                    {"rw": rwid},
                                )

                    # recalc_all_students(engine)  # uncomment if other tabs rely on stored totals
                    st.success("Decisions applied.")
                    # st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error applying decisions: {e}")

    # --- 📊 TAB 5: Redemption Insights ---
    with tabs[4]:
        st.subheader("📊 Transactions")
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
                df_status = pd.DataFrame(status_rows, columns=["Status", "Count"])
                df_status["Count"] = df_status["Count"].apply(
                    lambda x: int(float(x)) if x is not None else 0
                )
                st.table(df_status)
            else:
                st.info("No redemption data yet.")
        with col2:
            total_pts = (
                int(float(total_points_row.pts))
                if total_points_row and total_points_row.pts is not None
                else 0
            )
            st.metric("Total Points Spent (Approved)", total_pts)

        if top_rewards:
            df_tr = pd.DataFrame(top_rewards, columns=["Reward", "Redemption Count"])
            df_tr["Redemption Count"] = df_tr["Redemption Count"].apply(
                lambda x: int(float(x)) if x is not None else 0
            )
            st.markdown("**Top Rewards**")
            st.table(df_tr)

        if top_students:
            df_ts = pd.DataFrame(
                top_students, columns=["Student", "Redemption Count", "Points Spent"]
            )
            df_ts["Redemption Count"] = df_ts["Redemption Count"].apply(
                lambda x: int(float(x)) if x is not None else 0
            )
            df_ts["Points Spent"] = df_ts["Points Spent"].apply(
                lambda x: int(float(x)) if x is not None else 0
            )
            st.markdown("**Top Students**")
            st.table(df_ts)

        if ts_rows:
            df_line = pd.DataFrame(ts_rows, columns=["Date", "Approved Count"])
            df_line["Approved Count"] = df_line["Approved Count"].apply(
                lambda x: int(float(x)) if x is not None else 0
            )
            chart = (
                alt.Chart(df_line)
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
