from datetime import date

import numpy as np
import polars as pl
import pytest
from test_previsao_modelo import CAL, CUTOFF, END, START, T0, _raw

from curtamap.contracts import validate_forecast
from curtamap.previsao.faixas_servico import features_faixas, fit_v3
from curtamap.previsao.features import base_from_history, release_map
from curtamap.previsao.modelo import DailyForecaster, DailyModel, fit
from curtamap.previsao.produto import HISTORY_DAYS, latest_model_path

# Limiares de teste compatíveis com o histórico sintético (fração de 0,3 na meia-hora).
FAIXAS = {
    "meia_hora": {
        "eolica": {"k0": 0.0, "k1": 0.1, "k2": 0.25},
        "fotovoltaica": {"k0": 0.0, "k1": 0.1, "k2": 0.25},
    },
    "diario": {
        "eolica": {"k0": 0.0, "k1": 0.01, "k2": 0.04},
        "fotovoltaica": {"k0": 0.0, "k1": 0.01, "k2": 0.04},
    },
}
BANDS = ["p_faixa_sem_corte", "p_faixa_leve", "p_faixa_moderada", "p_faixa_severa"]
DAY_BANDS = [c.replace("p_faixa_", "p_faixa_dia_") for c in BANDS]


@pytest.fixture(scope="module")
def history() -> pl.DataFrame:
    return _raw()


@pytest.fixture(scope="module")
def base(history) -> pl.DataFrame:
    return base_from_history(history)


@pytest.fixture(scope="module")
def mapping() -> pl.DataFrame:
    return release_map(pl.date_range(START, END, eager=True).to_list(), CAL)


@pytest.fixture(scope="module")
def model_v3(base, mapping) -> DailyModel:
    return fit_v3(base, mapping, date(2026, 5, 15), FAIXAS, CAL)


def test_model_id_comes_from_the_version_in_the_metadata():
    assert DailyModel({}, {"versao": "diario_hgb_v3", "treino_ate": "2026-08-30"}).model_id == (
        "diario_hgb_v3_2026-08-30"
    )
    # Artefato v1 congelado não tinha a chave explícita em todos os usos: continua v1.
    assert DailyModel({}, {"treino_ate": "2026-08-30"}).model_id == "diario_hgb_v1_2026-08-30"


def test_product_prefers_v3_then_v1_then_baseline(tmp_path):
    folder = tmp_path / "previsao"
    folder.mkdir()
    assert latest_model_path(tmp_path) is None
    (folder / "diario_hgb_v1_2026-08-30.joblib").touch()
    assert latest_model_path(tmp_path).name == "diario_hgb_v1_2026-08-30.joblib"
    (folder / "diario_hgb_v3_2026-08-30.joblib").touch()
    assert latest_model_path(tmp_path).name == "diario_hgb_v3_2026-08-30.joblib"
    assert HISTORY_DAYS >= 130


def test_v3_forecast_adds_band_probabilities_with_provenance(model_v3, history):
    forecast = DailyForecaster(model_v3, CAL).predict(history, T0, CUTOFF)
    assert validate_forecast(forecast).equals(forecast)
    assert forecast["modelo_id"].unique().to_list() == ["diario_hgb_v3_2026-05-15"]
    for columns in (BANDS, DAY_BANDS):
        values = forecast.select(columns).to_numpy()
        assert np.allclose(values.sum(axis=1), 1.0)
        assert (values >= -1e-12).all()
    # k₀ da meia-hora é a ocorrência servida: sem corte = 1 − p_corte.
    assert np.allclose(forecast["p_faixa_sem_corte"], 1 - forecast["p_corte"])
    assert set(forecast["faixa_provavel"].unique()) <= {"sem_corte", "leve", "moderada", "severa"}
    daily = forecast.group_by("id_ons", pl.col("tau").dt.date()).agg(pl.col(DAY_BANDS).n_unique())
    assert (daily.select(DAY_BANDS).to_numpy() == 1).all()
    provenance = dict(forecast.select("fonte", "tipo_saida_faixas").unique().iter_rows())
    assert provenance == {
        "eolica": "k0:modelo,k1:historico,k2:historico",
        "fotovoltaica": "k0:modelo,k1:modelo,k2:modelo",
    }


def test_v1_model_without_bands_still_predicts(base, mapping, history):
    model = fit(base, mapping, date(2026, 5, 15))
    # Instância desserializada de um artefato v1: não tem o atributo `faixas`.
    model.__dict__.pop("faixas", None)
    forecast = DailyForecaster(model, CAL).predict(history, T0, CUTOFF)
    assert validate_forecast(forecast).equals(forecast)
    assert not any(c.startswith("p_faixa") for c in forecast.columns)
    assert forecast["modelo_id"].unique().to_list() == ["diario_hgb_v1_2026-05-15"]


def test_band_features_use_only_data_up_to_the_last_released_day(base):
    target = release_map([date(2026, 5, 20)], CAL)
    last = target["ultimo_dia"].item()
    changed = base.with_columns(
        pl.when(pl.col("dia") > last).then(pl.col("volume") * 3).otherwise(pl.col("volume"))
    )
    slot_a, day_a = features_faixas(base.filter(pl.col("dia") <= last), target, FAIXAS, CAL)
    slot_b, day_b = features_faixas(changed, target, FAIXAS, CAL)
    assert slot_a.sort(slot_a.columns).equals(slot_b.sort(slot_b.columns))
    assert day_a.sort(day_a.columns).equals(day_b.sort(day_b.columns))
    assert {"cap_91d", "exc_hist_k1", "exc_ult_k2"} <= set(slot_a.columns)
    assert slot_a["cap_91d"].drop_nulls().to_list() == [pytest.approx(40.0)] * slot_a.height


def test_training_labels_for_bands_stop_at_the_last_label_day(base, mapping, model_v3):
    info = model_v3.metadata["faixas"]
    assert info["treino_ate"] == "2026-05-15"
    assert info["servico"]["meia_hora"]["eolica"] == ["modelo", "historico", "historico"]
    later = base.with_columns(
        pl.when(pl.col("dia") > date(2026, 5, 15))
        .then(0.0)
        .otherwise(pl.col("volume"))
        .alias("volume")
    )
    again = fit_v3(later, mapping, date(2026, 5, 15), FAIXAS, CAL)
    row = release_map([date(2026, 5, 27)], CAL)
    slot, day = features_faixas(base.filter(pl.col("dia") <= date(2026, 5, 25)), row, FAIXAS, CAL)
    assert model_v3.faixas.predict_daily(day).equals(again.faixas.predict_daily(day))
