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


settings = Settings()
