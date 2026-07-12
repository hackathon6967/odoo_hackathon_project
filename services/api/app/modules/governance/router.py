from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, field_validator
from typing import Optional
import uuid
from datetime import datetime, timezone

from app.shared.db import get_db
from app.shared.auth import get_current_user, require_manager_or_admin
from app.shared.events import publish, COMPLIANCE_ISSUE_RAISED, POLICY_REMINDER, trigger_score_recompute
from app.modules.core.models import User
from app.modules.governance.models import ESGPolicy, PolicyAcknowledgement, Audit, ComplianceIssue

router = APIRouter()


# ── ESG Policies ──────────────────────────────────────────────────────────────

class PolicyCreate(BaseModel):
    title: str
    version: str = "1.0"
    body: Optional[str] = None
    effective_date: datetime
    requires_acknowledgement: bool = True


@router.get("/policies")
async def list_policies(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ESGPolicy))
    policies = result.scalars().all()
    return [{"id": str(p.id), "title": p.title, "version": p.version,
             "effective_date": p.effective_date.isoformat(), "status": p.status,
             "requires_acknowledgement": p.requires_acknowledgement} for p in policies]


@router.post("/policies", status_code=201)
async def create_policy(req: PolicyCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    policy = ESGPolicy(**req.model_dump())
    db.add(policy)
    await db.flush()
    return {"id": str(policy.id)}


@router.put("/policies/{policy_id}/publish")
async def publish_policy(policy_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    result = await db.execute(select(ESGPolicy).where(ESGPolicy.id == uuid.UUID(policy_id)))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(404, "Policy not found")
    policy.status = "published"
    # Trigger reminder notifications for all employees
    await publish(POLICY_REMINDER, {"policy_id": str(policy.id), "policy_title": policy.title})
    return {"id": str(policy.id), "status": "published"}


@router.post("/policies/{policy_id}/acknowledge")
async def acknowledge_policy(policy_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Check if already acknowledged
    check = await db.execute(
        select(PolicyAcknowledgement).where(
            PolicyAcknowledgement.policy_id == uuid.UUID(policy_id),
            PolicyAcknowledgement.employee_id == current_user.id,
        )
    )
    if check.scalar_one_or_none():
        return {"message": "Already acknowledged"}
    ack = PolicyAcknowledgement(
        policy_id=uuid.UUID(policy_id),
        employee_id=current_user.id,
        acknowledged_at=datetime.now(timezone.utc),
    )
    db.add(ack)
    return {"message": "Acknowledged"}


# ── Audits ────────────────────────────────────────────────────────────────────

class AuditCreate(BaseModel):
    title: str
    department_id: Optional[str] = None
    auditor: str
    scheduled_date: datetime


@router.get("/audits")
async def list_audits(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Audit))
    audits = result.scalars().all()
    return [{"id": str(a.id), "title": a.title, "auditor": a.auditor,
             "scheduled_date": a.scheduled_date.isoformat(), "status": a.status,
             "findings_summary": a.findings_summary} for a in audits]


@router.post("/audits", status_code=201)
async def create_audit(req: AuditCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    audit = Audit(
        title=req.title, auditor=req.auditor, scheduled_date=req.scheduled_date,
        department_id=uuid.UUID(req.department_id) if req.department_id else None,
    )
    db.add(audit)
    await db.flush()
    return {"id": str(audit.id)}


@router.put("/audits/{audit_id}")
async def update_audit(audit_id: str, findings: str, status: str = "completed",
                       db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    result = await db.execute(select(Audit).where(Audit.id == uuid.UUID(audit_id)))
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(404, "Audit not found")
    audit.status = status
    audit.findings_summary = findings
    return {"id": str(audit.id), "status": audit.status}


@router.put("/audits/{audit_id}/upload-log")
async def upload_audit_log(
    audit_id: str,
    log_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    from app.shared.storage import upload_file
    result = await db.execute(select(Audit).where(Audit.id == uuid.UUID(audit_id)))
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(404, "Audit not found")
    
    data = await log_file.read()
    file_ref = await upload_file(data, f"logs/audits/{audit_id}/{current_user.id}_{log_file.filename}", log_file.content_type)
    audit.file_ref = file_ref
    await db.flush()
    return {"id": str(audit.id), "file_ref": file_ref}


# ── Compliance Issues ─────────────────────────────────────────────────────────

class ComplianceIssueCreate(BaseModel):
    audit_id: Optional[str] = None
    severity: str
    description: str
    owner_id: str         # REQUIRED — business rule §6
    due_date: datetime    # REQUIRED — business rule §6


@router.get("/compliance-issues")
async def list_issues(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ComplianceIssue))
    issues = result.scalars().all()
    return [{"id": str(i.id), "severity": i.severity, "description": i.description,
             "owner_id": str(i.owner_id), "due_date": i.due_date.isoformat(),
             "status": i.status, "audit_id": str(i.audit_id) if i.audit_id else None} for i in issues]


@router.post("/compliance-issues", status_code=201)
async def create_issue(req: ComplianceIssueCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    # Business rule: owner_id and due_date are required — validated by Pydantic already
    issue = ComplianceIssue(
        audit_id=uuid.UUID(req.audit_id) if req.audit_id else None,
        severity=req.severity, description=req.description,
        owner_id=uuid.UUID(req.owner_id), due_date=req.due_date,
    )
    db.add(issue)
    await db.flush()
    # Emit event for notifications
    await publish(COMPLIANCE_ISSUE_RAISED, {"issue_id": str(issue.id), "owner_id": req.owner_id, "severity": req.severity})
    return {"id": str(issue.id)}


@router.put("/compliance-issues/{issue_id}")
async def update_issue(issue_id: str, status: str, resolution_notes: Optional[str] = None,
                       db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(ComplianceIssue).where(ComplianceIssue.id == uuid.UUID(issue_id)))
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(404, "Not found")
    
    if current_user.role not in ["admin", "manager"] and str(issue.owner_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Insufficient permissions to modify this issue")

    issue.status = status
    if resolution_notes:
        issue.resolution_notes = resolution_notes
    if status.lower() == "resolved":
        await trigger_score_recompute()
    return {"id": str(issue.id), "status": issue.status}
