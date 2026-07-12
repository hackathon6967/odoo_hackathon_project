from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import uuid
from datetime import datetime, timezone, timedelta
import os
import secrets

from app.shared.db import get_db
from app.shared.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_admin, require_manager_or_admin
)
from app.modules.core.models import User, Department, Category, ESGConfig, NotificationSetting, PendingRegistration, UserRole

router = APIRouter()


# ── Auth ─────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    full_name: str


@router.post("/auth/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=token, user_id=str(user.id), role=user.role, full_name=user.full_name)


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.EMPLOYEE
    department_id: Optional[str] = None


class SignupRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class OtpVerificationRequest(BaseModel):
    email: EmailStr
    otp_code: str


@router.post("/auth/signup/request-otp", status_code=202)
async def request_signup_otp(req: SignupRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    code = f"{secrets.randbelow(1_000_000):06d}"
    await db.execute(delete(PendingRegistration).where(PendingRegistration.email == req.email))
    db.add(PendingRegistration(
        email=req.email, full_name=req.full_name, hashed_password=hash_password(req.password),
        otp_code=code, expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    ))
    await db.flush()
    response = {"message": "Verification code created. It expires in 10 minutes."}
    if os.getenv("ENVIRONMENT", "development") == "development":
        response["development_otp"] = code
    return response


@router.post("/auth/signup/verify", response_model=TokenResponse)
async def verify_signup_otp(req: OtpVerificationRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PendingRegistration).where(PendingRegistration.email == req.email))
    pending = result.scalar_one_or_none()
    if not pending or pending.otp_code != req.otp_code or pending.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
    user = User(email=pending.email, full_name=pending.full_name, hashed_password=pending.hashed_password, role=UserRole.EMPLOYEE)
    db.add(user)
    await db.delete(pending)
    await db.flush()
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=token, user_id=str(user.id), role=user.role, full_name=user.full_name)


@router.post("/auth/register", status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=req.email,
        full_name=req.full_name,
        hashed_password=hash_password(req.password),
        role=req.role,
        department_id=uuid.UUID(req.department_id) if req.department_id else None,
    )
    db.add(user)
    await db.flush()
    return {"id": str(user.id), "email": user.email, "role": user.role}


@router.get("/auth/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "department_id": str(current_user.department_id) if current_user.department_id else None,
        "xp": current_user.xp,
        "points": current_user.points,
    }


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    result = await db.execute(select(User).where(User.is_active == True))
    users = result.scalars().all()
    return [{"id": str(u.id), "email": u.email, "full_name": u.full_name, "role": u.role,
             "department_id": str(u.department_id) if u.department_id else None,
             "xp": u.xp, "points": u.points} for u in users]


class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.EMPLOYEE
    department_id: Optional[str] = None


@router.post("/users", status_code=201)
async def admin_create_user(req: AdminCreateUserRequest, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=req.email, full_name=req.full_name, hashed_password=hash_password(req.password),
        role=req.role.value, department_id=uuid.UUID(req.department_id) if req.department_id else None,
    )
    db.add(user)
    await db.flush()
    return {"id": str(user.id), "email": user.email, "full_name": user.full_name, "role": user.role}


