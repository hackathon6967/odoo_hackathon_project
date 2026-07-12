from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional
import uuid
import os
from datetime import datetime, timezone

from redis import Redis
from rq import Queue

from app.shared.db import get_db
from app.shared.auth import get_current_user, require_manager_or_admin
from app.shared.storage import get_presigned_url
from app.modules.core.models import User, ESGConfig, Department
from app.modules.scoring_reporting.models import DepartmentScore, ReportJob

router = APIRouter()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_conn = Redis.from_url(REDIS_URL)
_queue = Queue("ecosphere", connection=_redis_conn)


# ── ESG Scores ───────────────────────────────────────────────────────────────

@router.get("/scores")
async def get_scores(period: Optional[str] = None, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    q = select(DepartmentScore)
    if period:
        q = q.where(DepartmentScore.period == period)
    result = await db.execute(q.order_by(DepartmentScore.period.desc()))
    scores = result.scalars().all()
    return [{"department_id": str(s.department_id), "period": s.period,
             "environmental_score": s.environmental_score, "social_score": s.social_score,
             "governance_score": s.governance_score, "total_score": s.total_score,
             "computed_at": s.computed_at.isoformat()} for s in scores]


@router.post("/scores/trigger")
async def trigger_scoring(period: Optional[str] = None, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    """Manually trigger the scoring recompute job."""
    import asyncio
    if not period:
        period = datetime.now(timezone.utc).strftime("%Y-%m")
    await asyncio.to_thread(_queue.enqueue, "worker.compute_scores", period)
    return {"message": f"Scoring job queued for period {period}"}


@router.get("/overall-esg")
async def overall_esg(period: Optional[str] = None, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    if not period:
        period = datetime.now(timezone.utc).strftime("%Y-%m")
    cfg_result = await db.execute(select(ESGConfig))
    config = cfg_result.scalar_one_or_none()
    w_env = config.weight_environmental if config else 0.40
    w_soc = config.weight_social if config else 0.30
    w_gov = config.weight_governance if config else 0.30

    scores_result = await db.execute(select(DepartmentScore).where(DepartmentScore.period == period))
    scores = scores_result.scalars().all()
    if not scores:
        return {"period": period, "overall_esg_score": 0.0, "departments_count": 0}

    avg_env = sum(s.environmental_score for s in scores) / len(scores)
    avg_soc = sum(s.social_score for s in scores) / len(scores)
    avg_gov = sum(s.governance_score for s in scores) / len(scores)
    overall = avg_env * w_env + avg_soc * w_soc + avg_gov * w_gov

    return {
        "period": period,
        "overall_esg_score": round(overall, 2),
        "environmental_avg": round(avg_env, 2),
        "social_avg": round(avg_soc, 2),
        "governance_avg": round(avg_gov, 2),
        "departments_count": len(scores),
        "weights": {"environmental": w_env, "social": w_soc, "governance": w_gov},
    }


@router.get("/leaderboard")
async def department_leaderboard(period: Optional[str] = None, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Returns a list of departments sorted by their total ESG score."""
    if not period:
        period = datetime.now(timezone.utc).strftime("%Y-%m")
    
    # We join with Department to get department names (though currently we just return IDs, we can look up names later or return as is)
    q = select(DepartmentScore, Department).join(Department, DepartmentScore.department_id == Department.id).where(DepartmentScore.period == period).order_by(DepartmentScore.total_score.desc())
    result = await db.execute(q)
    
    leaderboard = []
    for rank, (score, dept) in enumerate(result.all(), start=1):
        leaderboard.append({
            "rank": rank,
            "department_id": str(score.department_id),
            "department_name": dept.name,
            "environmental_score": round(score.environmental_score, 1),
            "social_score": round(score.social_score, 1),
            "governance_score": round(score.governance_score, 1),
            "total_score": round(score.total_score, 1)
        })
    return leaderboard


# ── Reports ───────────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    report_type: str  # environmental/social/governance/summary/custom
    format: str  # pdf/xlsx/csv
    filters: Optional[dict] = None


@router.post("/reports", status_code=202)
async def request_report(req: ReportRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    import asyncio
    job = ReportJob(
        report_type=req.report_type, format=req.format,
        filters=req.filters, requested_by_id=current_user.id, status="pending",
    )
    db.add(job)
    await db.flush()
    await asyncio.to_thread(_queue.enqueue, "worker.generate_report", str(job.id))
    return {"report_job_id": str(job.id), "status": "pending", "message": "Report generation queued"}


@router.get("/reports/{job_id}")
async def get_report_status(job_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ReportJob).where(ReportJob.id == uuid.UUID(job_id)))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Report job not found")
    download_url = None
    if job.status == "ready" and job.file_ref:
        download_url = await get_presigned_url(job.file_ref)
    return {
        "id": str(job.id), "status": job.status, "report_type": job.report_type,
        "format": job.format, "download_url": download_url,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.get("/reports")
async def list_reports(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(ReportJob).where(ReportJob.requested_by_id == current_user.id).order_by(ReportJob.created_at.desc())
    )
    jobs = result.scalars().all()
    return [{"id": str(j.id), "report_type": j.report_type, "format": j.format,
             "status": j.status, "created_at": j.created_at.isoformat()} for j in jobs]
