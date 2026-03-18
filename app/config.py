from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WEAK_KEY = "change-me-in-production"


class Settings(BaseSettings):
    SECRET_KEY: str = _WEAK_KEY
    DATABASE_URL: str = "sqlite:///./lan_dashboard.db"
    REGISTRATION_ENABLED: bool = True
    SEED_INVITE_TOKENS: str = ""
    ADMIN_INVITE_TOKEN: str = ""

    model_config = SettingsConfigDict(env_file=".env")

    @model_validator(mode="after")
    def reject_weak_secret_key(self) -> "Settings":
        if self.SECRET_KEY == _WEAK_KEY:
            raise RuntimeError(
                "Refusing to start: SECRET_KEY is still the default placeholder "
                f"'{_WEAK_KEY}'. Set a strong random SECRET_KEY in your .env file."
            )
        return self


settings = Settings()
