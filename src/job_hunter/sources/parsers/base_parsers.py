import re

_SALARY_PATTERN = re.compile(
    r"(?:(?:від|до|from|to|up to)\s+)?"
    r"(?:(?:[$€₴]|грн\.?|uah|usd|eur)\s*\d+(?:[\s.,]\d+)*\s*[kк]?"
    r"(?:\s*[-–—]\s*(?:[$€₴]|грн\.?|uah|usd|eur)?\s*\d+(?:[\s.,]\d+)*\s*[kк]?)?"
    r"|\d+(?:[\s.,]\d+)*\s*[kк]?"
    r"(?:\s*(?:[$€₴]|грн\.?|uah|usd|eur)?\s*[-–—]\s*\d+(?:[\s.,]\d+)*\s*[kк]?)?"
    r"\s*(?:[$€₴]|грн\.?|uah|usd|eur))"
    r"(?=\s|$|[.,;!?)])",
    flags=re.IGNORECASE,
)


def get_salary_from_str(text: str) -> str | None:
    match = _SALARY_PATTERN.search(text)
    return match.group(0).strip() if match else None


def extract_external_id_from_url(url: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(url)
    return match.group(1) if match else None
