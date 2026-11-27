from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import pytest
from google import genai
from google.genai.errors import APIError
from uuid6 import uuid7

from job_hunter.ai.gemini_client import GeminiScorer
from job_hunter.ai.schemas import BatchResponse, VacancyRatingOutput
from job_hunter.db.enums import VacancyStatus
from job_hunter.db.models import CalibrationExample, Vacancy


@dataclass
class _FakeUsage:
    total_token_count: int | None


@dataclass
class _FakeResponse:
    parsed: BatchResponse | None = None
    text: str | None = None
    usage_metadata: _FakeUsage | None = None


class _FakeModels:
    def __init__(self, handler: Callable[[int, str], _FakeResponse]) -> None:
        self._handler = handler
        self.calls = 0

    async def generate_content(
        self,
        *,
        model: str,
        contents: str,
        config: object,
    ) -> _FakeResponse:
        self.calls += 1
        return self._handler(self.calls, contents)


class _FakeAio:
    def __init__(self, handler: Callable[[int, str], _FakeResponse]) -> None:
        self.models = _FakeModels(handler)


class _FakeGenaiClient:
    def __init__(self, handler: Callable[[int, str], _FakeResponse]) -> None:
        self.aio = _FakeAio(handler)


def _make_vacancy(idx: int) -> Vacancy:
    return Vacancy(
        id=uuid7(),
        source="dou_rss",
        canonical_url=f"https://jobs.dou.ua/vacancies/{idx}",
        dedup_hash=f"hash-{idx}",
        title=f"Python Engineer {idx}",
        company="Unknown",
        description_raw=f"Role {idx} description at CloudCorp.",
        partial_data=False,
        status=VacancyStatus.NEW,
    )


def _make_calibration() -> list[CalibrationExample]:
    return [
        CalibrationExample(
            title="Junior Python Dev",
            description_snippet="FastAPI and PostgreSQL.",
            expected_score=85,
            rationale="Strong fit.",
            is_active=True,
        )
    ]


async def test_score_vacancies_returns_empty_without_client_or_vacancies() -> None:
    scorer_no_client = GeminiScorer(client=None, api_key=None)
    res1 = await scorer_no_client.score_vacancies([_make_vacancy(1)], _make_calibration(), "CV")
    assert res1.scored == []
    assert res1.total_tokens == 0
    assert res1.failed_ids == []

    fake_client = _FakeGenaiClient(lambda call, contents: _FakeResponse())
    scorer_empty = GeminiScorer(client=cast(genai.Client, fake_client), base_delay=0.0)
    res2 = await scorer_empty.score_vacancies([], _make_calibration(), "CV")
    assert res2.scored == []
    assert fake_client.aio.models.calls == 0


async def test_score_vacancies_batches_maps_ids_enrichment_and_tokens() -> None:
    v1, v2, v3 = _make_vacancy(1), _make_vacancy(2), _make_vacancy(3)

    def _handler(call: int, contents: str) -> _FakeResponse:
        if call == 1:
            return _FakeResponse(
                parsed=BatchResponse(
                    ratings=[
                        VacancyRatingOutput(
                            batch_index=1,
                            score=90,
                            summary="Great match.",
                            matched_skills=["Python"],
                            missing_skills=[],
                            detected_company="CloudCorp",
                            detected_location="Remote",
                        ),
                        VacancyRatingOutput(
                            batch_index=2,
                            score=60,
                            summary="Decent match.",
                            matched_skills=["SQL"],
                            missing_skills=["Docker"],
                        ),
                    ]
                ),
                usage_metadata=_FakeUsage(total_token_count=120),
            )
        return _FakeResponse(
            text=BatchResponse(
                ratings=[
                    VacancyRatingOutput(
                        batch_index=1,
                        score=40,
                        summary="Weak match.",
                    )
                ]
            ).model_dump_json(),
            usage_metadata=_FakeUsage(total_token_count=80),
        )

    fake_client = _FakeGenaiClient(_handler)
    scorer = GeminiScorer(
        client=cast(genai.Client, fake_client),
        batch_size=2,
        base_delay=0.0,
    )

    result = await scorer.score_vacancies([v1, v2, v3], _make_calibration(), "Python CV")

    assert fake_client.aio.models.calls == 2
    assert result.total_tokens == 200
    assert result.failed_ids == []
    assert [item.vacancy_id for item in result.scored] == [v1.id, v2.id, v3.id]
    assert result.scored[0].detected_company == "CloudCorp"
    assert result.scored[0].detected_location == "Remote"


