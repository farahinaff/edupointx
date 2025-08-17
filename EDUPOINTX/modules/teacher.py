import time
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from PIL import Image, ImageOps
import numpy as np
import cv2  # from opencv-python-headless

from modules.db import DB_URL

engine = create_engine(DB_URL)


# ---------- QR helpers ----------
def _decode_all_qr_strings_from_image(image_file) -> list[str]:
    """
    Decode QR codes using OpenCV QRCodeDetector (headless build).
    Works with multiple QR codes in one image.
    Returns unique decoded strings.
    """
    pil = Image.open(image_file)
    pil = ImageOps.exif_transpose(pil).convert("RGB")
    img_np = np.array(pil)
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    detector = cv2.QRCodeDetector()

    decoded = []

    # Try multi-detect
    retval, decoded_info, points, _ = detector.detectAndDecodeMulti(img_bgr)
    if retval and decoded_info:
        for s in decoded_info:
            if s and s.strip():
                decoded.append(s.strip())

    # Fallback: single detect
    if not decoded:
        data, _, _ = detector.detectAndDecode(img_bgr)
        if data and data.strip():
            decoded.append(data.strip())

    # Unique preserve order
    seen, uniq = set(), []
    for s in decoded:
        if s not in seen:
            uniq.append(s)
            seen.add(s)
    return uniq


import re


def _choose_addpoints_and_sid(decoded_list):
    """
    Pick the 'add points' QR among multiple decoded strings.
    Accepts either:
      - ?mode=deed&sid=...
      - ?action=addpoints&sid=...
    Returns (matched_string, sid) or (None, None).
    """
    for raw in decoded_list:
        if not raw:
            continue
        s = "".join(ch for ch in raw if ch.isprintable()).strip()
        low = s.lower()

        is_add = ("mode=deed" in low) or ("action=addpoints" in low)
        if is_add and "sid=" in low:
            m = re.search(r"(?:\?|&)\s*sid\s*=\s*([^&#\s]+)", s, flags=re.IGNORECASE)
            if m:
                return s, m.group(1)
    return None, None


