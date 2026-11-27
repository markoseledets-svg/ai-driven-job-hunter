from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from job_hunter.db.models import PipelineRun
from job_hunter.db.repo.base_repo import BaseRepository


class PipelineRepository(BaseRepository[PipelineRun]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(PipelineRun, session)

    async def start_run(self) -> PipelineRun:
        run = self.add(status="running", started_at=datetime.now(UTC))
        await self._session.flush()
        return run

    async def finish_run(
        self,
        run: PipelineRun,
        *,
        status: str,
        fetched_count: int = 0,
        deduped_count: int = 0,
        prefiltered_count: int = 0,
        ai_scored_count: int = 0,
        notified_count: int = 0,
        estimated_tokens: int = 0,
        error_log: str | None = None,
    ) -> PipelineRun:
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.fetched_count = fetched_count
        run.deduped_count = deduped_count
        run.prefiltered_count = prefiltered_count
        run.ai_scored_count = ai_scored_count
        run.notified_count = notified_count
        run.estimated_tokens = estimated_tokens
        run.error_log = error_log
        await self._session.flush()
        return run
