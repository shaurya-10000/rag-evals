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
import os as _os
from urllib.parse import urlparse as _urlparse
try:
    _u = _urlparse(str(settings.DATABASE_URL).replace("+psycopg", ""))
    print(
        f"[startup-debug] settings.DATABASE_URL -> scheme={settings.DATABASE_URL.split('://')[0]} "
        f"host={_u.hostname} port={_u.port} db={_u.path} | "
        f"first30={str(settings.DATABASE_URL)[:30]!r} | "
        f"DATABASE_URL in os.environ={'DATABASE_URL' in _os.environ}",
        flush=True,
    )
except Exception as _e:
    print(f"[startup-debug] failed: {_e!r}", flush=True)
# --- END TEMP DEBUG ---
