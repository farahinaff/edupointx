from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import Activity, Reward, Student, Teacher, TeacherClass, User
from .schemas import (
    ActivityCreate,
    AdminOverview,
    LoginRequest,
    SignupRequest,
    StudentDashboard,
    TeacherDashboard,
    UserSummary,
)
from .services import ensure_demo_data, hash_password, verify_password


STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="EduPointX Mobile",
    description="Mobile-first EduPointX PWA backed by a free SQLite database.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        ensure_demo_data(session)


@app.get("/")
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/manifest.webmanifest")
def manifest() -> FileResponse:
    return FileResponse(STATIC_DIR / "manifest.webmanifest")


@app.get("/service-worker.js")
def service_worker() -> FileResponse:
    return FileResponse(STATIC_DIR / "service-worker.js")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/classes")
def classes(db: Session = Depends(get_db)) -> list[str]:
    return list(
        db.scalars(select(Student.class_name).distinct().order_by(Student.class_name))
    )


@app.post("/api/auth/login", response_model=UserSummary)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> UserSummary:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    display_name = payload.username
    if user.student_id:
        student = db.get(Student, user.student_id)
        display_name = student.name if student else payload.username
    elif user.teacher_id:
        teacher = db.get(Teacher, user.teacher_id)
        display_name = teacher.name if teacher else payload.username

    return UserSummary(
        id=user.id,
        username=user.username,
        role=user.role,
        student_id=user.student_id,
        teacher_id=user.teacher_id,
        display_name=display_name,
    )


@app.post("/api/auth/signup", response_model=UserSummary)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> UserSummary:
    role = payload.role.lower()
    if role not in {"student", "teacher"}:
        raise HTTPException(status_code=400, detail="Role must be student or teacher.")
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status_code=409, detail="Username already exists.")

    student_id = None
    teacher_id = None
    if role == "student":
        if not payload.class_name:
            raise HTTPException(status_code=400, detail="Students must select a class.")
        student = Student(
            name=payload.full_name,
            class_name=payload.class_name,
            total_points=0,
        )
        db.add(student)
        db.flush()
        student_id = student.id
    else:
        teacher = Teacher(name=payload.full_name)
        db.add(teacher)
        db.flush()
        teacher_id = teacher.id

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=role,
        student_id=student_id,
        teacher_id=teacher_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserSummary(
        id=user.id,
        username=user.username,
        role=user.role,
        student_id=user.student_id,
        teacher_id=user.teacher_id,
        display_name=payload.full_name,
    )


@app.get("/api/rewards")
def rewards(db: Session = Depends(get_db)) -> list[dict[str, int | str]]:
    items = db.scalars(select(Reward).order_by(Reward.cost)).all()
    return [
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "cost": item.cost,
            "stock": item.stock,
            "source": item.source,
        }
        for item in items
    ]


@app.get("/api/students/{student_id}/dashboard", response_model=StudentDashboard)
def student_dashboard(student_id: int, db: Session = Depends(get_db)) -> StudentDashboard:
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    rewards = db.scalars(
        select(Reward).where(Reward.stock > 0).order_by(Reward.cost)
    ).all()
    activities = db.scalars(
        select(Activity)
        .where(Activity.student_id == student_id)
        .order_by(desc(Activity.created_at))
    ).all()
    leaderboard_rows = db.scalars(
        select(Student)
        .where(Student.class_name == student.class_name)
        .order_by(desc(Student.total_points))
        .limit(3)
    ).all()

    return StudentDashboard(
        name=student.name,
        class_name=student.class_name,
        total_points=student.total_points,
        rewards=rewards,
        activities=activities,
        leaderboard=[{"name": row.name, "points": row.total_points} for row in leaderboard_rows],
    )


@app.get("/api/teachers/{teacher_id}/classes")
def teacher_classes(teacher_id: int, db: Session = Depends(get_db)) -> list[str]:
    return list(
        db.scalars(
            select(TeacherClass.class_name)
            .where(TeacherClass.teacher_id == teacher_id)
            .order_by(TeacherClass.class_name)
        )
    )


@app.get("/api/teachers/{teacher_id}/dashboard", response_model=TeacherDashboard)
def teacher_dashboard(
    teacher_id: int, class_name: str, db: Session = Depends(get_db)
) -> TeacherDashboard:
    allowed = db.scalar(
        select(TeacherClass).where(
            TeacherClass.teacher_id == teacher_id,
            TeacherClass.class_name == class_name,
        )
    )
    if not allowed:
        raise HTTPException(
            status_code=403, detail="Teacher is not assigned to this class."
        )

    students = db.scalars(
        select(Student)
        .where(Student.class_name == class_name)
        .order_by(desc(Student.total_points), Student.name)
    ).all()
    category_rows = db.execute(
        select(Activity.category, func.count(Activity.id))
        .join(Student, Student.id == Activity.student_id)
        .where(Student.class_name == class_name)
        .group_by(Activity.category)
        .order_by(desc(func.count(Activity.id)))
    ).all()
    activity_rows = db.execute(
        select(
            Student.name, Activity.category, Activity.points, Activity.reason, Activity.created_at
        )
        .join(Student, Student.id == Activity.student_id)
        .where(Student.class_name == class_name)
        .order_by(desc(Activity.created_at))
        .limit(8)
    ).all()

    return TeacherDashboard(
        class_name=class_name,
        students=[{"id": row.id, "name": row.name, "points": row.total_points} for row in students],
        category_breakdown=[{"category": category, "count": count} for category, count in category_rows],
        recent_activities=[
            {
                "student_name": student_name,
                "category": category,
                "points": points,
                "reason": reason,
                "created_at": created_at,
            }
            for student_name, category, points, reason, created_at in activity_rows
        ],
    )


@app.post("/api/teachers/{teacher_id}/activities")
def add_activity(
    teacher_id: int, payload: ActivityCreate, db: Session = Depends(get_db)
) -> dict[str, str]:
    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    allowed = db.scalar(
        select(TeacherClass).where(
            TeacherClass.teacher_id == teacher_id,
            TeacherClass.class_name == student.class_name,
        )
    )
    if not allowed:
        raise HTTPException(
            status_code=403, detail="Teacher is not assigned to this student's class."
        )

    activity = Activity(
        student_id=payload.student_id,
        teacher_id=teacher_id,
        category=payload.category,
        points=payload.points,
        reason=payload.reason,
    )
    student.total_points += payload.points
    db.add(activity)
    db.commit()
    return {"message": "Activity added successfully."}


@app.get("/api/admin/overview", response_model=AdminOverview)
def admin_overview(db: Session = Depends(get_db)) -> AdminOverview:
    class_totals = db.execute(
        select(Student.class_name, func.count(Student.id), func.sum(Student.total_points))
        .group_by(Student.class_name)
        .order_by(Student.class_name)
    ).all()
    teacher_assignments = db.execute(
        select(Teacher.name, TeacherClass.class_name)
        .join(TeacherClass, TeacherClass.teacher_id == Teacher.id)
        .order_by(Teacher.name, TeacherClass.class_name)
    ).all()
    rewards = db.scalars(select(Reward).order_by(Reward.cost)).all()

    return AdminOverview(
        class_totals=[
            {
                "class_name": class_name,
                "student_count": student_count,
                "total_points": total_points or 0,
            }
            for class_name, student_count, total_points in class_totals
        ],
        rewards=rewards,
        teacher_assignments=[
            {"teacher_name": teacher_name, "class_name": class_name}
            for teacher_name, class_name in teacher_assignments
        ],
    )
