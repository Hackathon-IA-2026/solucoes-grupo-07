from datetime import date, datetime, timedelta

import polars as pl
import pytest

from curtamap.contracts import HORIZONS, validate_forecast
from curtamap.previsao.calendario import load_calendar
from curtamap.previsao.features import base_from_history, release_map
from curtamap.previsao.modelo import DailyForecaster, DailyModel, fit, training_rows
from curtamap.targets import derive_targets

CAL = load_calendar()
START = date(2026, 3, 1)
END = date(2026, 5, 31)
PLANTS = [("eolica", "A"), ("eolica", "B"), ("fotovoltaica", "C")]
CAUSES = ("ENE", "CNF", "REL")


def _raw(start: date = START, end: date = END) -> pl.DataFrame:
    rows = []
    day = start
    while day <= end:
        for fonte, id_ons in PLANTS:
            for slot in range(48):
                window = range(18, 32) if fonte == "eolica" else range(22, 30)
                cut = 12.0 if (slot in window and day.toordinal() % 2) else 0.0
                cause = CAUSES[day.toordinal() % 3]
                rows.append(
                    {
                        "fonte": fonte,
                        "id_ons": id_ons,
                        "nom_usina": id_ons,
                        "id_estado": "BA",
                        "id_subsistema": "NE",
                        "din_instante": datetime.combine(day, datetime.min.time())
                        + timedelta(minutes=30 * slot),
                        "val_geracaolimitada": 1.0 if cut else None,
                        "val_geracaoreferencia": 40.0,
                        "val_geracao": 40.0 - cut,
                        "cod_razaorestricao": cause if cut else None,
                        "cod_origemrestricao": "SIS" if cut else None,
                    }
                )
        day += timedelta(days=1)
    return derive_targets(pl.DataFrame(rows, infer_schema_length=None))


@pytest.fixture(scope="module")
def history() -> pl.DataFrame:
    return _raw()


@pytest.fixture(scope="module")
def model(history) -> DailyModel:
    base = base_from_history(history)
    mapping = release_map(pl.date_range(START, END, eager=True).to_list(), CAL)
    return fit(base, mapping, date(2026, 5, 15))


T0 = datetime(2026, 5, 27)  # quarta; emitido terça 26/05 às 20h
CUTOFF = datetime(2026, 5, 26)  # conhece até segunda 25/05


def _predict(model, history, **kwargs):
    return DailyForecaster(model, CAL).predict(
        history, kwargs.pop("t0", T0), kwargs.pop("cutoff", CUTOFF), **kwargs
    )


def test_forecast_honours_contract_with_48_horizons_per_entity(model, history):
    forecast = _predict(model, history, emitted_at=datetime(2026, 5, 26, 20))
    assert validate_forecast(forecast).equals(forecast)
    assert forecast.height == len(PLANTS) * HORIZONS
    assert forecast["tipo_saida"].unique().to_list() == ["modelo"]
    assert forecast["modelo_id"].unique().to_list() == ["diario_hgb_v1_2026-05-15"]
    assert forecast["corte_dados"].unique().to_list() == [CUTOFF]
    assert forecast["emitido_em"].unique().to_list() == [datetime(2026, 5, 26, 20)]
    assert forecast["idade_informacao_dias"].unique().to_list() == [2]
    assert forecast["causa_prevista"].null_count() == 0


def test_model_learns_the_intraday_profile(model, history):
    forecast = _predict(model, history)
    window = forecast.filter(pl.col("fonte") == "fotovoltaica").with_columns(
        pl.col("tau").dt.hour().alias("hora")
    )
    inside = window.filter(pl.col("hora").is_between(11, 14))["p_corte"].mean()
    outside = window.filter(pl.col("hora") < 6)["p_corte"].mean()
    assert inside > outside + 0.2


def test_forecast_ignores_everything_after_the_data_cutoff(model, history):
    tampered = history.with_columns(
        pl.when(pl.col("din_instante") >= CUTOFF)
        .then(0.0)
        .otherwise(pl.col("val_geracao"))
        .alias("val_geracao"),
        pl.when(pl.col("din_instante") >= CUTOFF)
        .then(pl.lit("CNF"))
        .otherwise(pl.col("cod_razaorestricao"))
        .alias("cod_razaorestricao"),
    )
    generated = datetime(2026, 9, 26)
    before = _predict(model, history, generated_at=generated)
    after = _predict(
        model, derive_targets(tampered.select(history.columns[:11])), generated_at=generated
    )
    assert before.equals(after)


