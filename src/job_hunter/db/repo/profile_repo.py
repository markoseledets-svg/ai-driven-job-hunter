from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_hunter.db.models import CandidateProfile
from job_hunter.db.repo.base_repo import BaseRepository


class ProfileRepository(BaseRepository[CandidateProfile]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(CandidateProfile, session)

    async def get_profile(self) -> CandidateProfile | None:
        result = await self._session.execute(select(CandidateProfile).limit(1))
        return result.scalar_one_or_none()
