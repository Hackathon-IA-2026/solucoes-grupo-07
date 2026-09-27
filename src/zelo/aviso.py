"""Aviso diário de cortes: transforma a previsão por meia-hora no que a usina lê às 20h.

Entrada: previsão no `FORECAST_SCHEMA`, com a coluna extra `potencial_referencia_mwmed` (a
geração de referência média da usina no horário em 28 dias). Nada aqui usa volume, R$ ou
CO₂. Previsão nula nunca vira alerta nem hora livre.

- **Janela em alerta:** meias-horas consecutivas com `alerta`.
- **Hora livre:** meia-hora prevista, sem alerta e com potencial de geração.
- **Motivo:** a causa mais frequente na janela, tirada da regra do histórico da usina
  (participação nas ordens em 28 dias), e não de um modelo.
"""

import json
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path

import polars as pl

STATUS_ALERTA = "em alerta"
STATUS_SEM_ALERTA = "sem alerta"
STATUS_SEM_PREVISAO = "sem previsão"
CAUSA_MISTA = "MISTA"
_ORDEM_STATUS = {STATUS_ALERTA: 0, STATUS_SEM_ALERTA: 1, STATUS_SEM_PREVISAO: 2}
_KEY = ["fonte", "id_ons"]
_STEP = timedelta(minutes=30)
_DESEMPENHO = Path(__file__).parents[2] / "configs" / "desempenho_aviso.json"

# Tradução dos códigos do Caderno para quem opera a usina.
MOTIVOS = {
    "ENE": "sobra de energia no sistema",
    "CNF": "limite de segurança da rede",
    "REL": "indisponibilidade na rede externa",
    CAUSA_MISTA: "motivos variados",
}
ORIGENS = {"SIS": "origem sistêmica", "LOC": "origem local"}


def _corridas(forecast: pl.DataFrame, marca: pl.Expr) -> pl.DataFrame:
    """Blocos de meias-horas consecutivas em que `marca` é verdadeira, por usina."""
    ordenado = forecast.sort([*_KEY, "horizonte"]).with_columns(marca.fill_null(False).alias("_m"))
    return ordenado.with_columns(
        (pl.col("_m") != pl.col("_m").shift(fill_value=False)).cum_sum().over(_KEY).alias("_bloco")
    ).filter(pl.col("_m"))


def _modo_causa(coluna: str) -> pl.Expr:
    """Causa mais frequente; empate entre causas diferentes vira `MISTA`."""
    contagem = pl.col(coluna).drop_nulls().value_counts(sort=True)
    topo = contagem.struct.field("count")
    return (
        pl.when(pl.col(coluna).drop_nulls().len() == 0)
        .then(pl.lit(None, pl.String))
        .when((topo.len() > 1) & (topo.first() == topo.slice(1, 1).first()))
        .then(pl.lit(CAUSA_MISTA))
        .otherwise(contagem.struct.field(coluna).first())
    )


def _agrupar(blocos: pl.DataFrame) -> pl.DataFrame:
    return (
        blocos.group_by([*_KEY, "t0", "_bloco"])
        .agg(
            pl.col("tau").min().alias("inicio"),
            (pl.col("tau").max() + _STEP).alias("fim"),
            (pl.len() / 2).alias("horas"),
            pl.col("p_corte").mean().alias("chance_media"),
            pl.col("p_corte").max().alias("chance_max"),
            _modo_causa("causa_prevista").alias("causa"),
            _modo_causa("origem_prevista").alias("origem"),
        )
        .drop("_bloco")
        .sort([*_KEY, "inicio"])
    )


def janelas_alerta(forecast: pl.DataFrame) -> pl.DataFrame:
    return _agrupar(_corridas(forecast, pl.col("p_corte").is_not_null() & pl.col("alerta")))


