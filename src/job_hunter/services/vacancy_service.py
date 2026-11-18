from uuid6 import UUID

from job_hunter.db.enums import VacancyStatus
from job_hunter.db.models import Vacancy
from job_hunter.db.repo.vacancy_repo import VacancyRepository
from job_hunter.schemas.vacancy_schemas import RawVacancy


class VacancyService:
    def __init__(self, vacancy_repo: VacancyRepository):
        self._vacancy_repo = vacancy_repo

    async def save_unique_vacancies(
        self, vacancies: list[RawVacancy], pipeline_id: UUID
    ) -> list[Vacancy]:
        if not vacancies:
            return []
        seen_urls = set()
        seen_hashes = set()
        unique_vacancies: list[RawVacancy] = []
        for vacancy in vacancies:
            if vacancy.canonical_url in seen_urls or vacancy.dedup_hash in seen_hashes:
                continue
            seen_urls.add(vacancy.canonical_url)
            seen_hashes.add(vacancy.dedup_hash)
            unique_vacancies.append(vacancy)
        existing_urls, existing_hashes = await self._vacancy_repo.get_dedup_params(
            urls=seen_urls, hashes=seen_hashes
        )
        unique_db_vacancies: list[Vacancy] = []
        for v in unique_vacancies:
            if v.canonical_url in existing_urls or v.dedup_hash in existing_hashes:
                continue
            unique_db_vacancies.append(
                Vacancy(
                    pipeline_id=pipeline_id,
                    source=v.source,
                    external_id=v.external_id,
                    canonical_url=v.canonical_url,
                    dedup_hash=v.dedup_hash,
                    title=v.title,
                    company=v.company,
                    location_or_remote=v.location_or_remote,
                    salary_raw=v.salary_raw,
                    description_raw=v.description_raw,
                    partial_data=v.partial_data,
                    status=VacancyStatus.NEW,
                    fetched_at=v.fetched_at,
                )
            )
        if not unique_db_vacancies:
            return []
        added_vacancies = await self._vacancy_repo.add_many(entities=unique_db_vacancies)
        await self._vacancy_repo._session.commit()
        return added_vacancies
