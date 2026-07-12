from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Float, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.shared.db import Base


class DepartmentScore(Base):
    __tablename__ = "department_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False)
    period: Mapped[str] = mapped_column(String(20), nullable=False)  # YYYY-MM
    environmental_score: Mapped[float] = mapped_column(Float, default=0.0)
    social_score: Mapped[float] = mapped_column(Float, default=0.0)
    governance_score: Mapped[float] = mapped_column(Float, default=0.0)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    department: Mapped["Department"] = relationship("Department")


class ReportJob(Base):
    __tablename__ = "report_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)  # environmental/social/governance/summary/custom
    filters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    format: Mapped[str] = mapped_column(String(20), nullable=False)  # pdf/xlsx/csv
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending/generating/ready/failed
    file_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    download_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    error_msg: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    requested_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
