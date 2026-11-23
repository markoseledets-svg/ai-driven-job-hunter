from collections.abc import Callable

from job_hunter.core.schemas import PrefilterConfig
from job_hunter.schemas.vacancy_schemas import RawVacancy
from job_hunter.services.prefilter import Prefilter


def test_excluded_companies_case_insensitive(
    make_raw_vacancy: Callable[..., RawVacancy],
) -> None:
    prefilter = Prefilter(PrefilterConfig(excluded_companies=["Bad Corp"]))
    result = prefilter.check(make_raw_vacancy(title="Python Developer", company="  bad corp "))
    assert not result.passed
    assert result.reason == "Excluded company:   bad corp "


def test_excluded_title_keywords_respects_word_boundaries(
    make_raw_vacancy: Callable[..., RawVacancy],
) -> None:
    prefilter = Prefilter(PrefilterConfig(excluded_title_keywords=["java", "go", "c++", "senior"]))

    assert prefilter.check(
        make_raw_vacancy(title="JavaScript / Django Developer", company="Acme Corp")
    ).passed
    assert prefilter.check(
        make_raw_vacancy(title="Good Python Engineer", company="Acme Corp")
    ).passed

    java_res = prefilter.check(make_raw_vacancy(title="Java Backend Engineer", company="Acme Corp"))
    assert not java_res.passed
    assert java_res.reason == "Excluded title keyword: java"

    cpp_res = prefilter.check(make_raw_vacancy(title="Middle C++ Developer", company="Acme Corp"))
    assert not cpp_res.passed
    assert cpp_res.reason == "Excluded title keyword: c++"


def test_excluded_description_keywords_respects_word_boundaries(
    make_raw_vacancy: Callable[..., RawVacancy],
) -> None:
    prefilter = Prefilter(PrefilterConfig(excluded_description_keywords=["php", "go"]))

    assert prefilter.check(
        make_raw_vacancy(
            title="Python Developer",
            company="Acme Corp",
            description_raw="We build Django services with good tests.",
        )
    ).passed

    php_res = prefilter.check(
        make_raw_vacancy(
            title="Python Developer",
            company="Acme Corp",
            description_raw="Stack: Python, PHP, MySQL",
        )
    )
    assert not php_res.passed
    assert php_res.reason == "Excluded description keyword: php"


def test_required_any_keywords_and_partial_data_handling(
    make_raw_vacancy: Callable[..., RawVacancy],
) -> None:
    prefilter = Prefilter(PrefilterConfig(required_any_keywords=["python", "fastapi"]))

    assert prefilter.check(
        make_raw_vacancy(
            title="Backend Engineer",
            company="Acme Corp",
            description_raw="Work with FastAPI daily.",
        )
    ).passed
    assert prefilter.check(
        make_raw_vacancy(
            title="Python Developer",
            company="Acme Corp",
            description_raw="No stack details.",
        )
    ).passed

    missing_res = prefilter.check(
        make_raw_vacancy(
            title="Backend Engineer",
            company="Acme Corp",
            description_raw="Work with Node.js daily.",
        )
    )
    assert not missing_res.passed
    assert missing_res.reason == "Missing required keywords"

    partial_res = prefilter.check(
        make_raw_vacancy(
            title="Back End Developer",
            company="Acme Corp",
            description_raw="",
            partial_data=True,
        )
    )
    assert partial_res.passed

    empty_required = Prefilter(PrefilterConfig(required_any_keywords=[]))
    assert empty_required.check(
        make_raw_vacancy(
            title="Any Role",
            company="Acme Corp",
            description_raw="No keywords needed.",
        )
    ).passed


def test_allowed_languages_heuristics(
    make_raw_vacancy: Callable[..., RawVacancy],
) -> None:
    default_pf = Prefilter(PrefilterConfig(allowed_languages=["en", "uk"]))
    assert default_pf.check(
        make_raw_vacancy(
            title="Python Developer",
            company="Acme Corp",
            description_raw="Шукаємо інженера у Києві.",
        )
    ).passed

    ru_res = default_pf.check(
        make_raw_vacancy(
            title="Python разработчик",
            company="Acme Corp",
            description_raw="Опыт работы от 2 лет.",
        )
    )
    assert not ru_res.passed
    assert ru_res.reason == "Language not allowed: ru"

    en_only = Prefilter(PrefilterConfig(allowed_languages=["en"]))
    assert en_only.check(
        make_raw_vacancy(
            title="Python Developer",
            company="Acme Corp",
            description_raw="FastAPI and PostgreSQL backend.",
        )
    ).passed
    uk_res = en_only.check(
        make_raw_vacancy(
            title="Python інженер",
            company="Acme Corp",
            description_raw="Робота в Києві.",
        )
    )
    assert not uk_res.passed
    assert uk_res.reason == "Language not allowed: uk"

    uk_only = Prefilter(PrefilterConfig(allowed_languages=["uk"]))
    en_res = uk_only.check(
        make_raw_vacancy(
            title="Python Engineer",
            company="Acme Corp",
            description_raw="Remote backend role.",
        )
    )
    assert not en_res.passed
    assert en_res.reason == "Language not allowed: en"


def test_rule_order_precedence(
    make_raw_vacancy: Callable[..., RawVacancy],
) -> None:
    prefilter = Prefilter(
        PrefilterConfig(
            excluded_companies=["Evil Inc"],
            excluded_title_keywords=["senior"],
            excluded_description_keywords=["1c"],
        )
    )
    res = prefilter.check(
        make_raw_vacancy(
            company="Evil Inc",
            title="Senior Developer",
            description_raw="1C integration",
        )
    )
    assert not res.passed
    assert res.reason == "Excluded company: Evil Inc"
