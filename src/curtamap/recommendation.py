"""Regras deterministicas de recomendacao, cenarios de impacto e resumo tatico."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import polars as pl

from curtamap.contracts import (
    RECOMMENDATION_SCHEMA,
    RESERVED_TEST_START,
    STEP,
    validate_forecast,
    validate_recommendations,
)
from curtamap.targets import derive_targets

DEFAULT_ASSUMPTIONS_PATH = Path(__file__).parents[2] / "configs" / "premissas" / "v1.json"
SCENARIOS = ("baixo", "base", "alto")
_EPISODE_KEY = ["fonte", "id_ons", "t0"]

_ACTIONS = {
    "REL": (
        "PRESERVAR_EVIDENCIAS_ESS",
        "Confirmar a mensagem do ONS, preservar telemetria e dados meteorologicos e preparar "
        "a conferencia da apuracao; somente REL pode ensejar ESS, sujeito as regras vigentes.",
    ),
    "CNF": (
        "COORDENAR_OPERACAO",
        "Coordenar com o centro de operacao e seguir o limite do ONS; avaliar manutencoes "
        "flexiveis sem elevar injecao nem violar requisitos de confiabilidade.",
    ),
    "ENE": (
        "AVALIAR_ARMAZENAMENTO",
        "Se houver bateria habilitada e margem operacional, simular carga durante o excedente "
        "e descarga posterior; nao alterar geracao sem comando e validacao do agente.",
    ),
    "PAR": (
        "REVISAR_PARECER_ACESSO",
        "Conferir o limite vigente no parecer de acesso e priorizar estudo de conexao/reforco; "
        "a restricao prevista no acesso nao deve ser tratada como recuperacao imediata.",
    ),
    None: (
        "VALIDAR_CAUSA",
        "Causa indeterminada: confirmar a mensagem do ONS antes de agir; nao inferir REL, CNF, "
        "ENE ou PAR a partir do volume previsto.",
    ),
}


def load_assumptions(path: str | Path = DEFAULT_ASSUMPTIONS_PATH) -> dict[str, Any]:
    """Carrega premissas versionadas; valores ausentes permanecem ausentes."""
    with Path(path).open(encoding="utf-8") as source:
        assumptions = json.load(source)
    if not assumptions.get("versao"):
        raise ValueError("arquivo de premissas sem versao")
    return assumptions


def _all_same_or_null(column: str) -> pl.Expr:
    value = pl.col(column)
    return (
        pl.when((value.count() == pl.len()) & (value.n_unique() == 1))
        .then(value.first())
        .otherwise(None)
        .alias(column)
    )


def group_risk_windows(forecast: pl.DataFrame) -> pl.DataFrame:
    """Agrupa alertas consecutivos por entidade e emissao, sem cruzar chaves ou `t0`."""
    validate_forecast(forecast)
    alerts = forecast.filter(pl.col("alerta"))
    if alerts.is_empty():
        return pl.DataFrame(
            schema={
                "fonte": pl.String,
                "id_ons": pl.String,
                "t0": pl.Datetime("us"),
                "inicio": pl.Datetime("us"),
                "fim": pl.Datetime("us"),
                "causa_base": pl.String,
                "origem_base": pl.String,
                "energia_em_risco_mwh": pl.Float64,
                "tipo_saida": pl.String,
                "modelo_id": pl.String,
            }
        )
    if alerts["energia_esperada_mwh"].null_count():
        raise ValueError("alerta com energia_esperada_mwh nula nao pode gerar impacto")

    sorted_alerts = alerts.sort([*_EPISODE_KEY, "tau"])
    starts = pl.col("tau").diff().over(_EPISODE_KEY).is_null() | (
        pl.col("tau").diff().over(_EPISODE_KEY) != STEP
    )
    numbered = sorted_alerts.with_columns(
        starts.cast(pl.Int64).cum_sum().over(_EPISODE_KEY).alias("episodio")
    )
    episodes = (
        numbered.group_by([*_EPISODE_KEY, "episodio"], maintain_order=True)
        .agg(
            pl.col("tau").min().alias("inicio"),
            (pl.col("tau").max() + STEP).alias("fim"),
            _all_same_or_null("causa_prevista"),
            _all_same_or_null("origem_prevista"),
            pl.col("energia_esperada_mwh").sum().alias("energia_em_risco_mwh"),
            _all_same_or_null("tipo_saida"),
            _all_same_or_null("modelo_id"),
        )
        .rename({"causa_prevista": "causa_base", "origem_prevista": "origem_base"})
        .drop("episodio")
    )
    missing_provenance = pl.any_horizontal(
        pl.col("tipo_saida").is_null(), pl.col("modelo_id").is_null()
    )
    if episodes.select(missing_provenance.any()).item():
        raise ValueError("episodio mistura proveniencias de previsao")
    return episodes


def _value(container: dict[str, Any], *path: str) -> float | None:
    current: Any = container
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if isinstance(current, dict):
        current = current.get("valor")
    return float(current) if isinstance(current, int | float) else None


def impact_sensitivity(
    energy_at_risk_mwh: float,
    duration: timedelta,
    action_code: str,
    assumptions: dict[str, Any],
) -> pl.DataFrame:
    """Calcula baixo/base/alto; falta de premissa financeira ou climatica vira nulo."""
    rows = []
    scenarios = assumptions.get("cenarios", {})
    names = [name for name in SCENARIOS if name in scenarios] or list(scenarios) or ["base"]
    for name in names:
        scenario = scenarios.get(name, {})
        price = _value(scenario, "preco_energia_brl_mwh")
        emission = _value(scenario, "fator_emissao_tco2_mwh")
        recoverable = 0.0
        if action_code == "AVALIAR_ARMAZENAMENTO":
            power = _value(scenario, "armazenamento", "potencia_mw")
            capacity = _value(scenario, "armazenamento", "capacidade_mwh")
            efficiency = _value(scenario, "armazenamento", "eficiencia")
            if power is not None and capacity is not None and efficiency is not None:
                input_energy = min(
                    energy_at_risk_mwh, power * duration.total_seconds() / 3600, capacity
                )
                recoverable = min(energy_at_risk_mwh, input_energy * efficiency)
        rows.append(
            {
                "cenario": name,
                "energia_recuperavel_mwh": recoverable,
                "valor_estimado_brl": recoverable * price if price is not None else None,
                "co2_evitado_t": recoverable * emission if emission is not None else None,
            }
        )
    return pl.DataFrame(
        rows,
        schema={
            "cenario": pl.String,
            "energia_recuperavel_mwh": pl.Float64,
            "valor_estimado_brl": pl.Float64,
            "co2_evitado_t": pl.Float64,
        },
    )


def _description(row: dict[str, Any], base: str) -> str:
    source = "parque eolico" if row["fonte"] == "eolica" else "usina fotovoltaica"
    lead_hours = (row["inicio"] - row["t0"]).total_seconds() / 3600
    origin = f" Origem prevista: {row['origem_base']}." if row["origem_base"] else ""
    return (
        f"Para o {source}, janela em {lead_hours:g} h.{origin} {base} "
        "Impacto é um cenário: energia cortada não vira automaticamente energia recuperada "
        "nem receita; depende do ativo, contrato, comando do ONS e regulação."
    )


def build_recommendations(
    forecast: pl.DataFrame, assumptions: dict[str, Any] | None = None
) -> pl.DataFrame:
    """Transforma episodios em uma recomendacao contratual por janela de risco."""
    assumptions = assumptions or load_assumptions()
    rows = []
    for episode in group_risk_windows(forecast).iter_rows(named=True):
        action_code, action_text = _ACTIONS[episode["causa_base"]]
        sensitivity = impact_sensitivity(
            episode["energia_em_risco_mwh"],
            episode["fim"] - episode["inicio"],
            action_code,
            assumptions,
        )
        selected = sensitivity.filter(pl.col("cenario") == "base")
        impact = (selected if selected.height else sensitivity.head(1)).row(0, named=True)
        rows.append(
            {
                "fonte": episode["fonte"],
                "id_ons": episode["id_ons"],
                "t0": episode["t0"],
                "inicio": episode["inicio"],
                "fim": episode["fim"],
                "causa_base": episode["causa_base"],
                "acao_codigo": action_code,
                "acao_descricao": _description(episode, action_text),
                "energia_em_risco_mwh": episode["energia_em_risco_mwh"],
                "energia_recuperavel_mwh": impact["energia_recuperavel_mwh"],
                "valor_estimado_brl": impact["valor_estimado_brl"],
                "co2_evitado_t": impact["co2_evitado_t"],
                "premissas_versao": assumptions["versao"],
                "tipo_saida": episode["tipo_saida"],
                "modelo_id": episode["modelo_id"],
            }
        )
    result = pl.DataFrame(rows, schema=RECOMMENDATION_SCHEMA)
    return validate_recommendations(result)


def summarize_history(observed: pl.DataFrame, grain: str = "mes") -> pl.DataFrame:
    """Agrega alvos observados por entidade, periodo, causa, UF e subsistema."""
    if grain not in {"semana", "mes"}:
        raise ValueError("grain deve ser 'semana' ou 'mes'")
    if observed.filter(pl.col("din_instante") >= RESERVED_TEST_START).height:
        raise ValueError("periodo reservado a partir de 2026-05-01 nao pode ser usado")
    target = derive_targets(observed)
    every = "1w" if grain == "semana" else "1mo"
    return (
        target.with_columns(pl.col("din_instante").dt.truncate(every).alias("periodo"))
        .group_by(
            "fonte",
            "id_ons",
            "periodo",
            "causa",
            pl.col("id_estado").alias("uf"),
            pl.col("id_subsistema").alias("subsistema"),
        )
        .agg(
            pl.len().alias("janelas_observadas"),
            pl.col("corte_positivo").fill_null(False).sum().alias("janelas_com_corte"),
            pl.col("energia_mwh").sum().alias("energia_observada_mwh"),
        )
        .sort(["fonte", "id_ons", "periodo", "causa"], nulls_last=True)
    )
