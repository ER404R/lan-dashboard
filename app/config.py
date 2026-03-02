from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SECRET_KEY: str = "change-me-in-production"
    DATABASE_URL: str = "sqlite:///./lan_dashboard.db"
    REGISTRATION_ENABLED: bool = True
    SEED_INVITE_TOKENS: str = ""
    ADMIN_INVITE_TOKEN: str = ""

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
