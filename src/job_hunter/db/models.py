from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import UUID

from job_hunter.db.base import BaseIndexModel, BaseTimeStampModel
from job_hunter.db.enums import VacancyStatus


class CandidateProfile(BaseIndexModel):
    __tablename__ = "candidate_profile"

    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    prefilter_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    min_notify_score: Mapped[int] = mapped_column(Integer, nullable=False, default=75)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class CalibrationExample(BaseIndexModel, BaseTimeStampModel):
    __tablename__ = "calibration_example"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description_snippet: Mapped[str] = mapped_column(Text, nullable=False)
    expected_score: Mapped[int] = mapped_column(Integer, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Vacancy(BaseIndexModel):
    __tablename__ = "vacancy"

    pipeline_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pipeline_run.id", ondelete="SET NULL"), index=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_url: Mapped[str] = mapped_column(Text, index=True, nullable=False)
    dedup_hash: Mapped[str] = mapped_column(Text, index=True, nullable=False)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    location_or_remote: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_raw: Mapped[str] = mapped_column(Text, nullable=False)
    partial_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    status: Mapped[VacancyStatus] = mapped_column(
        Enum(VacancyStatus, native_enum=False),
        nullable=False,
        default=VacancyStatus.NEW,
    )
    ai_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_skills: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    missing_skills: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    ai_model_used: Mapped[str | None] = mapped_column(Text, nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=lambda: datetime.now(UTC),
    )
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pipeline: Mapped["PipelineRun | None"] = relationship(back_populates="vacancies")


class PipelineRun(BaseIndexModel, BaseTimeStampModel):
    __tablename__ = "pipeline_run"

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deduped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prefiltered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_scored_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notified_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)

    vacancies: Mapped[list["Vacancy"]] = relationship(back_populates="pipeline")
