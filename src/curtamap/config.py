from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração local; credenciais nunca recebem valores padrão reais."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CURTAMAP_",
        extra="ignore",
    )

    data_dir: Path = Path("data")
    model_dir: Path = Path("models")


settings = Settings()
