"""Server configuration"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # Gemini
    gemini_api_key: str = ""

    # R2 Storage
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_url: str = ""

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # Worker
    worker_max_jobs: int = 10
    worker_job_timeout: int = 300
    worker_max_retries: int = 3

    # Default model
    default_model: str = "gemini-3-flash-preview"

    @property
    def redis_dsn(self) -> str:
        """Build Redis DSN"""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def r2_endpoint(self) -> str:
        """Build R2 endpoint from account_id"""
        if self.r2_account_id:
            return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"
        return ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
