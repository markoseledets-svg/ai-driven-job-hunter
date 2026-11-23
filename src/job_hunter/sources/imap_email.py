import asyncio
import imaplib
import logging

from job_hunter.schemas.vacancy_schemas import RawVacancy
from job_hunter.sources.base import BaseJobSource
from job_hunter.sources.parsers.email_parsers import parse_email

logger = logging.getLogger(__name__)


class ImapEmailSource(BaseJobSource):
    def __init__(
        self,
        allowed_emails: frozenset[str],
        host: str,
        port: int,
        mailbox: str,
        user: str | None = None,
        password: str | None = None,
        mark_seen: bool = True,
        timeout: float = 15.0,
    ):
        self._allowed_emails = allowed_emails
        self._host = host
        self._port = port
        self._mailbox = mailbox
        self._user = user
        self._password = password
        self._mark_seen = mark_seen
        self._timeout = timeout

    @property
    def source_name(self) -> str:
        return "imap_email"

    def _fetch_unseen_sync(self, user: str, password: str) -> list[bytes]:
        mails: list[bytes] = []
        with imaplib.IMAP4_SSL(self._host, self._port, timeout=self._timeout) as client:
            client.login(user, password)
            client.select(self._mailbox)
            status, data = client.uid("search", "UNSEEN")

            if status != "OK" or not data or not data[0]:
                return []

            unread_uids = data[0].split()
            for uid in unread_uids:
                uid_str = uid.decode("ascii")
                status, msg_data = client.uid("fetch", uid_str, "(BODY.PEEK[])")

                if (
                    status != "OK"
                    or not msg_data
                    or not isinstance(msg_data[0], tuple)
                    or not isinstance(msg_data[0][1], bytes)
                ):
                    logger.debug(
                        "Skipping malformed IMAP message uid=%s status=%s", uid_str, status
                    )
                    continue

                mails.append(msg_data[0][1])
                if self._mark_seen:
                    client.uid("store", uid_str, "+FLAGS", r"(\Seen)")
            return mails

    async def fetch(self) -> list[RawVacancy]:
        vacancies: list[RawVacancy] = []
        if not self._user or not self._password:
            logger.warning("IMAP auth config missing; skipping %s", self.source_name)
            return []
        raw_messages = await asyncio.to_thread(self._fetch_unseen_sync, self._user, self._password)
        for msg_bytes in raw_messages:
            vacancies_list = parse_email(msg_bytes, self._allowed_emails)
            vacancies.extend(vacancies_list)
        logger.info(
            "Fetched %d vacancies from %d unread emails (%s)",
            len(vacancies),
            len(raw_messages),
            self.source_name,
        )
        return vacancies
