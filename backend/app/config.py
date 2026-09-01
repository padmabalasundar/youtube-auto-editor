"""Application settings loaded from environment variables / .env file."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration.

    Local single-user MVP: no auth-related settings (no JWT/OAuth).
    """

    APP_NAME: str = "YouTube Auto Editor"
    DATABASE_URL: str = "sqlite:///./app.db"
    SECRET_KEY: str = "dev-secret-key"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]
    OUTPUT_DIR: str = "./output"
    MAX_VIDEO_DURATION_SECONDS: int = 1800

    class Config:
        env_file = ".env"
        # .env also carries VITE_API_URL for the frontend's convenience (see
        # .env.example) - ignore vars the backend doesn't define rather than
        # forbidding them (pydantic-settings v2 defaults to "forbid").
        extra = "ignore"


settings = Settings()
