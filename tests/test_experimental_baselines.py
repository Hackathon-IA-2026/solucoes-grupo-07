from datetime import datetime, timedelta

import polars as pl

from curtamap.experimental.baselines import generate_baselines


def history() -> pl.DataFrame:
    start = datetime(2025, 1, 1, 10)
    return pl.DataFrame(
        {
            "fonte": ["eolica"] * 8,
            "id_ons": ["A"] * 8,
            "id_estado": ["RJ"] * 8,
            "din_instante": [start + timedelta(days=i) for i in range(8)],
            "disponivel_em": [start + timedelta(days=i, hours=12) for i in range(8)],
            "restricao_registrada": [True] * 8,
            "corte_positivo": [False, True, False, True, False, True, False, True],
            "volume_mwmed": [0.0, 10.0, 0.0, 20.0, 0.0, 30.0, 0.0, 40.0],
            "volume_valido": [True] * 8,
            "causa": ["ENE", "CNF", "ENE", "CNF", "ENE", "CNF", "ENE", "CNF"],
        }
    )


def requests(t0: datetime, tau: datetime | None = None) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "fonte": ["eolica"],
            "id_ons": ["A"],
            "id_estado": ["RJ"],
            "t0": [t0],
            "tau": [tau or t0],
            "horizon": [1],
        }
    )


def test_all_required_baselines_are_emitted_with_provenance() -> None:
    result = generate_baselines(history(), requests(datetime(2025, 1, 9, 23)))

    assert set(result["baseline_id"]) == {
        "ultimo_valor",
        "mesmo_horario_dia_anterior",
        "mesmo_horario_recente",
        "historico",
    }
    assert result["fallback_level"].null_count() == 0
    assert result["history_age_hours"].null_count() == 0
    assert result["native_available"].dtype == pl.Boolean


def test_last_value_preserves_valid_zero_and_last_known_cause() -> None:
    result = generate_baselines(history(), requests(datetime(2025, 1, 8, 23)))
    row = result.filter(pl.col("baseline_id") == "ultimo_valor").row(0, named=True)

    assert row["prob_positive"] == 1.0
    assert row["volume_expected"] == 40.0
    assert row["cause_prediction"] == "CNF"
    assert row["native_available"] is True


def test_yesterday_unavailable_uses_named_statistical_fallback_without_looking_ahead() -> None:
    # Em 9/1 às 11h, a linha de 8/1 só será liberada às 22h nesta fixture.
    h = history().with_columns(
        pl.when(pl.col("din_instante") == datetime(2025, 1, 8, 10))
        .then(pl.lit(datetime(2025, 1, 9, 22)))
        .otherwise(pl.col("disponivel_em"))
        .alias("disponivel_em")
    )
    result = generate_baselines(h, requests(datetime(2025, 1, 9, 11), datetime(2025, 1, 9, 10)))
    row = result.filter(pl.col("baseline_id") == "mesmo_horario_dia_anterior").row(0, named=True)

    assert row["native_available"] is False
    assert row["fallback_level"] == "entidade_mesmo_horario"
    assert row["source_time"] < datetime(2025, 1, 8, 11)
    assert row["prob_positive"] == 3 / 7
    assert row["volume_positive_mean"] is None
    assert row["volume_expected"] == 0.0


def test_same_hour_recent_does_not_silently_become_yesterday_rule() -> None:
    # A observação exata de ontem não está disponível, mas uma anterior está.
    h = history().with_columns(
        pl.when(pl.col("din_instante") == datetime(2025, 1, 8, 10))
        .then(pl.lit(datetime(2025, 1, 9, 22)))
        .otherwise(pl.col("disponivel_em"))
        .alias("disponivel_em")
    )
    result = generate_baselines(h, requests(datetime(2025, 1, 9, 11), datetime(2025, 1, 9, 10)))
    row = result.filter(pl.col("baseline_id") == "mesmo_horario_recente").row(0, named=True)

    assert row["native_available"] is True
    assert row["source_time"] == datetime(2025, 1, 7, 10)
    assert row["history_age_hours"] == 49.0


def test_majority_cause_has_fixed_tie_break_and_unknown_is_excluded() -> None:
    h = history().with_columns(
        pl.when(pl.col("din_instante") == datetime(2025, 1, 8, 10))
        .then(pl.lit("DESCONHECIDA"))
        .otherwise(pl.col("causa"))
        .alias("causa")
    )
    row = (
        generate_baselines(h, requests(datetime(2025, 1, 9, 23)))
        .filter(pl.col("baseline_id") == "historico")
        .row(0, named=True)
    )
    assert row["cause_prediction"] == "ENE"
    assert "PAR" not in row["cause_probabilities"]


def test_no_evidence_fallback_is_explicit_not_disguised_as_native_prediction() -> None:
    h = history().head(1)
    row = (
        generate_baselines(h, requests(datetime(2025, 1, 2, 23)))
        .filter(pl.col("baseline_id") == "historico")
        .row(0, named=True)
    )
    assert row["fallback_level"] == "sem_evidencia"
    assert row["native_available"] is False
    assert row["prob_positive"] == 0.5
    assert row["volume_expected"] == 0.0
    assert row["cause_probabilities"] == {"CNF": 1 / 3, "ENE": 1 / 3, "REL": 1 / 3}