@router.put("/users/{user_id}/deactivate")
async def deactivate_user(user_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    return {"message": "User deactivated"}


class RoleUpdate(BaseModel):
    role: UserRole

@router.put("/users/{user_id}/role")
async def update_user_role(user_id: str, req: RoleUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = req.role
    return {"message": "User role updated", "role": user.role}


# ── Departments ───────────────────────────────────────────────────────────────

class DeptCreate(BaseModel):
    name: str
    code: str
    parent_department_id: Optional[str] = None
    employee_count: int = 0


@router.get("/departments")
async def list_departments(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Department))
    depts = result.scalars().all()
    return [{"id": str(d.id), "name": d.name, "code": d.code,
             "parent_department_id": str(d.parent_department_id) if d.parent_department_id else None,
             "employee_count": d.employee_count, "status": d.status} for d in depts]


@router.post("/departments", status_code=201)
async def create_department(req: DeptCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    dept = Department(
        name=req.name, code=req.code,
        parent_department_id=uuid.UUID(req.parent_department_id) if req.parent_department_id else None,
        employee_count=req.employee_count,
    )
    db.add(dept)
    await db.flush()
    return {"id": str(dept.id), "name": dept.name, "code": dept.code}


@router.put("/departments/{dept_id}")
async def update_department(dept_id: str, req: DeptCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    result = await db.execute(select(Department).where(Department.id == uuid.UUID(dept_id)))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    dept.name = req.name
    dept.code = req.code
    dept.employee_count = req.employee_count
    return {"id": str(dept.id), "name": dept.name}


@router.delete("/departments/{dept_id}")
async def archive_department(dept_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    result = await db.execute(select(Department).where(Department.id == uuid.UUID(dept_id)))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    dept.status = "archived"
    return {"message": "Department archived"}


# ── Categories ────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str
    type: str  # CSR_ACTIVITY | CHALLENGE


@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Category))
    cats = result.scalars().all()
    return [{"id": str(c.id), "name": c.name, "type": c.type, "status": c.status} for c in cats]


@router.post("/categories", status_code=201)
async def create_category(req: CategoryCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    cat = Category(name=req.name, type=req.type)
    db.add(cat)
    await db.flush()
    return {"id": str(cat.id), "name": cat.name, "type": cat.type}


@router.delete("/categories/{cat_id}")
async def archive_category(cat_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    result = await db.execute(select(Category).where(Category.id == uuid.UUID(cat_id)))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.status = "archived"
    return {"message": "Category archived"}


# ── ESG Config / Settings ────────────────────────────────────────────────────

class ESGConfigUpdate(BaseModel):
    weight_environmental: float = 0.40
    weight_social: float = 0.30
    weight_governance: float = 0.30
    auto_emission_calc: bool = True
    evidence_required: bool = True
    badge_auto_award: bool = True


@router.get("/settings/esg-config")
async def get_esg_config(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ESGConfig))
    config = result.scalar_one_or_none()
    if not config:
        config = ESGConfig()
        db.add(config)
        await db.flush()
    return {
        "weight_environmental": config.weight_environmental,
        "weight_social": config.weight_social,
        "weight_governance": config.weight_governance,
        "auto_emission_calc": config.auto_emission_calc,
        "evidence_required": config.evidence_required,
        "badge_auto_award": config.badge_auto_award,
    }


@router.put("/settings/esg-config")
async def update_esg_config(req: ESGConfigUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    if abs(req.weight_environmental + req.weight_social + req.weight_governance - 1.0) > 0.001:
        raise HTTPException(status_code=400, detail="Weights must sum to 1.0")
    result = await db.execute(select(ESGConfig))
    config = result.scalar_one_or_none()
    if not config:
        config = ESGConfig()
        db.add(config)
    config.weight_environmental = req.weight_environmental
    config.weight_social = req.weight_social
    config.weight_governance = req.weight_governance
    config.auto_emission_calc = req.auto_emission_calc
    config.evidence_required = req.evidence_required
    config.badge_auto_award = req.badge_auto_award
    await db.flush()
    from app.shared.events import trigger_score_recompute
    await trigger_score_recompute()
    return {"message": "ESG config updated"}


@router.get("/settings/notifications")
async def get_notification_settings(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(NotificationSetting))
    settings = result.scalars().all()
    return [{"notification_type": s.notification_type, "in_app_enabled": s.in_app_enabled, "email_enabled": s.email_enabled} for s in settings]


class NotificationSettingUpdate(BaseModel):
    notification_type: str
    in_app_enabled: bool
    email_enabled: bool

@router.put("/settings/notifications")
async def update_notification_settings(req_list: List[NotificationSettingUpdate], db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    for req in req_list:
        result = await db.execute(select(NotificationSetting).where(NotificationSetting.notification_type == req.notification_type))
        setting = result.scalar_one_or_none()
        if not setting:
            setting = NotificationSetting(notification_type=req.notification_type)
            db.add(setting)
        setting.in_app_enabled = req.in_app_enabled
        setting.email_enabled = req.email_enabled
    await db.flush()
    return {"message": "Notification settings updated"}