# ---------- Main UI ----------
def show_teacher_dashboard(user, is_admin=False):
    teacher_id = user.get("teacher_id")
    st.header("📊 Teacher Dashboard" if not is_admin else "📊 Admin View: Class Deeds")

    # Shared Class Selector
    with engine.connect() as conn:
        if is_admin:
            classes = conn.execute(
                text("SELECT DISTINCT class_name FROM students ORDER BY class_name")
            ).fetchall()
        else:
            classes = conn.execute(
                text(
                    "SELECT class_name FROM teacher_class "
                    "WHERE teacher_id = :tid ORDER BY class_name"
                ),
                {"tid": teacher_id},
            ).fetchall()

    class_list = [c[0] for c in classes]
    if not class_list:
        st.warning("No classes assigned.")
        return

    if "selected_class" not in st.session_state:
        st.session_state.selected_class = class_list[0]

    st.session_state.selected_class = st.selectbox(
        "🎓 Select Class",
        class_list,
        index=(
            class_list.index(st.session_state.selected_class)
            if st.session_state.selected_class in class_list
            else 0
        ),
        key="class_selector",
    )
    selected_class = st.session_state.selected_class

    tabs = st.tabs(
        [
            "➕ Add Points",
            "📷 Upload QR to Add Points",
            "📈 Class Insights",
            "🔥 Top Categories",
            "🏆 Student Rankings",
        ]
    )

    # -------- TAB 0: Manual Add Points --------
    with tabs[0]:
        with engine.connect() as conn:
            students = conn.execute(
                text(
                    "SELECT id, name FROM students "
                    "WHERE class_name = :cls ORDER BY name"
                ),
                {"cls": selected_class},
            ).fetchall()

        if not students:
            st.info("No students found in this class.")
        else:
            student_map = {name: sid for sid, name in students}
            st.subheader("📝 Add Student Points")

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
                    st.error(f"❌ Error adding points: {e}")

    # -------- TAB 1: Upload QR to Add Points --------
    with tabs[1]:
        st.subheader("📷 Upload Student QR (Add Points only)")
        st.caption(
            "Upload a photo of the student card. We will pick the **Add Points** QR and ignore the Redeem QR."
        )

        uploaded = st.file_uploader("Upload QR image", type=["png", "jpg", "jpeg"])

        if uploaded:
            decoded = _decode_all_qr_strings_from_image(uploaded)

            if not decoded:
                st.error("No QR code detected. Try a closer, clearer photo.")
            else:
                matched, sid = _choose_addpoints_and_sid(decoded)
                if not sid:
                    st.error("We found QR(s), but none is an **Add Points** QR.")
                else:
                    with engine.connect() as conn:
                        student = conn.execute(
                            text(
                                "SELECT id, name, class_name FROM students WHERE id = :sid"
                            ),
                            {"sid": sid},
                        ).fetchone()

                    if not student:
                        st.error("❌ Student not found.")
                    else:
                        st.success(
                            f"Student: {student.name} (Class: {student.class_name})"
                        )

                        with st.form("qr_add_form"):
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
                            reason = st.text_input("Reason / Description")
                            pts = st.number_input(
                                "Point Reward", min_value=1, max_value=100, step=1
                            )
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
                                            "sid": sid,
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
                                        {"pts": pts, "sid": sid},
                                    )
                                st.success(
                                    f"{pts} points added to {student.name} for '{cat}'."
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {e}")

    # -------- TAB 2: Class Insights --------
    with tabs[2]:
        st.subheader("📈 Class Performance Insights")
        with engine.connect() as conn:
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
        else:
            st.info("No points yet for this class.")

    # -------- TAB 3: Top Categories --------
    with tabs[3]:
        with engine.connect() as conn:
            category_data = conn.execute(
                text(
                    """
                    SELECT category, COUNT(*) as count, SUM(points) as total_points
                    FROM activities a
                    JOIN students s ON a.student_id = s.id
                    WHERE s.class_name = :cls
                    GROUP BY category
                    ORDER BY total_points DESC
                    """
                ),
                {"cls": selected_class},
            ).fetchall()

        if category_data:
            df = pd.DataFrame(
                category_data, columns=["Category", "Activity Count", "Total Points"]
            )
            st.table(df)
        else:
            st.info("No data yet for this class.")

    # -------- TAB 4: Student Rankings --------
    with tabs[4]:
        st.subheader("🏆 Student Rankings")

        with engine.connect() as conn:
            all_students = conn.execute(
                text(
                    "SELECT id, name, total_points FROM students WHERE class_name = :cls ORDER BY total_points DESC"
                ),
                {"cls": selected_class},
            ).fetchall()

        if not all_students:
            st.info("No students yet with points.")
        else:
            top_students = all_students[:3]
            bottom_students = all_students[-3:] if len(all_students) > 3 else []

            def student_breakdown(sid):
                with engine.connect() as conn:
                    rows = conn.execute(
                        text(
                            """
                            SELECT category, COUNT(*) as activity_count, SUM(points) as total_points
                            FROM activities
                            WHERE student_id = :sid
                            GROUP BY category
                            ORDER BY total_points DESC
                            """
                        ),
                        {"sid": sid},
                    ).fetchall()
                return (
                    pd.DataFrame(
                        rows, columns=["Category", "Activity Count", "Total Points"]
                    )
                    if rows
                    else None
                )

            # Top 3
            st.markdown("### 🥇 Top 3 Students")
            for sid, sname, pts in top_students:
                st.markdown(f"**{sname}** – {pts} pts")
                with st.expander(f"📂 Details for {sname}"):
                    df = student_breakdown(sid)
                    if df is not None:
                        st.table(df)
                    else:
                        st.info("No activity data.")

            # Bottom 3
            if bottom_students:
                st.markdown("### 🪫 Bottom 3 Students")
                for sid, sname, pts in bottom_students:
                    st.markdown(f"**{sname}** – {pts} pts")
                    with st.expander(f"📂 Details for {sname}"):
                        df = student_breakdown(sid)
                        if df is not None:
                            st.table(df)
                        else:
                            st.info("No activity data.")
