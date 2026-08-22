from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://todoscare:todoscare@localhost:5432/todoscare"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    cors_origins: str = "http://localhost:5173"

    # IA clínica (72.4): si hay API key, el conector lee el contenido real del
    # documento con un modelo Claude; si está vacío, usa el heurístico.
    anthropic_api_key: str = ""
    ia_model: str = "claude-haiku-4-5-20251001"
    ia_base_url: str = "https://api.anthropic.com"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
