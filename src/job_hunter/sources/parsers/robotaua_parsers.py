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

_ROBOTA_UA_ID_PATTERN = re.compile(r"/company\d+/vacancy(\d+)$")
_ROBOTA_UA_NETLOCS = frozenset({"robota.ua", "www.robota.ua"})


def _split_robota_meta(raw_meta: str) -> tuple[str | None, str | None, str]:
    marked = re.sub(r"\xa0{2,}|\s{2,}", "\t", raw_meta.strip())
    norm_for_salary = normalize_spaces(marked.replace("\t", " "))
    salary_raw = get_salary_from_str(norm_for_salary)

    cleaned = normalize_spaces(marked)
    if salary_raw:
        cleaned = cleaned.replace(salary_raw, "", 1).strip()

    if "\t" in cleaned:
        left, right = cleaned.split("\t", 1)
        location_or_remote = left.strip() or None
        company = right.strip() or "Unknown"
        return salary_raw, location_or_remote, company

    return salary_raw, None, cleaned.strip() or "Unknown"


def _parse_robota_solo_block(
    soup: BeautifulSoup,
    title: str,
) -> tuple[str, str | None, str | None, str]:
    lines = soup_lines(soup)
    try:
        idx = lines.index(title)
    except ValueError:
        return "Unknown", None, None, title

    company = lines[idx + 1] if idx + 1 < len(lines) else "Unknown"
    location_parts: list[str] = []
    if idx > 0 and lines[idx - 1] == "Віддалена робота":
        location_parts.append("Віддалена робота")
    if idx + 2 < len(lines):
        location_parts.append(lines[idx + 2])
    location_or_remote = ", ".join(location_parts) if location_parts else None

    desc_start = idx + 3
    desc_end = next(
        (
            i
            for i in range(desc_start, len(lines))
            if lines[i] in {"Відгукнутись на вакансію", "Вакансії за вашим запитом"}
        ),
        len(lines),
    )
    description_raw = "\n".join(lines[desc_start:desc_end]) if desc_start < desc_end else title
    salary_raw = get_salary_from_str(normalize_spaces(description_raw))
    return company, location_or_remote, salary_raw, description_raw


def parse_robota_ua_mail(soup: BeautifulSoup) -> list[RawVacancy]:
    grouped = get_urls_with_tags(soup, _ROBOTA_UA_ID_PATTERN, _ROBOTA_UA_NETLOCS, strip_query=True)
    vacancies: list[RawVacancy] = []
    for url, group in grouped.items():
        non_empty = [tag for tag in group.tags if tag.get_text(" ", strip=True)]
        if not non_empty:
            continue
        title = non_empty[0].get_text(" ", strip=True)
        if len(non_empty) >= 2:
            raw_meta = non_empty[1].get_text(" ", strip=True)
            salary_raw, location_or_remote, company = _split_robota_meta(raw_meta)
            description_raw = f"{title}\n{normalize_spaces(raw_meta)}"
            partial_data = True
        else:
            company, location_or_remote, salary_raw, description_raw = _parse_robota_solo_block(
                soup, title
            )
            partial_data = False

        vacancies.append(
            RawVacancy(
                source="robota_ua_email",
                external_id=group.external_id,
                canonical_url=url,
                dedup_hash=build_dedup_hash(title, dedup_param(company, description_raw)),
                title=title,
                company=company,
                location_or_remote=location_or_remote,
                salary_raw=salary_raw,
                description_raw=description_raw,
                partial_data=partial_data,
            )
        )
    return vacancies
