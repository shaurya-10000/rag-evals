from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # REMOVED the default localhost fallback for DATABASE_URL.
    # Pydantic will now throw a clear error if the env var is missing.
    DATABASE_URL: str
    GEMINI_API_KEY: str = "fake-key"
    RAG_API_KEY: str = "dev-secret-key-change-in-production"
    JWT_SECRET: str = "dev-jwt-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60 * 24 * 7  # 7 days

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


# --- TEMP DEBUG: remove after diagnosing ---
try:
    import os
    from urllib.parse import urlparse

    _url = str(settings.DATABASE_URL)
    _parsed = urlparse(_url.replace("+psycopg", ""))
    print(
        f"[startup-debug] host={_parsed.hostname} port={_parsed.port} "
        f"first30={_url[:30]!r} "
        f"in_os_environ={'DATABASE_URL' in os.environ}",
        flush=True,
    )
except Exception as _e:
    print(f"[startup-debug] failed: {_e!r}", flush=True)
# --- END TEMP DEBUG ---
