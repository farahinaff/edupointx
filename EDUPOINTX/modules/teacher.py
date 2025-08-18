import time
from datetime import datetime
import re

import altair as alt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from PIL import Image, ImageOps
import numpy as np
import cv2  # from opencv-python-headless

from modules.db import engine, recalc_all_students


# ---- flash helpers ----
def _flash(msg: str, level: str = "success"):
    st.session_state["_toast_msg"] = msg
    st.session_state["_toast_lvl"] = level


def _show_flash():
    msg = st.session_state.pop("_toast_msg", None)
    lvl = st.session_state.pop("_toast_lvl", "success")
    if msg:
        if lvl == "error":
            st.error(msg)
        elif lvl == "warning":
            st.warning(msg)
        elif lvl == "info":
            st.info(msg)
        else:
            st.success(msg)


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
    # _show_flash()
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
                    """
                    SELECT id, name
                    FROM students
                    WHERE class_name = :cls
                    ORDER BY name
                """
                ),
                {"cls": selected_class},
            ).fetchall()

        if not students:
            st.info("No students found in this class.")
        else:
            student_map = {name: sid for sid, name in students}
            st.subheader("📝 Add Student Points")

            # ✅ Use a fixed form key; avoid time.time() keys
            with st.form("add_points_form"):
                selected_student_name = st.selectbox(
                    "Select Student", list(student_map.keys()), key="add_pts_student"
                )
                deed_category = st.selectbox(
                    "Deed Category",
                    ["Discipline", "Academics", "Sports", "Leadership", "Other"],
                    key="add_pts_cat",
                )
                deed_reason = st.text_input(
                    "Reason / Description", key="add_pts_reason"
                )
                deed_points = st.number_input(
                    "Point Reward",
                    min_value=1,
                    max_value=100,
                    step=1,
                    key="add_pts_value",
                )
                submitted = st.form_submit_button("✅ Submit")

            if submitted:
                try:
                    with engine.begin() as tx:
                        tx.execute(
                            text(
                                """
                                INSERT INTO activities
                                    (student_id, teacher_id, category, reason, points, created_at)
                                VALUES
                                    (:sid, :tid, :cat, :reason, :pts, :ts)
                            """
                            ),
                            {
                                "sid": student_map[selected_student_name],
                                "tid": teacher_id,
                                "cat": deed_category,
                                "reason": deed_reason,
                                "pts": int(deed_points),
                                "ts": datetime.now(),
                            },
                        )
                    # Store a toast for the next render. DO NOT call st.rerun() here.
                    # _flash(
                    #     f"Added {int(deed_points)} pts to {selected_student_name}.",
                    #     "success",
                    # )
                    st.success(
                        f"Added {int(deed_points)} pts to {selected_student_name}."
                    )
                except Exception as e:
                    # _flash(f"❌ {e}", "error")
                    st.error(f"❌ {e}")

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

                        # QR ADD submit handler
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
                                            "sid": int(sid),
                                            "tid": teacher_id,
                                            "cat": cat,
                                            "reason": reason,
                                            "pts": int(pts),
                                            "ts": datetime.now(),
                                        },
                                    )
                                st.success(f"Added {int(pts)} pts to {student.name}.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ {e}")

    # -------- TAB 2: Class Insights --------
    with tabs[2]:
        # ---  📈 Class Performance Insights (defensive & Decimal-safe) ---
        st.subheader("📈 Class Performance Insights")

        rows = []
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT student_name, live_points
                        FROM v_student_live_points
                        WHERE class_name = :cls
                        ORDER BY live_points DESC, student_name
                    """
                    ),
                    {"cls": selected_class},
                ).fetchall()

            df = pd.DataFrame(
                [(r[0], int(r[1] or 0)) for r in rows], columns=["Name", "Points"]
            )

        except Exception as e:
            st.error(f"Failed to load class points: {e}")
            rows = []

        if not rows:
            st.info("No points data yet for this class.")
        else:
            # Ensure we hand Pandas a plain list of tuples (not Row objects)
            data = [(r[0], r[1]) for r in rows]
            df_points = pd.DataFrame(data, columns=["Name", "Points"])

            # Coerce Decimals/None safely -> int
            df_points["Points"] = (
                df_points["Points"]
                .apply(lambda x: 0 if x is None else int(float(x)))
                .astype(int)
            )

            st.markdown("**Total Points by Student**")
            chart = (
                alt.Chart(df_points)
                .mark_bar()
                .encode(x=alt.X("Name:N", sort="-y"), y=alt.Y("Points:Q"))
                .properties(height=300)
            )
            st.altair_chart(chart, use_container_width=True)

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
        st.subheader("🏅 Top 3 Students & Details")

        # live_points = sum(activities.points) - sum(approved redemptions cost)
        # Top 3 & Bottom 3 by live_points
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT student_id, student_name, earned_points, spent_points, live_points
                    FROM v_student_live_points
                    WHERE class_name = :cls
                    ORDER BY live_points DESC, student_name
                """
                ),
                {"cls": selected_class},
            ).fetchall()

        df = pd.DataFrame(rows, columns=["ID", "Name", "Earned", "Spent", "Live"])
        for col in ["Earned", "Spent", "Live"]:
            df[col] = df[col].apply(lambda x: int(x or 0))

        top3 = df.head(3)
        bottom3 = df.tail(3).iloc[::-1]  # lowest 3

        st.markdown("### 🥇 Top 3 (Live Points)")
        for _, r in top3.iterrows():
            with st.expander(f"{r['Name']} • {r['Live']} pts"):
                st.table(pd.DataFrame([r], columns=["Earned", "Spent", "Live"]))

        st.markdown("### 🥉 Bottom 3 (Live Points)")
        for _, r in bottom3.iterrows():
            with st.expander(f"{r['Name']} • {r['Live']} pts"):
                st.table(pd.DataFrame([r], columns=["Earned", "Spent", "Live"]))
