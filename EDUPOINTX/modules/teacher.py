import streamlit as st
import pandas as pd
import altair as alt
from sqlalchemy import create_engine, text
from datetime import datetime
import time
from modules.db import DB_URL

import streamlit.components.v1 as components


engine = create_engine(DB_URL)


def show_teacher_dashboard(user, is_admin=False):
    teacher_id = user.get("teacher_id")
    st.header("📊 Teacher Dashboard" if not is_admin else "📊 Admin View: Class Deeds")

    # === Shared Class Selector ===
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

    if not class_list:
        st.warning("No classes assigned.")
        return

    selected_class = st.selectbox("🎓 Select Class", class_list, key="class_selector")
    st.session_state.selected_class = selected_class

    # === Tabs ===
    tabs = st.tabs(
        [
            "➕ Add Deed",
            "📷 Scan QR to Add",
            "📈 Class Insights",
            "🔥 Top Categories",
            "🏅 Top Students",
        ]
    )

    with engine.connect() as conn:

        # === TAB 0: Add Deed Manually ===
        with tabs[0]:
            students = conn.execute(
                text(
                    "SELECT id, name FROM students WHERE class_name = :cls ORDER BY name"
                ),
                {"cls": selected_class},
            ).fetchall()
            student_map = {name: sid for sid, name in students}

            st.subheader("📝 Add Student Deed")
            form_key = f"form_{int(time.time())}"

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

        # === TAB 1: QR Upload to Add Points ===
        with tabs[1]:
            st.subheader("📷 Live Scan QR Code to Add Points")

            st.markdown(
                """
            **How to use this:**

            1. Click "Start Scanner" below.
            2. Point your phone camera to the student's QR code.
            3. Student info will auto-fill once scanned.
            """
            )

            # scanned_sid = st.experimental_get_query_params().get("sid", [None])[0]
            # scanned_action = st.experimental_get_query_params().get("action", [None])[0]
            scanned_sid = st.query_params.get("sid", None)
            scanned_action = st.query_params.get("action", None)

            if scanned_sid and scanned_action == "addpoints":
                student = conn.execute(
                    text("SELECT id, name, class_name FROM students WHERE id = :sid"),
                    {"sid": scanned_sid},
                ).fetchone()

                if not student:
                    st.error("❌ Student not found.")
                else:
                    st.success(f"Scanned: {student.name} ({student.class_name})")

                    with st.form("live_qr_add"):
                        cat = st.selectbox(
                            "Deed Category",
                            [
                                "Discipline",
                                "Academics",
                                "Sports",
                                "Leadership",
                                "Other",
                            ],
                        )
                        reason = st.text_input("Reason")
                        pts = st.number_input("Points", min_value=1, max_value=100)
                        submit_qr = st.form_submit_button("✅ Add Points")

                    if submit_qr:
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
                                        "sid": scanned_sid,
                                        "tid": teacher_id,
                                        "cat": cat,
                                        "reason": reason,
                                        "pts": pts,
                                        "ts": datetime.now(),
                                    },
                                )
                                tx.execute(
                                    text(
                                        "UPDATE students SET total_points = total_points + :pts WHERE id = :sid"
                                    ),
                                    {"pts": pts, "sid": scanned_sid},
                                )
                            st.success(f"{pts} points added to {student.name}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
            else:
                st.info("Waiting for QR scan...")

            st.markdown("### 📸 Start Scanner")
            components.html(
                """
                <script src="https://unpkg.com/html5-qrcode@2.3.8/minified/html5-qrcode.min.js"></script>
                <div id="reader" style="width: 300px;"></div>
                <script>
                    function navigateWithSID(sid) {
                        const base = window.location.origin + window.location.pathname;
                        const newUrl = base + "?action=addpoints&sid=" + sid;
                        window.location.href = newUrl;
                    }

                    function scanSuccess(decodedText, decodedResult) {
                        if (decodedText.includes("sid=")) {
                            const url = new URL(decodedText);
                            const sid = url.searchParams.get("sid");
                            if (sid) {
                                navigateWithSID(sid);
                            }
                        }
                    }

                    const html5QrCode = new Html5Qrcode("reader");
                    const config = { fps: 10, qrbox: 250 };
                    Html5Qrcode.getCameras().then(devices => {
                        if (devices && devices.length) {
                            html5QrCode.start({ facingMode: "environment" }, config, scanSuccess);
                        }
                    }).catch(err => {
                        document.getElementById("reader").innerText = "Camera error: " + err;
                    });
                </script>
            """,
                height=400,
            )

        # === TAB 2: Class Insights ===
        with tabs[2]:
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

        # === TAB 3: Category Pie Chart ===
        with tabs[3]:
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
                    .encode(
                        theta="Count", color="Category", tooltip=["Category", "Count"]
                    )
                    .properties(width=400)
                )
                st.altair_chart(pie, use_container_width=True)

        # === TAB 4: Top Students ===
        with tabs[4]:
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
