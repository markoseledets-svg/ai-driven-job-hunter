from datetime import UTC, datetime

import defusedxml.ElementTree as ET
from httpx import AsyncClient

from job_hunter.schemas.vacancy_schemas import RawVacancy
from job_hunter.sources.base import BaseHttpJobSource
from job_hunter.sources.normalizer import build_dedup_hash, canonicalize_url, sanitize_html
from job_hunter.sources.parsers import extract_dou_external_id, parse_dou_title

DOU_URL = "https://jobs.dou.ua/vacancies/feeds/?category=Python"


class DouRssSource(BaseHttpJobSource):
    def __init__(self, client: AsyncClient, url: str = DOU_URL, timeout: float = 15.0):
        super().__init__(client, url, timeout)

    @property
    def source_name(self) -> str:
        return "dou_rss"

    async def fetch(self) -> list[RawVacancy]:
        fetch_time = datetime.now(UTC)
        xml_response = await self._fetch_text()
        if not xml_response:
            return []
        root = ET.fromstring(xml_response)
        vacancies: list[RawVacancy] = []
        for item in root.findall(".//item"):
            raw_title = item.findtext("title")
            link = item.findtext("link")
            if not link or not raw_title:
                continue
            url = canonicalize_url(link)
            vacancy_data = parse_dou_title(raw_title)
            ext_id = extract_dou_external_id(url)
            raw_desc = item.findtext("description")
            description = sanitize_html(raw_desc) if raw_desc else ""
            dedup_param = (
                description[:500]
                if description and vacancy_data.company == "Unknown"
                else vacancy_data.company
            )
            vacancies.append(
                RawVacancy(
                    source=self.source_name,
                    external_id=ext_id if ext_id else None,
                    canonical_url=url,
                    dedup_hash=build_dedup_hash(vacancy_data.title, dedup_param),
                    title=vacancy_data.title,
                    company=vacancy_data.company,
                    location_or_remote=vacancy_data.location_or_remote,
                    salary_raw=vacancy_data.salary_raw,
                    description_raw=description,
                    partial_data=False,
                    fetched_at=fetch_time,
                )
            )
        return vacancies
