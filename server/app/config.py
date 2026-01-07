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
    r2_public_base_url: str = ""
    r2_endpoint: str = ""
    r2_bucket: str = ""
    r2_access_key: str = ""
    r2_secret_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Job processing
    job_poll_interval: float = 1.0
    job_max_retries: int = 3

    # Default model
    default_model: str = "gemini-2.0-flash"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
