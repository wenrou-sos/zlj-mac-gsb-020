from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://water:water@localhost:5432/watergrid"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    seed_on_startup: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_prefix="WATER_")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
