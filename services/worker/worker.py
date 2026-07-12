#!/usr/bin/env python
"""RQ Worker entry point for EcoSphere background jobs."""
import os
import sys
import logging
import json
import uuid
import io
import csv
from datetime import datetime, timezone, timedelta

from redis import Redis
from rq import Worker, Queue

sys.path.insert(0, "/api_app")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = Redis.from_url(REDIS_URL)


# ── Database helper ───────────────────────────────────────────────────────────

def get_sync_session():
    """Get a sync database session for worker jobs."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    db_url = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(db_url)
    return Session(engine), engine


# ── Filter infrastructure ─────────────────────────────────────────────────────

def _parse_filters(raw_filters):
    """Normalize filters from the ReportJob.filters JSON column."""
    if not raw_filters:
        return {}
    if isinstance(raw_filters, str):
        try:
            return json.loads(raw_filters)
        except (json.JSONDecodeError, TypeError):
            return {}
    return raw_filters


def _build_carbon_filter_sql(filters: dict):
    """Build WHERE clause fragments for carbon_transactions queries."""
    clauses = []
    params = {}
    if filters.get("department_id"):
        clauses.append("ct.department_id = :f_dept_id")
        params["f_dept_id"] = filters["department_id"]
    if filters.get("module"):
        clauses.append("ct.source_module = :f_module")
        params["f_module"] = filters["module"]
    if filters.get("employee_id"):
        clauses.append("ct.created_by_id = :f_employee_id")
        params["f_employee_id"] = filters["employee_id"]
    if filters.get("date_from"):
        clauses.append("ct.transaction_date >= :f_date_from")
        params["f_date_from"] = filters["date_from"]
    if filters.get("date_to"):
        clauses.append("ct.transaction_date <= :f_date_to")
        params["f_date_to"] = filters["date_to"]
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


def _build_participation_filter_sql(filters: dict):
    """Build WHERE clause fragments for employee_participations queries."""
    clauses = []
    params = {}
    if filters.get("employee_id"):
        clauses.append("ep.employee_id = :f_employee_id")
        params["f_employee_id"] = filters["employee_id"]
    if filters.get("department_id"):
        clauses.append("ca.department_id = :f_dept_id")
        params["f_dept_id"] = filters["department_id"]
    if filters.get("esg_category"):
        clauses.append("cat.name = :f_category")
        params["f_category"] = filters["esg_category"]
    if filters.get("date_from"):
        clauses.append("ep.created_at >= :f_date_from")
        params["f_date_from"] = filters["date_from"]
    if filters.get("date_to"):
        clauses.append("ep.created_at <= :f_date_to")
        params["f_date_to"] = filters["date_to"]
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


def _build_governance_filter_sql(filters: dict, table_alias: str = "ci"):
    """Build WHERE clause fragments for governance queries (compliance_issues, audits)."""
    clauses = []
    params = {}
    if filters.get("department_id"):
        if table_alias == "ci":
            clauses.append("ci.owner_id IN (SELECT id FROM users WHERE department_id = :f_dept_id)")
        elif table_alias == "a":
            clauses.append("a.department_id = :f_dept_id")
        params["f_dept_id"] = filters["department_id"]
    if filters.get("employee_id"):
        if table_alias == "ci":
            clauses.append("ci.owner_id = :f_employee_id")
            params["f_employee_id"] = filters["employee_id"]
    if filters.get("date_from"):
        date_col = "ci.created_at" if table_alias == "ci" else "a.scheduled_date"
        clauses.append(f"{date_col} >= :f_date_from")
        params["f_date_from"] = filters["date_from"]
    if filters.get("date_to"):
        date_col = "ci.created_at" if table_alias == "ci" else "a.scheduled_date"
        clauses.append(f"{date_col} <= :f_date_to")
        params["f_date_to"] = filters["date_to"]
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


def _build_challenge_filter_sql(filters: dict):
    """Build WHERE clause fragments for challenge queries."""
    clauses = []
    params = {}
    if filters.get("challenge_id"):
        clauses.append("cp.challenge_id = :f_challenge_id")
        params["f_challenge_id"] = filters["challenge_id"]
    if filters.get("employee_id"):
        clauses.append("cp.employee_id = :f_employee_id")
        params["f_employee_id"] = filters["employee_id"]
    if filters.get("date_from"):
        clauses.append("cp.created_at >= :f_date_from")
        params["f_date_from"] = filters["date_from"]
    if filters.get("date_to"):
        clauses.append("cp.created_at <= :f_date_to")
        params["f_date_to"] = filters["date_to"]
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


def _build_scores_filter_sql(filters: dict):
    """Build WHERE clause fragments for department_scores queries."""
    clauses = []
    params = {}
    if filters.get("department_id"):
        clauses.append("ds.department_id = :f_dept_id")
        params["f_dept_id"] = filters["department_id"]
    if filters.get("date_from"):
        clauses.append("ds.period >= :f_period_from")
        params["f_period_from"] = filters["date_from"][:7] if len(filters["date_from"]) >= 7 else filters["date_from"]
    if filters.get("date_to"):
        clauses.append("ds.period <= :f_period_to")
        params["f_period_to"] = filters["date_to"][:7] if len(filters["date_to"]) >= 7 else filters["date_to"]
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


# ── ESG Scoring Job ───────────────────────────────────────────────────────────

def compute_scores(period: str = None):
    """Idempotent ESG scoring job per department per period."""
    if not period:
        period = datetime.now(timezone.utc).strftime("%Y-%m")
    session, engine = get_sync_session()
    try:
        from sqlalchemy import text
        # Get all departments
        depts = session.execute(text("SELECT id FROM departments")).fetchall()
        cfg = session.execute(text("SELECT weight_environmental, weight_social, weight_governance FROM esg_config LIMIT 1")).fetchone()
        w_env = cfg[0] if cfg else 0.40
        w_soc = cfg[1] if cfg else 0.30
        w_gov = cfg[2] if cfg else 0.30

        period_start = datetime.strptime(period, "%Y-%m").replace(tzinfo=timezone.utc)
        period_end = (period_start + timedelta(days=32)).replace(day=1)

        for (dept_id,) in depts:
            # Environmental score: inverse of CO2e relative to max (lower = better)
            co2e_row = session.execute(text("""
                SELECT COALESCE(SUM(co2e_calculated), 0) FROM carbon_transactions
                WHERE department_id = :did AND transaction_date >= :start AND transaction_date < :end
            """), {"did": str(dept_id), "start": period_start, "end": period_end}).fetchone()
            co2e = co2e_row[0] if co2e_row else 0.0

            # Social score: approved CSR participations / total employees * 100
            social_row = session.execute(text("""
                SELECT COUNT(ep.id) FROM employee_participations ep
                JOIN csr_activities ca ON ep.activity_id = ca.id
                WHERE ep.approval_status = 'Approved'
                AND ca.department_id = :did
            """), {"did": str(dept_id)}).fetchone()
            emp_count_row = session.execute(text("SELECT employee_count FROM departments WHERE id = :did"), {"did": str(dept_id)}).fetchone()
            approved_participations = social_row[0] if social_row else 0
            emp_count = emp_count_row[0] if emp_count_row and emp_count_row[0] else 1
            social_score = min(100.0, (approved_participations / emp_count) * 100)

            # Governance score: resolved compliance issues / total issues * 100
            gov_row = session.execute(text("""
                SELECT COUNT(*) FROM compliance_issues WHERE owner_id IN (
                    SELECT id FROM users WHERE department_id = :did
                ) AND status = 'Resolved'
            """), {"did": str(dept_id)}).fetchone()
            total_gov_row = session.execute(text("""
                SELECT COUNT(*) FROM compliance_issues WHERE owner_id IN (
                    SELECT id FROM users WHERE department_id = :did
                )
            """), {"did": str(dept_id)}).fetchone()
            resolved = gov_row[0] if gov_row else 0
            total_issues = total_gov_row[0] if total_gov_row else 0
            gov_score = (resolved / total_issues * 100) if total_issues > 0 else 100.0

            # Environmental score: normalize (100 - score based on co2e)
            env_score = max(0.0, 100.0 - (co2e / 100.0))  # simplified normalization

            total_score = env_score * w_env + social_score * w_soc + gov_score * w_gov

            # Upsert (idempotent)
            existing = session.execute(text("""
                SELECT id FROM department_scores WHERE department_id = :did AND period = :period
            """), {"did": str(dept_id), "period": period}).fetchone()

            if existing:
                session.execute(text("""
                    UPDATE department_scores SET environmental_score=:env, social_score=:soc,
                    governance_score=:gov, total_score=:total, computed_at=NOW()
                    WHERE department_id=:did AND period=:period
                """), {"env": env_score, "soc": social_score, "gov": gov_score, "total": total_score,
                       "did": str(dept_id), "period": period})
            else:
                session.execute(text("""
                    INSERT INTO department_scores (id, department_id, period, environmental_score, social_score, governance_score, total_score)
                    VALUES (:id, :did, :period, :env, :soc, :gov, :total)
                """), {"id": str(uuid.uuid4()), "did": str(dept_id), "period": period,
                       "env": env_score, "soc": social_score, "gov": gov_score, "total": total_score})

        session.commit()
        logger.info(f"Scoring complete for period {period}")
    except Exception as e:
        session.rollback()
        logger.error(f"Scoring job error: {e}")
        raise
    finally:
        session.close()
        engine.dispose()


# ── Report Generation Job ─────────────────────────────────────────────────────

def generate_report(report_job_id: str):
    """Generate a report file and upload to MinIO."""
    session, engine = get_sync_session()
    try:
        from sqlalchemy import text
        from minio import Minio

        job = session.execute(text("SELECT * FROM report_jobs WHERE id = :id"), {"id": report_job_id}).fetchone()
        if not job:
            return

        session.execute(text("UPDATE report_jobs SET status = 'generating' WHERE id = :id"), {"id": report_job_id})
        session.commit()

        report_type = job.report_type
        fmt = job.format
        filters = _parse_filters(job.filters)

        # Generate content based on format
        if fmt == "csv":
            content = _generate_csv_report(session, report_type, filters)
            content_type = "text/csv"
            file_ext = "csv"
        elif fmt == "xlsx":
            content = _generate_xlsx_report(session, report_type, filters)
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            file_ext = "xlsx"
        else:  # pdf
            content = _generate_pdf_report(session, report_type, filters)
            content_type = "application/pdf"
            file_ext = "pdf"

        # Upload to MinIO
        minio_client = Minio(
            os.getenv("MINIO_ENDPOINT", "minio:9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin_secret"),
            secure=False,
        )
        bucket = os.getenv("MINIO_BUCKET", "ecosphere")
        object_name = f"reports/{report_job_id}.{file_ext}"
        minio_client.put_object(bucket, object_name, io.BytesIO(content), len(content), content_type=content_type)

        url = minio_client.presigned_get_object(bucket, object_name, expires=timedelta(hours=24))

        session.execute(text("""
            UPDATE report_jobs SET status='ready', file_ref=:ref, download_url=:url, completed_at=NOW()
            WHERE id=:id
        """), {"ref": object_name, "url": url, "id": report_job_id})
        session.commit()
        logger.info(f"Report {report_job_id} ready: {object_name}")
    except Exception as e:
        session.execute(text("UPDATE report_jobs SET status='failed', error_msg=:msg WHERE id=:id"),
                        {"msg": str(e)[:500], "id": report_job_id})
        session.commit()
        logger.error(f"Report generation error: {e}")
    finally:
        session.close()
        engine.dispose()


# ── Data Fetchers (shared by CSV/XLSX/PDF) ────────────────────────────────────

def _fetch_environmental_data(session, filters: dict):
    """Fetch carbon transactions with filters applied."""
    from sqlalchemy import text
    where_extra, params = _build_carbon_filter_sql(filters)
    sql = f"""
        SELECT ct.department_id, d.name AS department_name, ct.source_module,
               ct.quantity, ct.co2e_calculated, ct.transaction_date,
               ct.is_auto_calculated, ct.notes
        FROM carbon_transactions ct
        LEFT JOIN departments d ON ct.department_id = d.id
        WHERE 1=1 {where_extra}
        ORDER BY ct.transaction_date DESC
        LIMIT 5000
    """
    return session.execute(text(sql), params).fetchall()


def _fetch_social_data(session, filters: dict):
    """Fetch employee participations with filters applied."""
    from sqlalchemy import text
    where_extra, params = _build_participation_filter_sql(filters)
    sql = f"""
        SELECT ep.employee_id, u.full_name AS employee_name,
               ca.title AS activity_title, ca.department_id,
               d.name AS department_name, cat.name AS category_name,
               ep.approval_status, ep.points_earned, ep.completion_date, ep.created_at
        FROM employee_participations ep
        JOIN csr_activities ca ON ep.activity_id = ca.id
        LEFT JOIN users u ON ep.employee_id = u.id
        LEFT JOIN departments d ON ca.department_id = d.id
        LEFT JOIN categories cat ON ca.category_id = cat.id
        WHERE 1=1 {where_extra}
        ORDER BY ep.created_at DESC
        LIMIT 5000
    """
    return session.execute(text(sql), params).fetchall()


def _fetch_governance_policies(session, filters: dict):
    """Fetch ESG policies."""
    from sqlalchemy import text
    sql = """
        SELECT p.id, p.title, p.version, p.status, p.effective_date,
               p.requires_acknowledgement,
               (SELECT COUNT(*) FROM policy_acknowledgements pa WHERE pa.policy_id = p.id) AS ack_count
        FROM esg_policies p
        ORDER BY p.effective_date DESC
    """
    return session.execute(text(sql)).fetchall()


def _fetch_governance_audits(session, filters: dict):
    """Fetch audits with filters applied."""
    from sqlalchemy import text
    where_extra, params = _build_governance_filter_sql(filters, "a")
    sql = f"""
        SELECT a.id, a.title, a.department_id, d.name AS department_name,
               a.auditor, a.scheduled_date, a.status, a.findings_summary,
               (SELECT COUNT(*) FROM compliance_issues ci WHERE ci.audit_id = a.id) AS issue_count
        FROM audits a
        LEFT JOIN departments d ON a.department_id = d.id
        WHERE 1=1 {where_extra}
        ORDER BY a.scheduled_date DESC
        LIMIT 2000
    """
    return session.execute(text(sql), params).fetchall()


def _fetch_compliance_issues(session, filters: dict):
    """Fetch compliance issues with filters applied."""
    from sqlalchemy import text
    where_extra, params = _build_governance_filter_sql(filters, "ci")
    sql = f"""
        SELECT ci.id, ci.severity, ci.description, ci.status, ci.due_date,
               ci.resolution_notes, ci.created_at, ci.updated_at,
               u.full_name AS owner_name, u.department_id,
               d.name AS department_name,
               a.title AS audit_title
        FROM compliance_issues ci
        LEFT JOIN users u ON ci.owner_id = u.id
        LEFT JOIN departments d ON u.department_id = d.id
        LEFT JOIN audits a ON ci.audit_id = a.id
        WHERE 1=1 {where_extra}
        ORDER BY ci.created_at DESC
        LIMIT 5000
    """
    return session.execute(text(sql), params).fetchall()


def _fetch_scores_data(session, filters: dict):
    """Fetch department scores with filters applied."""
    from sqlalchemy import text
    where_extra, params = _build_scores_filter_sql(filters)
    sql = f"""
        SELECT ds.department_id, d.name AS department_name, ds.period,
               ds.environmental_score, ds.social_score, ds.governance_score,
               ds.total_score, ds.computed_at
        FROM department_scores ds
        LEFT JOIN departments d ON ds.department_id = d.id
        WHERE 1=1 {where_extra}
        ORDER BY ds.period DESC, ds.total_score DESC
    """
    return session.execute(text(sql), params).fetchall()


def _fetch_challenge_data(session, filters: dict):
    """Fetch challenge participations with filters applied."""
    from sqlalchemy import text
    where_extra, params = _build_challenge_filter_sql(filters)
    sql = f"""
        SELECT cp.id, c.title AS challenge_title, c.difficulty, c.xp AS challenge_xp,
               u.full_name AS employee_name, cp.progress, cp.approval_status,
               cp.xp_awarded, cp.created_at
        FROM challenge_participations cp
        JOIN challenges c ON cp.challenge_id = c.id
        LEFT JOIN users u ON cp.employee_id = u.id
        WHERE 1=1 {where_extra}
        ORDER BY cp.created_at DESC
        LIMIT 5000
    """
    return session.execute(text(sql), params).fetchall()


def _fetch_kpis(session, filters: dict):
    """Compute KPI summary values for report headers."""
    from sqlalchemy import text
    kpis = {}

    # Total CO2e
    cw, cp = _build_carbon_filter_sql(filters)
    row = session.execute(text(f"""
        SELECT COALESCE(SUM(ct.co2e_calculated), 0), COUNT(*)
        FROM carbon_transactions ct WHERE 1=1 {cw}
    """), cp).fetchone()
    kpis["total_co2e"] = round(row[0], 2) if row else 0.0
    kpis["transaction_count"] = row[1] if row else 0

    # Social participation rate
    pw, pp = _build_participation_filter_sql(filters)
    row = session.execute(text(f"""
        SELECT COUNT(*) FILTER (WHERE ep.approval_status = 'Approved'),
               COUNT(*)
        FROM employee_participations ep
        JOIN csr_activities ca ON ep.activity_id = ca.id
        LEFT JOIN categories cat ON ca.category_id = cat.id
        WHERE 1=1 {pw}
    """), pp).fetchone()
    approved = row[0] if row else 0
    total = row[1] if row else 0
    kpis["approved_participations"] = approved
    kpis["total_participations"] = total
    kpis["participation_rate"] = round((approved / total * 100), 1) if total > 0 else 0.0

    # Compliance rate
    gw, gp = _build_governance_filter_sql(filters, "ci")
    row = session.execute(text(f"""
        SELECT COUNT(*) FILTER (WHERE ci.status = 'Resolved'),
               COUNT(*) FILTER (WHERE ci.status IN ('Open', 'Overdue')),
               COUNT(*)
        FROM compliance_issues ci
        WHERE 1=1 {gw}
    """), gp).fetchone()
    resolved = row[0] if row else 0
    pending = row[1] if row else 0
    total_issues = row[2] if row else 0
    kpis["resolved_issues"] = resolved
    kpis["pending_issues"] = pending
    kpis["total_issues"] = total_issues
    kpis["compliance_rate"] = round((resolved / total_issues * 100), 1) if total_issues > 0 else 100.0

    # Overall ESG score
    sw, sp = _build_scores_filter_sql(filters)
    row = session.execute(text(f"""
        SELECT AVG(ds.environmental_score), AVG(ds.social_score),
               AVG(ds.governance_score), AVG(ds.total_score), COUNT(*)
        FROM department_scores ds WHERE 1=1 {sw}
    """), sp).fetchone()
    kpis["avg_env_score"] = round(row[0], 1) if row and row[0] else 0.0
    kpis["avg_soc_score"] = round(row[1], 1) if row and row[1] else 0.0
    kpis["avg_gov_score"] = round(row[2], 1) if row and row[2] else 0.0
    kpis["avg_total_score"] = round(row[3], 1) if row and row[3] else 0.0
    kpis["departments_scored"] = row[4] if row else 0

    return kpis


# ── CSV Generator ─────────────────────────────────────────────────────────────

def _generate_csv_report(session, report_type: str, filters: dict) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    if report_type == "environmental":
        writer.writerow(["Department ID", "Department", "Source Module", "Quantity", "CO2e (kg)", "Date", "Auto-Calculated", "Notes"])
        for row in _fetch_environmental_data(session, filters):
            writer.writerow([str(row[0]), row[1] or "", row[2], row[3], row[4], str(row[5]) if row[5] else "", row[6], row[7] or ""])

    elif report_type == "social":
        writer.writerow(["Employee ID", "Employee", "Activity", "Department", "Category", "Status", "Points", "Completion Date"])
        for row in _fetch_social_data(session, filters):
            writer.writerow([str(row[0]), row[1] or "", row[2], row[4] or "", row[5] or "", row[6], row[7], str(row[8]) if row[8] else ""])

    elif report_type == "governance":
        # Policies
        writer.writerow(["=== ESG Policies ==="])
        writer.writerow(["Title", "Version", "Status", "Effective Date", "Requires Acknowledgement", "Acknowledgements"])
        for row in _fetch_governance_policies(session, filters):
            writer.writerow([row[1], row[2], row[3], str(row[4]) if row[4] else "", row[5], row[6]])
        writer.writerow([])
        # Audits
        writer.writerow(["=== Audits ==="])
        writer.writerow(["Title", "Department", "Auditor", "Scheduled Date", "Status", "Issues Found", "Findings"])
        for row in _fetch_governance_audits(session, filters):
            writer.writerow([row[1], row[3] or "", row[4], str(row[5]) if row[5] else "", row[6], row[8], (row[7] or "")[:200]])
        writer.writerow([])
        # Compliance Issues
        writer.writerow(["=== Compliance Issues ==="])
        writer.writerow(["Severity", "Description", "Status", "Due Date", "Owner", "Department", "Audit", "Resolution Notes"])
        for row in _fetch_compliance_issues(session, filters):
            writer.writerow([row[1], (row[2] or "")[:200], row[3], str(row[4]) if row[4] else "",
                             row[8] or "", row[10] or "", row[11] or "", (row[5] or "")[:200]])

    elif report_type == "summary":
        writer.writerow(["Department ID", "Department", "Period", "Env Score", "Social Score", "Gov Score", "Total Score", "Computed At"])
        for row in _fetch_scores_data(session, filters):
            writer.writerow([str(row[0]), row[1] or "", row[2], row[3], row[4], row[5], row[6], str(row[7]) if row[7] else ""])

    elif report_type == "custom":
        # Custom: include data from all modules that match filters
        writer.writerow(["=== Department Scores ==="])
        writer.writerow(["Department", "Period", "Env Score", "Social Score", "Gov Score", "Total"])
        for row in _fetch_scores_data(session, filters):
            writer.writerow([row[1] or str(row[0]), row[2], row[3], row[4], row[5], row[6]])
        writer.writerow([])

        writer.writerow(["=== Carbon Transactions ==="])
        writer.writerow(["Department", "Source Module", "CO2e (kg)", "Date"])
        for row in _fetch_environmental_data(session, filters):
            writer.writerow([row[1] or str(row[0]), row[2], row[4], str(row[5]) if row[5] else ""])
        writer.writerow([])

        writer.writerow(["=== Social Participations ==="])
        writer.writerow(["Employee", "Activity", "Status", "Points"])
        for row in _fetch_social_data(session, filters):
            writer.writerow([row[1] or str(row[0]), row[2], row[6], row[7]])
        writer.writerow([])

        writer.writerow(["=== Compliance Issues ==="])
        writer.writerow(["Severity", "Description", "Status", "Owner", "Department"])
        for row in _fetch_compliance_issues(session, filters):
            writer.writerow([row[1], (row[2] or "")[:200], row[3], row[8] or "", row[10] or ""])

    else:
        # Fallback — department scores
        writer.writerow(["Department", "Period", "Env Score", "Social Score", "Gov Score", "Total"])
        for row in _fetch_scores_data(session, filters):
            writer.writerow([row[1] or str(row[0]), row[2], row[3], row[4], row[5], row[6]])

    return buffer.getvalue().encode('utf-8')


# ── XLSX Generator ────────────────────────────────────────────────────────────

def _write_xlsx_sheet(wb, sheet_name: str, headers: list, rows: list, row_mapper=None):
    """Helper to write a single sheet with header formatting."""
    ws = wb.add_worksheet(sheet_name[:31])  # Excel sheet names max 31 chars
    bold = wb.add_format({'bold': True, 'bg_color': '#1B5E20', 'font_color': 'white', 'border': 1})
    date_fmt = wb.add_format({'num_format': 'yyyy-mm-dd'})
    num_fmt = wb.add_format({'num_format': '#,##0.00'})
    for col, h in enumerate(headers):
        ws.write(0, col, h, bold)
    for r, row in enumerate(rows):
        mapped = row_mapper(row) if row_mapper else [str(v) if v is not None else "" for v in row]
        for c, val in enumerate(mapped):
            if isinstance(val, (int, float)):
                ws.write(r + 1, c, val, num_fmt)
            else:
                ws.write(r + 1, c, str(val) if val is not None else "")
    ws.autofilter(0, 0, len(rows), len(headers) - 1)
    return ws


def _generate_xlsx_report(session, report_type: str, filters: dict) -> bytes:
    import xlsxwriter
    buffer = io.BytesIO()
    wb = xlsxwriter.Workbook(buffer, {'in_memory': True})

    if report_type == "environmental":
        rows = _fetch_environmental_data(session, filters)
        _write_xlsx_sheet(wb, "Environmental", [
            "Department ID", "Department", "Source Module", "Quantity", "CO2e (kg)",
            "Transaction Date", "Auto-Calculated", "Notes"
        ], rows, lambda r: [str(r[0]), r[1] or "", r[2], r[3], r[4], str(r[5]) if r[5] else "", str(r[6]), r[7] or ""])

    elif report_type == "social":
        rows = _fetch_social_data(session, filters)
        _write_xlsx_sheet(wb, "Social", [
            "Employee ID", "Employee", "Activity", "Department ID", "Department",
            "Category", "Status", "Points Earned", "Completion Date", "Created"
        ], rows, lambda r: [str(r[0]), r[1] or "", r[2], str(r[3]) if r[3] else "",
                            r[4] or "", r[5] or "", r[6], r[7],
                            str(r[8]) if r[8] else "", str(r[9]) if r[9] else ""])

    elif report_type == "governance":
        # Sheet 1: Policies
        policies = _fetch_governance_policies(session, filters)
        _write_xlsx_sheet(wb, "Policies", [
            "Title", "Version", "Status", "Effective Date", "Requires Ack", "Acknowledgements"
        ], policies, lambda r: [r[1], r[2], r[3], str(r[4]) if r[4] else "", str(r[5]), r[6]])

        # Sheet 2: Audits
        audits = _fetch_governance_audits(session, filters)
        _write_xlsx_sheet(wb, "Audits", [
            "Title", "Department", "Auditor", "Scheduled Date", "Status", "Issues Found", "Findings Summary"
        ], audits, lambda r: [r[1], r[3] or "", r[4], str(r[5]) if r[5] else "", r[6], r[8], (r[7] or "")[:500]])

        # Sheet 3: Compliance Issues
        issues = _fetch_compliance_issues(session, filters)
        _write_xlsx_sheet(wb, "Compliance Issues", [
            "Severity", "Description", "Status", "Due Date", "Owner", "Department", "Audit", "Resolution Notes", "Created", "Updated"
        ], issues, lambda r: [r[1], (r[2] or "")[:500], r[3], str(r[4]) if r[4] else "",
                              r[8] or "", r[10] or "", r[11] or "", (r[5] or "")[:500],
                              str(r[6]) if r[6] else "", str(r[7]) if r[7] else ""])

    elif report_type == "summary":
        # Sheet 1: Overview scores
        scores = _fetch_scores_data(session, filters)
        _write_xlsx_sheet(wb, "ESG Scores", [
            "Department ID", "Department", "Period", "Environmental Score",
            "Social Score", "Governance Score", "Total Score", "Computed At"
        ], scores, lambda r: [str(r[0]), r[1] or "", r[2], r[3], r[4], r[5], r[6], str(r[7]) if r[7] else ""])

        # Sheet 2: Environmental summary
        env_rows = _fetch_environmental_data(session, filters)
        _write_xlsx_sheet(wb, "Environmental Data", [
            "Department", "Source Module", "CO2e (kg)", "Date"
        ], env_rows, lambda r: [r[1] or str(r[0]), r[2], r[4], str(r[5]) if r[5] else ""])

        # Sheet 3: Social summary
        soc_rows = _fetch_social_data(session, filters)
        _write_xlsx_sheet(wb, "Social Data", [
            "Employee", "Activity", "Status", "Points"
        ], soc_rows, lambda r: [r[1] or str(r[0]), r[2], r[6], r[7]])

        # Sheet 4: Governance summary
        issues = _fetch_compliance_issues(session, filters)
        _write_xlsx_sheet(wb, "Governance Data", [
            "Severity", "Description", "Status", "Owner", "Department"
        ], issues, lambda r: [r[1], (r[2] or "")[:300], r[3], r[8] or "", r[10] or ""])

    elif report_type == "custom":
        has_sheets = False
        # Scores
        scores = _fetch_scores_data(session, filters)
        if scores:
            _write_xlsx_sheet(wb, "Scores", [
                "Department", "Period", "Env", "Social", "Gov", "Total"
            ], scores, lambda r: [r[1] or str(r[0]), r[2], r[3], r[4], r[5], r[6]])
            has_sheets = True

        # Environmental
        env_rows = _fetch_environmental_data(session, filters)
        if env_rows:
            _write_xlsx_sheet(wb, "Environmental", [
                "Department", "Source Module", "CO2e (kg)", "Date"
            ], env_rows, lambda r: [r[1] or str(r[0]), r[2], r[4], str(r[5]) if r[5] else ""])
            has_sheets = True

        # Social
        soc_rows = _fetch_social_data(session, filters)
        if soc_rows:
            _write_xlsx_sheet(wb, "Social", [
                "Employee", "Activity", "Status", "Points"
            ], soc_rows, lambda r: [r[1] or str(r[0]), r[2], r[6], r[7]])
            has_sheets = True

        # Governance
        issues = _fetch_compliance_issues(session, filters)
        if issues:
            _write_xlsx_sheet(wb, "Compliance Issues", [
                "Severity", "Description", "Status", "Owner", "Department"
            ], issues, lambda r: [r[1], (r[2] or "")[:300], r[3], r[8] or "", r[10] or ""])
            has_sheets = True

        # Challenges
        challenges = _fetch_challenge_data(session, filters)
        if challenges:
            _write_xlsx_sheet(wb, "Challenges", [
                "Challenge", "Difficulty", "Employee", "Progress", "Status", "XP Awarded"
            ], challenges, lambda r: [r[1], r[2], r[4] or "", r[5], r[6], r[7]])
            has_sheets = True
            
        if not has_sheets:
            _write_xlsx_sheet(wb, "No Data", ["Message"], [["No data matched the selected filters"]])

    else:
        scores = _fetch_scores_data(session, filters)
        _write_xlsx_sheet(wb, "Scores", [
            "Department", "Period", "Env", "Social", "Gov", "Total"
        ], scores, lambda r: [r[1] or str(r[0]), r[2], r[3], r[4], r[5], r[6]])

    wb.close()
    return buffer.getvalue()


# ── PDF Generator ─────────────────────────────────────────────────────────────

_PDF_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 2cm; }
  body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #1e293b; font-size: 11px; line-height: 1.4; }
  .header { background: linear-gradient(135deg, #065f46, #0f766e); color: white; padding: 24px 28px; border-radius: 8px; margin-bottom: 20px; }
  .header h1 { margin: 0 0 4px 0; font-size: 22px; font-weight: 700; }
  .header p { margin: 0; font-size: 11px; opacity: 0.85; }
  .meta { display: flex; gap: 24px; margin-bottom: 18px; font-size: 10px; color: #64748b; }
  .meta span { background: #f1f5f9; padding: 4px 10px; border-radius: 4px; }
  .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
  .kpi-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; text-align: center; }
  .kpi-card .value { font-size: 24px; font-weight: 700; color: #0f172a; }
  .kpi-card .label { font-size: 10px; color: #64748b; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.5px; }
  .kpi-card.env .value { color: #059669; }
  .kpi-card.soc .value { color: #d97706; }
  .kpi-card.gov .value { color: #4f46e5; }
  .kpi-card.total .value { color: #0891b2; }
  h2 { font-size: 15px; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-top: 24px; }
  table { width: 100%; border-collapse: collapse; font-size: 10px; margin-bottom: 16px; }
  th { background: #1B5E20; color: white; padding: 8px 6px; text-align: left; font-weight: 600; font-size: 9px; text-transform: uppercase; letter-spacing: 0.3px; }
  td { padding: 6px; border-bottom: 1px solid #e2e8f0; }
  tr:nth-child(even) td { background: #f8fafc; }
  .severity-critical { color: #dc2626; font-weight: 700; }
  .severity-high { color: #ea580c; font-weight: 600; }
  .severity-medium { color: #d97706; }
  .severity-low { color: #65a30d; }
  .status-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 9px; font-weight: 600; }
  .status-resolved { background: #dcfce7; color: #166534; }
  .status-open { background: #fef3c7; color: #92400e; }
  .status-overdue { background: #fee2e2; color: #991b1b; }
  .footer { margin-top: 30px; padding-top: 12px; border-top: 1px solid #e2e8f0; text-align: center; font-size: 9px; color: #94a3b8; }
  .section-summary { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 12px; margin-bottom: 16px; font-size: 10px; }
  .dept-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .dept-stat { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px; }
  .dept-stat .name { font-weight: 600; font-size: 10px; color: #0f172a; }
  .dept-stat .score { font-size: 18px; font-weight: 700; color: #0891b2; }
</style>
</head>
<body>
  <div class="header">
    <h1>EcoSphere {{ report_title }} Report</h1>
    <p>Generated: {{ generated_at }} | Format: PDF</p>
  </div>

  <div class="meta">
    <span>Report Type: <strong>{{ report_type }}</strong></span>
    <span>Period: <strong>{{ period }}</strong></span>
    {% if filters_description %}<span>Filters: <strong>{{ filters_description }}</strong></span>{% endif %}
  </div>

  <!-- KPI Cards -->
  <div class="kpi-grid">
    <div class="kpi-card total"><div class="value">{{ kpis.avg_total_score }}</div><div class="label">Overall ESG Score</div></div>
    <div class="kpi-card env"><div class="value">{{ kpis.avg_env_score }}</div><div class="label">Environmental Avg</div></div>
    <div class="kpi-card soc"><div class="value">{{ kpis.avg_soc_score }}</div><div class="label">Social Avg</div></div>
    <div class="kpi-card gov"><div class="value">{{ kpis.avg_gov_score }}</div><div class="label">Governance Avg</div></div>
  </div>

  <div class="kpi-grid">
    <div class="kpi-card"><div class="value">{{ kpis.total_co2e }}</div><div class="label">Total CO2e (kg)</div></div>
    <div class="kpi-card"><div class="value">{{ kpis.participation_rate }}%</div><div class="label">Participation Rate</div></div>
    <div class="kpi-card"><div class="value">{{ kpis.compliance_rate }}%</div><div class="label">Compliance Rate</div></div>
    <div class="kpi-card"><div class="value">{{ kpis.departments_scored }}</div><div class="label">Departments Scored</div></div>
  </div>

  {% if dept_stats %}
  <h2>Department Statistics</h2>
  <div class="dept-stats">
    {% for ds in dept_stats[:12] %}
    <div class="dept-stat">
      <div class="name">{{ ds.name }}</div>
      <div class="score">{{ ds.total }}</div>
      <div style="font-size:9px;color:#64748b">E:{{ ds.env }} S:{{ ds.soc }} G:{{ ds.gov }}</div>
    </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if env_rows %}
  <h2>Environmental — Carbon Transactions</h2>
  <table>
    <tr><th>Department</th><th>Source</th><th>Quantity</th><th>CO2e (kg)</th><th>Date</th></tr>
    {% for r in env_rows[:50] %}
    <tr><td>{{ r[1] or r[0] }}</td><td>{{ r[2] }}</td><td>{{ r[3] }}</td><td>{{ r[4] }}</td><td>{{ r[5] }}</td></tr>
    {% endfor %}
    {% if env_rows|length > 50 %}<tr><td colspan="5" style="text-align:center;color:#64748b;">… and {{ env_rows|length - 50 }} more rows</td></tr>{% endif %}
  </table>
  {% endif %}

  {% if soc_rows %}
  <h2>Social — Employee Participations</h2>
  <table>
    <tr><th>Employee</th><th>Activity</th><th>Department</th><th>Status</th><th>Points</th></tr>
    {% for r in soc_rows[:50] %}
    <tr><td>{{ r[1] or r[0] }}</td><td>{{ r[2] }}</td><td>{{ r[4] or '' }}</td><td>{{ r[6] }}</td><td>{{ r[7] }}</td></tr>
    {% endfor %}
    {% if soc_rows|length > 50 %}<tr><td colspan="5" style="text-align:center;color:#64748b;">… and {{ soc_rows|length - 50 }} more rows</td></tr>{% endif %}
  </table>
  {% endif %}

  {% if policies %}
  <h2>Governance — ESG Policies</h2>
  <table>
    <tr><th>Title</th><th>Version</th><th>Status</th><th>Effective Date</th><th>Acknowledgements</th></tr>
    {% for r in policies %}
    <tr><td>{{ r[1] }}</td><td>{{ r[2] }}</td><td>{{ r[3] }}</td><td>{{ r[4] }}</td><td>{{ r[6] }}</td></tr>
    {% endfor %}
  </table>
  {% endif %}

  {% if audits %}
  <h2>Governance — Audits</h2>
  <table>
    <tr><th>Title</th><th>Department</th><th>Auditor</th><th>Date</th><th>Status</th><th>Issues</th></tr>
    {% for r in audits %}
    <tr><td>{{ r[1] }}</td><td>{{ r[3] or '' }}</td><td>{{ r[4] }}</td><td>{{ r[5] }}</td><td>{{ r[6] }}</td><td>{{ r[8] }}</td></tr>
    {% endfor %}
  </table>
  {% endif %}

  {% if issues %}
  <h2>Governance — Compliance Issues</h2>
  <div class="section-summary">
    Resolved: <strong>{{ kpis.resolved_issues }}</strong> |
    Pending/Open: <strong>{{ kpis.pending_issues }}</strong> |
    Total: <strong>{{ kpis.total_issues }}</strong> |
    Compliance Rate: <strong>{{ kpis.compliance_rate }}%</strong>
  </div>
  <table>
    <tr><th>Severity</th><th>Description</th><th>Status</th><th>Due Date</th><th>Owner</th><th>Department</th></tr>
    {% for r in issues[:80] %}
    <tr>
      <td class="severity-{{ r[1]|lower }}">{{ r[1] }}</td>
      <td>{{ r[2][:120] if r[2] else '' }}</td>
      <td><span class="status-badge status-{{ r[3]|lower|replace(' ', '-') }}">{{ r[3] }}</span></td>
      <td>{{ r[4] }}</td><td>{{ r[8] or '' }}</td><td>{{ r[10] or '' }}</td>
    </tr>
    {% endfor %}
    {% if issues|length > 80 %}<tr><td colspan="6" style="text-align:center;color:#64748b;">… and {{ issues|length - 80 }} more rows</td></tr>{% endif %}
  </table>
  {% endif %}

  {% if challenge_rows %}
  <h2>Challenges</h2>
  <table>
    <tr><th>Challenge</th><th>Difficulty</th><th>Employee</th><th>Progress</th><th>Status</th><th>XP</th></tr>
    {% for r in challenge_rows[:50] %}
    <tr><td>{{ r[1] }}</td><td>{{ r[2] }}</td><td>{{ r[4] or '' }}</td><td>{{ r[5] }}%</td><td>{{ r[6] }}</td><td>{{ r[7] }}</td></tr>
    {% endfor %}
  </table>
  {% endif %}

  <div class="footer">
    EcoSphere ESG Management Platform · Report ID: {{ report_id }} · Generated {{ generated_at }}
  </div>
</body>
</html>
"""


