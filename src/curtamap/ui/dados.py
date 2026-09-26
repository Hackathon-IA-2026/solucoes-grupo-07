"""Leitura em cache para a interface: histórico, previsão e recomendações.

Nenhuma regra de negócio mora aqui. O preditor vem de `product_predictor()`, que escolhe o
modelo mais recente em `models/previsao/` ou, sem artefato, o baseline provisório; a
interface não sabe qual dos dois gerou a previsão.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl
import streamlit as st

from curtamap.config import settings
from curtamap.contracts import RESERVED_TEST_START, TIMEZONE
from curtamap.data_contract import SPECS
from curtamap.forecasting import known_entities, load_history, nightly_cutoff
from curtamap.painel.exemplo import example_recommendations
from curtamap.previsao.produto import HISTORY_DAYS, latest_model_path, product_predictor

SOURCE_FILES = {source: SPECS[source].filename for source in ("eolica", "fotovoltaica")}


def raw_paths() -> dict[str, Path]:
    return {source: settings.data_dir / "raw" / name for source, name in SOURCE_FILES.items()}


def missing_files() -> list[Path]:
    return [path for path in raw_paths().values() if not path.exists()]


def now_brasilia() -> datetime:
    """Instante atual no fuso do contrato, sem fuso, como os demais timestamps."""
    return datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None)


@st.cache_data(show_spinner=False)
def data_range() -> tuple[datetime, datetime]:
    """Primeiro e último `din_instante` locais antes do teste reservado."""
    frames = [
        pl.scan_parquet(path)
        .select(pl.col("din_instante").cast(pl.Datetime("us")))
        .filter(pl.col("din_instante") < RESERVED_TEST_START)
        for path in raw_paths().values()
    ]
    moments = pl.concat(frames).select(
        first=pl.col("din_instante").min(), last=pl.col("din_instante").max()
    )
    first, last = moments.collect().row(0)
    return first, last


@dataclass(frozen=True)
class ForecastBundle:
    forecast: pl.DataFrame
    entities: pl.DataFrame
    history_start: datetime
    data_cutoff: datetime
    model_path: str | None


def _model_key() -> str | None:
    path = latest_model_path()
    return str(path) if path else None


@st.cache_data(show_spinner="Gerando a previsão das próximas 24 h…", max_entries=16)
def _forecast(t0: datetime, model_key: str | None) -> ForecastBundle:
    cutoff = nightly_cutoff(t0)
    start = cutoff - timedelta(days=HISTORY_DAYS)
    history = load_history(settings.data_dir, start, cutoff)
    predictor = product_predictor()
    # `generated_at` explícito: o contrato usa horário de Brasília sem fuso, e o servidor
    # (container na AWS) roda em UTC.
    forecast = predictor.predict(history, t0, cutoff, generated_at=now_brasilia())
    return ForecastBundle(forecast, known_entities(history, cutoff), start, cutoff, model_key)


def forecast_for(t0: datetime) -> ForecastBundle:
    # O caminho do modelo entra na chave: um artefato novo invalida o cache.
    return _forecast(t0, _model_key())


@dataclass(frozen=True)
class Recommendations:
    frame: pl.DataFrame
    is_example: bool


def recommendations_for(t0: datetime) -> Recommendations:
    """Até a Etapa 3 chegar ao `main`, só existe o exemplo simulado.

    Quando chegar, basta trocar por `build_recommendations(forecast)`: o formato é o mesmo.
    """
    return Recommendations(example_recommendations(t0), is_example=True)


@st.cache_data(show_spinner="Lendo o histórico observado…", max_entries=8)
def observed_history(start: datetime, end: datetime) -> pl.DataFrame:
    return load_history(settings.data_dir, start, end)
