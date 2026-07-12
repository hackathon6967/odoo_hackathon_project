from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from sqlalchemy.dialects.postgresql import UUID as PUUID
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime, timezone

from app.shared.db import get_db
from app.shared.auth import get_current_user, require_manager_or_admin
from app.shared.storage import upload_file
from app.shared.events import publish, CHALLENGE_PARTICIPATION_DECISION, BADGE_UNLOCKED, REWARD_REDEEMED
from app.modules.core.models import User, ESGConfig
from app.modules.gamification.models import (
    Challenge, ChallengeParticipation, Badge, EmployeeBadge, Reward, RewardRedemption
)

router = APIRouter()

# Valid challenge state transitions
CHALLENGE_TRANSITIONS = {
    "Draft": ["Active", "Archived"],
    "Active": ["Under Review", "Archived"],
    "Under Review": ["Completed", "Active", "Archived"],
    "Completed": ["Archived"],
}


# ── Challenges ────────────────────────────────────────────────────────────────

class ChallengeCreate(BaseModel):
    title: str
    category_id: Optional[str] = None
    description: Optional[str] = None
    xp: int = 50
    difficulty: str = "medium"
    evidence_required: bool = True
    deadline: Optional[datetime] = None


@router.get("/challenges")
async def list_challenges(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Challenge))
    challenges = result.scalars().all()
    return [{"id": str(c.id), "title": c.title, "xp": c.xp, "difficulty": c.difficulty,
             "status": c.status, "evidence_required": c.evidence_required,
             "deadline": c.deadline.isoformat() if c.deadline else None} for c in challenges]


@router.post("/challenges", status_code=201)
async def create_challenge(req: ChallengeCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_manager_or_admin)):
    ch = Challenge(
        title=req.title, description=req.description, xp=req.xp, difficulty=req.difficulty,
        evidence_required=req.evidence_required, deadline=req.deadline,
        category_id=uuid.UUID(req.category_id) if req.category_id else None,
        created_by_id=current_user.id,
    )
    db.add(ch)
    await db.flush()
    return {"id": str(ch.id)}


