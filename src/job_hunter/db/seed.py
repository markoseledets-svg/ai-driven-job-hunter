import argparse
import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_hunter.core.schemas import PrefilterConfig
from job_hunter.db.enums import VacancySource, VacancyStatus
from job_hunter.db.models import (
    CalibrationExample,
    CandidateProfile,
    PipelineRun,
    Vacancy,
)
from job_hunter.sources.normalizer import build_dedup_hash

logger = logging.getLogger(__name__)

DEFAULT_SEED_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "seed_data.json"


class CandidateProfileSeed(BaseModel):
    resume_text: str = Field(min_length=20)
    prefilter_config: PrefilterConfig
    min_notify_score: int = Field(ge=0, le=100, default=75)


class CalibrationExampleSeed(BaseModel):
    title: str = Field(min_length=3)
    description_snippet: str = Field(min_length=10)
    expected_score: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=10)
    is_active: bool = True


class VacancySeed(BaseModel):
    source: VacancySource
    external_id: str | None = None
    canonical_url: str = Field(min_length=8)
    title: str = Field(min_length=3)
    company: str = Field(min_length=2)
    location_or_remote: str | None = None
    salary_raw: str | None = None
    description_raw: str = Field(min_length=10)
    partial_data: bool = False
    status: VacancyStatus = VacancyStatus.NEW
    ai_score: int | None = Field(default=None, ge=0, le=100)
    ai_summary: str | None = None
    matched_skills: list[str] | None = None
    missing_skills: list[str] | None = None
    ai_model_used: str | None = None


class SeedPayload(BaseModel):
    profile: CandidateProfileSeed
    calibration_examples: list[CalibrationExampleSeed] = Field(min_length=1)
    vacancies: list[VacancySeed] = Field(default_factory=list)


@dataclass(frozen=True)
class SeedStats:
    profiles_inserted: int
    calibrations_inserted: int
    vacancies_inserted: int
    pipeline_runs_inserted: int


def load_seed_payload(path: Path = DEFAULT_SEED_PATH) -> SeedPayload:
    """Read and validate seed fixtures from JSON file."""
    raw_json = path.read_text(encoding="utf-8")
    return SeedPayload.model_validate_json(raw_json)


async def seed_database(session: AsyncSession, payload: SeedPayload) -> SeedStats:
    """Idempotently populate database with synthetic development seed data."""
    profiles_inserted = 0
    calibrations_inserted = 0
    vacancies_inserted = 0
    pipeline_runs_inserted = 0

    existing_profile = await session.scalar(select(CandidateProfile.id).limit(1))
    if existing_profile is None:
        session.add(
            CandidateProfile(
                resume_text=payload.profile.resume_text,
                prefilter_config=payload.profile.prefilter_config.model_dump(),
                min_notify_score=payload.profile.min_notify_score,
            )
        )
        profiles_inserted = 1

    existing_titles = set(await session.scalars(select(CalibrationExample.title)))
    for item in payload.calibration_examples:
        if item.title in existing_titles:
            continue
        session.add(
            CalibrationExample(
                title=item.title,
                description_snippet=item.description_snippet,
                expected_score=item.expected_score,
                rationale=item.rationale,
                is_active=item.is_active,
            )
        )
        existing_titles.add(item.title)
        calibrations_inserted += 1

    existing_urls = set(await session.scalars(select(Vacancy.canonical_url)))
    existing_hashes = set(await session.scalars(select(Vacancy.dedup_hash)))

    vacancies_to_insert: list[Vacancy] = []
    now = datetime.now(UTC)

    for vac in payload.vacancies:
        dedup_hash = build_dedup_hash(vac.title, vac.company)
        if vac.canonical_url in existing_urls or dedup_hash in existing_hashes:
            continue

        vacancies_to_insert.append(
            Vacancy(
                source=vac.source,
                external_id=vac.external_id,
                canonical_url=vac.canonical_url,
                dedup_hash=dedup_hash,
                title=vac.title,
                company=vac.company,
                location_or_remote=vac.location_or_remote,
                salary_raw=vac.salary_raw,
                description_raw=vac.description_raw,
                partial_data=vac.partial_data,
                status=vac.status,
                ai_score=vac.ai_score,
                ai_summary=vac.ai_summary,
                matched_skills=vac.matched_skills,
                missing_skills=vac.missing_skills,
                ai_model_used=vac.ai_model_used,
                fetched_at=now,
                scored_at=now if vac.ai_score is not None else None,
            )
        )
        existing_urls.add(vac.canonical_url)
        existing_hashes.add(dedup_hash)

    if vacancies_to_insert:
        existing_run_id = await session.scalar(select(PipelineRun.id).limit(1))
        if existing_run_id is None:
            scored_count = sum(1 for v in vacancies_to_insert if v.ai_score is not None)
            notified_count = sum(
                1
                for v in vacancies_to_insert
                if v.status in {VacancyStatus.NOTIFIED, VacancyStatus.APPLIED}
            )
            prefiltered_count = sum(
                1 for v in vacancies_to_insert if v.status == VacancyStatus.PREFILTERED
            )
            seed_run = PipelineRun(
                started_at=now,
                finished_at=now,
                fetched_count=len(vacancies_to_insert),
                deduped_count=len(vacancies_to_insert),
                prefiltered_count=prefiltered_count,
                ai_scored_count=scored_count,
                notified_count=notified_count,
                estimated_tokens=1850,
                status="seed_success",
            )
            session.add(seed_run)
            await session.flush()
            pipeline_runs_inserted = 1
            for vacancy in vacancies_to_insert:
                if vacancy.status != VacancyStatus.NEW:
                    vacancy.pipeline_id = seed_run.id

        session.add_all(vacancies_to_insert)
        vacancies_inserted = len(vacancies_to_insert)

    await session.commit()
    return SeedStats(
        profiles_inserted=profiles_inserted,
        calibrations_inserted=calibrations_inserted,
        vacancies_inserted=vacancies_inserted,
        pipeline_runs_inserted=pipeline_runs_inserted,
    )


async def run_seed(seed_path: Path = DEFAULT_SEED_PATH) -> SeedStats:
    """Load seed JSON and apply it using configured async database session."""
    from job_hunter.db.session import async_session_maker

    payload = load_seed_payload(seed_path)
    async with async_session_maker() as session:
        return await seed_database(session, payload)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Seed database with synthetic dev data.")
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_SEED_PATH,
        help="Path to seed JSON file.",
    )
    args = parser.parse_args()
    stats = asyncio.run(run_seed(args.file))
    logger.info(
        "Seed complete: profiles=%d, calibrations=%d, vacancies=%d, pipeline_runs=%d",
        stats.profiles_inserted,
        stats.calibrations_inserted,
        stats.vacancies_inserted,
        stats.pipeline_runs_inserted,
    )


if __name__ == "__main__":
    main()