def horas_livres(forecast: pl.DataFrame) -> pl.DataFrame:
    livre = (
        pl.col("p_corte").is_not_null()
        & ~pl.col("alerta")
        & (pl.col("potencial_referencia_mwmed") > 0)
    )
    return _agrupar(_corridas(forecast, livre)).select(*_KEY, "t0", "inicio", "fim", "horas")


def resumo_usinas(forecast: pl.DataFrame) -> pl.DataFrame:
    """Uma linha por usina, da que tem mais horas em alerta amanhã para a que tem menos."""
    previsto = pl.col("p_corte").is_not_null()
    alerta = previsto & pl.col("alerta").fill_null(False)
    livre = previsto & ~alerta & (pl.col("potencial_referencia_mwmed") > 0)
    tem_previsao = previsto.any()
    resumo = forecast.group_by([*_KEY, "t0"]).agg(
        pl.when(tem_previsao).then(alerta.sum() / 2).alias("horas_alerta"),
        pl.when(tem_previsao).then(livre.sum() / 2).alias("horas_livres"),
        pl.col("tau").filter(alerta).min().alias("primeiro_alerta"),
        pl.col("p_corte").filter(alerta).max().alias("chance_max"),
        tem_previsao.alias("_tem"),
    )
    janelas = janelas_alerta(forecast)
    principal = (
        janelas.sort([*_KEY, "horas", "inicio"], descending=[False, False, True, False])
        .group_by(_KEY, maintain_order=True)
        .agg(
            pl.col("inicio").first().alias("janela_inicio"),
            pl.col("fim").first().alias("janela_fim"),
            pl.col("causa").first().alias("motivo"),
            pl.col("origem").first().alias("origem"),
            pl.len().alias("janelas"),
        )
    )
    status = (
        pl.when(~pl.col("_tem"))
        .then(pl.lit(STATUS_SEM_PREVISAO))
        .when(pl.col("horas_alerta") > 0)
        .then(pl.lit(STATUS_ALERTA))
        .otherwise(pl.lit(STATUS_SEM_ALERTA))
    )
    extras = [c for c in ("nom_usina", "id_estado", "id_subsistema") if c in forecast.columns]
    atributos = forecast.group_by(_KEY).agg(pl.col(c).drop_nulls().first() for c in extras)
    return (
        resumo.with_columns(status.alias("status"))
        .join(principal, on=_KEY, how="left")
        .join(atributos, on=_KEY, how="left")
        .with_columns(
            pl.col("janelas").fill_null(0),
            pl.col("status").replace_strict(_ORDEM_STATUS, return_dtype=pl.Int8).alias("_o"),
        )
        .sort(["_o", "horas_alerta", "primeiro_alerta", *_KEY],
              descending=[False, True, False, False, False], nulls_last=True)
        .drop("_o", "_tem")
    )  # fmt: skip


def _hora(momento: datetime, referencia: datetime) -> str:
    if momento.date() > referencia.date() and momento.time() == datetime.min.time():
        return "24h"
    return f"{momento.hour}h" + (f"{momento.minute:02d}" if momento.minute else "")


def formatar_janela(inicio: datetime, fim: datetime) -> str:
    return f"{_hora(inicio, inicio)} às {_hora(fim, inicio)}"


def motivo_texto(causa: str | None, origem: str | None) -> str:
    if causa is None:
        return "sem ordens recentes com motivo conhecido"
    texto = MOTIVOS.get(causa, causa)
    return f"{texto} · {ORIGENS[origem]}" if origem in ORIGENS else texto


def sugestao(horas: float) -> str:
    """Sugestão genérica: o aviso orienta o preparo, não promete ganho."""
    base = "Prepare a equipe para receber e cumprir a ordem nesta janela."
    if horas >= 2:
        return base + " Janela longa: boa candidata para uma manutenção curta já prevista."
    return base


@cache
def carregar_desempenho(caminho: Path = _DESEMPENHO) -> dict:
    """Acerto medido fora da amostra, versionado com a origem do número."""
    return json.loads(Path(caminho).read_text(encoding="utf-8"))
