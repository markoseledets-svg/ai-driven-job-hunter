import logging
from datetime import UTC, datetime

import defusedxml.ElementTree as ET
from httpx import AsyncClient

from job_hunter.schemas.vacancy_schemas import RawVacancy
from job_hunter.sources.base import BaseHttpJobSource
from job_hunter.sources.normalizer import build_dedup_hash, normalize_rss_xml
from job_hunter.sources.parsers.djini_parsers import (
    extract_djini_external_id,
    parse_djini_description,
)

logger = logging.getLogger(__name__)
DJINI_URL = "https://djinni.co/jobs/rss/?primary_keyword=Python"


class DjiniRssSource(BaseHttpJobSource):
    def __init__(self, client: AsyncClient, url: str = DJINI_URL, timeout: float = 15.0):
        super().__init__(client, url, timeout)

    @property
    def source_name(self) -> str:
        return "djini_rss"

    async def fetch(self) -> list[RawVacancy]:
        fetch_time = datetime.now(UTC)
        xml_response = await self._fetch_text()
        if not xml_response:
            logger.warning("Djinni RSS returned empty response")
            return []
        root = ET.fromstring(xml_response)
        vacancies: list[RawVacancy] = []
        skipped = 0
        for item in root.findall(".//item"):
            normalized = normalize_rss_xml(item)
            if not normalized:
                skipped += 1
                logger.debug("Skipping malformed Djinni RSS item")
                continue
            ext_id = extract_djini_external_id(normalized.url)
            vacancy_data = parse_djini_description(normalized.description)
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
                    dedup_hash=build_dedup_hash(normalized.title, dedup_param),
                    title=normalized.title,
                    company=vacancy_data.company,
                    location_or_remote=vacancy_data.location_or_remote,
                    salary_raw=vacancy_data.salary,
                    description_raw=normalized.description,
                    partial_data=False,
                    fetched_at=fetch_time,
                )
            )
        logger.info(
            "Fetched %d vacancies from %s (skipped=%d)",
            len(vacancies),
            self.source_name,
            skipped,
        )
        return vacancies
