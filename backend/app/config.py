"""Application configuration.

DATABASE_URL supports PostgreSQL in production and SQLite (default, used by tests).
"""
import os


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./watergrid.db",
    )
    # Auto-seed demo network on startup when the database is empty
    SEED_ON_STARTUP: bool = os.getenv("SEED_ON_STARTUP", "true").lower() == "true"
    CORS_ORIGINS: list[str] = ["*"]


settings = Settings()
