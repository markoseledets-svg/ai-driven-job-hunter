import re
from dataclasses import dataclass

from job_hunter.core.schemas import PrefilterConfig
from job_hunter.schemas.vacancy_schemas import RawVacancy

_RU_SPECIFIC_RE = re.compile(r"[ыэъё]", re.IGNORECASE)
_UK_SPECIFIC_RE = re.compile(r"[іїєґ]", re.IGNORECASE)
_CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁіїєґІЇЄҐ]")
_LATIN_RE = re.compile(r"[a-zA-Z]")


@dataclass(frozen=True)
class PrefilterResult:
    passed: bool
    reason: str | None = None


def _compile_keyword_patterns(keywords: list[str]) -> tuple[tuple[str, re.Pattern[str]], ...]:
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for raw_kw in keywords:
        kw = raw_kw.strip()
        if not kw:
            continue
        compiled.append((kw, re.compile(rf"(?<!\w){re.escape(kw)}(?!\w)", re.IGNORECASE)))
    return tuple(compiled)


def _find_matching_keyword(
    text: str, patterns: tuple[tuple[str, re.Pattern[str]], ...]
) -> str | None:
    for kw, pattern in patterns:
        if pattern.search(text):
            return kw
    return None


class Prefilter:
    def __init__(self, config: PrefilterConfig | None = None) -> None:
        self.config = config or PrefilterConfig()
        self._excluded_companies = frozenset(
            company.strip().lower() for company in self.config.excluded_companies if company.strip()
        )
        self._excluded_title_patterns = _compile_keyword_patterns(
            self.config.excluded_title_keywords
        )
        self._excluded_description_patterns = _compile_keyword_patterns(
            self.config.excluded_description_keywords
        )
        self._required_any_patterns = _compile_keyword_patterns(self.config.required_any_keywords)
        self._allowed_languages = frozenset(
            lang.strip().lower() for lang in self.config.allowed_languages if lang.strip()
        )

    def _check_language(self, text: str) -> str | None:
        if not self._allowed_languages:
            return None
        if "ru" not in self._allowed_languages and _RU_SPECIFIC_RE.search(text):
            return "Language not allowed: ru"
        if "uk" not in self._allowed_languages and _UK_SPECIFIC_RE.search(text):
            return "Language not allowed: uk"
        has_cyrillic = bool(_CYRILLIC_RE.search(text))
        if (
            "uk" not in self._allowed_languages
            and "ru" not in self._allowed_languages
            and has_cyrillic
        ):
            return "Language not allowed: cyrillic"
        if "en" not in self._allowed_languages and not has_cyrillic and _LATIN_RE.search(text):
            return "Language not allowed: en"
        return None

    def check(self, vacancy: RawVacancy) -> PrefilterResult:
        if vacancy.company.strip().lower() in self._excluded_companies:
            return PrefilterResult(passed=False, reason=f"Excluded company: {vacancy.company}")

        if matched_title := _find_matching_keyword(vacancy.title, self._excluded_title_patterns):
            return PrefilterResult(passed=False, reason=f"Excluded title keyword: {matched_title}")

        if matched_desc := _find_matching_keyword(
            vacancy.description_raw, self._excluded_description_patterns
        ):
            return PrefilterResult(
                passed=False, reason=f"Excluded description keyword: {matched_desc}"
            )

        if self._required_any_patterns and not vacancy.partial_data:
            has_required = any(
                pattern.search(vacancy.title) or pattern.search(vacancy.description_raw)
                for _, pattern in self._required_any_patterns
            )
            if not has_required:
                return PrefilterResult(passed=False, reason="Missing required keywords")

        if lang_reason := self._check_language(f"{vacancy.title}\n{vacancy.description_raw}"):
            return PrefilterResult(passed=False, reason=lang_reason)

        return PrefilterResult(passed=True)
