from job_hunter.sources.normalizer import build_dedup_hash
from job_hunter.sources.parsers.email_parsers import parse_email
from tests.factories.email_factory import (
    ALLOWED_TEST_EMAILS,
    build_eml,
    linkedin_digest_eml,
    robota_ua_batch_eml,
    robota_ua_solo_eml,
    work_ua_digest_eml,
    work_ua_instant_eml,
)


def test_parse_email_linkedin_digest() -> None:
    vacancies = parse_email(linkedin_digest_eml(), ALLOWED_TEST_EMAILS)

    assert len(vacancies) == 2
    first = vacancies[0]
    assert first.source == "linkedin_email"
    assert first.external_id == "4432476345"
    assert first.canonical_url == "https://www.linkedin.com/jobs/view/4432476345"
    assert first.title == "Back End Developer"
    assert first.company == "Acme Corp"
    assert first.location_or_remote == "EMEA (Віддалена робота)"
    assert first.partial_data is True
    assert first.dedup_hash == build_dedup_hash("Back End Developer", "Acme Corp")

    second = vacancies[1]
    assert second.external_id == "4343363446"
    assert second.company == "CloudLab"
    assert second.location_or_remote == "Lviv (Робота в офісі)"


def test_parse_email_work_ua_digest() -> None:
    vacancies = parse_email(work_ua_digest_eml(), ALLOWED_TEST_EMAILS)

    assert len(vacancies) == 1
    vac = vacancies[0]
    assert vac.source == "work_ua_email"
    assert vac.external_id == "8673772"
    assert vac.canonical_url == "https://www.work.ua/jobs/8673772"
    assert vac.title == "Python developer"
    assert vac.company == "FinTech Corp"
    assert vac.location_or_remote == "Дистанційно"
    assert vac.partial_data is True
    assert vac.dedup_hash == build_dedup_hash("Python developer", "FinTech Corp")


def test_parse_email_work_ua_instant_full_description() -> None:
    vacancies = parse_email(work_ua_instant_eml(), ALLOWED_TEST_EMAILS)

    assert len(vacancies) == 1
    vac = vacancies[0]
    assert vac.source == "work_ua_email"
    assert vac.external_id == "8248191"
    assert vac.title == "Junior Python Dev"
    assert vac.company == "NovaSoft"
    assert vac.salary_raw == "40 000 – 55 000 грн"
    assert vac.location_or_remote == "Львів"
    assert vac.partial_data is False
    assert "FastAPI services" in vac.description_raw


def test_parse_email_robota_ua_batch() -> None:
    vacancies = parse_email(robota_ua_batch_eml(), ALLOWED_TEST_EMAILS)

    assert len(vacancies) == 2
    first = vacancies[0]
    assert first.source == "robota_ua_email"
    assert first.external_id == "11412291"
    assert first.canonical_url == "https://robota.ua/company1006322/vacancy11412291"
    assert first.title == "Junior AI Developer"
    assert first.company == "Farmak"
    assert first.salary_raw is None
    assert first.location_or_remote == "Київ"
    assert first.partial_data is True

    second = vacancies[1]
    assert second.external_id == "11383538"
    assert second.company == "TechLab"
    assert second.salary_raw == "75 000 грн"
    assert second.location_or_remote == "Київ"


def test_parse_email_robota_ua_solo_full_description() -> None:
    vacancies = parse_email(robota_ua_solo_eml(), ALLOWED_TEST_EMAILS)

    assert len(vacancies) == 1
    vac = vacancies[0]
    assert vac.source == "robota_ua_email"
    assert vac.external_id == "11393199"
    assert vac.title == "AI Engineer"
    assert vac.company == "NovaPay"
    assert vac.location_or_remote == "Віддалена робота, Київ"
    assert vac.salary_raw == "$2000"
    assert vac.partial_data is False
    assert "Python LLM agents" in vac.description_raw


def test_parse_email_filters_empty_disallowed_unknown_and_no_html() -> None:
    assert parse_email(b"", ALLOWED_TEST_EMAILS) == []

    disallowed = build_eml("spam@linkedin.com", "<html><body>Hi</body></html>")
    assert parse_email(disallowed, ALLOWED_TEST_EMAILS) == []

    unknown_domain = build_eml("alerts@unknown.example", "<html><body>Hi</body></html>")
    assert parse_email(unknown_domain, frozenset({"alerts@unknown.example"})) == []

    plain_only = build_eml("jobalerts-noreply@linkedin.com", html=None)
    assert parse_email(plain_only, ALLOWED_TEST_EMAILS) == []
