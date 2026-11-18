from enum import StrEnum


class VacancyStatus(StrEnum):
    NEW = "NEW"
    PREFILTERED = "PREFILTERED"
    SCORED = "SCORED"
    NOTIFIED = "NOTIFIED"
    SKIPPED = "SKIPPED"
    APPLIED = "APPLIED"
