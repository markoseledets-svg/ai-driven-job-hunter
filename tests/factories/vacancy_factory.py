from polyfactory import Use
from uuid6 import uuid7

from job_hunter.schemas.vacancy_schemas import RawVacancy
from tests.factories.base_factory import BaseModelFactory


def _unique_url() -> str:
    return f"https://jobs.dou.ua/vacancies/{uuid7()}/"


def _unique_hash() -> str:
    return uuid7().hex + uuid7().hex


class RawVacancyFactory(BaseModelFactory[RawVacancy]):
    source = "dou_rss"
    external_id: str | None = None
    canonical_url = Use(_unique_url)
    dedup_hash = Use(_unique_hash)
    title = Use(BaseModelFactory.__faker__.job)
    company = Use(BaseModelFactory.__faker__.company)
    location_or_remote = "Remote"
    salary_raw = "$1500-$2500"
    description_raw = "Python, FastAPI, SQLAlchemy, PostgreSQL, Docker."
    partial_data = False
