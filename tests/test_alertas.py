from datetime import date, datetime, timedelta

import polars as pl
import pytest

from curtamap.previsao.alertas import alert_metrics, rank_alerts, validate_alerts


def sample():
    start = datetime(2026, 8, 3)
    return pl.DataFrame(
        {
            "fonte": ["eolica"] * 48,
            "id_ons": ["A"] * 48,
            "dia": [start.date()] * 48,
            "tau": [start + timedelta(minutes=30 * i) for i in range(48)],
            "p_corte": [0.8, None, 0.2] + [0.1] * 45,
            "limiar_alerta": [0.5] * 48,
        }
    ).with_columns((pl.col("p_corte") >= pl.col("limiar_alerta")).alias("alerta"))


def test_rank_preserves_missing_and_counts_duration_not_daily_probability():
    result = rank_alerts(sample()).row(0, named=True)
    assert result["janelas_alerta"] == 1
    assert result["horas_alerta"] == 0.5
    assert result["janelas_sem_previsao"] == 1
    assert result["primeiro_alerta"] == datetime(2026, 8, 3)
    assert "probabilidade_diaria" not in result


def test_no_evidence_does_not_become_no_risk_and_keys_keep_source_and_day():
    missing = sample().with_columns(
        pl.lit("fotovoltaica").alias("fonte"),
        pl.lit(None, pl.Float64).alias("p_corte"),
        pl.lit(None, pl.Boolean).alias("alerta"),
    )
    rows = rank_alerts(pl.concat([sample(), missing])).to_dicts()
    assert len(rows) == 2
    assert rows[1]["status"] == "sem previsão"
    assert rows[1]["probabilidade_maxima"] is None
    assert rows[1]["horas_alerta"] is None


@pytest.mark.parametrize("bad", [-0.1, 1.1, float("nan"), float("inf")])
def test_reject_invalid_probabilities(bad):
    with pytest.raises(ValueError):
        validate_alerts(sample().with_columns(pl.lit(bad).alias("p_corte")))


def test_reject_duplicates_partial_grid_and_inconsistent_alerts():
    for frame in [
        pl.concat([sample(), sample().head(1)]),
        sample().head(47),
        sample().with_columns(pl.lit(False).alias("alerta")),
    ]:
        with pytest.raises(ValueError):
            validate_alerts(frame)


def test_metrics_score_same_known_rows_and_count_missing_without_imputation():
    rows = pl.DataFrame(
        {
            "fonte": ["eolica"] * 5,
            "dia": [date(2026, 8, 3)] * 5,
            "idade": [2] * 5,
            "y_corte": [1, 0, 1, 0, None],
            "p_corte": [0.9, 0.8, 0.2, 0.1, 0.8],
            "hist_28d": [0.9, 0.8, None, 0.1, 0.8],
            "ultimo_slot": [1.0, 1.0, 0.0, 0.0, 1.0],
            "ultimo_valor_corte": [1.0, 1.0, 0.0, 0.0, 1.0],
        }
    )
    result = alert_metrics(rows, {"eolica": 0.5})
    hgb = result.filter((pl.col("modelo") == "hgb_servido") & (pl.col("recorte") == "mes"))
    row = hgb.row(0, named=True)
    assert row["linhas_grade"] == 5
    assert row["linhas_rotuladas"] == 4
    assert row["n"] == 3  # interseção conhecida, sem preencher baseline nulo com zero
    assert (row["tp"], row["fp"], row["fn"], row["tn"]) == (1, 1, 0, 1)
    assert row["f1"] == pytest.approx(2 / 3)
    assert row["cobertura_comum"] == 0.75


def test_reproduction_matches_original_classifier_and_ignores_future_labels():
    from test_previsao_modelo import _raw

    from curtamap.previsao.alertas import reproduce
    from curtamap.previsao.calendario import load_calendar
    from curtamap.previsao.features import OCCURRENCE, base_from_history, release_map
    from curtamap.previsao.modelo import _matrix, fit_source, training_rows

    base = base_from_history(_raw(date(2026, 3, 1), date(2026, 5, 31)))
    base = base.filter(pl.col("fonte") == "eolica")
    first = date(2026, 5, 26)
    prediction, model, info = reproduce(base, first, first, 0.5)
    cutoff = date.fromisoformat(info["treino_ate"])
    days = pl.date_range(cutoff - timedelta(days=364), cutoff, eager=True)
    rows = training_rows(
        base.filter(pl.col("dia") <= cutoff), release_map(days, load_calendar()), cutoff
    )
    original = fit_source(rows)
    assert model.predict_proba(_matrix(rows, OCCURRENCE)) == pytest.approx(
        original.occurrence.predict_proba(_matrix(rows, OCCURRENCE))
    )
    poisoned = base.with_columns(
        pl.when(pl.col("dia") > cutoff)
        .then(1 - pl.col("corte"))
        .otherwise(pl.col("corte"))
        .alias("corte"),
        pl.when(pl.col("dia") > cutoff).then(1e6).otherwise(pl.col("volume")).alias("volume"),
    )
    after, _, _ = reproduce(poisoned, first, first, 0.5)
    assert prediction["p_corte"].to_list() == pytest.approx(after["p_corte"].to_list())
    assert prediction["tau"].max() == datetime(2026, 5, 26, 23, 30)
    assert prediction["emitido_em"].unique().to_list() == [datetime(2026, 5, 25, 20)]
    assert prediction["corte_dados"].max() <= prediction["emitido_em"].min()


def test_projecting_occurrence_features_preserves_values_and_row_order():
    from polars.testing import assert_frame_equal
    from test_previsao_modelo import _raw

    from curtamap.previsao.calendario import load_calendar
    from curtamap.previsao.features import (
        OCCURRENCE,
        base_from_history,
        build_features,
        release_map,
    )

    base = base_from_history(_raw(date(2026, 3, 1), date(2026, 5, 31)))
    mapping = release_map([date(2026, 5, 26), date(2026, 5, 27)], load_calendar())
    full = build_features(base, mapping)
    small = build_features(base, mapping, feature_columns=[*OCCURRENCE, "ultimo_valor_corte"])
    assert_frame_equal(small, full.select(small.columns))
    assert "vol_hist_28d" not in small.columns
