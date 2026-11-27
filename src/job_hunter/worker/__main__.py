import argparse
import asyncio
import logging

import httpx

from job_hunter.ai.gemini_client import GeminiScorer
from job_hunter.core.config import settings
from job_hunter.core.logging import configure_logging
from job_hunter.db.repo.calibration_repo import CalibrationRepository
from job_hunter.db.repo.pipeline_repo import PipelineRepository
from job_hunter.db.repo.profile_repo import ProfileRepository
from job_hunter.db.repo.vacancy_repo import VacancyRepository
from job_hunter.db.session import async_session_maker, engine
from job_hunter.services.pipeline_service import PipelineService
from job_hunter.services.vacancy_service import VacancyService
from job_hunter.sources.djini_rss import DjiniRssSource
from job_hunter.sources.dou_rss import DouRssSource
from job_hunter.sources.imap_email import ImapEmailSource

logger = logging.getLogger(__name__)


async def run_worker(*, mark_seen: bool = True) -> int:
    """Wire dependencies and execute one full job-hunting pipeline run."""
    configure_logging(level=settings.log_level, log_format=settings.log_format)

    try:
        async with httpx.AsyncClient() as http_client, async_session_maker() as session:
            pipeline_repo = PipelineRepository(session)
            profile_repo = ProfileRepository(session)
            calibration_repo = CalibrationRepository(session)
            vacancy_repo = VacancyRepository(session)

            vacancy_service = VacancyService(vacancy_repo)
            gemini_scorer = GeminiScorer(
                api_key=settings.api_key,
                model=settings.model,
                batch_size=settings.ai_batch_size,
            )

            sources = [
                DouRssSource(client=http_client),
                DjiniRssSource(client=http_client),
                ImapEmailSource(
                    allowed_emails=settings.allowed_emails,
                    host=settings.imap_host,
                    port=settings.imap_port,
                    mailbox=settings.imap_mailbox,
                    user=settings.imap_user,
                    password=settings.imap_password,
                    mark_seen=mark_seen,
                ),
            ]

            pipeline = PipelineService(
                session=session,
                sources=sources,
                pipeline_repo=pipeline_repo,
                profile_repo=profile_repo,
                calibration_repo=calibration_repo,
                vacancy_repo=vacancy_repo,
                vacancy_service=vacancy_service,
                gemini_scorer=gemini_scorer,
                max_ai_jobs_per_run=settings.max_ai_jobs_per_run,
            )
            run = await pipeline.run()
            return 1 if run.status == "failed" else 0
    finally:
        await engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AI-Driven Job Hunter pipeline worker.")
    parser.add_argument(
        "--no-mark-seen",
        action="store_true",
        help="Read unread IMAP emails without marking them as \\Seen.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    exit_code = asyncio.run(run_worker(mark_seen=not args.no_mark_seen))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
