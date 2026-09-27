"""Leitura em cache dos avisos já emitidos. Nenhuma regra de negócio mora aqui."""

from datetime import date, datetime, time
from pathlib import Path

import polars as pl
import streamlit as st

from zelo.previsao.avisos import ARCHIVE

# Só para testes: aponta o painel para outro arquivo de avisos.
ARCHIVE_OVERRIDE: Path | None = None


def _caminho() -> Path:
    return ARCHIVE_OVERRIDE or ARCHIVE


def arquivo_ausente() -> bool:
    return not _caminho().exists()


@st.cache_data(show_spinner="Carregando os avisos emitidos…")
def _carregar(path: str, modificado: float) -> pl.DataFrame:
    return pl.read_parquet(path)


def avisos() -> pl.DataFrame:
    # A data de modificação entra na chave: um arquivo regenerado invalida o cache.
    caminho = _caminho()
    return _carregar(str(caminho), caminho.stat().st_mtime)


def dias(arquivo: pl.DataFrame) -> list[date]:
    return sorted(d.date() for d in arquivo["t0"].unique())


def aviso_do_dia(arquivo: pl.DataFrame, dia: date) -> pl.DataFrame:
    return arquivo.filter(pl.col("t0") == datetime.combine(dia, time()))