def _generate_pdf_report(session, report_type: str, filters: dict) -> bytes:
    """Generate a data-rich PDF report via WeasyPrint with ReportLab fallback."""
    from jinja2 import Template

    now = datetime.now(timezone.utc)
    kpis = _fetch_kpis(session, filters)

    # Build filter description string
    filter_parts = []
    for k, v in filters.items():
        if v:
            filter_parts.append(f"{k}: {v}")
    filters_description = ", ".join(filter_parts) if filter_parts else ""

    # Fetch data based on report type
    env_rows = []
    soc_rows = []
    policies = []
    audits = []
    issues = []
    challenge_rows = []
    dept_stats = []

    # Department stats (always show)
    scores_data = _fetch_scores_data(session, filters)
    dept_stats = [
        {"name": r[1] or str(r[0])[:8], "env": round(r[3], 1), "soc": round(r[4], 1),
         "gov": round(r[5], 1), "total": round(r[6], 1)}
        for r in scores_data
    ]

    if report_type in ("environmental", "summary", "custom"):
        env_rows = _fetch_environmental_data(session, filters)
    if report_type in ("social", "summary", "custom"):
        soc_rows = _fetch_social_data(session, filters)
    if report_type in ("governance", "summary", "custom"):
        policies = _fetch_governance_policies(session, filters)
        audits = _fetch_governance_audits(session, filters)
        issues = _fetch_compliance_issues(session, filters)
    if report_type == "custom":
        challenge_rows = _fetch_challenge_data(session, filters)

    title_map = {
        "environmental": "Environmental",
        "social": "Social",
        "governance": "Governance",
        "summary": "Summary",
        "custom": "Custom",
    }
    report_title = title_map.get(report_type, report_type.title())

    template_ctx = {
        "report_title": report_title,
        "report_type": report_type,
        "report_id": "—",
        "generated_at": now.strftime("%Y-%m-%d %H:%M UTC"),
        "period": now.strftime("%Y-%m"),
        "filters_description": filters_description,
        "kpis": kpis,
        "dept_stats": dept_stats,
        "env_rows": env_rows,
        "soc_rows": soc_rows,
        "policies": policies,
        "audits": audits,
        "issues": issues,
        "challenge_rows": challenge_rows,
    }

    try:
        from weasyprint import HTML
        tmpl = Template(_PDF_TEMPLATE)
        html_str = tmpl.render(**template_ctx)
        return HTML(string=html_str).write_pdf()
    except Exception as weasy_err:
        logger.warning(f"WeasyPrint unavailable ({weasy_err}), falling back to ReportLab")
        return _generate_pdf_reportlab(template_ctx)


