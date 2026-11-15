from pydantic import BaseModel, Field


class PrefilterConfig(BaseModel):
    """Deterministic keyword and language filtering rules for candidate matching."""

    excluded_title_keywords: list[str] = Field(default_factory=list)
    excluded_description_keywords: list[str] = Field(default_factory=list)
    excluded_companies: list[str] = Field(default_factory=list)
    required_any_keywords: list[str] = Field(default_factory=list)
    allowed_languages: list[str] = Field(default_factory=lambda: ["en", "uk"])
