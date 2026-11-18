import re
from dataclasses import dataclass

from job_hunter.sources.parsers.base_parsers import (
    extract_external_id_from_url,
    get_salary_from_str,
)

_DOU_ID_PATTERN = re.compile(r"/vacancies/(\d+)")


@dataclass(frozen=True)
class DouTitleParts:
    title: str
    company: str
    salary_raw: str | None = None
    location_or_remote: str | None = None


def extract_dou_external_id(url: str) -> str | None:
    return extract_external_id_from_url(url=url, pattern=_DOU_ID_PATTERN)


def _split_dou_title_tail(raw_title: str) -> tuple[str, str | None]:
    best_idx = -1
    best_sep = ""
    for sep in (" в ", " at "):
        idx = raw_title.rfind(sep)
        if idx > best_idx:
            best_idx = idx
            best_sep = sep
    if best_idx == -1:
        return raw_title.strip(), None
    return raw_title[:best_idx].strip(), raw_title[best_idx + len(best_sep) :].strip()


def parse_dou_title(raw_title: str) -> DouTitleParts:
    title, tail = _split_dou_title_tail(raw_title)
    if not tail:
        return DouTitleParts(title=title, company="Unknown")

    parts = [part.strip() for part in tail.split(",") if part.strip()]
    if not parts:
        return DouTitleParts(title=title, company="Unknown")

    company = parts[0]
    salary_raw: str | None = None
    locations: list[str] = []

    for part in parts[1:]:
        detected_salary = get_salary_from_str(part)
        if detected_salary and salary_raw is None:
            salary_raw = detected_salary
        else:
            locations.append(part)

    location_or_remote = ", ".join(locations) if locations else None
    return DouTitleParts(
        title=title,
        company=company,
        salary_raw=salary_raw,
        location_or_remote=location_or_remote,
    )
