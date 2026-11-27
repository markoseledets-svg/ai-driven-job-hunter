from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_hunter.db.models import CalibrationExample
from job_hunter.db.repo.base_repo import BaseRepository


class CalibrationRepository(BaseRepository[CalibrationExample]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(CalibrationExample, session)

    async def get_active_examples(self) -> list[CalibrationExample]:
        result = await self._session.execute(
            select(CalibrationExample).where(CalibrationExample.is_active.is_(True))
        )
        return list(result.scalars().all())
