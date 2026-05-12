from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Activity, Redemption, Reward, Student, Teacher, TeacherClass, User


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    return hash_password(password) == stored_hash or password == stored_hash


def _parse_student_card_filename(file_name: str) -> tuple[str, str] | None:
    stem = Path(file_name).stem
    if "_" not in stem:
        return None
    low = stem.lower()
    if re.search(r"_(addpoint|addpoints|redeem|redemption)$", low):
        return None
    if re.match(r"^\d+_(addpoint|addpoints|redeem|redemption)", low):
        return None
    parts = stem.split("_")
    if len(parts) >= 3 and parts[-2].isdigit():
        name_part = "_".join(parts[:-2])
        class_name = f"{parts[-2]} {parts[-1]}"
    else:
        name_part, class_name = stem.rsplit("_", 1)
    name = " ".join(name_part.split("_"))
    if not re.search(r"[A-Za-z]", name):
        return None
    return name, class_name


def _make_unique_username(base_name: str, existing: set[str]) -> str:
    username = re.sub(r"[^a-z0-9]", "", base_name.lower())
    if not username:
        username = "student"
    candidate = username
    suffix = 1
    while candidate in existing:
        suffix += 1
        candidate = f"{username}{suffix}"
    existing.add(candidate)
    return candidate


DEMO_STUDENTS: list[tuple[str, str, str | None, int]] = [
    ("Ali Karim", "1 Bestari", "male", 120),
    ("Fatimah Zahra", "1 Bestari", "female", 150),
    ("Ahmad Fahmi", "1 Bestari", "male", 90),
    ("Muhammad Fariz", "1 Bestari", "male", 80),
    ("Ariff Ikhram", "1 Bestari", "male", 70),
    ("Ahmad Harif", "1 Bestari", "male", 75),
    ("Luqman Hakeem", "1 Bestari", "male", 65),
    ("Afiq Haziq", "1 Bestari", "male", 85),
    ("Abdurrahim Hadif", "1 Bestari", "male", 95),
    ("Siti Nabila", "2 Amanah", "female", 180),
    ("Muhammad Danial", "2 Amanah", "male", 160),
    ("Nur Alisha", "2 Amanah", "female", 105),
    ("Iman Darwisy", "2 Amanah", "male", 115),
    ("Aqil Danish", "3 Cemerlang", "male", 140),
    ("Aishah Humaira", "3 Cemerlang", "female", 130),
    ("Faris Aiman", "3 Cemerlang", "male", 110),
    ("Nur Farzana", "3 Cemerlang", "female", 100),
    ("Ammar Zikri", "4 Bestari", "male", 125),
    ("Nur Adriana", "4 Bestari", "female", 118),
    ("Irfan Khairi", "4 Bestari", "male", 108),
    ("Haziq Afiq", "4 Cemerlang", "male", 90),
    ("Sofea Humaira", "4 Cemerlang", "female", 97),
    ("Aiman Luqman", "5 Bestari", "male", 135),
    ("Nur Atikah", "5 Bestari", "female", 128),
    ("Alya Natasha", "5 Cemerlang", "female", 122),
    ("Adam Harris", "5 Cemerlang", "male", 112),
]


REQUESTED_DEMO_STUDENT_NAMES = {
    "Muhammad Fariz",
    "Ariff Ikhram",
    "Ahmad Harif",
    "Luqman Hakeem",
    "Afiq Haziq",
    "Abdurrahim Hadif",
}


DEMO_TEACHERS: list[tuple[str, str | None, str, str, list[str]]] = [
    ("Mr. Hassan", "male", "hassan", "teacher", ["1 Bestari", "2 Amanah"]),
    ("Ms. Aishah", "female", "aishah", "admin", ["1 Bestari", "2 Amanah", "3 Cemerlang", "4 Bestari", "4 Cemerlang", "5 Bestari", "5 Cemerlang"]),
    ("Cikgu Zainab", "female", "zainab", "teacher", ["3 Cemerlang", "4 Cemerlang"]),
    ("Cikgu Faizal", "male", "faizal", "teacher", ["4 Bestari", "5 Bestari"]),
    ("Cikgu Maryam", "female", "maryam", "teacher", ["5 Cemerlang"]),
]


DEMO_REWARDS: list[tuple[str, str, int, int, str]] = [
    ("Stationery Set", "Includes pens, pencils and a ruler.", 100, 10, "Coop"),
    ("Canteen Voucher", "RM5 food voucher for the school canteen.", 150, 8, "Canteen"),
    ("Library Fast Pass", "Priority checkout for the school library.", 200, 4, "Coop"),
    ("Notebook Pack", "Exercise books for class notes.", 80, 12, "Coop"),
    ("Healthy Snack", "Snack redemption from the canteen.", 60, 15, "Canteen"),
]


def _get_student(session: Session, name: str, class_name: str) -> Student | None:
    return session.scalar(
        select(Student).where(
            func.lower(Student.name) == name.lower(),
            func.lower(Student.class_name) == class_name.lower(),
        )
    )


def _get_teacher(session: Session, name: str) -> Teacher | None:
    return session.scalar(select(Teacher).where(func.lower(Teacher.name) == name.lower()))


def _get_reward(session: Session, name: str) -> Reward | None:
    return session.scalar(select(Reward).where(func.lower(Reward.name) == name.lower()))


def _ensure_student(session: Session, name: str, class_name: str, gender: str | None, points: int) -> Student:
    student = _get_student(session, name, class_name)
    if student is None:
        student = Student(name=name, class_name=class_name, gender=gender, total_points=points)
        session.add(student)
        session.flush()
    else:
        if gender and not student.gender:
            student.gender = gender
    return student


