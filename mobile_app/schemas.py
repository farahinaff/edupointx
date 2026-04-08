from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class SignupRequest(BaseModel):
    username: str
    password: str = Field(min_length=6)
    full_name: str
    role: str
    class_name: str | None = None


class ActivityCreate(BaseModel):
    student_id: int
    category: str
    reason: str
    points: int = Field(ge=1, le=100)


class UserSummary(BaseModel):
    id: int
    username: str
    role: str
    student_id: int | None = None
    teacher_id: int | None = None
    display_name: str


class RewardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    cost: int
    stock: int
    source: str


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str
    reason: str
    points: int
    created_at: datetime


class StudentDashboard(BaseModel):
    name: str
    class_name: str
    total_points: int
    rewards: list[RewardOut]
    activities: list[ActivityOut]
    leaderboard: list[dict[str, int | str]]


class TeacherDashboard(BaseModel):
    class_name: str
    students: list[dict[str, int | str]]
    category_breakdown: list[dict[str, int | str]]
    recent_activities: list[dict[str, int | str | datetime]]


class AdminOverview(BaseModel):
    class_totals: list[dict[str, int | str]]
    rewards: list[RewardOut]
    teacher_assignments: list[dict[str, str]]
