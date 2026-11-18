import re
from dataclasses import dataclass

from job_hunter.sources.parsers.base_parsers import (
    extract_external_id_from_url,
    get_salary_from_str,
)

_DJINI_ID_PATTERN = re.compile(r"/jobs/(\d+)")

_QUOTED_DASH_PATTERN = re.compile(r'^\s*[«"]([^»"]{2,40})[»"]\s*[—–-]')
_HIRING_VERB_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z0-9.&'-]{1,30})\s+(?:is looking for|is hiring|is seeking)\b"
)
_SECTION_HEADER_PATTERN = re.compile(r"(?m)^(?:About|Why|Про)\s+([A-ZА-ЯІЇЄҐ][\w.&'-]{1,30})\s*$")

_HIRING_STOP_WORDS = frozenset({"client", "team", "company", "we", "startup", "partner"})
_HEADER_STOP_WORDS = frozenset({"us", "company", "team", "project", "role", "client", "nas", "нас"})

_COMPANY_PATTERNS: tuple[tuple[re.Pattern[str], frozenset[str]], ...] = (
    (_QUOTED_DASH_PATTERN, frozenset()),
    (_HIRING_VERB_PATTERN, _HIRING_STOP_WORDS),
    (_SECTION_HEADER_PATTERN, _HEADER_STOP_WORDS),
)

_WORK_MODE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "Remote",
        re.compile(
            r"\b(?:fully\s+remote|100%\s+remote|remote-first|remote\s+mode|"
            r"remote(?!\s+(?:access|control|desktop|server))|віддален[оа]|дистанційн[оа])\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Hybrid",
        re.compile(r"\b(?:hybrid|гібрид(?:н[ийао])?)\b", re.IGNORECASE),
    ),
    (
        "On-site",
        re.compile(
            r"\b(?:on-?site|in-office|в\s+офісі|офіс\s+(?:у|в)|office\s+in|office\s+location)\b",
            re.IGNORECASE,
        ),
    ),
)

_OFFICE_LOCATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:офіс\s+(?:у|в)|локація\s*:)\s*([А-ЯІЇЄҐ][а-яіїєґ'-]{2,25})"),
    re.compile(
        r"(?:office\s+(?:in|location\s*:)|based\s+in|location\s*:)\s*"
        r"([A-Z][a-zA-Z'-]{2,25}(?:,\s*[A-Z][a-zA-Z'-]{2,25})?)"
    ),
)


@dataclass
class DjiniDescriptionParts:
    company: str
    salary: str | None = None
    location_or_remote: str | None = None


def extract_djini_external_id(url: str) -> str | None:
    return extract_external_id_from_url(url=url, pattern=_DJINI_ID_PATTERN)


def extract_djini_company(text: str) -> str:
    for pattern, stop_words in _COMPANY_PATTERNS:
        for match in pattern.finditer(text):
            candidate = match.group(1).strip()
            if candidate and candidate.lower() not in stop_words:
                return candidate
    return "Unknown"


def _extract_office_location(text: str) -> str | None:
    for pattern in _OFFICE_LOCATION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def extract_djini_location_or_remote(text: str) -> str | None:
    modes = [label for label, pattern in _WORK_MODE_PATTERNS if pattern.search(text)]
    office_location = _extract_office_location(text)

    if office_location and "On-site" not in modes and "Hybrid" not in modes:
        modes.append("On-site")

    if not modes and not office_location:
        return None
    if office_location:
        return f"{', '.join(modes)} ({office_location})"
    return ", ".join(modes)


def parse_djini_description(description: str) -> DjiniDescriptionParts:
    if not description:
        return DjiniDescriptionParts(company="Unknown")
    salary = get_salary_from_str(description)
    company = extract_djini_company(description)
    location_or_remote = extract_djini_location_or_remote(description)
    return DjiniDescriptionParts(
        company=company, salary=salary, location_or_remote=location_or_remote
    )
