from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, ensure_legacy_sqlite_compatibility
from .models import Activity, Redemption, Reward, Student, Teacher, TeacherClass, User
from .services import ensure_demo_data, hash_password, recalc_student_points, verify_password


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
LEGACY_ASSETS_DIR = APP_DIR / "assets"

app = FastAPI(
    title="EduPointX Mobile",
    description="Publishable mobile web version of the original EduPointX flow.",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if LEGACY_ASSETS_DIR.exists():
    app.mount("/legacy-assets", StaticFiles(directory=LEGACY_ASSETS_DIR), name="legacy-assets")


class LoginRequest(BaseModel):
    username: str
    password: str


class SignupRequest(BaseModel):
    username: str
    password: str = Field(min_length=1)
    full_name: str
    role: str
    gender: str | None = None
    class_name: str | None = None


class ActivityCreate(BaseModel):
    student_id: int
    category: str
    reason: str
    points: int = Field(ge=1, le=100)


class ActivityBulkCreate(BaseModel):
    student_ids: list[int] = Field(min_length=1)
    category: str
    reason: str
    points: int = Field(ge=1, le=100)


class RedemptionRequest(BaseModel):
    student_id: int
    reward_id: int


class RewardCreate(BaseModel):
    name: str
    description: str
    cost: int = Field(ge=1)
    stock: int = Field(ge=0)
    source: str


class RewardUpdate(BaseModel):
    cost: int = Field(ge=1)
    stock: int = Field(ge=0)


class TeacherAssignmentRequest(BaseModel):
    teacher_id: int
    class_name: str
    assign: bool


class PasswordResetRequest(BaseModel):
    username: str


class RedemptionDecisionItem(BaseModel):
    id: int
    decision: str


class RedemptionDecisionRequest(BaseModel):
    items: list[RedemptionDecisionItem]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_display_name(user: User, db: Session) -> str:
    if user.student_id:
        student = db.get(Student, user.student_id)
        return student.name if student else user.username
    if user.teacher_id:
        teacher = db.get(Teacher, user.teacher_id)
        return teacher.name if teacher else user.username
    return user.username


def decode_qr_strings(image_bytes: bytes) -> list[str]:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="QR scanning dependency is not installed.") from exc

    np_bytes = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(np_bytes, cv2.IMREAD_COLOR)
    if image is None:
        return []

    detector = cv2.QRCodeDetector()
    decoded: list[str] = []

    retval, decoded_info, _points, _ = detector.detectAndDecodeMulti(image)
    if retval and decoded_info:
        decoded.extend([item.strip() for item in decoded_info if item and item.strip()])

    if not decoded:
        single, _points, _ = detector.detectAndDecode(image)
        if single and single.strip():
            decoded.append(single.strip())

    uniq: list[str] = []
    seen: set[str] = set()
    for item in decoded:
        if item not in seen:
            uniq.append(item)
            seen.add(item)
    return uniq


def choose_addpoints_sid(decoded_list: list[str]) -> tuple[str | None, str | None]:
    for raw in decoded_list:
        low = raw.lower()
        is_add = ("mode=deed" in low) or ("action=addpoints" in low)
        if is_add and "sid=" in low:
            parts = raw.split("sid=", 1)
            if len(parts) == 2:
                sid = parts[1].split("&", 1)[0].strip()
                return raw, sid
    return None, None


def get_students_for_activity(db: Session, student_ids: list[int]) -> list[Student]:
    unique_ids = list(dict.fromkeys(student_ids))
    if not unique_ids:
        raise HTTPException(status_code=400, detail="Select at least one student.")
    students = db.scalars(select(Student).where(Student.id.in_(unique_ids))).all()
    students_by_id = {student.id: student for student in students}
    missing_ids = [student_id for student_id in unique_ids if student_id not in students_by_id]
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Student(s) not found: {', '.join(str(student_id) for student_id in missing_ids)}.",
        )
    return [students_by_id[student_id] for student_id in unique_ids]


def ensure_teacher_can_award_students(db: Session, teacher_id: int, students: list[Student]) -> None:
    user = db.scalar(select(User).where(User.teacher_id == teacher_id))
    is_admin = bool(user and user.role == "admin")
    if is_admin:
        return

    class_names = sorted({student.class_name for student in students})
    assigned_classes = set(
        db.scalars(
            select(TeacherClass.class_name).where(
                TeacherClass.teacher_id == teacher_id,
                TeacherClass.class_name.in_(class_names),
            )
        )
    )
    unauthorized_classes = [class_name for class_name in class_names if class_name not in assigned_classes]
    if unauthorized_classes:
        raise HTTPException(
            status_code=403,
            detail=f"Teacher is not assigned to class(es): {', '.join(unauthorized_classes)}.",
        )


