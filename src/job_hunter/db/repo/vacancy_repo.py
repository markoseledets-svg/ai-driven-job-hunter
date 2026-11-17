from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

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
