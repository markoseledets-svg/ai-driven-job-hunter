from collections.abc import Callable
from pathlib import Path

import httpx

from job_hunter.sources.dou_rss import DouRssSource
from job_hunter.sources.normalizer import build_dedup_hash

FIXTURE_XML = (Path(__file__).parent / "dou_rss.xml").read_text(encoding="utf-8")


async def test_dou_rss_fetch_parses_valid_items_and_skips_broken(
    mock_http_client: Callable[..., httpx.AsyncClient],
) -> None:
    async with mock_http_client(text=FIXTURE_XML) as client:
        source = DouRssSource(client=client)
        vacancies = await source.fetch()

    assert len(vacancies) == 2

    first = vacancies[0]
    assert first.source == "dou_rss"
    assert first.external_id == "900123"
    assert first.canonical_url == "https://jobs.dou.ua/companies/findata-solutions/vacancies/900123"
    assert first.title == "Junior Data Engineer (Python, SQL, C#, Azure)"
    assert first.company == "FinData Solutions"
    assert first.salary_raw == "$1300–1900"
    assert first.location_or_remote == "віддалено"
    assert first.partial_data is False
    assert first.dedup_hash == build_dedup_hash(first.title, "FinData Solutions")
    assert "<p>" not in first.description_raw
    assert "Python ETL pipelines" in first.description_raw

    second = vacancies[1]
    assert second.external_id == "900124"
    assert second.canonical_url == "https://jobs.dou.ua/companies/cloudforge/vacancies/900124"
    assert second.company == "CloudForge"
    assert second.salary_raw is None
    assert second.location_or_remote == "Poland (remote), Ukraine (remote), Львів"
    assert "alert" not in second.description_raw


async def test_dou_rss_fetch_empty_response(
    mock_http_client: Callable[..., httpx.AsyncClient],
) -> None:
    async with mock_http_client(text="") as client:
        vacancies = await DouRssSource(client=client).fetch()

    assert vacancies == []


async def test_dou_rss_fetch_unknown_company_uses_description_for_dedup(
    mock_http_client: Callable[..., httpx.AsyncClient],
) -> None:
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0"><channel><item>
      <title>Junior Backend</title>
      <link>https://jobs.dou.ua/companies/anon/vacancies/999001/</link>
      <description>&lt;p&gt;Unique description for backend role.&lt;/p&gt;</description>
    </item></channel></rss>
    """
    async with mock_http_client(text=xml) as client:
        vacancies = await DouRssSource(client=client).fetch()

    assert len(vacancies) == 1
    vac = vacancies[0]
    assert vac.company == "Unknown"
    assert vac.dedup_hash == build_dedup_hash("Junior Backend", vac.description_raw[:500])
