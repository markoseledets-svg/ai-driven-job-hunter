from collections.abc import Callable
from typing import Any

import httpx
import pytest

from job_hunter.schemas.vacancy_schemas import RawVacancy
from tests.factories.vacancy_factory import RawVacancyFactory


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


@pytest.fixture
def fake_session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def make_raw_vacancy() -> Callable[..., RawVacancy]:
    def _factory(**overrides: Any) -> RawVacancy:
        return RawVacancyFactory.build(**overrides)

    return _factory


@pytest.fixture
def mock_http_client() -> Callable[..., httpx.AsyncClient]:
    def _factory(
        *,
        text: str | None = None,
        json_data: Any = None,
        status_code: int = 200,
    ) -> httpx.AsyncClient:
        def _handler(request: httpx.Request) -> httpx.Response:
            if json_data is not None:
                return httpx.Response(status_code=status_code, json=json_data)
            return httpx.Response(status_code=status_code, text=text or "")

        return httpx.AsyncClient(transport=httpx.MockTransport(_handler))

    return _factory
