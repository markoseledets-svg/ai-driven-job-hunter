import logging
from collections.abc import Sequence
from itertools import batched

import httpx
from google import genai
from google.genai import types
from google.genai.errors import APIError
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)
from uuid6 import UUID

from job_hunter.ai.prompts import build_batch_user_prompt, build_system_prompt
from job_hunter.ai.schemas import BatchResponse, ScoredVacancy, ScoringResult
from job_hunter.db.models import CalibrationExample, Vacancy

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


def _is_retryable_error(exc: BaseException) -> bool:
    if isinstance(exc, APIError):
        return exc.code in _RETRYABLE_STATUS_CODES
    return isinstance(exc, (TimeoutError, ConnectionError, httpx.TransportError))


class GeminiScorer:
    def __init__(
        self,
        client: genai.Client | None = None,
        api_key: str | None = None,
        model: str = "gemini-4-hydrogen",
        batch_size: int = 8,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        if client is not None:
            self._client: genai.Client | None = client
        elif api_key:
            self._client = genai.Client(api_key=api_key)
        else:
            self._client = None

        self._model = model
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._base_delay = base_delay

    async def _send_to_ai(
        self,
        client: genai.Client,
        sys_prompt: str,
        content: str,
    ) -> tuple[BatchResponse, int]:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(_is_retryable_error),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(
                multiplier=self._base_delay,
                min=self._base_delay,
                max=15,
            ),
            reraise=True,
        ):
            with attempt:
                response = await client.aio.models.generate_content(
                    model=self._model,
                    contents=content,
                    config=types.GenerateContentConfig(
                        system_instruction=sys_prompt,
                        response_mime_type="application/json",
                        response_schema=BatchResponse,
                        temperature=0.1,
                    ),
                )
                if isinstance(response.parsed, BatchResponse):
                    result = response.parsed
                elif response.text:
                    result = BatchResponse.model_validate_json(response.text)
                else:
                    raise ValueError("Gemini returned an empty response")

                usage = response.usage_metadata
                tokens_spent = (usage.total_token_count or 0) if usage is not None else 0
                return result, tokens_spent

        raise RuntimeError("Unreachable")

    async def score_vacancies(
        self,
        vacancies: Sequence[Vacancy],
        calibration_examples: Sequence[CalibrationExample],
        resume_text: str,
    ) -> ScoringResult:
        if self._client is None:
            logger.warning("Gemini client is not configured; skipping AI scoring")
            return ScoringResult(scored=[])
        if not vacancies:
            return ScoringResult(scored=[])

        system_prompt = build_system_prompt(resume_text, calibration_examples)
        rates: list[ScoredVacancy] = []
        failed_ids: list[UUID] = []
        total_tokens = 0

        for batch in batched(vacancies, self._batch_size):
            id_mapping: dict[int, UUID] = {idx: v.id for idx, v in enumerate(batch, start=1)}
            batch_prompt = build_batch_user_prompt(batch)

            try:
                batch_response, token_spent = await self._send_to_ai(
                    self._client, system_prompt, batch_prompt
                )
            except Exception:
                logger.exception(
                    "Failed to score batch of %d vacancies with model=%s",
                    len(batch),
                    self._model,
                )
                failed_ids.extend(v.id for v in batch)
                continue

            total_tokens += token_spent
            scored_in_batch: set[UUID] = set()

            for rating in batch_response.ratings:
                v_id = id_mapping.get(rating.batch_index)
                if v_id is None:
                    logger.warning(
                        "Gemini returned unknown batch_index=%s (expected 1..%d)",
                        rating.batch_index,
                        len(batch),
                    )
                    continue
                if v_id in scored_in_batch:
                    logger.warning(
                        "Gemini returned duplicate rating for batch_index=%s",
                        rating.batch_index,
                    )
                    continue

                scored_in_batch.add(v_id)
                rates.append(
                    ScoredVacancy(
                        vacancy_id=v_id,
                        score=rating.score,
                        summary=rating.summary,
                        matched_skills=rating.matched_skills,
                        missing_skills=rating.missing_skills,
                        detected_company=rating.detected_company,
                        detected_location=rating.detected_location,
                    )
                )

            missing_in_batch = [v.id for v in batch if v.id not in scored_in_batch]
            if missing_in_batch:
                logger.warning(
                    "Gemini omitted %d vacancies from batch response",
                    len(missing_in_batch),
                )
                failed_ids.extend(missing_in_batch)

        logger.info(
            "AI scoring complete (scored=%d, failed=%d, total_tokens=%d)",
            len(rates),
            len(failed_ids),
            total_tokens,
        )
        return ScoringResult(
            scored=rates,
            total_tokens=total_tokens,
            failed_ids=failed_ids,
        )