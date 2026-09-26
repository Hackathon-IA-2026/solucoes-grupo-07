"""Construtores de previsões pequenas e válidas no contrato para os testes do painel."""

from datetime import datetime, timedelta

import polars as pl

from curtamap.contracts import FORECAST_SCHEMA, HORIZONS, STEP, validate_forecast

T0 = datetime(2026, 8, 20)
NO_EVIDENCE = "sem_observacao_valida_no_horario_28d"


def entity_forecast(
    fonte: str,
    id_ons: str,
    *,
    alerts: dict[int, tuple[float | None, str | None]] | None = None,
    missing: set[int] = frozenset(),
    p_alert: float = 1.0,
    kind: str = "baseline",
    t0: datetime = T0,
    extra: dict | None = None,
) -> pl.DataFrame:
    """48 janelas; `alerts` mapeia horizonte → (energia MWh, causa); `missing` fica nulo."""
    alerts = alerts or {}
    rows = []
    for h in range(1, HORIZONS + 1):
        energy, cause, p = 0.0, None, 0.0
        if h in alerts:
            energy, cause = alerts[h]
            p = p_alert
        if h in missing:
            energy, cause, p = None, None, None
        rows.append(
            {
                "fonte": fonte,
                "id_ons": id_ons,
                "t0": t0,
                "horizonte": h,
                "tau": t0 + (h - 1) * STEP,
                "p_restricao": p,
                "p_corte": p,
                "limiar_alerta": None if p is None else 0.5,
                "alerta": None if p is None else p >= 0.5,
                "volume_condicional_mwmed": energy * 2 if energy else None,
                "volume_esperado_mwmed": None if energy is None else energy * 2,
                "energia_esperada_mwh": energy,
                "volume_p10_mwmed": None,
                "volume_p90_mwmed": None,
                "causa_prevista": cause,
                **{
                    f"p_causa_{c.lower()}": None if cause is None else float(cause == c)
                    for c in ("REL", "CNF", "ENE")
                },
                "origem_prevista": None,
                "motivo_sem_previsao": NO_EVIDENCE if p is None or energy is None else None,
                "motivo_sem_causa": None if cause else "sem_ordem_reconhecida_no_horario_28d",
                "tipo_saida": kind,
                "modelo_id": f"{kind}_teste",
                "corte_dados": t0 - timedelta(days=2),
                "cenario_disponibilidade": "noturno_teste",
                "instante_observacao": None,
                "cobertura_historico": 0.9,
                "gerado_em": t0,
            }
        )
    frame = pl.DataFrame(rows, schema=FORECAST_SCHEMA)
    if extra:
        frame = frame.with_columns(pl.lit(v).alias(k) for k, v in extra.items())
    return validate_forecast(frame)


def entities(*rows: tuple[str, str, str | None, str | None, str | None]) -> pl.DataFrame:
    """Atributos como `known_entities`: fonte, id_ons, nome, UF, subsistema."""
    return pl.DataFrame(
        rows,
        schema=["fonte", "id_ons", "nom_usina", "id_estado", "id_subsistema"],
        orient="row",
    ).with_columns(pl.lit(T0 - timedelta(days=3)).alias("visto_em"))
