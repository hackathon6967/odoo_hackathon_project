from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel
from typing import Optional, List
import uuid
import logging
from datetime import datetime, timezone

from app.shared.db import get_db
from app.shared.auth import get_current_user, require_manager_or_admin
from app.modules.core.models import User, ESGConfig
from app.modules.environmental.models import EmissionFactor, CarbonTransaction, EnvironmentalGoal, ProductESGProfile
from app.shared.events import trigger_score_recompute

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Emission Factors ──────────────────────────────────────────────────────────

class EmissionFactorCreate(BaseModel):
    source_type: str
    unit: str
    co2e_per_unit: float
    effective_date: datetime
    description: Optional[str] = None


@router.get("/emission-factors")
async def list_factors(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(EmissionFactor).where(EmissionFactor.status == "active").order_by(EmissionFactor.effective_date.desc()))
    factors = result.scalars().all()
    return [{"id": str(f.id), "source_type": f.source_type, "unit": f.unit,
             "co2e_per_unit": f.co2e_per_unit, "effective_date": f.effective_date.isoformat(),
             "description": f.description} for f in factors]


@router.post("/emission-factors", status_code=201)
async def create_factor(req: EmissionFactorCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    factor = EmissionFactor(**req.model_dump())
    db.add(factor)
    await db.flush()
    return {"id": str(factor.id), "source_type": factor.source_type, "co2e_per_unit": factor.co2e_per_unit}


@router.put("/emission-factors/{factor_id}")
async def update_factor(factor_id: str, req: EmissionFactorCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    result = await db.execute(select(EmissionFactor).where(EmissionFactor.id == uuid.UUID(factor_id)))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(404, "Emission factor not found")
    for k, v in req.model_dump().items():
        setattr(f, k, v)
    return {"id": str(f.id)}


@router.delete("/emission-factors/{factor_id}")
async def delete_factor(factor_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    result = await db.execute(select(EmissionFactor).where(EmissionFactor.id == uuid.UUID(factor_id)))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(404, "Not found")
    f.status = "archived"
    return {"message": "Archived"}


# ── Carbon Transactions ───────────────────────────────────────────────────────

class CarbonTxCreate(BaseModel):
    department_id: str
    source_module: str
    emission_factor_id: str
    quantity: float
    transaction_date: datetime
    notes: Optional[str] = None


@router.get("/carbon-transactions")
async def list_transactions(
    department_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(CarbonTransaction)
    if department_id:
        q = q.where(CarbonTransaction.department_id == uuid.UUID(department_id))
    result = await db.execute(q.order_by(CarbonTransaction.transaction_date.desc()))
    txns = result.scalars().all()
    return [{"id": str(t.id), "department_id": str(t.department_id), "source_module": t.source_module,
             "co2e_calculated": t.co2e_calculated, "quantity": t.quantity,
             "transaction_date": t.transaction_date.isoformat(), "is_auto_calculated": t.is_auto_calculated} for t in txns]


@router.post("/carbon-transactions", status_code=201)
async def create_transaction(req: CarbonTxCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Lookup emission factor and calculate co2e
    ef_result = await db.execute(select(EmissionFactor).where(EmissionFactor.id == uuid.UUID(req.emission_factor_id)))
    ef = ef_result.scalar_one_or_none()
    if not ef:
        raise HTTPException(404, "Emission factor not found")
    co2e = ef.co2e_per_unit * req.quantity
    txn = CarbonTransaction(
        department_id=uuid.UUID(req.department_id),
        source_module=req.source_module,
        emission_factor_id=uuid.UUID(req.emission_factor_id),
        quantity=req.quantity,
        co2e_calculated=co2e,
        transaction_date=req.transaction_date,
        notes=req.notes,
        is_auto_calculated=False,
        created_by_id=current_user.id,
    )
    db.add(txn)
    await db.flush()
    # Update environmental goal progress
    await _update_goal_progress(db, txn.department_id)
    await trigger_score_recompute()
    return {"id": str(txn.id), "co2e_calculated": co2e}


@router.put("/carbon-transactions/{transaction_id}/upload-log")
async def upload_transaction_log(
    transaction_id: str,
    log_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.shared.storage import upload_file
    result = await db.execute(select(CarbonTransaction).where(CarbonTransaction.id == uuid.UUID(transaction_id)))
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    
    data = await log_file.read()
    file_ref = await upload_file(data, f"logs/env/{transaction_id}/{current_user.id}_{log_file.filename}", log_file.content_type)
    txn.file_ref = file_ref
    await db.flush()
    return {"id": str(txn.id), "file_ref": file_ref}

async def _update_goal_progress(db: AsyncSession, department_id: uuid.UUID = None):
    """Recompute current_value for active environmental goals matching the department.

    For goals with metric containing 'co2e', current_value = total CO2e emitted
    for that department (or org-wide if department_id is null on the goal).
    """
    try:
        goals_q = select(EnvironmentalGoal).where(EnvironmentalGoal.status == "active")
        goals_result = await db.execute(goals_q)
        goals = goals_result.scalars().all()

        for goal in goals:
            # Match department-specific goals or org-wide goals
            if goal.department_id and department_id and goal.department_id != department_id:
                continue

            # Compute current value from actual CO2e data
            co2e_q = select(func.coalesce(func.sum(CarbonTransaction.co2e_calculated), 0.0))
            if goal.department_id:
                co2e_q = co2e_q.where(CarbonTransaction.department_id == goal.department_id)
            result = await db.execute(co2e_q)
            total_co2e = result.scalar() or 0.0
            goal.current_value = round(total_co2e, 2)

            # Check if goal is achieved (for reduction goals, current < target is good)
            if goal.target_value > 0:
                if goal.current_value >= goal.target_value:
                    goal.status = "failed"
                elif datetime.now(timezone.utc) > goal.target_date and goal.current_value < goal.target_value:
                    goal.status = "achieved"
    except Exception as e:
        logger.warning(f"Goal progress update failed: {e}")


# ── Automatic Emission Calculation ────────────────────────────────────────────

class AutoEmitRequest(BaseModel):
    """Auto-generate a CarbonTransaction from module data."""
    department_id: str
    source_module: str  # purchase / manufacturing / fleet / expense
    quantity: float
    transaction_date: Optional[datetime] = None
    notes: Optional[str] = None


async def _auto_emit(
    db: AsyncSession,
    department_id: uuid.UUID,
    source_module: str,
    quantity: float,
    transaction_date: datetime = None,
    notes: str = None,
    created_by_id: uuid.UUID = None,
) -> Optional[CarbonTransaction]:
    """Core auto-emission logic. Checks ESGConfig.auto_emission_calc, finds
    the matching emission factor, creates a CarbonTransaction, and updates
    goal progress. Returns None if auto-calc is disabled or no factor found."""
    # Check if auto emission calculation is enabled
    cfg_result = await db.execute(select(ESGConfig))
    config = cfg_result.scalar_one_or_none()
    if config and not config.auto_emission_calc:
        return None

    # Find the most recent active emission factor for this source type
    ef_result = await db.execute(
        select(EmissionFactor)
        .where(EmissionFactor.source_type == source_module, EmissionFactor.status == "active")
        .order_by(EmissionFactor.effective_date.desc())
        .limit(1)
    )
    ef = ef_result.scalar_one_or_none()
    if not ef:
        logger.warning(f"No active emission factor for source_type='{source_module}', skipping auto-emit")
        return None

    co2e = ef.co2e_per_unit * quantity
    txn = CarbonTransaction(
        department_id=department_id,
        source_module=source_module,
        emission_factor_id=ef.id,
        quantity=quantity,
        co2e_calculated=co2e,
        transaction_date=transaction_date or datetime.now(timezone.utc),
        notes=notes or f"Auto-calculated from {source_module}",
        is_auto_calculated=True,
        created_by_id=created_by_id,
    )
    db.add(txn)
    await db.flush()

    # Update environmental goal progress
    await _update_goal_progress(db, department_id)
    await trigger_score_recompute()

    logger.info(f"Auto-emit: {source_module} dept={department_id} qty={quantity} co2e={co2e}")
    return txn


@router.post("/auto-emit", status_code=201)
async def auto_emit(
    req: AutoEmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Automatically generate a CarbonTransaction from purchase/manufacturing/fleet/expense data.
    Respects ESGConfig.auto_emission_calc. Looks up the matching emission factor by source_type."""
    txn = await _auto_emit(
        db=db,
        department_id=uuid.UUID(req.department_id),
        source_module=req.source_module,
        quantity=req.quantity,
        transaction_date=req.transaction_date,
        notes=req.notes,
        created_by_id=current_user.id,
    )
    if txn is None:
        return {"message": "Auto emission calculation is disabled or no matching emission factor found", "created": False}
    return {"id": str(txn.id), "co2e_calculated": txn.co2e_calculated, "is_auto_calculated": True, "created": True}


# ── Environmental Goals ───────────────────────────────────────────────────────

class GoalCreate(BaseModel):
    department_id: Optional[str] = None
    metric: str
    target_value: float
    unit: str
    target_date: datetime


@router.get("/goals")
async def list_goals(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(EnvironmentalGoal).where(EnvironmentalGoal.status == "active"))
    goals = result.scalars().all()
    return [{"id": str(g.id), "metric": g.metric, "target_value": g.target_value,
             "current_value": g.current_value, "unit": g.unit,
             "target_date": g.target_date.isoformat(), "status": g.status,
             "department_id": str(g.department_id) if g.department_id else None,
             "progress_pct": round((g.current_value / g.target_value * 100) if g.target_value > 0 else 0, 1)} for g in goals]


@router.post("/goals", status_code=201)
async def create_goal(req: GoalCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    goal = EnvironmentalGoal(
        department_id=uuid.UUID(req.department_id) if req.department_id else None,
        metric=req.metric, target_value=req.target_value, unit=req.unit, target_date=req.target_date,
    )
    db.add(goal)
    await db.flush()
    return {"id": str(goal.id)}


@router.get("/dashboard")
async def env_dashboard(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    # Total CO2e this month
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.sum(CarbonTransaction.co2e_calculated)).where(CarbonTransaction.transaction_date >= month_start)
    )
    total_this_month = result.scalar() or 0.0

    # All-time total
    result2 = await db.execute(select(func.sum(CarbonTransaction.co2e_calculated)))
    total_all = result2.scalar() or 0.0

    # Goals
    goals_result = await db.execute(select(EnvironmentalGoal).where(EnvironmentalGoal.status == "active"))
    goals = goals_result.scalars().all()

    return {
        "total_co2e_this_month": round(total_this_month, 2),
        "total_co2e_all_time": round(total_all, 2),
        "active_goals": len(goals),
        "goals_summary": [
            {"metric": g.metric, "progress_pct": round(g.current_value / g.target_value * 100 if g.target_value > 0 else 0, 1)}
            for g in goals
        ]
    }


# ── Product ESG Profiles ──────────────────────────────────────────────────────

class ProductESGProfileCreate(BaseModel):
    product_ref: str
    emission_factor_id: Optional[str] = None
    sustainability_notes: Optional[str] = None


@router.get("/products")
async def list_products(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ProductESGProfile).order_by(ProductESGProfile.created_at.desc()))
    profiles = result.scalars().all()
    return [{"id": str(p.id), "product_ref": p.product_ref,
             "emission_factor_id": str(p.emission_factor_id) if p.emission_factor_id else None,
             "sustainability_notes": p.sustainability_notes} for p in profiles]


@router.post("/products", status_code=201)
async def create_product(req: ProductESGProfileCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    ef_id = None
    if req.emission_factor_id:
        ef_result = await db.execute(select(EmissionFactor).where(EmissionFactor.id == uuid.UUID(req.emission_factor_id)))
        if not ef_result.scalar_one_or_none():
            raise HTTPException(400, "Invalid emission factor ID")
        ef_id = uuid.UUID(req.emission_factor_id)

    profile = ProductESGProfile(
        product_ref=req.product_ref,
        emission_factor_id=ef_id,
        sustainability_notes=req.sustainability_notes
    )
    db.add(profile)
    await db.flush()
    return {"id": str(profile.id)}


@router.get("/trend")
async def env_trend(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Return monthly CO2e totals for the past 6 months."""
    now = datetime.now(timezone.utc)
    months = []
    for i in range(6):
        # Calculate month and year robustly
        m_index = now.month - i - 1
        m = m_index % 12 + 1
        y = now.year if m_index >= 0 else now.year - 1 - (abs(m_index) - 1) // 12
        months.append((y, m))
    months.reverse() # chronological
    
    start_y, start_m = months[0]
    start_date = datetime(start_y, start_m, 1, tzinfo=timezone.utc)
    
    result = await db.execute(
        select(CarbonTransaction)
        .where(CarbonTransaction.transaction_date >= start_date)
    )
    txns = result.scalars().all()
    
    trend_dict = {}
    for t in txns:
        key = (t.transaction_date.year, t.transaction_date.month)
        trend_dict[key] = trend_dict.get(key, 0.0) + t.co2e_calculated
        
    out = []
    for y, m in months:
        d = datetime(y, m, 1)
        out.append({"month": d.strftime("%b"), "co2": round(trend_dict.get((y, m), 0.0), 2)})
        
    return out
