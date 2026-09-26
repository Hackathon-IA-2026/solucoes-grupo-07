import polars as pl

from curtamap.previsao.relatorio import decide


def _table(model_ap, base_ap, model_wape, base_wape):
    n = len(model_ap)
    return pl.DataFrame(
        {
            "fonte": ["eolica"] * n,
            "ap_modelo": model_ap,
            "ap_historico": base_ap,
            "ap_mesmo_slot_ultimo_dia": [0.1] * n,
            "ap_ultimo_valor": [0.1] * n,
            "wape_modelo": model_wape,
            "wape_historico": base_wape,
            "wape_mesmo_slot_ultimo_dia": [9.0] * n,
            "wape_ultimo_valor": [9.0] * n,
            "f1_modelo": [0.5] * n,
            "f1_usina_28d": [0.6] * n,
            "f1_estado_7d": [0.1] * n,
        }
    )


def test_model_needs_mean_win_and_six_of_eight_months():
    table = _table([0.9] * 6 + [0.1] * 2, [0.5] * 8, [0.8] * 5 + [2.0] * 3, [1.0] * 8)
    decision = {r["celula"]: r for r in decide(table).iter_rows(named=True)}
    assert decision["corte"]["adota_modelo"] is True
    assert decision["corte"]["meses_vencidos"] == 6
    # Volume: menor WAPE em só 5 de 8 meses e pior na média.
    assert decision["volume"]["adota_modelo"] is False
    assert decision["volume"]["melhor_baseline"] == "historico"
    assert decision["causa"]["adota_modelo"] is False
    assert decision["causa"]["melhor_baseline"] == "usina_28d"
