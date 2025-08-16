import pymysql
from sqlalchemy import create_engine, text
import hashlib

from modules.db import DB_URL

engine = create_engine(DB_URL)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def login_user(username, password):
    # hashed = hash_password(password)
    hashed = password
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """ SELECT id, username, role, student_id, teacher_id FROM users WHERE username = :username AND password_hash = :hashed """
            ),
            {"username": username, "hashed": hashed},
        ).fetchone()

    if result:
        return dict(result._mapping)
    return None
