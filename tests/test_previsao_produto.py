from datetime import date

import polars as pl
from test_previsao_modelo import _raw

from zelo.forecasting import SameSlotRecentBaseline
from zelo.previsao.calendario import load_calendar
from zelo.previsao.features import base_from_history, release_map
from zelo.previsao.modelo import DailyForecaster, fit
from zelo.previsao.produto import HISTORY_DAYS, latest_model_path, product_predictor


def test_without_a_trained_model_the_product_falls_back_to_the_baseline(tmp_path):
    assert latest_model_path(tmp_path) is None
    assert isinstance(product_predictor(tmp_path), SameSlotRecentBaseline)


def test_older_artifacts_with_volume_are_not_served(tmp_path):
    (tmp_path / "previsao").mkdir()
    (tmp_path / "previsao" / "diario_hgb_v3_2026-08-30.joblib").write_bytes(b"")
    (tmp_path / "previsao" / "diario_hgb_v1_2026-08-30.joblib").write_bytes(b"")
    assert latest_model_path(tmp_path) is None


def test_product_uses_the_most_recent_trained_model(tmp_path):
    history = _raw(date(2026, 3, 1), date(2026, 4, 30))
    days = pl.date_range(date(2026, 3, 1), date(2026, 4, 30), eager=True).to_list()
    base = base_from_history(history)
    cal = load_calendar()
    fit(base, release_map(days, cal), date(2026, 4, 10)).save(tmp_path / "previsao")
    fit(base, release_map(days, cal), date(2026, 4, 20)).save(tmp_path / "previsao")
    predictor = product_predictor(tmp_path)
    assert isinstance(predictor, DailyForecaster)
    assert predictor.model_id == "diario_ocorrencia_v1_2026-04-20"
    assert HISTORY_DAYS >= 92