def build_student_points_rows(db: Session, class_name: str) -> list[dict[str, int | str]]:
    students = db.scalars(
        select(Student).where(Student.class_name == class_name).order_by(Student.name)
    ).all()
    rows = []
    for student in students:
        earned = db.scalar(
            select(func.coalesce(func.sum(Activity.points), 0)).where(Activity.student_id == student.id)
        )
        spent = db.scalar(
            select(func.coalesce(func.sum(Reward.cost), 0))
            .select_from(Redemption)
            .join(Reward, Reward.id == Redemption.reward_id)
            .where(Redemption.student_id == student.id, Redemption.status == "approved")
        )
        live_points = int(earned or 0) - int(spent or 0)
        rows.append(
            {
                "student_id": student.id,
                "student_name": student.name,
                "earned_points": int(earned or 0),
                "spent_points": int(spent or 0),
                "live_points": live_points,
            }
        )
    rows.sort(key=lambda row: (-int(row["live_points"]), str(row["student_name"])))
    return rows


def build_student_dashboard(db: Session, student_id: int) -> dict:
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    recalc_student_points(db, student_id)
    db.commit()
    db.refresh(student)

    rewards = db.scalars(select(Reward).where(Reward.stock > 0).order_by(Reward.cost)).all()
    activities = db.scalars(
        select(Activity).where(Activity.student_id == student_id).order_by(desc(Activity.created_at))
    ).all()
    redemptions = db.execute(
        select(Reward.name, Redemption.status, Redemption.created_at)
        .join(Redemption, Redemption.reward_id == Reward.id)
        .where(Redemption.student_id == student_id)
        .order_by(desc(Redemption.created_at))
    ).all()
    leaderboard_rows = build_student_points_rows(db, student.class_name)

    trend = {}
    for activity in reversed(activities):
        key = activity.created_at.date().isoformat()
        trend[key] = trend.get(key, 0) + int(activity.points)

    return {
        "student": {
            "id": student.id,
            "name": student.name,
            "gender": student.gender,
            "class_name": student.class_name,
            "total_points": student.total_points,
        },
        "rewards": [
            {
                "id": reward.id,
                "name": reward.name,
                "description": reward.description,
                "cost": reward.cost,
                "stock": reward.stock,
                "source": reward.source,
            }
            for reward in rewards
        ],
        "redemptions": [
            {"reward": name, "status": status, "date": created_at.isoformat()}
            for name, status, created_at in redemptions
        ],
        "activities": [
            {
                "category": activity.category,
                "reason": activity.reason,
                "points": activity.points,
                "date": activity.created_at.isoformat(),
            }
            for activity in activities
        ],
        "leaderboard": leaderboard_rows,
        "trend": [{"date": date, "points": points} for date, points in trend.items()],
    }


def build_teacher_dashboard(db: Session, teacher_id: int, class_name: str, is_admin: bool) -> dict:
    if not is_admin:
        allowed = db.scalar(
            select(TeacherClass).where(
                TeacherClass.teacher_id == teacher_id,
                TeacherClass.class_name == class_name,
            )
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="Teacher is not assigned to this class.")

    students = db.scalars(
        select(Student).where(Student.class_name == class_name).order_by(Student.name)
    ).all()
    student_rows = build_student_points_rows(db, class_name)
    categories = db.execute(
        select(Activity.category, func.count(Activity.id), func.coalesce(func.sum(Activity.points), 0))
        .join(Student, Student.id == Activity.student_id)
        .where(Student.class_name == class_name)
        .group_by(Activity.category)
        .order_by(desc(func.coalesce(func.sum(Activity.points), 0)))
    ).all()

    recent = db.execute(
        select(Student.name, Activity.category, Activity.reason, Activity.points, Activity.created_at)
        .join(Student, Student.id == Activity.student_id)
        .where(Student.class_name == class_name)
        .order_by(desc(Activity.created_at))
        .limit(20)
    ).all()

    return {
        "class_name": class_name,
        "students": [{"id": student.id, "name": student.name} for student in students],
        "class_points": [
            {"name": row["student_name"], "points": row["live_points"]} for row in student_rows
        ],
        "categories": [
            {"category": category, "count": int(count), "total_points": int(total_points)}
            for category, count, total_points in categories
        ],
        "top3": student_rows[:3],
        "bottom3": list(reversed(student_rows[-3:])) if student_rows else [],
        "recent": [
            {
                "student_name": student_name,
                "category": category,
                "reason": reason,
                "points": points,
                "date": created_at.isoformat(),
            }
            for student_name, category, reason, points, created_at in recent
        ],
    }


