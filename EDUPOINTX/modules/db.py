import streamlit as st
from sqlalchemy import create_engine

cfg = st.secrets["db"]

DB_URL = f"mysql+pymysql://{cfg.user}:{cfg.password}@{cfg.host}:{cfg.port}/{cfg.database}?ssl_disabled=false"
engine = create_engine(DB_URL)
