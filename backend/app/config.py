from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "MERIDIAN Auction RFQ"
    DATABASE_URL: str = "postgresql://meridian:meridian_secret@127.0.0.1:5432/meridian_db"
    JWT_SECRET: str = "meridian_secret_super_key_jwt_auth_production_grade_token_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost:80,http://localhost"
    ECHO_SQL: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

