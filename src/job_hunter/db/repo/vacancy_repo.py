from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_hunter.ai.schemas import ScoredVacancy
from job_hunter.db.enums import VacancyStatus
from job_hunter.db.models import Vacancy
from job_hunter.db.repo.base_repo import BaseRepository


class VacancyRepository(BaseRepository[Vacancy]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Vacancy, session)

    async def get_dedup_params(
        self,
        urls: set[str],
        hashes: set[str],
        lookback_days: int = 90,
    ) -> tuple[set[str], set[str]]:
        if not urls and not hashes:
            return set(), set()

        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
        stmt = select(Vacancy.canonical_url, Vacancy.dedup_hash).where(
            Vacancy.fetched_at >= cutoff,
            or_(
                Vacancy.canonical_url.in_(urls),
                Vacancy.dedup_hash.in_(hashes),
            ),
        )
        rows = (await self._session.execute(stmt)).all()
        return {row[0] for row in rows}, {row[1] for row in rows}

    async def list_new_for_scoring(self, limit: int) -> list[Vacancy]:
        stmt = (
            select(Vacancy)
            .where(Vacancy.status == VacancyStatus.NEW)
            .order_by(Vacancy.fetched_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def apply_scores(self, scored: Sequence[ScoredVacancy], model_name: str) -> int:
        if not scored:
            return 0

        by_id = {item.vacancy_id: item for item in scored}
        result = await self._session.execute(select(Vacancy).where(Vacancy.id.in_(by_id.keys())))
        vacancies = list(result.scalars().all())
        now = datetime.now(UTC)

        for vacancy in vacancies:
            rating = by_id[vacancy.id]
            vacancy.ai_score = rating.score
            vacancy.ai_summary = rating.summary
            vacancy.matched_skills = rating.matched_skills
            vacancy.missing_skills = rating.missing_skills
            vacancy.ai_model_used = model_name
            vacancy.scored_at = now
            vacancy.status = VacancyStatus.SCORED

            if (
                vacancy.company == "Unknown"
                and rating.detected_company
                and rating.detected_company.strip()
            ):
                vacancy.company = rating.detected_company.strip()
            if (
                vacancy.location_or_remote is None
                and rating.detected_location
                and rating.detected_location.strip()
            ):
                vacancy.location_or_remote = rating.detected_location.strip()

        await self._session.flush()
        return len(vacancies)
