"""Contratos de saída entre previsão, recomendação e interface — versão 1.

O contrato fixa o formato, não o modelo. Qualquer preditor (baseline hoje, modelo escolhido
na Etapa 2C depois) deve produzir `FORECAST_SCHEMA`; recomendação e dashboard consomem só
esse formato e nunca importam `curtamap.experimental`.

Unidade da previsão: `fonte + id_ons + t0 + horizonte`, com `tau = t0 + (h - 1) × 30 min`
referente ao intervalo semiaberto `[tau, tau + 30 min)`. Timestamps são ingênuos, em horário
de Brasília como publicado pelo ONS (`TIMEZONE`); não reinterpretar como UTC.

Colunas extras são permitidas (diagnósticos, explicações), mas as obrigatórias não mudam
de nome nem de tipo sem nova versão do contrato.
"""

from datetime import datetime, timedelta

import polars as pl

CONTRACT_VERSION = "1"
TIMEZONE = "America/Sao_Paulo"
HORIZONS = 48
STEP = timedelta(minutes=30)
# Etapa 2A: maio–agosto de 2026 é o teste reservado. Nada do produto (fixtures, demo,
# números de impacto) pode ler esse período antes de a Etapa 2C liberá-lo.
RESERVED_TEST_START = datetime(2026, 5, 1)

SOURCES = ("eolica", "fotovoltaica")
# PAR não tem suporte para aprendizado e DESCONHECIDA não é causa física (protocolo §5.3).
PREDICTABLE_CAUSES = ("REL", "CNF", "ENE")
RECOMMENDATION_CAUSES = ("REL", "CNF", "ENE", "PAR")
ORIGINS = ("LOC", "SIS")
OUTPUT_KINDS = ("modelo", "baseline", "simulado")

_TS = pl.Datetime("us")

FORECAST_SCHEMA = pl.Schema(
    {
        "fonte": pl.String,
        "id_ons": pl.String,
        "t0": _TS,
        "horizonte": pl.Int16,
        "tau": _TS,
        # Ocorrência: comando registrado (secundária) e volume positivo (principal).
        "p_restricao": pl.Float64,
        "p_corte": pl.Float64,
        "limiar_alerta": pl.Float64,
        "alerta": pl.Boolean,
        # Volume em MWmed do patamar; energia = MWmed × 0,5.
        "volume_condicional_mwmed": pl.Float64,
        "volume_esperado_mwmed": pl.Float64,
        "energia_esperada_mwh": pl.Float64,
        "volume_p10_mwmed": pl.Float64,
        "volume_p90_mwmed": pl.Float64,
        # Causa condicional: "se houver ordem, qual causa?".
        "causa_prevista": pl.String,
        "p_causa_rel": pl.Float64,
        "p_causa_cnf": pl.Float64,
        "p_causa_ene": pl.Float64,
        "origem_prevista": pl.String,
        "motivo_sem_previsao": pl.String,
        "motivo_sem_causa": pl.String,
        # Proveniência.
        "tipo_saida": pl.String,
        "modelo_id": pl.String,
        "corte_dados": _TS,
        "gerado_em": _TS,
    }
)

RECOMMENDATION_SCHEMA = pl.Schema(
    {
        "fonte": pl.String,
        "id_ons": pl.String,
        "t0": _TS,
        "inicio": _TS,
        "fim": _TS,
        "causa_base": pl.String,
        "acao_codigo": pl.String,
        "acao_descricao": pl.String,
        "energia_em_risco_mwh": pl.Float64,
        "energia_recuperavel_mwh": pl.Float64,
        "valor_estimado_brl": pl.Float64,
        "co2_evitado_t": pl.Float64,
        "premissas_versao": pl.String,
        "tipo_saida": pl.String,
        "modelo_id": pl.String,
    }
)

_PROBABILITIES = ("p_restricao", "p_corte", "limiar_alerta", "p_causa_rel", "p_causa_cnf")
_PROBABILITIES += ("p_causa_ene",)
_FORECAST_VOLUMES = (
    "volume_condicional_mwmed",
    "volume_esperado_mwmed",
    "energia_esperada_mwh",
    "volume_p10_mwmed",
    "volume_p90_mwmed",
)
_CAUSE_PROBABILITIES = ("p_causa_rel", "p_causa_cnf", "p_causa_ene")
_TOLERANCE = 1e-6


class ContractError(ValueError):
    """Violação do contrato; a mensagem cita a coluna e a quantidade de linhas."""


def _check_schema(frame: pl.DataFrame, schema: pl.Schema) -> None:
    missing = [name for name in schema if name not in frame.columns]
    if missing:
        raise ContractError(f"colunas ausentes: {', '.join(missing)}")
    wrong = [
        f"{name} ({frame.schema[name]} ≠ {dtype})"
        for name, dtype in schema.items()
        if frame.schema[name] != dtype
    ]
    if wrong:
        raise ContractError(f"tipos incorretos: {', '.join(wrong)}")


def _require(frame: pl.DataFrame, violation: pl.Expr, message: str) -> None:
    count = frame.select(violation.fill_null(False).sum()).item()
    if count:
        raise ContractError(f"{message} ({count} linha(s))")


def _not_blank(column: str) -> pl.Expr:
    return pl.col(column).is_null() | (pl.col(column).str.strip_chars() == "")


def _outside(column: str, domain: tuple[str, ...]) -> pl.Expr:
    return pl.col(column).is_not_null() & ~pl.col(column).is_in(domain)


def _bad_number(column: str, *, lower: float | None = None, upper: float | None = None):
    value = pl.col(column)
    bad = value.is_nan() | value.is_infinite()
    if lower is not None:
        bad = bad | (value < lower)
    if upper is not None:
        bad = bad | (value > upper)
    return value.is_not_null() & bad


