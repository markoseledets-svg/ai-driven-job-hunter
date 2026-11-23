import re

from bs4 import BeautifulSoup

from job_hunter.schemas.vacancy_schemas import RawVacancy
from job_hunter.sources.normalizer import build_dedup_hash
from job_hunter.sources.parsers.base_parsers import (
    dedup_param,
    get_urls_with_tags,
    tag_lines,
)

_LINKEDIN_ID_PATTERN = re.compile(r"/jobs/view/(\d+)")
_LINKEDIN_NETLOCS = frozenset({"www.linkedin.com", "linkedin.com"})


def parse_linked_in_mail(soup: BeautifulSoup) -> list[RawVacancy]:
    grouped = get_urls_with_tags(
        soup,
        _LINKEDIN_ID_PATTERN,
        _LINKEDIN_NETLOCS,
        url_template="https://www.linkedin.com/jobs/view/{external_id}",
    )
    vacancies: list[RawVacancy] = []
    for url, group in grouped.items():
        card_lines = max((tag_lines(tag) for tag in group.tags), key=len, default=None)
        if not card_lines:
            continue
        title = card_lines[0]
        company = "Unknown"
        location_or_remote: str | None = None
        if len(card_lines) >= 2:
            left, sep, right = card_lines[1].partition(" · ")
            company = left.strip() or "Unknown"
            location_or_remote = right.strip() or None if sep else None
        description_raw = "\n".join(card_lines)
        vacancies.append(
            RawVacancy(
                source="linkedin_email",
                external_id=group.external_id,
                canonical_url=url,
                dedup_hash=build_dedup_hash(title, dedup_param(company, description_raw)),
                title=title,
                company=company,
                location_or_remote=location_or_remote,
                salary_raw=None,
                description_raw=description_raw,
                partial_data=True,
            )
        )
    return vacancies
