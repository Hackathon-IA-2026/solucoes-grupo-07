from datetime import date

import numpy as np
import polars as pl
import pytest
from test_previsao_modelo import _raw

from curtamap.previsao.avaliacao import backtest_month, choose_threshold, metrics
from curtamap.previsao.calendario import load_calendar
from curtamap.previsao.features import base_from_history


def test_threshold_maximizes_f1():
    y = np.array([1, 1, 0, 0, 1, 0])
    p = np.array([0.9, 0.8, 0.7, 0.2, 0.6, 0.1])
    # Limiar 0,6 alerta 4 linhas com 3 acertos: F1 = 6/7, o máximo possível aqui.
    assert choose_threshold(y, p) == pytest.approx(0.6)


@pytest.fixture(scope="module")
def backtest():
    base = base_from_history(_raw(date(2026, 3, 1), date(2026, 5, 31)))
    return backtest_month(base, date(2026, 5, 1), load_calendar())


def test_backtest_trains_before_the_month_and_scores_every_labelled_row(backtest):
    assert backtest["treino_ate"].unique().to_list() == [date(2026, 4, 29)]
    assert backtest["dia"].min() == date(2026, 5, 1)
    assert backtest["dia"].max() == date(2026, 5, 31)
    assert backtest["y_corte"].null_count() == 0
    assert backtest.height == 31 * 48 * 3


def test_metrics_compare_model_and_baselines_on_the_same_rows(backtest):
    table = metrics(backtest, {"eolica": 0.5, "fotovoltaica": 0.5})
    assert table["fonte"].to_list() == ["eolica", "fotovoltaica"]
    row = table.row(0, named=True)
    for name in ("modelo", "historico", "mesmo_slot_ultimo_dia", "ultimo_valor"):
        assert 0 <= row[f"ap_{name}"] <= 1
    assert {"f1_usina_28d", "f1_estado_7d", "recall_alerta", "precisao_alerta"} <= set(row)
    assert not any(c.startswith(("wape_", "mae_", "cobertura_p10", "f1_modelo")) for c in row)
    assert pl.DataFrame(table).height == 2


def test_threshold_scores_whole_tie_groups():
    # O alerta usa p >= limiar, então um limiar inclui o grupo empatado inteiro.
    # Limiar 0,5 alerta 8 linhas com 2 acertos (F1 = 0,40); limiar 0,9 dá F1 = 0,67.
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0])
    p = np.array([0.9, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.1])
    assert choose_threshold(y, p) == pytest.approx(0.9)
