from datetime import UTC, datetime

from pydantic import BaseModel, Field


class RawVacancy(BaseModel):
    source: str
    external_id: str | None = None
    canonical_url: str
    dedup_hash: str
    title: str
    company: str
    location_or_remote: str | None = None
    salary_raw: str | None = None
    description_raw: str
    partial_data: bool = False
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