def _generate_pdf_reportlab(ctx: dict) -> bytes:
    """ReportLab fallback PDF with actual data tables."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle('ReportTitle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#065f46'))
    story.append(Paragraph(f"EcoSphere {ctx['report_title']} Report", title_style))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(f"Generated: {ctx['generated_at']} | Type: {ctx['report_type']}", styles['Normal']))
    if ctx.get('filters_description'):
        story.append(Paragraph(f"Filters: {ctx['filters_description']}", styles['Normal']))
    story.append(Spacer(1, 6*mm))

    # KPI summary
    kpis = ctx['kpis']
    kpi_data = [
        ["Overall ESG", "Environmental Avg", "Social Avg", "Governance Avg"],
        [str(kpis['avg_total_score']), str(kpis['avg_env_score']), str(kpis['avg_soc_score']), str(kpis['avg_gov_score'])],
        ["Total CO2e (kg)", "Participation Rate", "Compliance Rate", "Depts Scored"],
        [str(kpis['total_co2e']), f"{kpis['participation_rate']}%", f"{kpis['compliance_rate']}%", str(kpis['departments_scored'])],
    ]
    kpi_table = Table(kpi_data, colWidths=[doc.width/4]*4)
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#f1f5f9')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTSIZE', (0, 1), (-1, 1), 14),
        ('FONTSIZE', (0, 3), (-1, 3), 14),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 8*mm))

    # Helper for data tables
    header_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B5E20')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ])

    def _add_table(title, headers, rows, max_rows=40):
        story.append(Paragraph(title, styles['Heading2']))
        story.append(Spacer(1, 2*mm))
        data = [headers] + rows[:max_rows]
        if not rows:
            story.append(Paragraph("No data available.", styles['Normal']))
            story.append(Spacer(1, 4*mm))
            return
        ncols = len(headers)
        col_w = doc.width / ncols
        t = Table(data, colWidths=[col_w]*ncols, repeatRows=1)
        t.setStyle(header_style)
        story.append(t)
        if len(rows) > max_rows:
            story.append(Paragraph(f"… and {len(rows) - max_rows} more rows", styles['Normal']))
        story.append(Spacer(1, 6*mm))

    # Department stats
    if ctx.get('dept_stats'):
        dept_rows = [[d['name'], str(d['env']), str(d['soc']), str(d['gov']), str(d['total'])] for d in ctx['dept_stats'][:20]]
        _add_table("Department Statistics", ["Department", "Environmental", "Social", "Governance", "Total"], dept_rows)

    # Environmental
    if ctx.get('env_rows'):
        _add_table("Environmental — Carbon Transactions",
                   ["Department", "Source", "Qty", "CO2e", "Date"],
                   [[str(r[1] or r[0]), str(r[2]), str(r[3]), str(r[4]), str(r[5])] for r in ctx['env_rows']])

    # Social
    if ctx.get('soc_rows'):
        _add_table("Social — Participations",
                   ["Employee", "Activity", "Status", "Points"],
                   [[str(r[1] or r[0]), str(r[2]), str(r[6]), str(r[7])] for r in ctx['soc_rows']])

    # Governance
    if ctx.get('policies'):
        _add_table("Governance — Policies",
                   ["Title", "Version", "Status", "Effective Date", "Acks"],
                   [[str(r[1]), str(r[2]), str(r[3]), str(r[4]), str(r[6])] for r in ctx['policies']])

    if ctx.get('audits'):
        _add_table("Governance — Audits",
                   ["Title", "Dept", "Auditor", "Date", "Status", "Issues"],
                   [[str(r[1]), str(r[3] or ''), str(r[4]), str(r[5]), str(r[6]), str(r[8])] for r in ctx['audits']])

    if ctx.get('issues'):
        _add_table("Governance — Compliance Issues",
                   ["Severity", "Description", "Status", "Owner", "Dept"],
                   [[str(r[1]), str(r[2] or '')[:80], str(r[3]), str(r[8] or ''), str(r[10] or '')] for r in ctx['issues']])

    if ctx.get('challenge_rows'):
        _add_table("Challenges",
                   ["Challenge", "Difficulty", "Employee", "Progress", "Status", "XP"],
                   [[str(r[1]), str(r[2]), str(r[4] or ''), f"{r[5]}%", str(r[6]), str(r[7])] for r in ctx['challenge_rows']])

    # Footer
    story.append(Spacer(1, 10*mm))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#94a3b8'), alignment=1)
    story.append(Paragraph(f"EcoSphere ESG Management Platform · Generated {ctx['generated_at']}", footer_style))

    doc.build(story)
    return buffer.getvalue()


# ── Scheduled Jobs ────────────────────────────────────────────────────────────

def flag_overdue_compliance_issues():
    """Scheduled job: flag compliance issues past due_date as Overdue."""
    session, engine = get_sync_session()
    try:
        from sqlalchemy import text
        result = session.execute(text("""
            UPDATE compliance_issues SET status = 'Overdue'
            WHERE status = 'Open' AND due_date < NOW()
        """))
        session.commit()
        logger.info(f"Flagged {result.rowcount} issues as Overdue")
    finally:
        session.close()
        engine.dispose()


def update_all_goal_progress():
    """Scheduled job: recompute current_value for all active EnvironmentalGoals
    from actual CarbonTransaction CO2e sums."""
    session, engine = get_sync_session()
    try:
        from sqlalchemy import text

        # Get all active goals
        goals = session.execute(text("""
            SELECT id, department_id, target_value, target_date FROM environmental_goals
            WHERE status = 'active'
        """)).fetchall()

        for goal_id, dept_id, target_value, target_date in goals:
            # Compute total CO2e for this goal's scope
            if dept_id:
                result = session.execute(text("""
                    SELECT COALESCE(SUM(co2e_calculated), 0.0)
                    FROM carbon_transactions WHERE department_id = :dept_id
                """), {"dept_id": dept_id})
            else:
                result = session.execute(text("""
                    SELECT COALESCE(SUM(co2e_calculated), 0.0) FROM carbon_transactions
                """))
            total_co2e = result.scalar() or 0.0

            # Update goal
            new_status = 'active'
            if target_value > 0:
                if total_co2e >= target_value:
                    new_status = 'failed'
                elif datetime.now(timezone.utc) > target_date and total_co2e < target_value:
                    new_status = 'achieved'
            session.execute(text("""
                UPDATE environmental_goals
                SET current_value = :val, status = :status, updated_at = NOW()
                WHERE id = :gid
            """), {"val": round(total_co2e, 2), "status": new_status, "gid": goal_id})

        session.commit()
        logger.info(f"Updated progress for {len(goals)} environmental goals")
    finally:
        session.close()
        engine.dispose()


def scheduled_score_recompute():
    """Scheduled job: recompute ESG scores for the current period."""
    from datetime import datetime
    period = datetime.now().strftime("%Y-%m")
    logger.info(f"Scheduled ESG score recomputation for period: {period}")
    compute_scores(period)


# ── Worker Entry Point ────────────────────────────────────────────────────────

def _register_scheduled_jobs(queue):
    """Register recurring scheduled jobs using RQ's built-in scheduler.
    Jobs are enqueued with meta to prevent duplicate scheduling."""
    from datetime import timedelta

    # Daily ESG score recomputation at 02:00 UTC
    queue.enqueue_in(
        timedelta(seconds=10),  # Initial run shortly after startup
        scheduled_score_recompute,
        job_id="scheduled_score_recompute_initial",
    )

    # Register recurring jobs using RQ scheduler
    # These will be picked up by the worker's built-in scheduler (with_scheduler=True)
    try:
        from rq_scheduler import Scheduler
        scheduler = Scheduler(queue_name="ecosphere", connection=redis_conn)

        # Clear any stale scheduled jobs from previous runs
        for job in scheduler.get_jobs():
            if job.meta.get("ecosphere_scheduled"):
                scheduler.cancel(job)

        # Daily score recompute — every 24 hours
        scheduler.schedule(
            scheduled_time=datetime.now(timezone.utc),
            func=scheduled_score_recompute,
            interval=86400,  # 24 hours
            repeat=None,     # repeat forever
            meta={"ecosphere_scheduled": True},
            id="ecosphere_daily_score_recompute",
        )

        # Flag overdue compliance issues — every 6 hours
        scheduler.schedule(
            scheduled_time=datetime.now(timezone.utc),
            func=flag_overdue_compliance_issues,
            interval=21600,  # 6 hours
            repeat=None,
            meta={"ecosphere_scheduled": True},
            id="ecosphere_compliance_flagging",
        )

        # Update environmental goal progress — every 4 hours
        scheduler.schedule(
            scheduled_time=datetime.now(timezone.utc),
            func=update_all_goal_progress,
            interval=14400,  # 4 hours
            repeat=None,
            meta={"ecosphere_scheduled": True},
            id="ecosphere_goal_progress_update",
        )

        logger.info("Scheduled jobs registered via rq-scheduler: score recompute (24h), compliance flagging (6h), goal progress (4h)")
    except ImportError:
        # rq-scheduler not installed — fall back to one-shot jobs
        logger.warning("rq-scheduler not available, scheduling one-shot jobs only")
        from datetime import timedelta
        queue.enqueue_in(timedelta(hours=6), flag_overdue_compliance_issues, job_id="compliance_flagging_fallback")
        queue.enqueue_in(timedelta(hours=4), update_all_goal_progress, job_id="goal_progress_fallback")
    except Exception as e:
        logger.warning(f"Failed to register scheduled jobs: {e}")


def run_worker():
    """Start the worker after its job functions are importable as ``worker.*``."""
    logger.info("EcoSphere RQ Worker starting...")
    q = Queue("ecosphere", connection=redis_conn)
    _register_scheduled_jobs(q)
    worker = Worker([q], connection=redis_conn)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    run_worker()