def test_t0_inside_a_day_spans_two_target_days(model, history):
    forecast = _predict(model, history, t0=datetime(2026, 5, 27, 10))
    first = forecast.filter(pl.col("horizonte") == 1)["tau"].unique().to_list()
    last = forecast.filter(pl.col("horizonte") == HORIZONS)["tau"].unique().to_list()
    assert first == [datetime(2026, 5, 27, 10)]
    assert last == [datetime(2026, 5, 28, 9, 30)]
    assert sorted(forecast["idade_informacao_dias"].unique().to_list()) == [2, 3]


def test_refuses_cutoff_after_t0_and_reserved_period(model, history):
    with pytest.raises(ValueError, match="vaza"):
        _predict(model, history, cutoff=datetime(2026, 5, 28))
    with pytest.raises(ValueError, match="teste reservado"):
        _predict(model, history, t0=datetime(2026, 8, 31, 12), cutoff=datetime(2026, 8, 30))


def test_training_uses_only_labels_up_to_the_last_label_day(history):
    base = base_from_history(history)
    mapping = release_map(pl.date_range(START, END, eager=True).to_list(), CAL)
    rows = training_rows(base, mapping, date(2026, 4, 30))
    assert rows["dia"].max() == date(2026, 4, 30)
    assert rows["ultimo_dia"].max() < date(2026, 4, 30)


def test_saved_model_reproduces_predictions(model, history, tmp_path):
    path = model.save(tmp_path)
    assert path.with_suffix(".json").exists()
    generated = datetime(2026, 9, 26)
    again = _predict(DailyModel.load(path), history, generated_at=generated)
    assert again.equals(_predict(model, history, generated_at=generated))


def test_unknown_history_yields_an_empty_valid_forecast(model):
    empty = _raw(date(2026, 1, 1), date(2026, 1, 2))
    forecast = _predict(model, empty)
    assert forecast.height == 0


def test_serving_uses_the_winning_baselines_with_provenance(model, history):
    from curtamap.previsao.features import build_features
    from curtamap.previsao.modelo import SERVING, forecast_mapping

    forecast = _predict(model, history)
    assert SERVING["eolica"]["volume"] == "historico"
    wind = forecast.filter(pl.col("fonte") == "eolica")
    solar = forecast.filter(pl.col("fonte") == "fotovoltaica")
    assert wind["tipo_saida_volume"].unique().to_list() == ["baseline_historico_28d"]
    assert solar["tipo_saida_volume"].unique().to_list() == ["modelo"]
    assert set(forecast["tipo_saida_causa"].drop_nulls().unique()) <= {
        "baseline_usina_28d",
        "baseline_estado_7d",
    }
    base = base_from_history(history.filter(pl.col("din_instante") < CUTOFF))
    features = build_features(base, forecast_mapping(T0, CUTOFF, CAL)).filter(
        pl.col("fonte") == "eolica"
    )
    joined = wind.with_columns(pl.col("tau").dt.date().alias("dia")).join(
        features.with_columns(
            (
                pl.col("dia").cast(pl.Datetime("us"))
                + pl.duration(minutes=30 * pl.col("slot").cast(pl.Int64))
            ).alias("tau")
        ),
        on=["fonte", "id_ons", "tau"],
    )
    assert joined.height == wind.height
    assert (joined["volume_esperado_mwmed"] - joined["vol_hist_28d"]).abs().max() < 1e-4
    with_plant = joined.filter(pl.col("tipo_saida_causa") == "baseline_usina_28d")
    assert with_plant.height > 0
    mode = with_plant.select(
        pl.concat_list("causa_rel_28d", "causa_cnf_28d", "causa_ene_28d")
        .list.arg_max()
        .replace_strict({0: "REL", 1: "CNF", 2: "ENE"})
    ).to_series()
    assert (with_plant["causa_prevista"] == mode).all()


def test_served_baseline_volume_stays_inside_the_p10_p90_band():
    from curtamap.previsao.modelo import apply_serving

    rows = pl.DataFrame(
        {
            "volume_esperado_mwmed": [5.0, 5.0],
            "volume_p10_mwmed": [2.0, 2.0],
            "volume_p90_mwmed": [8.0, 8.0],
            "vol_hist_28d": [12.0, 1.0],
        }
    )
    served = apply_serving(rows, {"volume": "historico"})
    assert served["volume_esperado_mwmed"].to_list() == [12.0, 1.0]
    assert served["volume_p90_mwmed"].to_list() == [12.0, 8.0]
    assert served["volume_p10_mwmed"].to_list() == [2.0, 1.0]
