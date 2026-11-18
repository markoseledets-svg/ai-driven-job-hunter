from datetime import UTC, datetime

import defusedxml.ElementTree as ET
from httpx import AsyncClient

from job_hunter.schemas.vacancy_schemas import RawVacancy
from job_hunter.sources.base import BaseHttpJobSource
from job_hunter.sources.normalizer import build_dedup_hash, normalize_rss_xml
from job_hunter.sources.parsers.dou_parsers import extract_dou_external_id, parse_dou_title

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
            normalized = normalize_rss_xml(item)
            if not normalized:
                continue
            vacancy_data = parse_dou_title(normalized.title)
            ext_id = extract_dou_external_id(normalized.url)
            dedup_param = (
                normalized.description[:500]
                if normalized.description and vacancy_data.company == "Unknown"
                else vacancy_data.company
            )
            vacancies.append(
                RawVacancy(
                    source=self.source_name,
                    external_id=ext_id if ext_id else None,
                    canonical_url=normalized.url,
                    dedup_hash=build_dedup_hash(vacancy_data.title, dedup_param),
                    title=vacancy_data.title,
                    company=vacancy_data.company,
                    location_or_remote=vacancy_data.location_or_remote,
                    salary_raw=vacancy_data.salary_raw,
                    description_raw=normalized.description,
                    partial_data=False,
                    fetched_at=fetch_time,
                )
            )
        return vacancies
