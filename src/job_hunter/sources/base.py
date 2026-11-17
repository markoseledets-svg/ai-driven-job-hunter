from abc import ABC, abstractmethod
from typing import Any

from httpx import AsyncClient, Response

from job_hunter.schemas.vacancy_schemas import RawVacancy

headers = {"User-Agent": "ai-driven-job-hunter/0.1"}


class BaseJobSource(ABC):
    @abstractmethod
    async def fetch(self) -> list[RawVacancy]:
        pass

    @property
    @abstractmethod
    def source_name(self) -> str: ...


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
