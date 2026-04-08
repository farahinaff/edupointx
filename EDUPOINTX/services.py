from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Activity, Redemption, Reward, Student, Teacher, TeacherClass, User


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    return hash_password(password) == stored_hash or password == stored_hash


def ensure_demo_data(session: Session) -> None:
    if session.scalar(select(func.count()).select_from(User)) > 0:
        return

    students = [
        Student(name="Ali Karim", class_name="1 Bestari", gender="male", total_points=120),
        Student(name="Fatimah Zahra", class_name="1 Bestari", gender="female", total_points=150),
        Student(name="Ahmad Fahmi", class_name="1 Bestari", gender="male", total_points=90),
        Student(name="Siti Nabila", class_name="2 Amanah", gender="female", total_points=180),
        Student(name="Muhammad Danial", class_name="2 Amanah", gender="male", total_points=160),
    ]
    teachers = [Teacher(name="Mr. Hassan", gender="male"), Teacher(name="Ms. Aishah", gender="female")]
    rewards = [
        Reward(
            name="Stationery Set",
            description="Includes pens, pencils and a ruler.",
            cost=100,
            stock=10,
            source="School",
        ),
        Reward(
            name="Canteen Voucher",
            description="RM5 food voucher for the school canteen.",
            cost=150,
            stock=5,
            source="Canteen",
        ),
        Reward(
            name="Library Fast Pass",
            description="Priority checkout for the school library.",
            cost=200,
            stock=4,
            source="Library",
        ),
    ]
    session.add_all(students + teachers + rewards)
    session.flush()

    session.add_all(
        [
            TeacherClass(teacher_id=teachers[0].id, class_name="1 Bestari"),
            TeacherClass(teacher_id=teachers[1].id, class_name="2 Amanah"),
        ]
    )
    session.add_all(
        [
            Activity(
                student_id=students[0].id,
                teacher_id=teachers[0].id,
                category="Discipline",
                points=20,
                reason="Picked up trash after assembly",
                created_at=datetime(2025, 7, 13, 13, 58, 28),
            ),
            Activity(
                student_id=students[1].id,
                teacher_id=teachers[0].id,
                category="Leadership",
                points=30,
                reason="Led group project presentation",
                created_at=datetime(2025, 7, 13, 13, 58, 28),
            ),
            Activity(
                student_id=students[3].id,
                teacher_id=teachers[1].id,
                category="Academic",
                points=40,
                reason="Top scorer in mathematics test",
                created_at=datetime(2025, 7, 13, 13, 58, 28),
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            User(
                username="ali",
                password_hash=hash_password("password123"),
                role="student",
                student_id=students[0].id,
            ),
            User(
                username="fatimah",
                password_hash=hash_password("password123"),
                role="student",
                student_id=students[1].id,
            ),
            User(
                username="hassan",
                password_hash=hash_password("password123"),
                role="teacher",
                teacher_id=teachers[0].id,
            ),
            User(
                username="aishah",
                password_hash=hash_password("password123"),
                role="admin",
                teacher_id=teachers[1].id,
            ),
        ]
    )
    session.add(
        Redemption(
            student_id=students[0].id,
            reward_id=rewards[0].id,
            status="approved",
            created_at=datetime(2025, 7, 15, 9, 30, 0),
        )
    )
    session.commit()


def recalc_student_points(session: Session, student_id: int) -> int:
    earned = session.scalar(
        select(func.coalesce(func.sum(Activity.points), 0)).where(Activity.student_id == student_id)
    )
    spent = session.scalar(
        select(func.coalesce(func.sum(Reward.cost), 0))
        .select_from(Redemption)
        .join(Reward, Reward.id == Redemption.reward_id)
        .where(Redemption.student_id == student_id, Redemption.status == "approved")
    )
    total = int(earned or 0) - int(spent or 0)
    student = session.get(Student, student_id)
    if student:
        student.total_points = total
        session.flush()
    return total
