import logging
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from job_hunter.ai.gemini_client import GeminiScorer
from job_hunter.core.logging import bind_run_id
from job_hunter.core.schemas import PrefilterConfig
from job_hunter.db.enums import VacancyStatus
from job_hunter.db.models import PipelineRun
from job_hunter.db.repo.calibration_repo import CalibrationRepository
from job_hunter.db.repo.pipeline_repo import PipelineRepository
from job_hunter.db.repo.profile_repo import ProfileRepository
from job_hunter.db.repo.vacancy_repo import VacancyRepository
from job_hunter.schemas.vacancy_schemas import RawVacancy
from job_hunter.services.prefilter import Prefilter
from job_hunter.services.vacancy_service import VacancyService
from job_hunter.sources.base import BaseJobSource

logger = logging.getLogger(__name__)


class PipelineService:
    def __init__(
        self,
        session: AsyncSession,
        sources: Sequence[BaseJobSource],
        pipeline_repo: PipelineRepository,
        profile_repo: ProfileRepository,
        calibration_repo: CalibrationRepository,
        vacancy_repo: VacancyRepository,
        vacancy_service: VacancyService,
        gemini_scorer: GeminiScorer,
        max_ai_jobs_per_run: int = 30,
    ) -> None:
        self._session = session
        self._sources = list(sources)
        self._pipeline_repo = pipeline_repo
        self._profile_repo = profile_repo
        self._calibration_repo = calibration_repo
        self._vacancy_repo = vacancy_repo
        self._vacancy_service = vacancy_service
        self._gemini_scorer = gemini_scorer
        self._max_ai_jobs_per_run = max_ai_jobs_per_run

    async def _fetch_source(
        self,
        source: BaseJobSource,
        errors: list[str],
    ) -> tuple[list[RawVacancy], bool]:
        try:
            vacancies = await source.fetch()
        except Exception as exc:
            logger.exception("Source %s failed during fetch", source.source_name)
            errors.append(f"Source {source.source_name} failed: {exc}")
            return [], False
        logger.info("Source %s fetched %d raw vacancies", source.source_name, len(vacancies))
        return vacancies, True

    async def run(self) -> PipelineRun:
        run = await self._pipeline_repo.start_run()
        errors: list[str] = []

        with bind_run_id(run_id=str(run.id)):
            logger.info(
                "Pipeline run started (sources=%d, max_ai_jobs=%d)",
                len(self._sources),
                self._max_ai_jobs_per_run,
            )

            profile = await self._profile_repo.get_profile()
            if profile is None:
                logger.error("Pipeline run aborted: candidate profile not found")
                await self._pipeline_repo.finish_run(
                    run=run,
                    status="failed",
                    error_log="Candidate profile not found",
                )
                await self._session.commit()
                return run

            prefilter = Prefilter(PrefilterConfig.model_validate(profile.prefilter_config))

            raw_vacancies: list[RawVacancy] = []
            successful_sources = 0
            for source in self._sources:
                fetched, ok = await self._fetch_source(source, errors)
                raw_vacancies.extend(fetched)
                if ok:
                    successful_sources += 1

            fetched_count = len(raw_vacancies)
            saved_vacancies = await self._vacancy_service.save_unique_vacancies(
                raw_vacancies,
                pipeline_id=run.id,
                prefilter=prefilter,
            )
            await self._session.commit()

            deduped_count = fetched_count - len(saved_vacancies)
            prefiltered_count = sum(
                1 for v in saved_vacancies if v.status == VacancyStatus.PREFILTERED
            )

            new_vacancies = await self._vacancy_repo.list_new_for_scoring(
                limit=self._max_ai_jobs_per_run
            )

            ai_scored_count = 0
            estimated_tokens = 0
            ai_failed_count = 0

            if new_vacancies:
                logger.info("Sending %d NEW vacancies for AI scoring", len(new_vacancies))
                calibration_examples = await self._calibration_repo.get_active_examples()
                scoring_result = await self._gemini_scorer.score_vacancies(
                    vacancies=new_vacancies,
                    calibration_examples=calibration_examples,
                    resume_text=profile.resume_text,
                )
                estimated_tokens = scoring_result.total_tokens
                ai_failed_count = len(scoring_result.failed_ids)

                if scoring_result.scored:
                    ai_scored_count = await self._vacancy_repo.apply_scores(
                        scored=scoring_result.scored,
                        model_name=self._gemini_scorer.model_name,
                    )

                if scoring_result.failed_ids:
                    logger.warning(
                        "AI scoring failed for %d/%d vacancies; keeping them NEW",
                        ai_failed_count,
                        len(new_vacancies),
                    )
                    errors.append(f"AI scoring failed for {ai_failed_count} vacancies")
            else:
                logger.info("No NEW vacancies pending AI scoring")

            all_sources_failed = bool(self._sources) and successful_sources == 0
            all_ai_failed = bool(new_vacancies) and ai_scored_count == 0 and ai_failed_count > 0

            if all_sources_failed or all_ai_failed:
                status = "failed"
            elif errors:
                status = "partial_error"
            else:
                status = "success"

            error_log = "\n".join(errors) if errors else None
            await self._pipeline_repo.finish_run(
                run=run,
                status=status,
                fetched_count=fetched_count,
                deduped_count=deduped_count,
                prefiltered_count=prefiltered_count,
                ai_scored_count=ai_scored_count,
                notified_count=0,
                estimated_tokens=estimated_tokens,
                error_log=error_log,
            )
            await self._session.commit()

            logger.info(
                "Pipeline run finished status=%s fetched=%d deduped=%d prefiltered=%d "
                "ai_scored=%d tokens=%d errors=%d",
                status,
                fetched_count,
                deduped_count,
                prefiltered_count,
                ai_scored_count,
                estimated_tokens,
                len(errors),
            )
            return run
