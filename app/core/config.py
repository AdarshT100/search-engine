# Application settings loaded from environment variables via pydantic BaseSettings.
"""
app/core/config.py
Central configuration — reads from .env automatically via pydantic-settings.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
 
 
class Settings(BaseSettings):
    # PostgreSQL
    DATABASE_URL: str 
 
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
 
    # JWT (also read directly by auth_service via os.environ)
    SECRET_KEY: str 
 
    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET_NAME: str = ""
    AWS_REGION: str = "ap-south-1"
 
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173"
 
    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]
 
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
 
 
@lru_cache
def get_settings() -> Settings:
    return Settings()
