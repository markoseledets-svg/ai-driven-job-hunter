import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from job_hunter.sources.normalizer import canonicalize_url

_SALARY_PATTERN = re.compile(
    r"(?:(?:від|до|from|to|up to)\s+)?"
    r"(?:(?:[$€₴]|грн\.?|uah|usd|eur)\s*\d+(?:[\s.,]\d+)*\s*[kк]?"
    r"(?:\s*[-–—]\s*(?:[$€₴]|грн\.?|uah|usd|eur)?\s*\d+(?:[\s.,]\d+)*\s*[kк]?)?"
    r"|\d+(?:[\s.,]\d+)*\s*[kк]?"
    r"(?:\s*(?:[$€₴]|грн\.?|uah|usd|eur)?\s*[-–—]\s*\d+(?:[\s.,]\d+)*\s*[kк]?)?"
    r"\s*(?:[$€₴]|грн\.?|uah|usd|eur))"
    r"(?=\s|$|[.,;!?)])",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class GroupedVacancyLinks:
    external_id: str
    tags: list[Tag] = field(default_factory=list)


def get_salary_from_str(text: str) -> str | None:
    match = _SALARY_PATTERN.search(text)
    return match.group(0).strip() if match else None


def extract_external_id_from_url(url: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(url)
    return match.group(1) if match else None


def tag_lines(tag: Tag) -> list[str]:
    return [line.strip() for line in tag.get_text("\n").splitlines() if line.strip()]


def soup_lines(soup: BeautifulSoup) -> list[str]:
    return [
        re.sub(r"\s+", " ", line).strip()
        for line in soup.get_text("\n").splitlines()
        if line.strip()
    ]


def normalize_spaces(text: str) -> str:
    text = text.replace("\xad", "")
    return re.sub(r"[\u2009\u202f\xa0]+", " ", text)


def dedup_param(company: str, description: str) -> str:
    return description[:500] if description and company == "Unknown" else company


def get_urls_with_tags(
    soup: BeautifulSoup,
    id_pattern: re.Pattern[str],
    allowed_netlocs: frozenset[str],
    url_template: str | None = None,
    strip_query: bool = False,
) -> dict[str, GroupedVacancyLinks]:
    """Group matching vacancy <a> tags by canonical URL (or normalized template)."""
    grouped: dict[str, GroupedVacancyLinks] = {}
    for tag in soup.find_all("a", href=True):
        url = str(tag["href"])
        parsed_url = urlparse(url)
        if parsed_url.scheme != "https" or parsed_url.netloc.lower() not in allowed_netlocs:
            continue
        clean_url = (
            f"{parsed_url.scheme}://{parsed_url.netloc.lower()}{parsed_url.path.rstrip('/')}"
            if strip_query
            else canonicalize_url(url)
        )
        ext_id = extract_external_id_from_url(clean_url, id_pattern)
        if not ext_id:
            continue
        key = url_template.format(external_id=ext_id) if url_template else clean_url
        if key not in grouped:
            grouped[key] = GroupedVacancyLinks(external_id=ext_id)
        grouped[key].tags.append(tag)
    return grouped
