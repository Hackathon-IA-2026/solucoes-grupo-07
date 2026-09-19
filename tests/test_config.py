from pathlib import Path

from curtamap.config import Settings


def test_default_paths_are_local() -> None:
    settings = Settings(_env_file=None)

    assert settings.data_dir == Path("data")
    assert settings.model_dir == Path("models")
