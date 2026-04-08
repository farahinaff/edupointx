from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    class_name: Mapped[str] = mapped_column(String(50), nullable=False)
    total_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    activities: Mapped[list["Activity"]] = relationship(back_populates="student")
    user: Mapped["User | None"] = relationship(back_populates="student", uselist=False)


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    activities: Mapped[list["Activity"]] = relationship(back_populates="teacher")
    classes: Mapped[list["TeacherClass"]] = relationship(back_populates="teacher")
    user: Mapped["User | None"] = relationship(back_populates="teacher", uselist=False)


class TeacherClass(Base):
    __tablename__ = "teacher_class"

    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), primary_key=True)
    class_name: Mapped[str] = mapped_column(String(50), primary_key=True)

    teacher: Mapped[Teacher] = relationship(back_populates="classes")


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"))
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    student: Mapped[Student] = relationship(back_populates="activities")
    teacher: Mapped[Teacher | None] = relationship(back_populates="activities")


class Reward(Base):
    __tablename__ = "rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cost: Mapped[int] = mapped_column(Integer, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="School", nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"))
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"))

    student: Mapped[Student | None] = relationship(back_populates="user")
    teacher: Mapped[Teacher | None] = relationship(back_populates="user")
