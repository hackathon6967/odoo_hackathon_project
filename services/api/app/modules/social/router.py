from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime, timezone

from app.shared.db import get_db
from app.shared.auth import get_current_user, require_manager_or_admin
from app.shared.storage import upload_file
from app.shared.events import publish, PARTICIPATION_DECISION, trigger_score_recompute
from app.modules.core.models import User, ESGConfig
from app.modules.social.models import CSRActivity, EmployeeParticipation, DiversityMetric, TrainingModule, TrainingCompletion

router = APIRouter()


class CSRActivityCreate(BaseModel):
    title: str
    category_id: str
    department_id: Optional[str] = None
    description: Optional[str] = None
    date: datetime
    evidence_required: bool = True
    points_reward: int = 0


@router.get("/activities")
async def list_activities(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    joined = select(EmployeeParticipation.activity_id).where(EmployeeParticipation.employee_id == current_user.id)
    result = await db.execute(select(CSRActivity).where(CSRActivity.status == "active", CSRActivity.id.not_in(joined.scalar_subquery())))
    acts = result.scalars().all()
    return [{"id": str(a.id), "title": a.title, "date": a.date.isoformat(),
             "points_reward": a.points_reward, "evidence_required": a.evidence_required,
             "department_id": str(a.department_id) if a.department_id else None} for a in acts]


@router.post("/activities", status_code=201)
async def create_activity(req: CSRActivityCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    act = CSRActivity(
        title=req.title, category_id=uuid.UUID(req.category_id),
        department_id=uuid.UUID(req.department_id) if req.department_id else None,
        description=req.description, date=req.date,
        evidence_required=req.evidence_required, points_reward=req.points_reward,
    )
    db.add(act)
    await db.flush()
    return {"id": str(act.id)}


@router.post("/activities/{activity_id}/participate", status_code=201)
async def submit_participation(
    activity_id: str,
    proof_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    act_result = await db.execute(select(CSRActivity).where(CSRActivity.id == uuid.UUID(activity_id)))
    activity = act_result.scalar_one_or_none()
    if not activity:
        raise HTTPException(404, "Activity not found")
    existing = await db.execute(select(EmployeeParticipation).where(
        EmployeeParticipation.activity_id == activity.id,
        EmployeeParticipation.employee_id == current_user.id,
    ))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "You have already chosen this CSR activity")

    proof_ref = None
    if proof_file:
        data = await proof_file.read()
        proof_ref = await upload_file(data, f"proofs/csr/{activity_id}/{current_user.id}_{proof_file.filename}", proof_file.content_type)

    participation = EmployeeParticipation(
        employee_id=current_user.id,
        activity_id=uuid.UUID(activity_id),
        proof_file_ref=proof_ref,
    )
    db.add(participation)
    await db.flush()
    return {"id": str(participation.id), "status": "Pending"}


@router.put("/participations/{participation_id}/approve")
async def approve_participation(
    participation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    result = await db.execute(select(EmployeeParticipation).where(EmployeeParticipation.id == uuid.UUID(participation_id)))
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(404, "Participation not found")

    # Enforce evidence requirement
    cfg_result = await db.execute(select(ESGConfig))
    config = cfg_result.scalar_one_or_none()
    if config and config.evidence_required and not part.proof_file_ref:
        raise HTTPException(400, "Evidence required but not uploaded")

    act_result = await db.execute(select(CSRActivity).where(CSRActivity.id == part.activity_id))
    activity = act_result.scalar_one_or_none()

    part.approval_status = "Approved"
    part.completion_date = datetime.now(timezone.utc)
    part.reviewer_id = current_user.id
    part.points_earned = activity.points_reward if activity else 0

    # Award points to employee
    emp_result = await db.execute(select(User).where(User.id == part.employee_id))
    emp = emp_result.scalar_one_or_none()
    if emp:
        emp.points += part.points_earned

    await publish(PARTICIPATION_DECISION, {"employee_id": str(part.employee_id), "status": "Approved", "points": part.points_earned})
    await trigger_score_recompute()
    return {"id": str(part.id), "status": "Approved", "points_earned": part.points_earned}


@router.put("/participations/{participation_id}/reject")
async def reject_participation(
    participation_id: str,
    reason: str = "Does not meet criteria",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    result = await db.execute(select(EmployeeParticipation).where(EmployeeParticipation.id == uuid.UUID(participation_id)))
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(404, "Not found")
    part.approval_status = "Rejected"
    part.reviewer_id = current_user.id
    part.rejection_reason = reason
    await publish(PARTICIPATION_DECISION, {"employee_id": str(part.employee_id), "status": "Rejected"})
    return {"id": str(part.id), "status": "Rejected"}


@router.get("/participations")
async def list_participations(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(EmployeeParticipation)
    if current_user.role == "employee":
        q = q.where(EmployeeParticipation.employee_id == current_user.id)
    if status:
        q = q.where(EmployeeParticipation.approval_status == status)
    result = await db.execute(q)
    parts = result.scalars().all()
    return [{"id": str(p.id), "activity_id": str(p.activity_id), "employee_id": str(p.employee_id),
             "approval_status": p.approval_status, "points_earned": p.points_earned,
             "proof_file_ref": p.proof_file_ref} for p in parts]


@router.get("/dashboard")
async def social_dashboard(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    total = await db.execute(select(func.count(EmployeeParticipation.id)))
    approved = await db.execute(select(func.count(EmployeeParticipation.id)).where(EmployeeParticipation.approval_status == "Approved"))
    pending = await db.execute(select(func.count(EmployeeParticipation.id)).where(EmployeeParticipation.approval_status == "Pending"))
    return {
        "total_participations": total.scalar() or 0,
        "approved_participations": approved.scalar() or 0,
        "pending_participations": pending.scalar() or 0,
    }


# ── Diversity Metrics ─────────────────────────────────────────────────────────

class DiversityMetricCreate(BaseModel):
    department_id: Optional[str] = None
    period: str
    gender_male: int
    gender_female: int
    gender_other: int
    tenure_0_1: int
    tenure_1_3: int
    tenure_3_5: int
    tenure_5_plus: int


@router.get("/diversity-metrics")
async def list_diversity_metrics(
    period: Optional[str] = None,
    department_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(DiversityMetric)
    if period:
        q = q.where(DiversityMetric.period == period)
    if department_id:
        q = q.where(DiversityMetric.department_id == uuid.UUID(department_id))
    result = await db.execute(q.order_by(DiversityMetric.period.desc()))
    metrics = result.scalars().all()
    return [{
        "id": str(m.id), "period": m.period, "department_id": str(m.department_id) if m.department_id else None,
        "gender_male": m.gender_male, "gender_female": m.gender_female, "gender_other": m.gender_other,
        "tenure_0_1": m.tenure_0_1, "tenure_1_3": m.tenure_1_3, "tenure_3_5": m.tenure_3_5, "tenure_5_plus": m.tenure_5_plus
    } for m in metrics]


@router.post("/diversity-metrics", status_code=201)
async def create_diversity_metric(
    req: DiversityMetricCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)
):
    metric = DiversityMetric(
        department_id=uuid.UUID(req.department_id) if req.department_id else None,
        period=req.period,
        gender_male=req.gender_male, gender_female=req.gender_female, gender_other=req.gender_other,
        tenure_0_1=req.tenure_0_1, tenure_1_3=req.tenure_1_3, tenure_3_5=req.tenure_3_5, tenure_5_plus=req.tenure_5_plus
    )
    db.add(metric)
    await db.flush()
    return {"id": str(metric.id)}


# ── Training ──────────────────────────────────────────────────────────────────

class TrainingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    xp_reward: int = 50
    is_mandatory: bool = False


@router.get("/trainings")
async def list_trainings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(TrainingModule).where(TrainingModule.status == "active"))
    trainings = result.scalars().all()

    # Get completions for current user
    comp_result = await db.execute(select(TrainingCompletion.training_id).where(TrainingCompletion.employee_id == current_user.id))
    completed_ids = {row[0] for row in comp_result.all()}

    return [{"id": str(t.id), "title": t.title, "description": t.description,
             "xp_reward": t.xp_reward, "is_mandatory": t.is_mandatory,
             "is_completed": t.id in completed_ids} for t in trainings]


@router.post("/trainings", status_code=201)
async def create_training(req: TrainingCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    training = TrainingModule(**req.model_dump())
    db.add(training)
    await db.flush()
    return {"id": str(training.id)}


@router.post("/trainings/{training_id}/complete", status_code=200)
async def complete_training(training_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Check if training exists
    result = await db.execute(select(TrainingModule).where(TrainingModule.id == uuid.UUID(training_id)))
    training = result.scalar_one_or_none()
    if not training or training.status != "active":
        raise HTTPException(404, "Training module not found")

    # Check if already completed
    comp_result = await db.execute(
        select(TrainingCompletion).where(
            TrainingCompletion.training_id == training.id,
            TrainingCompletion.employee_id == current_user.id
        )
    )
    if comp_result.scalar_one_or_none():
        return {"message": "Already completed"}

    # Create completion record
    completion = TrainingCompletion(training_id=training.id, employee_id=current_user.id)
    db.add(completion)

    # Award XP
    current_user.xp += training.xp_reward

    await db.flush()
    return {"id": str(completion.id), "xp_rewarded": training.xp_reward}


@router.get("/trainings/completion-stats")
async def training_completion_stats(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    # Count active training modules
    total_result = await db.execute(select(func.count(TrainingModule.id)).where(TrainingModule.status == "active"))
    total_modules = total_result.scalar() or 0

    if total_modules == 0:
        return {"completion_rate": 0, "total_modules": 0, "total_completions": 0}

    # Count total users
    users_result = await db.execute(select(func.count(User.id)).where(User.is_active == True))
    total_users = users_result.scalar() or 0

    if total_users == 0:
        return {"completion_rate": 0, "total_modules": total_modules, "total_completions": 0}

    # Count all completions
    comp_result = await db.execute(select(func.count(TrainingCompletion.id)))
    total_completions = comp_result.scalar() or 0

    # Max possible completions = users * modules
    max_possible = total_users * total_modules
    completion_rate = min(100, round((total_completions / max_possible) * 100)) if max_possible > 0 else 0

    return {
        "completion_rate": completion_rate,
        "total_modules": total_modules,
        "total_completions": total_completions
    }
