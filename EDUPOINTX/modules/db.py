import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy import text

cfg = st.secrets["db"]

DB_URL = f"mysql+pymysql://{cfg.user}:{cfg.password}@{cfg.host}:{cfg.port}/{cfg.database}?ssl_disabled=false"

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,  # test connection before using it, reconnect if dead
    pool_recycle=280,  # recycle connections after 280s (< 5 minutes)
    pool_size=5,  # adjust as needed
    max_overflow=10,  # allow extra if needed
)


def recalc_all_students(engine):
    with engine.begin() as tx:
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