def build_admin_dashboard(db: Session, selected_class: str | None, redemption_status: str = "pending") -> dict:
    class_names = list(db.scalars(select(Student.class_name).distinct().order_by(Student.class_name)))
    class_name = selected_class or (class_names[0] if class_names else None)

    students = []
    assigned_teachers = []
    if class_name:
        class_students = db.scalars(
            select(Student).where(Student.class_name == class_name).order_by(Student.name)
        ).all()
        students = [{"id": s.id, "name": s.name, "points": s.total_points} for s in class_students]
        assigned_teachers = db.execute(
            select(Teacher.name)
            .join(TeacherClass, TeacherClass.teacher_id == Teacher.id)
            .where(TeacherClass.class_name == class_name)
            .order_by(Teacher.name)
        ).all()

    teachers = db.scalars(select(Teacher).order_by(Teacher.name)).all()
    assignments = db.execute(
        select(TeacherClass.teacher_id, TeacherClass.class_name)
    ).all()
    assignment_set = {(teacher_id, class_name_value) for teacher_id, class_name_value in assignments}

    rewards = db.scalars(select(Reward).order_by(Reward.name)).all()

    redemption_rows = db.execute(
        select(
            Redemption.id,
            Student.id,
            Student.name,
            Student.class_name,
            Student.total_points,
            Reward.id,
            Reward.name,
            Reward.cost,
            Reward.stock,
            Redemption.status,
            Redemption.created_at,
        )
        .join(Student, Student.id == Redemption.student_id)
        .join(Reward, Reward.id == Redemption.reward_id)
        .order_by(desc(Redemption.created_at))
    ).all()

    filtered_redemptions = []
    for row in redemption_rows:
        (
            redemption_id,
            student_id,
            _student_name,
            student_class,
            total_points,
            reward_id,
            reward_name,
            cost,
            stock,
            status,
            created_at,
        ) = row
        insufficient = status == "pending" and (int(total_points) < int(cost) or int(stock) <= 0)
        if redemption_status == "insufficient" and not insufficient:
            continue
        if redemption_status != "insufficient" and status != redemption_status:
            continue
        if class_name and student_class != class_name:
            continue
        filtered_redemptions.append(
            {
                "id": redemption_id,
                "student_id": student_id,
                "reward_id": reward_id,
                "student_name": row[2],
                "class_name": student_class,
                "points": int(total_points),
                "reward_name": reward_name,
                "cost": int(cost),
                "stock": int(stock),
                "status": status,
                "date": created_at.isoformat(),
                "insufficient": insufficient,
            }
        )

    status_rows = db.execute(
        select(Redemption.status, func.count(Redemption.id)).group_by(Redemption.status)
    ).all()
    total_spent = db.scalar(
        select(func.coalesce(func.sum(Reward.cost), 0))
        .select_from(Redemption)
        .join(Reward, Reward.id == Redemption.reward_id)
        .where(Redemption.status == "approved")
    )
    top_rewards = db.execute(
        select(Reward.name, func.count(Redemption.id))
        .join(Redemption, Redemption.reward_id == Reward.id)
        .where(Redemption.status == "approved")
        .group_by(Reward.id, Reward.name)
        .order_by(desc(func.count(Redemption.id)))
        .limit(10)
    ).all()
    top_students = db.execute(
        select(Student.name, func.count(Redemption.id), func.coalesce(func.sum(Reward.cost), 0))
        .join(Redemption, Redemption.student_id == Student.id)
        .join(Reward, Reward.id == Redemption.reward_id)
        .where(Redemption.status == "approved")
        .group_by(Student.id, Student.name)
        .order_by(desc(func.count(Redemption.id)))
        .limit(10)
    ).all()
    timeline = db.execute(
        select(func.date(Redemption.created_at), func.count(Redemption.id))
        .where(Redemption.status == "approved")
        .group_by(func.date(Redemption.created_at))
        .order_by(func.date(Redemption.created_at))
    ).all()

    transaction_query = (
        select(
            Activity.id,
            Student.id,
            Student.name,
            Student.class_name,
            Teacher.name,
            Activity.category,
            Activity.reason,
            Activity.points,
            Activity.created_at,
        )
        .join(Student, Student.id == Activity.student_id)
        .outerjoin(Teacher, Teacher.id == Activity.teacher_id)
        .order_by(desc(Activity.created_at), desc(Activity.id))
        .limit(100)
    )
    if class_name:
        transaction_query = transaction_query.where(Student.class_name == class_name)
    point_transactions = db.execute(transaction_query).all()

    return {
        "classes": class_names,
        "selected_class": class_name,
        "class_view": {
            "students": students,
            "teachers": [name for (name,) in assigned_teachers],
        },
        "teacher_assignment": {
            "teachers": [
                {
                    "id": teacher.id,
                    "name": teacher.name,
                    "classes": sorted([assigned_class for tid, assigned_class in assignment_set if tid == teacher.id]),
                    "assigned_to_selected_class": (teacher.id, class_name) in assignment_set if class_name else False,
                }
                for teacher in teachers
            ]
        },
        "rewards": [
            {
                "id": reward.id,
                "name": reward.name,
                "description": reward.description,
                "cost": reward.cost,
                "stock": reward.stock,
                "source": reward.source,
            }
            for reward in rewards
        ],
        "redemptions": filtered_redemptions,
        "redemption_insights": {
            "status_counts": [{"status": status, "count": int(count)} for status, count in status_rows],
            "total_spent": int(total_spent or 0),
            "top_rewards": [{"name": name, "count": int(count)} for name, count in top_rewards],
            "top_students": [
                {"name": name, "count": int(count), "spent": int(spent)} for name, count, spent in top_students
            ],
            "timeline": [{"date": str(date), "count": int(count)} for date, count in timeline],
        },
        "point_transactions": [
            {
                "id": activity_id,
                "student_id": student_id,
                "student_name": student_name,
                "class_name": student_class,
                "teacher_name": teacher_name or "Unknown",
                "category": category,
                "reason": reason,
                "points": int(points),
                "date": created_at.isoformat(),
            }
            for (
                activity_id,
                student_id,
                student_name,
                student_class,
                teacher_name,
                category,
                reason,
                points,
                created_at,
            ) in point_transactions
        ],
    }


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_legacy_sqlite_compatibility()
    with SessionLocal() as session:
        ensure_demo_data(session)
        for student in session.scalars(select(Student)).all():
            recalc_student_points(session, student.id)
        session.commit()


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
    return list(db.scalars(select(Student.class_name).distinct().order_by(Student.class_name)))


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "student_id": user.student_id,
        "teacher_id": user.teacher_id,
        "display_name": get_display_name(user, db),
    }


