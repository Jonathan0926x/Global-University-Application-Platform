import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "Global University Application Platform API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://jonathangermain@localhost:5432/uniglobe"
    )
    
    # Auth configuration
    AUTH_PROVIDER: str = os.getenv("AUTH_PROVIDER", "mock") # "clerk" or "mock"
    CLERK_SECRET_KEY: Optional[str] = os.getenv("CLERK_SECRET_KEY", None)
    CLERK_PUBLISHABLE_KEY: Optional[str] = os.getenv("CLERK_PUBLISHABLE_KEY", None)
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)



settings = Settings()
