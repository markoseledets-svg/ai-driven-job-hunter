from collections.abc import Callable
from pathlib import Path

import httpx

from job_hunter.sources.djini_rss import DjiniRssSource
from job_hunter.sources.normalizer import build_dedup_hash

FIXTURE_XML = (Path(__file__).parent / "djini_rss.xml").read_text(encoding="utf-8")


async def test_djini_rss_fetch_parses_items_and_skips_broken(
    mock_http_client: Callable[..., httpx.AsyncClient],
) -> None:
    async with mock_http_client(text=FIXTURE_XML) as client:
        vacancies = await DjiniRssSource(client=client).fetch()

    assert len(vacancies) == 3

    first = vacancies[0]
    assert first.source == "djini_rss"
    assert first.external_id == "858641"
    assert first.canonical_url == "https://djinni.co/jobs/858641-junior-ai-automation-engineer"
    assert first.title == "Junior AI Automation Engineer (Python, Claude Code)"
    assert first.company == "Нексус-Буд"
    assert first.salary_raw == "$700–1100"
    assert first.location_or_remote == "On-site (Києві)"
    assert first.partial_data is False
    assert first.dedup_hash == build_dedup_hash(first.title, "Нексус-Буд")

    second = vacancies[1]
    assert second.external_id == "858605"
    assert second.company == "NovaBridge"
    assert second.salary_raw is None
    assert second.location_or_remote == "Remote"
    assert second.dedup_hash == build_dedup_hash(second.title, "NovaBridge")

    third = vacancies[2]
    assert third.external_id == "858577"
    assert third.company == "ApexLabs"
    assert third.location_or_remote == "Hybrid"


async def test_djini_rss_fetch_empty_response(
    mock_http_client: Callable[..., httpx.AsyncClient],
) -> None:
    async with mock_http_client(text="") as client:
        vacancies = await DjiniRssSource(client=client).fetch()

    assert vacancies == []


async def test_djini_rss_fetch_unknown_company_uses_description_for_dedup(
    mock_http_client: Callable[..., httpx.AsyncClient],
) -> None:
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0"><channel><item>
      <title>Python Developer</title>
      <link>https://djinni.co/jobs/999002-python-developer/</link>
      <description>
        &lt;p&gt;We are building a fintech API with FastAPI and PostgreSQL.&lt;/p&gt;
      </description>
    </item></channel></rss>
    """
    async with mock_http_client(text=xml) as client:
        vacancies = await DjiniRssSource(client=client).fetch()

    assert len(vacancies) == 1
    vac = vacancies[0]
    assert vac.company == "Unknown"
    assert vac.dedup_hash == build_dedup_hash("Python Developer", vac.description_raw[:500])