@router.put("/challenges/{challenge_id}/transition")
async def transition_challenge(challenge_id: str, new_status: str,
                               db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    result = await db.execute(select(Challenge).where(Challenge.id == uuid.UUID(challenge_id)))
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(404, "Challenge not found")
    allowed = CHALLENGE_TRANSITIONS.get(ch.status, [])
    if new_status not in allowed and new_status != "Archived":
        raise HTTPException(400, f"Cannot transition from '{ch.status}' to '{new_status}'")
    ch.status = new_status
    return {"id": str(ch.id), "status": ch.status}


@router.post("/challenges/{challenge_id}/participate", status_code=201)
async def submit_challenge_participation(
    challenge_id: str,
    proof_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ch_result = await db.execute(select(Challenge).where(Challenge.id == uuid.UUID(challenge_id)))
    ch = ch_result.scalar_one_or_none()
    if not ch or ch.status != "Active":
        raise HTTPException(400, "Challenge is not active")
    proof_ref = None
    if proof_file:
        data = await proof_file.read()
        proof_ref = await upload_file(data, f"proofs/challenge/{challenge_id}/{current_user.id}_{proof_file.filename}", proof_file.content_type)
    part = ChallengeParticipation(
        challenge_id=uuid.UUID(challenge_id), employee_id=current_user.id, proof_file_ref=proof_ref,
    )
    db.add(part)
    await db.flush()
    return {"id": str(part.id), "status": "Pending"}


@router.put("/challenge-participations/{part_id}/approve")
async def approve_challenge_participation(part_id: str, db: AsyncSession = Depends(get_db),
                                          current_user: User = Depends(require_manager_or_admin)):
    result = await db.execute(select(ChallengeParticipation).where(ChallengeParticipation.id == uuid.UUID(part_id)))
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(404, "Not found")
    ch_result = await db.execute(select(Challenge).where(Challenge.id == part.challenge_id))
    ch = ch_result.scalar_one_or_none()
    part.approval_status = "Approved"
    part.xp_awarded = ch.xp if ch else 0

    # Award XP and Points to employee
    emp_result = await db.execute(select(User).where(User.id == part.employee_id))
    emp = emp_result.scalar_one_or_none()
    if emp:
        emp.xp += part.xp_awarded
        emp.points += part.xp_awarded

    await publish(CHALLENGE_PARTICIPATION_DECISION, {"employee_id": str(part.employee_id), "xp": part.xp_awarded, "status": "Approved"})

    # Check badge auto-award toggle
    cfg_result = await db.execute(select(ESGConfig))
    config = cfg_result.scalar_one_or_none()
    if config and config.badge_auto_award and emp:
        await _check_and_award_badges(emp, db)

    return {"id": str(part.id), "xp_awarded": part.xp_awarded}


@router.put("/challenge-participations/{part_id}/reject")
async def reject_challenge_participation(
    part_id: str,
    reason: str = "Does not meet criteria",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    result = await db.execute(select(ChallengeParticipation).where(ChallengeParticipation.id == uuid.UUID(part_id)))
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(404, "Not found")

    part.approval_status = "Rejected"
    part.rejection_reason = reason
    part.xp_awarded = 0
    await publish(CHALLENGE_PARTICIPATION_DECISION, {"employee_id": str(part.employee_id), "xp": 0, "status": "Rejected"})
    
    return {"id": str(part.id), "status": "Rejected"}


async def _check_and_award_badges(emp: User, db: AsyncSession):
    """Evaluate badge unlock rules against employee XP/completed challenge count."""
    # Count completed challenges
    count_result = await db.execute(
        select(func.count(ChallengeParticipation.id)).where(
            ChallengeParticipation.employee_id == emp.id,
            ChallengeParticipation.approval_status == "Approved",
        )
    )
    completed_count = count_result.scalar() or 0

    # Get already awarded badge IDs
    awarded_result = await db.execute(select(EmployeeBadge.badge_id).where(EmployeeBadge.employee_id == emp.id))
    awarded_ids = {row[0] for row in awarded_result.all()}

    # Evaluate all badges
    badges_result = await db.execute(select(Badge))
    badges = badges_result.scalars().all()
    for badge in badges:
        if badge.id in awarded_ids:
            continue
        rule = badge.unlock_rule or {}
        metric = rule.get("metric")
        threshold = rule.get("threshold", 0)
        unlocked = False
        if metric == "xp" and emp.xp >= threshold:
            unlocked = True
        elif metric == "challenges_completed" and completed_count >= threshold:
            unlocked = True
        if unlocked:
            eb = EmployeeBadge(employee_id=emp.id, badge_id=badge.id)
            db.add(eb)
            await publish(BADGE_UNLOCKED, {"employee_id": str(emp.id), "badge_name": badge.name})


# ── Badges ────────────────────────────────────────────────────────────────────

class BadgeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    unlock_rule: dict  # {"metric": "xp", "threshold": 500}
    icon: Optional[str] = None


@router.get("/badges")
async def list_badges(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Badge))
    badges = result.scalars().all()
    return [{"id": str(b.id), "name": b.name, "description": b.description,
             "unlock_rule": b.unlock_rule, "icon": b.icon} for b in badges]


@router.post("/badges", status_code=201)
async def create_badge(req: BadgeCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    badge = Badge(**req.model_dump())
    db.add(badge)
    await db.flush()
    return {"id": str(badge.id)}


@router.get("/my-badges")
async def my_badges(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(EmployeeBadge).where(EmployeeBadge.employee_id == current_user.id)
    )
    ebs = result.scalars().all()
    badges = []
    for eb in ebs:
        b_result = await db.execute(select(Badge).where(Badge.id == eb.badge_id))
        b = b_result.scalar_one_or_none()
        if b:
            badges.append({"badge_id": str(b.id), "name": b.name, "icon": b.icon, "awarded_at": eb.awarded_at.isoformat()})
    return badges


# ── Rewards ───────────────────────────────────────────────────────────────────

class RewardCreate(BaseModel):
    name: str
    description: Optional[str] = None
    points_required: int
    stock: int


@router.get("/rewards")
async def list_rewards(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Reward).where(Reward.status == "active"))
    rewards = result.scalars().all()
    return [{"id": str(r.id), "name": r.name, "description": r.description,
             "points_required": r.points_required, "stock": r.stock} for r in rewards]


@router.post("/rewards", status_code=201)
async def create_reward(req: RewardCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    reward = Reward(**req.model_dump())
    db.add(reward)
    await db.flush()
    return {"id": str(reward.id)}


@router.post("/rewards/{reward_id}/redeem")
async def redeem_reward(reward_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Race-safe redemption using SELECT FOR UPDATE to prevent double-spend on last stock unit."""
    # Lock the reward row
    result = await db.execute(
        select(Reward).where(Reward.id == uuid.UUID(reward_id)).with_for_update()
    )
    reward = result.scalar_one_or_none()
    if not reward or reward.status != "active":
        raise HTTPException(404, "Reward not found or inactive")
    if reward.stock <= 0:
        raise HTTPException(400, "Out of stock")
    
    # Lock the user row to get fresh points
    user_res = await db.execute(select(User).where(User.id == current_user.id).with_for_update())
    fresh_user = user_res.scalar_one_or_none()

    if not fresh_user or fresh_user.points < reward.points_required:
        raise HTTPException(400, "Insufficient points")

    # Deduct points and decrement stock atomically
    fresh_user.points -= reward.points_required
    reward.stock -= 1

    redemption = RewardRedemption(
        reward_id=reward.id, employee_id=fresh_user.id, points_deducted=reward.points_required
    )
    db.add(redemption)
    await publish(REWARD_REDEEMED, {"employee_id": str(fresh_user.id), "reward_name": reward.name})
    return {"message": "Redeemed successfully", "remaining_points": fresh_user.points}


# ── Leaderboards ──────────────────────────────────────────────────────────────

@router.get("/leaderboard")
async def leaderboard(department_id: Optional[str] = None, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    q = select(User).where(User.is_active == True).order_by(User.xp.desc()).limit(50)
    if department_id:
        q = q.where(User.department_id == uuid.UUID(department_id))
    result = await db.execute(q)
    users = result.scalars().all()
    return [{"rank": i+1, "user_id": str(u.id), "full_name": u.full_name,
             "department_id": str(u.department_id) if u.department_id else None,
             "xp": u.xp, "points": u.points} for i, u in enumerate(users)]
