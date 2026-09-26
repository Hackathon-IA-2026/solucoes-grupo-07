"""Contrato estático da imagem: sem Docker disponível, garante o essencial do deploy."""

from pathlib import Path

ROOT = Path(__file__).parents[1]
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
IGNORED = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()


def test_image_serves_streamlit_on_8501_with_health_check() -> None:
    assert "EXPOSE 8501" in DOCKERFILE
    assert "/_stcore/health" in DOCKERFILE
    assert "--server.port=8501" in DOCKERFILE
    assert "--server.address=0.0.0.0" in DOCKERFILE
    assert "FROM python:3.12" in DOCKERFILE


def test_data_and_models_never_enter_the_image() -> None:
    assert {"data/", "models/", ".env"} <= set(IGNORED)
    copies = [line for line in DOCKERFILE.splitlines() if line.startswith("COPY ")]
    assert not [line for line in copies if " data" in line or " models" in line]


def test_startup_syncs_from_s3_and_uses_the_frozen_lock() -> None:
    assert "python -m curtamap.s3_sync" in DOCKERFILE
    assert "uv sync --frozen --no-dev --extra aws" in DOCKERFILE
    assert "COPY configs ./configs" in DOCKERFILE
