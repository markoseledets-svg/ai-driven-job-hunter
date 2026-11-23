import email
import email.policy
from collections.abc import Callable
from email.utils import parseaddr

from bs4 import BeautifulSoup

from job_hunter.schemas.vacancy_schemas import RawVacancy
from job_hunter.sources.parsers.linkedin_parsers import parse_linked_in_mail
from job_hunter.sources.parsers.robotaua_parsers import parse_robota_ua_mail
from job_hunter.sources.parsers.workua_parsers import parse_work_ua_mail

_DOMAIN_PARSERS: dict[str, Callable[[BeautifulSoup], list[RawVacancy]]] = {
    "linkedin.com": parse_linked_in_mail,
    "work.ua": parse_work_ua_mail,
    "robota.ua": parse_robota_ua_mail,
    "rabota.ua": parse_robota_ua_mail,
}


def _resolve_parser(sender_email: str) -> Callable[[BeautifulSoup], list[RawVacancy]] | None:
    _, _, domain = sender_email.partition("@")
    for allowed_domain, parser in _DOMAIN_PARSERS.items():
        if domain == allowed_domain or domain.endswith(f".{allowed_domain}"):
            return parser
    return None


def parse_email(raw_bytes: bytes, allowed_emails: frozenset[str]) -> list[RawVacancy]:
    if not raw_bytes:
        return []
    msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)
    _, sender_email = parseaddr(msg.get("From", ""))
    sender_email = sender_email.strip().lower()
    if not sender_email or sender_email not in allowed_emails:
        return []

    parser = _resolve_parser(sender_email)
    if parser is None:
        return []

    html_part = msg.get_body(preferencelist=("html",))
    if not html_part:
        return []

    soup = BeautifulSoup(html_part.get_content(), "html.parser")
    return parser(soup)
