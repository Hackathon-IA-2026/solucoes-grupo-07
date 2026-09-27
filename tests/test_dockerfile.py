"""Contrato estático da imagem: sem Docker disponível, garante o essencial do deploy."""

from pathlib import Path

ROOT = Path(__file__).parents[1]
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
IGNORED = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
MODELO = "models/previsao/diario_ocorrencia_v1_2026-08-30.joblib"
AVISOS = "data/processed/avisos.parquet"


def test_image_serves_streamlit_on_8501_with_health_check() -> None:
    assert "EXPOSE 8501" in DOCKERFILE
    assert "/_stcore/health" in DOCKERFILE
    assert "--server.port=8501" in DOCKERFILE
    assert "--server.address=0.0.0.0" in DOCKERFILE
    assert "FROM python:3.12" in DOCKERFILE


def test_only_the_served_model_and_the_notices_enter_the_image() -> None:
    assert {"data/*", "models/*", ".env"} <= set(IGNORED)
    assert f"!{MODELO}" in IGNORED and f"!{AVISOS}" in IGNORED
    assert MODELO in DOCKERFILE and AVISOS in DOCKERFILE
    assert "data/raw" not in DOCKERFILE
    # Os arquivos que a imagem copia existem no repositório.
    assert (ROOT / MODELO).exists() and (ROOT / AVISOS).exists()


def test_image_pins_the_lock_and_runs_the_daily_routine() -> None:
    assert "pip install --no-cache-dir -r requirements.txt" in DOCKERFILE
    assert "python -m zelo.previsao.ao_vivo --loop" in DOCKERFILE
    assert "COPY .streamlit/" in DOCKERFILE and "COPY configs/" in DOCKERFILE
    requisitos = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "scikit-learn==" in requisitos and "tzdata==" in requisitos
