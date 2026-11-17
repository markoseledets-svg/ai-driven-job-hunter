from collections.abc import Callable
from typing import cast

from uuid6 import uuid7

from job_hunter.db.enums import VacancyStatus
from job_hunter.db.models import Vacancy
from job_hunter.db.repo.vacancy_repo import VacancyRepository
from job_hunter.schemas.vacancy_schemas import RawVacancy
from job_hunter.services.vacancy_service import VacancyService
from tests.conftest import FakeSession


class _FakeVacancyRepository:
    def __init__(
        self,
        session: FakeSession,
        existing_urls: set[str] | None = None,
        existing_hashes: set[str] | None = None,
    ) -> None:
        self._session = session
        self._existing_urls = existing_urls or set()
        self._existing_hashes = existing_hashes or set()
        self.get_dedup_calls = 0
        self.add_many_calls = 0
        self.saved_entities: list[Vacancy] = []

    async def get_dedup_params(
        self,
        urls: set[str],
        hashes: set[str],
        lookback_days: int = 90,
    ) -> tuple[set[str], set[str]]:
        self.get_dedup_calls += 1
        return (urls & self._existing_urls), (hashes & self._existing_hashes)

    async def add_many(self, entities: list[Vacancy]) -> list[Vacancy]:
        self.add_many_calls += 1
        self.saved_entities.extend(entities)
        return list(entities)


async def test_save_unique_vacancies_empty_input(fake_session: FakeSession) -> None:
    repo = _FakeVacancyRepository(session=fake_session)
    service = VacancyService(cast(VacancyRepository, repo))

    result = await service.save_unique_vacancies([], pipeline_id=uuid7())

    assert result == []
    assert repo.get_dedup_calls == 0
    assert repo.add_many_calls == 0


async def test_save_unique_vacancies_deduplicates_within_batch(
    fake_session: FakeSession,
    make_raw_vacancy: Callable[..., RawVacancy],
) -> None:
    repo = _FakeVacancyRepository(session=fake_session)
    service = VacancyService(cast(VacancyRepository, repo))
    pipeline_id = uuid7()

    vacancies = [
        make_raw_vacancy(canonical_url="https://jobs.dou.ua/1", dedup_hash="hash-1"),
        make_raw_vacancy(canonical_url="https://jobs.dou.ua/1", dedup_hash="hash-different"),
        make_raw_vacancy(canonical_url="https://remotive.com/2", dedup_hash="hash-1"),
        make_raw_vacancy(canonical_url="https://remotive.com/3", dedup_hash="hash-3"),
    ]

    result = await service.save_unique_vacancies(vacancies, pipeline_id=pipeline_id)

    assert len(result) == 2
    assert [v.canonical_url for v in result] == [
        "https://jobs.dou.ua/1",
        "https://remotive.com/3",
    ]
    assert repo.get_dedup_calls == 1
    assert repo.add_many_calls == 1
    assert fake_session.committed is True


async def test_save_unique_vacancies_filters_existing_db_urls_and_hashes(
    fake_session: FakeSession,
    make_raw_vacancy: Callable[..., RawVacancy],
) -> None:
    repo = _FakeVacancyRepository(
        session=fake_session,
        existing_urls={"https://jobs.dou.ua/existing"},
        existing_hashes={"hash-crosspost"},
    )
    service = VacancyService(cast(VacancyRepository, repo))
    pipeline_id = uuid7()

    vacancies = [
        make_raw_vacancy(canonical_url="https://jobs.dou.ua/existing", dedup_hash="hash-new-1"),
        make_raw_vacancy(
            canonical_url="https://remotive.com/crosspost", dedup_hash="hash-crosspost"
        ),
        make_raw_vacancy(
            canonical_url="https://remotive.com/brand-new", dedup_hash="hash-brand-new"
        ),
    ]

    result = await service.save_unique_vacancies(vacancies, pipeline_id=pipeline_id)

    assert len(result) == 1
    saved = result[0]
    assert saved.canonical_url == "https://remotive.com/brand-new"
    assert saved.dedup_hash == "hash-brand-new"
    assert saved.pipeline_id == pipeline_id
    assert saved.status == VacancyStatus.NEW
