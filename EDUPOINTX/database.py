from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
RENDER_DATA_DIR = Path("/var/data")
DATA_DIR = RENDER_DATA_DIR if RENDER_DATA_DIR.exists() else BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DB_PATH = DATA_DIR / "edupointx.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def ensure_legacy_sqlite_compatibility() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    column_additions = {
        "students": {
            "gender": "ALTER TABLE students ADD COLUMN gender VARCHAR(20)",
        },
        "teachers": {
            "gender": "ALTER TABLE teachers ADD COLUMN gender VARCHAR(20)",
        },
        "rewards": {
            "source": "ALTER TABLE rewards ADD COLUMN source VARCHAR(30) DEFAULT 'School' NOT NULL",
        },
    }

    with engine.begin() as conn:
        for table_name, additions in column_additions.items():
            if table_name not in existing_tables:
                continue
            current_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in additions.items():
                if column_name not in current_columns:
                    conn.execute(text(ddl))
