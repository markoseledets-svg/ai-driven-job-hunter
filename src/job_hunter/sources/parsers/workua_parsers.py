import re

from bs4 import BeautifulSoup

from job_hunter.schemas.vacancy_schemas import RawVacancy
from job_hunter.sources.normalizer import build_dedup_hash
from job_hunter.sources.parsers.base_parsers import (
    dedup_param,
    get_salary_from_str,
    get_urls_with_tags,
    normalize_spaces,
    soup_lines,
)

_WORK_UA_ID_PATTERN = re.compile(r"/jobs/(\d+)")
_WORK_UA_COMPANY_PATTERN = re.compile(r"/jobs/by-company/\d+")
_WORK_UA_NETLOCS = frozenset({"www.work.ua", "work.ua"})


def _parse_work_ua_instant(
    soup: BeautifulSoup,
    url: str,
    external_id: str,
) -> list[RawVacancy]:
    lines = soup_lines(soup)
    company_tag = soup.find("a", href=_WORK_UA_COMPANY_PATTERN)
    company = company_tag.get_text(" ", strip=True) if company_tag else "Unknown"

    title = "Unknown"
    for idx, line in enumerate(lines):
        if line.startswith("Вакансія від ") and idx + 1 < len(lines):
            title = lines[idx + 1]
            break

    desc_start = next((i + 1 for i, line in enumerate(lines) if line == "Опис вакансії"), None)
    if desc_start is not None:
        desc_end = next(
            (
                i
                for i in range(desc_start, len(lines))
                if lines[i] in {"Відгукнутися", "Переглянути схожі вакансії"}
            ),
            len(lines),
        )
        description_raw = "\n".join(lines[desc_start:desc_end])
    else:
        description_raw = "\n".join(lines)

    header_text = normalize_spaces("\n".join(lines[: desc_start or 20]))
    salary_raw = get_salary_from_str(header_text)

    location_or_remote: str | None = None
    for idx, line in enumerate(lines):
        if line == "Показати телефон" and idx >= 2 and lines[idx - 1].endswith("·"):
            location_or_remote = lines[idx - 2]
            break

    return [
        RawVacancy(
            source="work_ua_email",
            external_id=external_id,
            canonical_url=url,
            dedup_hash=build_dedup_hash(title, dedup_param(company, description_raw)),
            title=title,
            company=company,
            location_or_remote=location_or_remote,
            salary_raw=salary_raw,
            description_raw=description_raw,
            partial_data=False,
        )
    ]


def parse_work_ua_mail(soup: BeautifulSoup) -> list[RawVacancy]:
    grouped = get_urls_with_tags(soup, _WORK_UA_ID_PATTERN, _WORK_UA_NETLOCS)
    if not grouped:
        return []

    if soup.find("a", href=_WORK_UA_COMPANY_PATTERN) and len(grouped) == 1:
        url, group = next(iter(grouped.items()))
        return _parse_work_ua_instant(soup, url, group.external_id)

    vacancies: list[RawVacancy] = []
    for url, group in grouped.items():
        non_empty = [tag for tag in group.tags if tag.get_text(" ", strip=True)]
        if not non_empty:
            continue
        title = non_empty[0].get_text(" ", strip=True)
        company = non_empty[1].get_text(" ", strip=True) if len(non_empty) >= 2 else "Unknown"
        parent = non_empty[-1].parent
        parent_text = normalize_spaces(parent.get_text(" ", strip=True)) if parent else ""
        location_or_remote: str | None = None
        if " · " in parent_text:
            location_or_remote = parent_text.split(" · ", 1)[1].strip() or None
        salary_raw = get_salary_from_str(parent_text)
        description_raw = parent_text or title
        vacancies.append(
            RawVacancy(
                source="work_ua_email",
                external_id=group.external_id,
                canonical_url=url,
                dedup_hash=build_dedup_hash(title, dedup_param(company, description_raw)),
                title=title,
                company=company,
                location_or_remote=location_or_remote,
                salary_raw=salary_raw,
                description_raw=description_raw,
                partial_data=True,
            )
        )
    return vacancies
