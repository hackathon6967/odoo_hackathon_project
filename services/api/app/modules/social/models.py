from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.shared.db import Base


class CSRActivity(Base):
    __tablename__ = "csr_activities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_required: Mapped[bool] = mapped_column(Boolean, default=True)
    max_participants: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    points_reward: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    participations: Mapped[list["EmployeeParticipation"]] = relationship("EmployeeParticipation", back_populates="activity")


class EmployeeParticipation(Base):
    __tablename__ = "employee_participations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    activity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("csr_activities.id"), nullable=False)
    proof_file_ref: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(50), default="Pending")  # Pending/Approved/Rejected
    points_earned: Mapped[int] = mapped_column(Integer, default=0)
    completion_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    activity: Mapped["CSRActivity"] = relationship("CSRActivity", back_populates="participations")
    employee: Mapped["User"] = relationship("User", foreign_keys=[employee_id])


class DiversityMetric(Base):
    __tablename__ = "diversity_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    period: Mapped[str] = mapped_column(String(20), nullable=False)  # YYYY-MM
    gender_male: Mapped[int] = mapped_column(Integer, default=0)
    gender_female: Mapped[int] = mapped_column(Integer, default=0)
    gender_other: Mapped[int] = mapped_column(Integer, default=0)
    tenure_0_1: Mapped[int] = mapped_column(Integer, default=0)
    tenure_1_3: Mapped[int] = mapped_column(Integer, default=0)
    tenure_3_5: Mapped[int] = mapped_column(Integer, default=0)
    tenure_5_plus: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TrainingModule(Base):
    __tablename__ = "training_modules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    xp_reward: Mapped[int] = mapped_column(Integer, default=0)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TrainingCompletion(Base):
    __tablename__ = "training_completions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    training_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_modules.id"), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    training: Mapped["TrainingModule"] = relationship("TrainingModule")
    employee: Mapped["User"] = relationship("User")