@app.post("/api/auth/signup")
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> dict:
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
            gender=payload.gender,
            total_points=0,
        )
        db.add(student)
        db.flush()
        student_id = student.id
    else:
        teacher = Teacher(name=payload.full_name, gender=payload.gender)
        db.add(teacher)
        db.flush()
        teacher_id = teacher.id

    user = User(
        username=payload.username,
        password_hash=payload.password,
        role=role,
        student_id=student_id,
        teacher_id=teacher_id,
    )
    db.add(user)
    db.commit()
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "student_id": user.student_id,
        "teacher_id": user.teacher_id,
        "display_name": payload.full_name,
    }


@app.get("/api/students/{student_id}/dashboard")
def student_dashboard(student_id: int, db: Session = Depends(get_db)) -> dict:
    return build_student_dashboard(db, student_id)


@app.post("/api/redemptions/request")
def request_redemption(payload: RedemptionRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    student = db.get(Student, payload.student_id)
    reward = db.get(Reward, payload.reward_id)
    if not student or not reward:
        raise HTTPException(status_code=404, detail="Student or reward not found.")
    db.add(Redemption(student_id=payload.student_id, reward_id=payload.reward_id, status="pending"))
    db.commit()
    return {"message": f"Request submitted for '{reward.name}'."}


@app.post("/api/qr/decode-addpoints")
async def decode_addpoints_qr(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    decoded = decode_qr_strings(await file.read())
    _matched, sid = choose_addpoints_sid(decoded)
    if not sid:
        raise HTTPException(status_code=400, detail="No Add Points QR found in the uploaded image.")
    try:
        student_id = int(sid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid student ID in QR.") from exc
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    return {
        "student_id": student.id,
        "name": student.name,
        "class_name": student.class_name,
        "decoded": decoded,
    }


@app.get("/api/teachers/{teacher_id}/classes")
def teacher_classes(teacher_id: int, db: Session = Depends(get_db)) -> list[str]:
    user = db.scalar(select(User).where(User.teacher_id == teacher_id))
    if user and user.role == "admin":
        return list(db.scalars(select(Student.class_name).distinct().order_by(Student.class_name)))
    return list(
        db.scalars(
            select(TeacherClass.class_name)
            .where(TeacherClass.teacher_id == teacher_id)
            .order_by(TeacherClass.class_name)
        )
    )


@app.get("/api/teachers/{teacher_id}/dashboard")
def teacher_dashboard(teacher_id: int, class_name: str, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.teacher_id == teacher_id))
    is_admin = bool(user and user.role == "admin")
    return build_teacher_dashboard(db, teacher_id, class_name, is_admin=is_admin)


@app.post("/api/teachers/{teacher_id}/activities")
def add_activity(teacher_id: int, payload: ActivityCreate, db: Session = Depends(get_db)) -> dict[str, str]:
    student = get_students_for_activity(db, [payload.student_id])[0]
    ensure_teacher_can_award_students(db, teacher_id, [student])

    db.add(
        Activity(
            student_id=payload.student_id,
            teacher_id=teacher_id,
            category=payload.category,
            reason=payload.reason,
            points=payload.points,
        )
    )
    recalc_student_points(db, payload.student_id)
    db.commit()
    return {"message": "Points added successfully."}


@app.post("/api/teachers/{teacher_id}/activities/bulk")
def add_bulk_activities(
    teacher_id: int,
    payload: ActivityBulkCreate,
    db: Session = Depends(get_db),
) -> dict[str, int | str]:
    students = get_students_for_activity(db, payload.student_ids)
    ensure_teacher_can_award_students(db, teacher_id, students)

    for student in students:
        db.add(
            Activity(
                student_id=student.id,
                teacher_id=teacher_id,
                category=payload.category,
                reason=payload.reason,
                points=payload.points,
            )
        )

    db.flush()
    for student in students:
        recalc_student_points(db, student.id)
    db.commit()
    return {"message": f"Points added to {len(students)} student(s).", "count": len(students)}


@app.get("/api/admin/dashboard")
def admin_dashboard(
    class_name: str | None = None,
    redemption_status: str = "pending",
    db: Session = Depends(get_db),
) -> dict:
    return build_admin_dashboard(db, class_name, redemption_status)


@app.post("/api/admin/teacher-assignment")
def teacher_assignment(payload: TeacherAssignmentRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    existing = db.scalar(
        select(TeacherClass).where(
            TeacherClass.teacher_id == payload.teacher_id,
            TeacherClass.class_name == payload.class_name,
        )
    )
    if payload.assign and not existing:
        db.add(TeacherClass(teacher_id=payload.teacher_id, class_name=payload.class_name))
    if not payload.assign and existing:
        db.delete(existing)
    db.commit()
    return {"message": "Teacher assignment updated."}


@app.post("/api/admin/rewards")
def create_reward(payload: RewardCreate, db: Session = Depends(get_db)) -> dict[str, str]:
    db.add(
        Reward(
            name=payload.name,
            description=payload.description,
            cost=payload.cost,
            stock=payload.stock,
            source=payload.source,
        )
    )
    db.commit()
    return {"message": "Reward created."}


@app.patch("/api/admin/rewards/{reward_id}")
def update_reward(reward_id: int, payload: RewardUpdate, db: Session = Depends(get_db)) -> dict[str, str]:
    reward = db.get(Reward, reward_id)
    if not reward:
        raise HTTPException(status_code=404, detail="Reward not found.")
    reward.cost = payload.cost
    reward.stock = payload.stock
    db.commit()
    return {"message": "Reward updated."}


@app.delete("/api/admin/rewards/{reward_id}")
def delete_reward(reward_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    reward = db.get(Reward, reward_id)
    if not reward:
        raise HTTPException(status_code=404, detail="Reward not found.")
    db.delete(reward)
    db.commit()
    return {"message": "Reward deleted."}


@app.post("/api/admin/redemptions/decide")
def decide_redemptions(payload: RedemptionDecisionRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    for item in payload.items:
        redemption = db.get(Redemption, item.id)
        if not redemption:
            continue
        decision = item.decision.strip().lower()
        if decision == "reject":
            if redemption.status == "pending":
                redemption.status = "rejected"
        elif decision == "approve":
            if redemption.status != "pending":
                continue
            student = db.get(Student, redemption.student_id)
            reward = db.get(Reward, redemption.reward_id)
            if not student or not reward:
                continue
            recalc_student_points(db, student.id)
            if student.total_points >= reward.cost and reward.stock > 0:
                redemption.status = "approved"
                reward.stock -= 1
                recalc_student_points(db, student.id)
        else:
            continue
    db.commit()
    return {"message": "Decisions applied."}


@app.post("/api/admin/reset-password")
def reset_password(payload: PasswordResetRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.password_hash = hash_password("password123")
    db.commit()
    return {"message": "Password reset to password123."}
