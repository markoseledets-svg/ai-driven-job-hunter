from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient, Response
from pydantic import BaseModel, Field

from job_hunter.db.enums import VacancySource

headers = {"User-Agent": "ai-driven-job-hunter/0.1"}


class RawVacancy(BaseModel):
    source: VacancySource
    external_id: str | None = None
    canonical_url: str
    dedup_hash: str
    title: str
    company: str
    location_or_remote: str | None = None
    salary_raw: str | None = None
    description_raw: str
    partial_data: bool
    fetched_at: datetime = Field(default=datetime.now(UTC))


class BaseJobSource(ABC):
    @abstractmethod
    async def fetch(self) -> list[RawVacancy]:
        pass

    @abstractmethod
    @property
    def source_name(self) -> VacancySource: ...


class BaseHttpJobSource(BaseJobSource, ABC):
    def __init__(self, client: AsyncClient, url: str, timeout: float = 15.0):
        self._client = client
        self._url = url
        self._timeout = timeout

    async def _fetch(self) -> Response:
        response = await self._client.get(
            url=self._url, headers=headers, timeout=self._timeout, follow_redirects=True
        )
        response.raise_for_status()
        return response

    async def _fetch_text(self) -> str:
        response = await self._fetch()
        return response.text

    async def _fetch_json(self) -> Any:
        response = await self._fetch()
        return response.json()
