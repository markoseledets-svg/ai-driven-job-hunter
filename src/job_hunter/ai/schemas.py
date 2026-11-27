from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from uuid6 import UUID


class VacancyRatingOutput(BaseModel):
    """Structured LLM output for a single vacancy inside a scoring batch."""

    batch_index: int = Field(
        ge=1,
        description="1-based index from the <vacancy index='...'> tag.",
    )
    score: int = Field(
        ge=0,
        le=100,
        description="Overall candidate fit score from 0 to 100.",
    )
    summary: str = Field(
        max_length=500,
        description=(
            "2-3 concise English sentences explaining key fit reasons, gaps, "
            "and explicitly noting 'Partial data' when partial_data='true'."
        ),
    )
    matched_skills: list[str] = Field(
        default_factory=list,
        description="Candidate skills from the resume that match this vacancy.",
    )
    missing_skills: list[str] = Field(
        default_factory=list,
        description="Important required skills missing from the candidate resume.",
    )
    detected_company: str | None = Field(
        default=None,
        description=(
            "Company name extracted from vacancy text ONLY if input Company is 'Unknown'; "
            "otherwise null."
        ),
    )
    detected_location: str | None = Field(
        default=None,
        description=(
            "Location or work mode extracted from text ONLY if input Location is "
            "'Unknown' or 'Not specified'; otherwise null."
        ),
    )


class BatchResponse(BaseModel):
    """Structured batch response returned by Gemini."""

    ratings: list[VacancyRatingOutput]


@dataclass(frozen=True)
class ScoredVacancy:
    """Internal domain DTO mapping a Gemini rating back to its database vacancy UUID."""

    vacancy_id: UUID
    score: int
    summary: str
    matched_skills: list[str]
    missing_skills: list[str]
    detected_company: str | None = None
    detected_location: str | None = None


@dataclass(frozen=True)
class ScoringResult:
    """Internal output after scoring."""

    scored: list[ScoredVacancy]
    total_tokens: int = 0
    failed_ids: list[UUID] = field(default_factory=list)
