import streamlit as st
from sqlalchemy import create_engine

cfg = st.secrets["db"]

DB_URL = f"mysql+pymysql://{cfg.user}:{cfg.password}@{cfg.host}:{cfg.port}/{cfg.database}?ssl_disabled=false"

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,  # test connection before using it, reconnect if dead
    pool_recycle=280,  # recycle connections after 280s (< 5 minutes)
    pool_size=5,  # adjust as needed
    max_overflow=10,  # allow extra if needed
)
