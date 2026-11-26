from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import UUID, uuid7

from job_hunter.ai.gemini_client import GeminiScorer
from job_hunter.ai.schemas import ScoredVacancy, ScoringResult
from job_hunter.db.enums import VacancyStatus
from job_hunter.db.models import CalibrationExample, CandidateProfile, PipelineRun, Vacancy
from job_hunter.db.repo.calibration_repo import CalibrationRepository
from job_hunter.db.repo.pipeline_repo import PipelineRepository
from job_hunter.db.repo.profile_repo import ProfileRepository
from job_hunter.db.repo.vacancy_repo import VacancyRepository
from job_hunter.schemas.vacancy_schemas import RawVacancy
from job_hunter.services.pipeline_service import PipelineService
from job_hunter.services.vacancy_service import VacancyService
from job_hunter.sources.base import BaseJobSource
from tests.conftest import FakeSession


class _FakeSource(BaseJobSource):
    def __init__(
        self,
        name: str,
        items: list[RawVacancy] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._name = name
        self._items = items or []
        self._error = error

    @property
    def source_name(self) -> str:
        return self._name

    async def fetch(self) -> list[RawVacancy]:
        if self._error is not None:
            raise self._error
        return list(self._items)


class _FakePipelineRepo:
    def __init__(self) -> None:
        self.run = PipelineRun(id=uuid7(), started_at=datetime.now(UTC), status="running")

    async def start_run(self) -> PipelineRun:
        return self.run

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
        return run


class _FakeProfileRepo:
    def __init__(self, profile: CandidateProfile | None) -> None:
        self._profile = profile

    async def get_profile(self) -> CandidateProfile | None:
        return self._profile


class _FakeCalibrationRepo:
    def __init__(self, examples: Sequence[CalibrationExample] | None = None) -> None:
        self._examples = list(examples or [])

    async def get_active_examples(self) -> Sequence[CalibrationExample]:
        return self._examples


class _FakeVacancyRepo:
    def __init__(self, session: FakeSession) -> None:
        self._session = session
        self.stored: list[Vacancy] = []
        self.applied_models: list[str] = []

    async def get_dedup_params(
        self,
        urls: set[str],
        hashes: set[str],
        lookback_days: int = 90,
    ) -> tuple[set[str], set[str]]:
        existing_urls = {v.canonical_url for v in self.stored if v.canonical_url in urls}
        existing_hashes = {v.dedup_hash for v in self.stored if v.dedup_hash in hashes}
        return existing_urls, existing_hashes

    async def add_many(self, entities: Sequence[Vacancy]) -> list[Vacancy]:
        for entity in entities:
            if entity.id is None:
                entity.id = uuid7()
        self.stored.extend(entities)
        return list(entities)

    async def list_new_for_scoring(self, limit: int) -> list[Vacancy]:
        return [v for v in self.stored if v.status == VacancyStatus.NEW][:limit]

    async def apply_scores(self, scored: Sequence[ScoredVacancy], model_name: str) -> int:
        self.applied_models.append(model_name)
        by_id = {item.vacancy_id: item for item in scored}
        updated = 0
        for vacancy in self.stored:
            rating = by_id.get(vacancy.id)
            if rating is None:
                continue
            vacancy.ai_score = rating.score
            vacancy.ai_summary = rating.summary
            vacancy.status = VacancyStatus.SCORED
            updated += 1
        return updated


class _FakeGeminiScorer:
    def __init__(
        self,
        *,
        score: int = 88,
        tokens: int = 150,
        fail_all: bool = False,
    ) -> None:
        self._score = score
        self._tokens = tokens
        self._fail_all = fail_all
        self.called_with_ids: list[UUID] = []

    @property
    def model_name(self) -> str:
        return "gemini-test-model"

    async def score_vacancies(
        self,
        vacancies: Sequence[Vacancy],
        calibration_examples: Sequence[CalibrationExample],
        resume_text: str,
    ) -> ScoringResult:
        self.called_with_ids = [v.id for v in vacancies]
        if self._fail_all:
            return ScoringResult(
                scored=[],
                total_tokens=0,
                failed_ids=[v.id for v in vacancies],
            )
        scored = [
            ScoredVacancy(
                vacancy_id=v.id,
                score=self._score,
                summary="Good Python match.",
                matched_skills=["Python"],
                missing_skills=[],
            )
            for v in vacancies
        ]
        return ScoringResult(scored=scored, total_tokens=self._tokens, failed_ids=[])


def _make_profile() -> CandidateProfile:
    return CandidateProfile(
        id=uuid7(),
        resume_text="Junior Python Developer: FastAPI, PostgreSQL, Docker.",
        prefilter_config={
            "excluded_title_keywords": ["senior", "java"],
            "required_any_keywords": ["python", "fastapi"],
            "allowed_languages": ["en", "uk"],
        },
        min_notify_score=75,
    )


def _build_service(
    *,
    session: FakeSession,
    sources: Sequence[BaseJobSource],
    profile: CandidateProfile | None,
    scorer: _FakeGeminiScorer,
) -> tuple[PipelineService, _FakeVacancyRepo]:
    vacancy_repo = _FakeVacancyRepo(session)
    service = PipelineService(
        session=cast(AsyncSession, session),
        sources=sources,
        pipeline_repo=cast(PipelineRepository, _FakePipelineRepo()),
        profile_repo=cast(ProfileRepository, _FakeProfileRepo(profile)),
        calibration_repo=cast(CalibrationRepository, _FakeCalibrationRepo()),
        vacancy_repo=cast(VacancyRepository, vacancy_repo),
        vacancy_service=VacancyService(cast(VacancyRepository, vacancy_repo)),
        gemini_scorer=cast(GeminiScorer, scorer),
        max_ai_jobs_per_run=30,
    )
    return service, vacancy_repo


async def test_pipeline_run_happy_path(
    fake_session: FakeSession,
    make_raw_vacancy: Callable[..., RawVacancy],
) -> None:
    vac_good = make_raw_vacancy(
        title="Junior Python Backend",
        company="Acme",
        canonical_url="https://jobs.dou.ua/vacancies/1",
        dedup_hash="hash-1",
    )
    vac_dup = make_raw_vacancy(
        title="Junior Python Backend",
        company="Acme",
        canonical_url="https://djinni.co/jobs/1",
        dedup_hash="hash-1",
    )
    vac_filtered = make_raw_vacancy(
        title="Senior Java Engineer",
        company="Legacy",
        canonical_url="https://jobs.dou.ua/vacancies/2",
        dedup_hash="hash-2",
    )

    scorer = _FakeGeminiScorer(score=88, tokens=150)
    service, vacancy_repo = _build_service(
        session=fake_session,
        sources=[
            _FakeSource("dou_rss", [vac_good, vac_filtered]),
            _FakeSource("djini_rss", [vac_dup]),
        ],
        profile=_make_profile(),
        scorer=scorer,
    )

    run = await service.run()

    assert run.status == "success"
    assert run.fetched_count == 3
    assert run.deduped_count == 1
    assert run.prefiltered_count == 1
    assert run.ai_scored_count == 1
    assert run.estimated_tokens == 150
    assert run.error_log is None
    assert fake_session.committed is True

    by_title = {v.title: v for v in vacancy_repo.stored}
    assert by_title["Senior Java Engineer"].status == VacancyStatus.PREFILTERED
    assert by_title["Junior Python Backend"].status == VacancyStatus.SCORED
    assert by_title["Junior Python Backend"].ai_score == 88
    assert vacancy_repo.applied_models == ["gemini-test-model"]


async def test_pipeline_run_isolates_failing_source(
    fake_session: FakeSession,
    make_raw_vacancy: Callable[..., RawVacancy],
) -> None:
    vac = make_raw_vacancy(title="Python FastAPI Dev", company="CloudCo")
    scorer = _FakeGeminiScorer(score=81, tokens=90)
    service, _ = _build_service(
        session=fake_session,
        sources=[
            _FakeSource("dou_rss", error=RuntimeError("DNS timeout")),
            _FakeSource("djini_rss", [vac]),
        ],
        profile=_make_profile(),
        scorer=scorer,
    )

    run = await service.run()

    assert run.status == "partial_error"
    assert run.fetched_count == 1
    assert run.ai_scored_count == 1
    assert run.error_log is not None
    assert "dou_rss" in run.error_log


async def test_pipeline_run_fails_without_candidate_profile(
    fake_session: FakeSession,
    make_raw_vacancy: Callable[..., RawVacancy],
) -> None:
    scorer = _FakeGeminiScorer()
    service, _ = _build_service(
        session=fake_session,
        sources=[_FakeSource("dou_rss", [make_raw_vacancy(title="Python Dev")])],
        profile=None,
        scorer=scorer,
    )

    run = await service.run()

    assert run.status == "failed"
    assert run.error_log == "Candidate profile not found"
    assert scorer.called_with_ids == []
    assert fake_session.committed is True


async def test_pipeline_run_marks_failed_when_all_ai_scoring_fails(
    fake_session: FakeSession,
    make_raw_vacancy: Callable[..., RawVacancy],
) -> None:
    vac = make_raw_vacancy(title="Python FastAPI Dev", company="CloudCo")
    scorer = _FakeGeminiScorer(fail_all=True)
    service, vacancy_repo = _build_service(
        session=fake_session,
        sources=[_FakeSource("dou_rss", [vac])],
        profile=_make_profile(),
        scorer=scorer,
    )

    run = await service.run()

    assert run.status == "failed"
    assert run.ai_scored_count == 0
    assert run.error_log is not None
    assert "AI scoring failed" in run.error_log
    assert vacancy_repo.stored[0].status == VacancyStatus.NEW
