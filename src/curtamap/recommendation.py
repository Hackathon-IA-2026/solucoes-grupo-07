"""Regras deterministicas de recomendacao, cenarios de impacto e resumo tatico."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import timedelta
from math import fsum, isclose, isfinite
from pathlib import Path
from typing import Any

import polars as pl

from curtamap.assumptions import SCENARIOS, nonnegative, validate_assumptions
from curtamap.contracts import (
    RECOMMENDATION_SCHEMA,
    RESERVED_TEST_START,
    STEP,
    validate_forecast,
    validate_recommendations,
)
from curtamap.targets import derive_targets

DEFAULT_ASSUMPTIONS_PATH = Path(__file__).parents[2] / "configs" / "premissas" / "v2.json"
_EPISODE_KEY = ["fonte", "id_ons", "t0"]

_ACTIONS = {
    "REL": (
        "PRESERVAR_EVIDENCIAS_ESS",
        "Confirmar a mensagem do ONS, preservar telemetria e dados meteorologicos e preparar "
        "a conferencia da apuracao. Elegibilidade e eventual compensacao exigem validacao "
        "regulatoria do evento, contrato e periodo; esta regra nao calcula ESS.",
    ),
    "CNF": (
        "COORDENAR_OPERACAO",
        "Coordenar com o centro de operacao e seguir o limite do ONS; avaliar manutencoes "
        "flexiveis sem elevar injecao nem violar requisitos de confiabilidade. Preservar "
        "evidencias para avaliacao regulatoria; CNF nao implica ausencia de direito financeiro.",
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
    return validate_assumptions(assumptions)


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
    forbidden = (
        (pl.col("tau") + STEP > RESERVED_TEST_START)
        | (pl.col("corte_dados") > RESERVED_TEST_START)
        | (pl.col("instante_observacao") >= RESERVED_TEST_START)
    )
    if forecast.select(forbidden.any()).item():
        raise ValueError("periodo reservado nao pode gerar recomendacao")
    if forecast.select((pl.col("t0") != pl.col("t0").dt.truncate("30m")).any()).item():
        raise ValueError("t0 fora da grade de 30 minutos")
    provenance = ["tipo_saida", "modelo_id", "corte_dados", "cenario_disponibilidade", "gerado_em"]
    mixed = forecast.group_by(_EPISODE_KEY).agg(pl.col(provenance).n_unique())
    if mixed.select(pl.any_horizontal(pl.col(provenance) > 1).any()).item():
        raise ValueError("emissao mistura proveniencias de previsao")
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
                "energia_por_janela_mwh": pl.List(pl.Float64),
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
            pl.col("energia_esperada_mwh").alias("energia_por_janela_mwh"),
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
    *,
    energy_profile_mwh: Sequence[float] | None = None,
) -> pl.DataFrame:
    """Cenário isolado; sem perfil semi-horário, o resultado é apenas um teto agregado."""
    validate_assumptions(assumptions)
    energy = nonnegative(energy_at_risk_mwh, "energia em risco")
    if not isinstance(duration, timedelta) or duration.total_seconds() <= 0:
        raise ValueError("duracao deve ser positiva")
    if action_code not in {action[0] for action in _ACTIONS.values()}:
        raise ValueError("acao desconhecida")
    hours = duration.total_seconds() / 3600
    profile = None
    if energy_profile_mwh is not None:
        profile = [nonnegative(e, "energia por janela") for e in energy_profile_mwh]
        if not isclose(len(profile) * 0.5, hours) or not isclose(
            fsum(profile), energy, rel_tol=1e-9, abs_tol=1e-6
        ):
            raise ValueError("perfil de energia incompativel com duracao ou total")
    rows = []
    for name in SCENARIOS:
        scenario = assumptions["cenarios"][name]
        price = _value(scenario, "preco_energia_brl_mwh")
        emission = _value(scenario, "fator_emissao_tco2_mwh")
        recoverable = 0.0
        if action_code == "AVALIAR_ARMAZENAMENTO":
            power = _value(scenario, "armazenamento", "potencia_mw")
            capacity = _value(scenario, "armazenamento", "capacidade_mwh")
            efficiency = _value(scenario, "armazenamento", "eficiencia")
            recoverable = None
            if power is not None and capacity is not None and efficiency is not None:
                input_energy = (
                    fsum(min(e, power * 0.5) for e in profile)
                    if profile is not None
                    else min(energy, power * hours)
                )
                if assumptions.get("base_capacidade", "entrada") == "saida_util":
                    recoverable = min(energy, input_energy * efficiency, capacity)
                else:  # Reprodução explícita das premissas v1 arquivadas.
                    recoverable = min(energy, min(input_energy, capacity) * efficiency)
        money = recoverable * price if recoverable is not None and price is not None else None
        carbon = (
            recoverable * emission if recoverable is not None and emission is not None else None
        )
        if any(v is not None and not isfinite(v) for v in (recoverable, money, carbon)):
            raise ValueError("impacto nao finito: overflow numerico")
        rows.append(
            {
                "cenario": name,
                "energia_recuperavel_mwh": recoverable,
                "valor_estimado_brl": money,
                "co2_evitado_t": carbon,
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


def recommendation_rule(
    cause: str | None,
    source: str,
    origin: str | None,
    *,
    lead_hours: float,
) -> dict[str, str]:
    """Resolve uma regra explícita, inclusive PAR histórico e causa indeterminada."""
    if cause not in _ACTIONS:
        raise ValueError(f"causa sem regra: {cause}")
    if source not in {"eolica", "fotovoltaica"}:
        raise ValueError(f"fonte sem regra: {source}")
    if origin not in {None, "LOC", "SIS"}:
        raise ValueError("origem sem regra")
    nonnegative(lead_hours, "antecedencia")
    action_code, base = _ACTIONS[cause]
    source_label = "o parque eolico" if source == "eolica" else "a usina fotovoltaica"
    origin_label = f" Origem prevista: {origin}." if origin else ""
    description = (
        f"Para {source_label}, inicio previsto em {lead_hours:g} h desde a emissao "
        f"(nao e prazo garantido para agir).{origin_label} {base} "
        "Impacto é um cenário: energia cortada não vira automaticamente energia recuperada "
        "nem receita; depende do ativo, contrato, comando do ONS e regulação."
    )
    return {"acao_codigo": action_code, "acao_descricao": description}


def build_recommendations(
    forecast: pl.DataFrame, assumptions: dict[str, Any] | None = None
) -> pl.DataFrame:
    """Transforma episodios em uma recomendacao contratual por janela de risco."""
    assumptions = load_assumptions() if assumptions is None else validate_assumptions(assumptions)
    rows = []
    for episode in group_risk_windows(forecast).iter_rows(named=True):
        rule = recommendation_rule(
            episode["causa_base"],
            episode["fonte"],
            episode["origem_base"],
            lead_hours=(episode["inicio"] - episode["t0"]).total_seconds() / 3600,
        )
        action_code = rule["acao_codigo"]
        sensitivity = impact_sensitivity(
            episode["energia_em_risco_mwh"],
            episode["fim"] - episode["inicio"],
            action_code,
            assumptions,
            energy_profile_mwh=episode["energia_por_janela_mwh"],
        )
        selected = sensitivity.filter(pl.col("cenario") == "base")
        impact = selected.row(0, named=True)
        if impact["energia_recuperavel_mwh"] is None:
            raise ValueError(
                "energia recuperavel indeterminada: contrato exige valor; nao usar zero"
            )
        rows.append(
            {
                "fonte": episode["fonte"],
                "id_ons": episode["id_ons"],
                "t0": episode["t0"],
                "inicio": episode["inicio"],
                "fim": episode["fim"],
                "causa_base": episode["causa_base"],
                "acao_codigo": action_code,
                "acao_descricao": rule["acao_descricao"],
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
    if observed["din_instante"].null_count():
        raise ValueError("din_instante nulo impede verificar periodo reservado")
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
            pl.col("energia_mwh").is_null().sum().alias("janelas_volume_nulo"),
            pl.col("volume_valido").sum().alias("janelas_volume_valido"),
            pl.col("corte_positivo").is_null().sum().alias("janelas_corte_indeterminado"),
            pl.when(pl.col("energia_mwh").null_count() == 0)
            .then(pl.col("energia_mwh").sum())
            .otherwise(None)
            .alias("energia_observada_mwh"),
            pl.when(pl.col("energia_mwh").count() > 0)
            .then(pl.col("energia_mwh").sum())
            .otherwise(None)
            .alias("energia_conhecida_mwh"),
        )
        .sort(["fonte", "id_ons", "periodo", "causa"], nulls_last=True)
    )
