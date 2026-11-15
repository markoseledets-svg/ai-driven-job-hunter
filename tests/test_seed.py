from job_hunter.db.enums import VacancyStatus
from job_hunter.db.seed import DEFAULT_SEED_PATH, build_dedup_hash, load_seed_payload


def test_seed_fixture_is_valid() -> None:
    payload = load_seed_payload(DEFAULT_SEED_PATH)

    assert len(payload.calibration_examples) >= 6
    scores = [item.expected_score for item in payload.calibration_examples]
    assert min(scores) < 30
    assert max(scores) >= 85

    statuses = {vac.status for vac in payload.vacancies}
    assert VacancyStatus.NEW in statuses
    assert VacancyStatus.SCORED in statuses
    assert VacancyStatus.NOTIFIED in statuses


def test_build_dedup_hash_is_case_and_whitespace_insensitive() -> None:
    first = build_dedup_hash("  Junior Python Dev ", " Northstar Cloud ")
    second = build_dedup_hash("junior python dev", "northstar cloud")
    assert first == second
    assert len(first) == 64
