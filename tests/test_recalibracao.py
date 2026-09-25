from datetime import datetime, timedelta

import numpy as np
import polars as pl
import pytest

from curtamap.recalibracao import bias_factor_refit, rolling_refit, sigmoid_refit

START = datetime(2025, 5, 1)


def _frame(days: int = 35, *, lag_hours: int = 38, eligible: bool = True) -> pl.DataFrame:
    t0 = [START + timedelta(days=d) for d in range(days)]
    return pl.DataFrame(
        {
            "t0": t0,
            "tau": [t + timedelta(hours=12) for t in t0],
            "target_available_at": [t + timedelta(hours=12 + lag_hours) for t in t0],
            "eligible_history": [eligible] * days,
            "target": [float(d) for d in range(days)],
            "raw": [0.5] * days,
            "prediction": [1.0] * days,
        }
    )


def _recording_fit(calls: list[pl.DataFrame]):
    def fit(window: pl.DataFrame):
        calls.append(window)
        return lambda week: np.full(week.height, float(len(calls)) + 1)

    return fit


def test_semana_zero_mantem_previsao_congelada_e_janela_respeita_liberacao():
    calls: list[pl.DataFrame] = []
    out = rolling_refit(_frame(), START, _recording_fit(calls), min_days=1)
    np.testing.assert_array_equal(out[:7], 1.0)
    first = calls[0]
    refresh = START + timedelta(days=7)
    assert (first["target_available_at"] <= refresh).all()
    assert (first["t0"] + timedelta(hours=24) <= refresh).all()
    # Só os t0 dos dias 0..4 têm rótulo liberado até o dia 7 (50 h depois de t0).
    assert first.height == 5
    np.testing.assert_array_equal(out[7:14], 2.0)
    np.testing.assert_array_equal(out[28:], 5.0)


def test_janela_limita_a_28_dias_antes_do_reajuste():
    calls: list[pl.DataFrame] = []
    rolling_refit(_frame(70), START, _recording_fit(calls), min_days=1)
    last_refresh = START + timedelta(days=63)
    assert calls[-1]["t0"].min() >= last_refresh - timedelta(days=28)


def test_janela_curta_mantem_ajuste_anterior():
    calls: list[pl.DataFrame] = []
    out = rolling_refit(_frame(21), START, _recording_fit(calls), min_days=7)
    # Em R = dia 7 só há 5 dias rotulados: fica o congelado; em R = dia 14 já há 12.
    np.testing.assert_array_equal(out[7:14], 1.0)
    np.testing.assert_array_equal(out[14:], 2.0)
    assert len(calls) == 1


def test_linhas_sem_historico_elegivel_nao_mudam_nem_entram_na_janela():
    frame = _frame().with_columns(pl.Series("eligible_history", [d % 2 == 0 for d in range(35)]))
    calls: list[pl.DataFrame] = []
    out = rolling_refit(frame, START, _recording_fit(calls), min_days=1)
    ineligible = ~frame["eligible_history"].to_numpy()
    np.testing.assert_array_equal(out[ineligible], 1.0)
    assert all(c["eligible_history"].all() for c in calls)


def test_ajuste_nulo_reproduz_a_previsao_salva():
    frame = _frame()
    out = rolling_refit(frame, START, lambda window: None, min_days=1)
    np.testing.assert_array_equal(out, frame["prediction"].to_numpy())


def test_ordem_das_linhas_e_preservada():
    frame = _frame().reverse()
    out = rolling_refit(frame, START, lambda w: lambda week: week["target"].to_numpy(), min_days=1)
    late = frame["t0"] >= START + timedelta(days=7)
    np.testing.assert_array_equal(out[late.to_numpy()], frame.filter(late)["target"].to_numpy())


def test_fator_de_vies_corrige_nivel_e_respeita_limites():
    window = pl.DataFrame({"prediction": [1.0, 1.0], "target": [1.5, 1.5]})
    week = pl.DataFrame({"prediction": [2.0, 4.0]})
    np.testing.assert_allclose(bias_factor_refit()(window)(week), [3.0, 6.0])
    high = pl.DataFrame({"prediction": [1.0], "target": [10.0]})
    np.testing.assert_allclose(bias_factor_refit()(high)(week), [4.0, 8.0])
    zero = pl.DataFrame({"prediction": [0.0], "target": [3.0]})
    assert bias_factor_refit()(zero) is None


def test_sigmoide_reajustada_acompanha_nova_prevalencia():
    rng = np.random.default_rng(0)
    raw = rng.uniform(0, 1, 5_000)
    target = (rng.uniform(0, 1, raw.size) < np.clip(raw * 1.6, 0, 1)).astype(float)
    window = pl.DataFrame({"raw": raw, "target": target})
    transform = sigmoid_refit(seed=42)(window)
    predicted = transform(window)
    assert predicted.mean() == pytest.approx(target.mean(), abs=0.01)
    assert sigmoid_refit(seed=42)(window.with_columns(target=pl.lit(0.0))) is None