def _ensure_teacher(session: Session, name: str, gender: str | None) -> Teacher:
    teacher = _get_teacher(session, name)
    if teacher is None:
        teacher = Teacher(name=name, gender=gender)
        session.add(teacher)
        session.flush()
    else:
        if gender and not teacher.gender:
            teacher.gender = gender
    return teacher


def _ensure_reward(session: Session, name: str, description: str, cost: int, stock: int, source: str) -> Reward:
    reward = _get_reward(session, name)
    if reward is None:
        reward = Reward(name=name, description=description, cost=cost, stock=stock, source=source)
        session.add(reward)
        session.flush()
    return reward


def _ensure_user(
    session: Session,
    username_base: str,
    role: str,
    existing_usernames: set[str],
    student_id: int | None = None,
    teacher_id: int | None = None,
    reset_password: bool = True,
) -> User:
    linked_user = None
    if student_id is not None:
        linked_user = session.scalar(select(User).where(User.student_id == student_id))
    elif teacher_id is not None:
        linked_user = session.scalar(select(User).where(User.teacher_id == teacher_id))

    if linked_user is not None:
        if reset_password:
            linked_user.password_hash = hash_password("password123")
        if linked_user.role != role:
            linked_user.role = role
        existing_usernames.add(linked_user.username)
        return linked_user

    preferred_username = re.sub(r"[^a-z0-9]", "", username_base.lower()) or role
    existing = session.scalar(select(User).where(User.username == preferred_username))
    if existing is None and preferred_username not in existing_usernames:
        username = preferred_username
        existing_usernames.add(username)
    else:
        username = _make_unique_username(username_base, existing_usernames)

    user = User(
        username=username,
        password_hash=hash_password("password123"),
        role=role,
        student_id=student_id,
        teacher_id=teacher_id,
    )
    session.add(user)
    session.flush()
    return user


def _ensure_teacher_class(session: Session, teacher_id: int, class_name: str) -> None:
    existing = session.scalar(
        select(TeacherClass).where(
            TeacherClass.teacher_id == teacher_id,
            TeacherClass.class_name == class_name,
        )
    )
    if existing is None:
        session.add(TeacherClass(teacher_id=teacher_id, class_name=class_name))


def ensure_demo_data(session: Session, qr_cards_dir: Path) -> None:
    existing_usernames: set[str] = set(session.scalars(select(User.username)).all())

    seeded_students: dict[tuple[str, str], Student] = {}
    for name, class_name, gender, points in DEMO_STUDENTS:
        student = _ensure_student(session, name, class_name, gender, points)
        seeded_students[(name.lower(), class_name.lower())] = student
        _ensure_user(
            session,
            name,
            "student",
            existing_usernames,
            student_id=student.id,
            reset_password=name in REQUESTED_DEMO_STUDENT_NAMES,
        )

    # Seed additional demo students from existing combined QR cards only when the
    # database is empty. This avoids creating students from generated QR action files.
    if session.scalar(select(func.count()).select_from(Student)) <= len(seeded_students) and qr_cards_dir.exists():
        for file_path in sorted(qr_cards_dir.glob("*.png")):
            parsed = _parse_student_card_filename(file_path.name)
            if not parsed:
                continue
            name, class_name = parsed
            key = (name.lower(), class_name.lower())
            if key in seeded_students:
                continue
            student = _ensure_student(session, name, class_name, None, 0)
            seeded_students[key] = student
            _ensure_user(session, name, "student", existing_usernames, student_id=student.id)

    teachers_by_username: dict[str, Teacher] = {}
    for name, gender, username, role, class_names in DEMO_TEACHERS:
        teacher = _ensure_teacher(session, name, gender)
        teachers_by_username[username] = teacher
        _ensure_user(session, username, role, existing_usernames, teacher_id=teacher.id)
        for class_name in class_names:
            _ensure_teacher_class(session, teacher.id, class_name)

    rewards = [_ensure_reward(session, *reward_data) for reward_data in DEMO_REWARDS]
    session.flush()

    if session.scalar(select(func.count()).select_from(Activity)) == 0:
        hassan = teachers_by_username.get("hassan")
        aishah = teachers_by_username.get("aishah")
        sample_activities = [
            ("Ali Karim", "1 Bestari", hassan, "Discipline", 20, "Picked up trash after assembly"),
            ("Fatimah Zahra", "1 Bestari", hassan, "Leadership", 30, "Led group project presentation"),
            ("Muhammad Fariz", "1 Bestari", hassan, "Academics", 25, "Completed homework early"),
            ("Afiq Haziq", "1 Bestari", hassan, "Sports", 15, "Helped team during training"),
            ("Siti Nabila", "2 Amanah", aishah, "Academic", 40, "Top scorer in mathematics test"),
            ("Aqil Danish", "3 Cemerlang", aishah, "Volunteerism", 20, "Helped arrange classroom materials"),
        ]
        for name, class_name, teacher, category, points, reason in sample_activities:
            student = _get_student(session, name, class_name)
            if student is not None:
                session.add(
                    Activity(
                        student_id=student.id,
                        teacher_id=teacher.id if teacher else None,
                        category=category,
                        points=points,
                        reason=reason,
                        created_at=datetime(2025, 7, 13, 13, 58, 28),
                    )
                )
        if rewards:
            ali = _get_student(session, "Ali Karim", "1 Bestari")
            if ali is not None:
                session.add(
                    Redemption(
                        student_id=ali.id,
                        reward_id=rewards[0].id,
                        status="approved",
                        created_at=datetime(2025, 7, 15, 9, 30, 0),
                    )
                )
    session.commit()


def recalc_student_points(session: Session, student_id: int) -> int:
    session.flush()
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
