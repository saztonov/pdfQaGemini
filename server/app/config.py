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

    All other settings (Gemini API, R2, defaults) are in Supabase qa_app_settings table.
    """

    # Supabase - required to connect and load other settings
    supabase_url: str = ""
    supabase_key: str = ""

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
