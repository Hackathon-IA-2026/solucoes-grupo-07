from datetime import date, datetime

import polars as pl
from test_previsao_modelo import _raw

from curtamap.contracts import HORIZONS, validate_forecast
from curtamap.previsao.calendario import load_calendar
from curtamap.previsao.features import base_from_history, release_map
from curtamap.previsao.modelo import fit
from curtamap.previsao.reproducao import replay

CAL = load_calendar()


def test_replay_emits_daily_at_20h_with_observed_truth_alongside():
    history = _raw(date(2026, 3, 1), date(2026, 5, 31))
    days = pl.date_range(date(2026, 3, 1), date(2026, 5, 20), eager=True).to_list()
    model = fit(base_from_history(history), release_map(days, CAL), date(2026, 5, 20))
    result = replay(model, history, date(2026, 5, 26), date(2026, 5, 28), CAL)
    assert result["t0"].unique().sort().to_list() == [
        datetime(2026, 5, 26),
        datetime(2026, 5, 27),
        datetime(2026, 5, 28),
    ]
    assert result.height == 3 * 3 * HORIZONS
    validate_forecast(result)
    first = result.filter(pl.col("t0") == datetime(2026, 5, 26))
    assert first["emitido_em"].unique().to_list() == [datetime(2026, 5, 25, 20)]
    # Segunda 25/05 às 20h: sexta, sábado e domingo liberados; conhece até 24/05.
    assert first["corte_dados"].unique().to_list() == [datetime(2026, 5, 25)]
    assert result["observado_corte"].null_count() == 0
    assert result["observado_volume_mwmed"].null_count() == 0