def _check_key(frame: pl.DataFrame, key: list[str]) -> None:
    _require(frame, pl.any_horizontal([pl.col(c).is_null() for c in key]), "chave nula")
    if frame.select(pl.struct(key).is_duplicated().any()).item():
        raise ContractError(f"chave duplicada: {' + '.join(key)}")


def validate_forecast(frame: pl.DataFrame) -> pl.DataFrame:
    """Valida e devolve o próprio frame; levanta `ContractError` na primeira violação."""
    _check_schema(frame, FORECAST_SCHEMA)
    _check_key(frame, ["fonte", "id_ons", "t0", "horizonte"])
    col = pl.col
    _require(frame, _outside("fonte", SOURCES), f"fonte fora de {SOURCES}")
    _require(frame, _outside("tipo_saida", OUTPUT_KINDS), f"tipo_saida fora de {OUTPUT_KINDS}")
    _require(frame, col("tipo_saida").is_null(), "tipo_saida nulo")
    _require(frame, _not_blank("modelo_id"), "modelo_id vazio")
    _require(frame, ~col("horizonte").is_between(1, HORIZONS), f"horizonte fora de 1..{HORIZONS}")
    expected_tau = col("t0") + pl.duration(minutes=30 * (col("horizonte").cast(pl.Int64) - 1))
    _require(frame, col("tau") != expected_tau, "tau ≠ t0 + (horizonte − 1) × 30 min")
    _require(frame, col("corte_dados").is_null(), "corte_dados nulo")
    _require(frame, col("corte_dados") > col("t0"), "corte_dados posterior a t0")
    _require(frame, col("gerado_em").is_null(), "gerado_em nulo")

    for name in _PROBABILITIES:
        _require(frame, _bad_number(name, lower=0.0, upper=1.0), f"{name} fora de [0, 1]")
    for name in _FORECAST_VOLUMES:
        _require(frame, _bad_number(name, lower=0.0), f"{name} negativo ou não finito")
    energy_gap = (col("energia_esperada_mwh") - col("volume_esperado_mwmed") * 0.5).abs()
    _require(frame, energy_gap > _TOLERANCE, "energia_esperada_mwh ≠ volume_esperado × 0,5")
    _require(
        frame,
        col("volume_p10_mwmed") > col("volume_p90_mwmed"),
        "volume_p10_mwmed maior que volume_p90_mwmed",
    )

    no_forecast = col("p_corte").is_null() | col("volume_esperado_mwmed").is_null()
    _require(
        frame,
        no_forecast & _not_blank("motivo_sem_previsao"),
        "previsão ausente sem motivo_sem_previsao",
    )
    _require(
        frame,
        col("alerta") != (col("p_corte") >= col("limiar_alerta")),
        "alerta incoerente com p_corte ≥ limiar_alerta",
    )
    _require(frame, col("p_corte").is_not_null() & col("alerta").is_null(), "alerta nulo")

    _require(
        frame,
        _outside("causa_prevista", PREDICTABLE_CAUSES),
        f"causa_prevista fora de {PREDICTABLE_CAUSES}",
    )
    _require(
        frame,
        col("causa_prevista").is_null() & _not_blank("motivo_sem_causa"),
        "causa ausente sem motivo_sem_causa",
    )
    present = pl.all_horizontal([col(c).is_not_null() for c in _CAUSE_PROBABILITIES])
    partial = pl.any_horizontal([col(c).is_not_null() for c in _CAUSE_PROBABILITIES]) & ~present
    total = pl.sum_horizontal(_CAUSE_PROBABILITIES)
    _require(frame, partial, "p_causa_* parcialmente preenchidas")
    _require(frame, present & ((total - 1).abs() > _TOLERANCE), "p_causa_* não somam 1")
    _require(frame, _outside("origem_prevista", ORIGINS), f"origem_prevista fora de {ORIGINS}")
    return frame


def validate_recommendations(frame: pl.DataFrame) -> pl.DataFrame:
    """Valida recomendações; valores monetários e de CO2 são cenários, podendo ser nulos."""
    _check_schema(frame, RECOMMENDATION_SCHEMA)
    _check_key(frame, ["fonte", "id_ons", "t0", "inicio", "acao_codigo"])
    col = pl.col
    _require(frame, _outside("fonte", SOURCES), f"fonte fora de {SOURCES}")
    _require(frame, _outside("tipo_saida", OUTPUT_KINDS), f"tipo_saida fora de {OUTPUT_KINDS}")
    _require(frame, col("tipo_saida").is_null(), "tipo_saida nulo")
    _require(frame, _not_blank("modelo_id"), "modelo_id vazio")
    _require(frame, _not_blank("premissas_versao"), "premissas_versao vazia")
    _require(frame, _not_blank("acao_descricao"), "acao_descricao vazia")
    _require(
        frame,
        _outside("causa_base", RECOMMENDATION_CAUSES),
        f"causa_base fora de {RECOMMENDATION_CAUSES}",
    )
    _require(frame, col("fim").is_null() | (col("fim") <= col("inicio")), "fim ≤ inicio")
    _require(frame, col("inicio") < col("t0"), "inicio anterior a t0")
    for name in ("energia_em_risco_mwh", "energia_recuperavel_mwh", "co2_evitado_t"):
        _require(frame, _bad_number(name, lower=0.0), f"{name} negativo ou não finito")
    _require(frame, _bad_number("valor_estimado_brl"), "valor_estimado_brl não finito")
    _require(
        frame,
        col("energia_recuperavel_mwh") > col("energia_em_risco_mwh") + _TOLERANCE,
        "energia_recuperavel_mwh maior que energia_em_risco_mwh",
    )
    return frame