async def test_score_vacancies_retries_on_retryable_api_error() -> None:
    v1 = _make_vacancy(1)

    def _handler(call: int, contents: str) -> _FakeResponse:
        if call == 1:
            raise APIError(429, {"error": {"message": "Rate limit"}})
        return _FakeResponse(
            parsed=BatchResponse(
                ratings=[VacancyRatingOutput(batch_index=1, score=82, summary="Good fit.")]
            ),
            usage_metadata=_FakeUsage(total_token_count=50),
        )

    fake_client = _FakeGenaiClient(_handler)
    scorer = GeminiScorer(
        client=cast(genai.Client, fake_client),
        max_retries=3,
        base_delay=0.0,
    )

    result = await scorer.score_vacancies([v1], _make_calibration(), "Python CV")

    assert fake_client.aio.models.calls == 2
    assert len(result.scored) == 1
    assert result.scored[0].vacancy_id == v1.id
    assert result.failed_ids == []
    assert result.total_tokens == 50


async def test_score_vacancies_does_not_retry_on_400_and_isolates_failed_batch() -> None:
    v1, v2 = _make_vacancy(1), _make_vacancy(2)

    def _handler(call: int, contents: str) -> _FakeResponse:
        if call == 1:
            raise APIError(400, {"error": {"message": "Bad request"}})
        return _FakeResponse(
            parsed=BatchResponse(
                ratings=[VacancyRatingOutput(batch_index=1, score=77, summary="Match.")]
            ),
            usage_metadata=_FakeUsage(total_token_count=60),
        )

    fake_client = _FakeGenaiClient(_handler)
    scorer = GeminiScorer(
        client=cast(genai.Client, fake_client),
        batch_size=1,
        max_retries=3,
        base_delay=0.0,
    )

    result = await scorer.score_vacancies([v1, v2], _make_calibration(), "Python CV")

    assert fake_client.aio.models.calls == 2
    assert result.failed_ids == [v1.id]
    assert [item.vacancy_id for item in result.scored] == [v2.id]
    assert result.total_tokens == 60


async def test_score_vacancies_tracks_missing_and_unknown_indices() -> None:
    v1, v2 = _make_vacancy(1), _make_vacancy(2)

    def _handler(call: int, contents: str) -> _FakeResponse:
        return _FakeResponse(
            parsed=BatchResponse(
                ratings=[
                    VacancyRatingOutput(batch_index=1, score=85, summary="Strong fit."),
                    VacancyRatingOutput(batch_index=99, score=50, summary="Hallucinated index."),
                ]
            ),
            usage_metadata=None,
        )

    fake_client = _FakeGenaiClient(_handler)
    scorer = GeminiScorer(
        client=cast(genai.Client, fake_client),
        batch_size=5,
        base_delay=0.0,
    )

    result = await scorer.score_vacancies([v1, v2], _make_calibration(), "Python CV")

    assert [item.vacancy_id for item in result.scored] == [v1.id]
    assert result.failed_ids == [v2.id]
    assert result.total_tokens == 0


async def test_init_uses_vertexai_when_flag_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    fake_client = _FakeGenaiClient(lambda call, contents: _FakeResponse())

    def _fake_client_ctor(**kwargs: Any) -> _FakeGenaiClient:
        calls.append(kwargs)
        return fake_client

    monkeypatch.setattr("job_hunter.ai.gemini_client.genai.Client", _fake_client_ctor)

    GeminiScorer(api_key="key", use_vertexai=True, gcp_project="proj")

    assert calls == [{"vertexai": True, "project": "proj", "location": "global"}]


async def test_init_disables_client_when_vertexai_enabled_without_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def _fake_client_ctor(**kwargs: Any) -> _FakeGenaiClient:
        calls.append(kwargs)
        return _FakeGenaiClient(lambda call, contents: _FakeResponse())

    monkeypatch.setattr("job_hunter.ai.gemini_client.genai.Client", _fake_client_ctor)

    scorer = GeminiScorer(api_key="key", use_vertexai=True, gcp_project=None)
    result = await scorer.score_vacancies([_make_vacancy(1)], _make_calibration(), "CV")

    assert calls == []
    assert result.scored == []
    assert result.total_tokens == 0
    assert result.failed_ids == []


async def test_init_uses_api_key_when_vertexai_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    fake_client = _FakeGenaiClient(lambda call, contents: _FakeResponse())

    def _fake_client_ctor(**kwargs: Any) -> _FakeGenaiClient:
        calls.append(kwargs)
        return fake_client

    monkeypatch.setattr("job_hunter.ai.gemini_client.genai.Client", _fake_client_ctor)

    GeminiScorer(api_key="key", use_vertexai=False, gcp_project="proj")

    assert calls == [{"api_key": "key"}]


async def test_init_falls_back_to_vertexai_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []
    fake_client = _FakeGenaiClient(lambda call, contents: _FakeResponse())

    def _fake_client_ctor(**kwargs: Any) -> _FakeGenaiClient:
        calls.append(kwargs)
        return fake_client

    monkeypatch.setattr("job_hunter.ai.gemini_client.genai.Client", _fake_client_ctor)

    GeminiScorer(
        api_key=None,
        use_vertexai=False,
        gcp_project="proj",
        gcp_location="europe-west1",
    )

    assert calls == [{"vertexai": True, "project": "proj", "location": "europe-west1"}]
