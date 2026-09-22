from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ExperimentalSettings(BaseSettings):
    """Caminhos locais do experimento, sempre substituíveis por variáveis de ambiente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CURTAMAP_",
        extra="ignore",
    )

    data_dir: Path = Path("data")
    model_dir: Path = Path("models")
    experiment_dir: Path = Path("experiments")
    cache_dir: Path = Path(".cache/curtamap")
    temp_dir: Path = Path("tmp/curtamap")

    seed: int = 42
    threads: int = 6
    duckdb_memory_limit: str = "22GB"

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.model_dir,
            self.experiment_dir,
            self.cache_dir,
            self.temp_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
