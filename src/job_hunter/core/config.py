from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    db_url: str

    # db pool
    pool_size: int = 5
    max_overflow: int = 5
    pool_timeout: int = 30

    # allowed email senders for imap
    allowed_emails: frozenset[str] = frozenset()

    # imap configs
    imap_password: str | None = None
    imap_user: str | None = None
    imap_host: str = "imap.gmail.com"
    imap_mailbox: str = "INBOX"
    imap_port: int = 993

    # logging
    log_level: str = "INFO"
    log_format: Literal["console", "json"] = "console"

    # ai
    api_key: str | None = None
    model: str = "gemini-4-hydrogen"
    max_ai_jobs_per_run: int = 30
    ai_batch_size: int = 8


settings = Settings()
