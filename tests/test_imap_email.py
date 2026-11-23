import imaplib
from collections.abc import Callable
from types import TracebackType

import pytest
from uuid6 import uuid7

from job_hunter.sources.imap_email import ImapEmailSource
from tests.factories.email_factory import (
    ALLOWED_TEST_EMAILS,
    linkedin_digest_eml,
    work_ua_digest_eml,
)


class _FakeImapClient:
    def __init__(self, messages: dict[bytes, bytes]) -> None:
        self._messages = messages
        self.logged_in: tuple[str, str] | None = None
        self.selected_mailbox: str | None = None
        self.uid_calls: list[tuple[str, ...]] = []

    def __enter__(self) -> "_FakeImapClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        return None

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
        self.logged_in = (user, password)
        return "OK", [b"Logged in"]

    def select(self, mailbox: str) -> tuple[str, list[bytes]]:
        self.selected_mailbox = mailbox
        return "OK", [b"1"]

    def uid(self, command: str, *args: str) -> tuple[str, list[object]]:
        self.uid_calls.append((command, *args))
        if command == "search":
            if not self._messages:
                return "OK", [b""]
            return "OK", [b" ".join(self._messages.keys())]
        if command == "fetch":
            uid_bytes = args[0].encode("ascii")
            raw = self._messages.get(uid_bytes)
            if raw is None:
                return "NO", []
            return "OK", [(b"1 (BODY[] {100})", raw), b")"]
        if command == "store":
            return "OK", []
        return "BAD", []


def _imap_factory(client: _FakeImapClient) -> Callable[..., _FakeImapClient]:
    def _create(*args: object, **kwargs: object) -> _FakeImapClient:
        return client

    return _create


async def test_imap_source_skips_when_credentials_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    def _fail_if_called(*args: object, **kwargs: object) -> _FakeImapClient:
        calls.append(True)
        return _FakeImapClient({})

    monkeypatch.setattr(imaplib, "IMAP4_SSL", _fail_if_called)

    source = ImapEmailSource(
        allowed_emails=ALLOWED_TEST_EMAILS,
        host="imap.gmail.com",
        port=993,
        mailbox="INBOX",
        user=None,
        password=None,
    )
    assert source.source_name == "imap_email"
    assert await source.fetch() == []
    assert not calls


async def test_imap_source_fetches_parses_and_marks_seen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeImapClient(
        {
            b"101": linkedin_digest_eml(),
            b"102": work_ua_digest_eml(),
        }
    )
    monkeypatch.setattr(imaplib, "IMAP4_SSL", _imap_factory(fake_client))

    source = ImapEmailSource(
        allowed_emails=ALLOWED_TEST_EMAILS,
        host="imap.gmail.com",
        port=993,
        mailbox="INBOX",
        user="bot@example.com",
        password=uuid7().hex,
        mark_seen=True,
    )
    vacancies = await source.fetch()

    assert fake_client.logged_in is not None
    assert fake_client.logged_in[0] == "bot@example.com"
    assert fake_client.selected_mailbox == "INBOX"
    assert ("search", "UNSEEN") in fake_client.uid_calls
    assert ("fetch", "101", "(BODY.PEEK[])") in fake_client.uid_calls
    assert ("fetch", "102", "(BODY.PEEK[])") in fake_client.uid_calls
    assert ("store", "101", "+FLAGS", r"(\Seen)") in fake_client.uid_calls
    assert ("store", "102", "+FLAGS", r"(\Seen)") in fake_client.uid_calls

    assert len(vacancies) == 3
    assert {v.source for v in vacancies} == {"linkedin_email", "work_ua_email"}


async def test_imap_source_respects_mark_seen_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeImapClient({b"101": work_ua_digest_eml()})
    monkeypatch.setattr(imaplib, "IMAP4_SSL", _imap_factory(fake_client))

    source = ImapEmailSource(
        allowed_emails=ALLOWED_TEST_EMAILS,
        host="imap.gmail.com",
        port=993,
        mailbox="INBOX",
        user="bot@example.com",
        password=uuid7().hex,
        mark_seen=False,
    )
    vacancies = await source.fetch()

    assert len(vacancies) == 1
    assert not any(call[0] == "store" for call in fake_client.uid_calls)


async def test_imap_source_returns_empty_when_no_unseen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeImapClient({})
    monkeypatch.setattr(imaplib, "IMAP4_SSL", _imap_factory(fake_client))

    source = ImapEmailSource(
        allowed_emails=ALLOWED_TEST_EMAILS,
        host="imap.gmail.com",
        port=993,
        mailbox="INBOX",
        user="bot@example.com",
        password=uuid7().hex,
    )
    assert await source.fetch() == []
    assert fake_client.uid_calls == [("search", "UNSEEN")]
