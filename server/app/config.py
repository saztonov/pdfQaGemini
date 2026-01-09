"""Server configuration - infrastructure settings only

Application settings (Gemini API key, R2 credentials, etc.) are stored in Supabase
and loaded dynamically via app_settings module.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Infrastructure settings loaded from environment variables.

    Only contains settings needed to connect to infrastructure:
    - Supabase (to load app settings and store data)
    - Redis (for job queue)
    - Basic server settings (host, port)
    - Master encryption key for sensitive data

    All other settings (Gemini API, R2, defaults) are in Supabase qa_app_settings table.
    Sensitive values (API keys) are stored encrypted using APP_SECRET_KEY.
    """

    # Supabase - required to connect and load other settings
    supabase_url: str = ""
    supabase_key: str = ""

    # Master encryption key for sensitive settings (32 bytes, base64 encoded)
    # Generate with: python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
    app_secret_key: str = ""

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # Redis - local infrastructure
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    @property
    def redis_dsn(self) -> str:
        """Build Redis DSN"""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
