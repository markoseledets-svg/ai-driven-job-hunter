from collections.abc import Callable
from typing import Any

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
