import polars as pl

from curtamap.previsao.relatorio import decide


def _table(model_ap, base_ap):
    n = len(model_ap)
    return pl.DataFrame(
        {
            "fonte": ["eolica"] * n,
            "ap_modelo": model_ap,
            "ap_historico": base_ap,
            "ap_mesmo_slot_ultimo_dia": [0.1] * n,
            "ap_ultimo_valor": [0.1] * n,
        }
    )


def test_model_needs_mean_win_and_six_of_eight_months():
    decision = {
        r["celula"]: r
        for r in decide(_table([0.9] * 6 + [0.1] * 2, [0.5] * 8)).iter_rows(named=True)
    }
    assert set(decision) == {"corte"}
    assert decision["corte"]["adota_modelo"] is True
    assert decision["corte"]["meses_vencidos"] == 6


def test_model_winning_five_months_is_not_adopted():
    decision = decide(_table([0.9] * 5 + [0.4] * 3, [0.5] * 8)).row(0, named=True)
    assert decision["adota_modelo"] is False
    assert decision["melhor_baseline"] == "historico"
