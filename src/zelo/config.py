from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração local; credenciais nunca recebem valores padrão reais."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ZELO_",
        extra="ignore",
    )

    data_dir: Path = Path("data")
    model_dir: Path = Path("models")
    # Calendário de feriados do corte de publicação; vazio usa configs/ do repositório.
    calendar_path: Path | None = None


settings = Settings()
