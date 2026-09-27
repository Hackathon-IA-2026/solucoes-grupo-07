from datetime import date

import polars as pl
import pytest

from zelo.previsao.impacto import (
    FIRST_START,
    LAST_START,
    block_table,
    choose,
    coverage,
    stop_loss_mwh,
)


def _loss(geracao, referencia, limitada, fraction):
    frame = pl.DataFrame({"geracao": [geracao], "referencia": [referencia], "limitada": [limitada]})
    return frame.select(stop_loss_mwh(fraction))[0, 0]


def test_parada_sem_restricao_tira_a_fracao_da_geracao():
    assert _loss(100.0, 102.0, False, 0.1) == pytest.approx(5.0)


def test_parada_sob_teto_folgado_nao_perde_nada():
    # teto de 60 MW, capacidade restante 0,9 × 120 = 108 MW
    assert _loss(60.0, 120.0, True, 0.1) == 0.0


def test_parada_sob_teto_apertado_perde_so_o_que_falta():
    # teto de 115 MW, capacidade restante 108 MW: perde 7 MW por meia-hora
    assert _loss(115.0, 120.0, True, 0.1) == pytest.approx(3.5)


@pytest.mark.parametrize("fraction", [0.0, -0.1, 1.5])
def test_fracao_invalida(fraction):
    with pytest.raises(ValueError):
        stop_loss_mwh(fraction)


def _day(p_corte, limited_slots, source="eolica"):
    slots = list(range(48))
    return pl.DataFrame(
        {
            "fonte": source,
            "id_ons": "U1",
            "dia": date(2026, 9, 1),
            "slot": pl.Series(slots, dtype=pl.Int8),
            "limitada": [s in limited_slots for s in slots],
            "corte": [s in limited_slots for s in slots],
            "energia_mwh": [10.0 if s in limited_slots else 0.0 for s in slots],
            "geracao": [50.0 if s in limited_slots else 100.0 for s in slots],
            "referencia": [100.0] * 48,
            "p_corte": p_corte,
            "hist_28d": [0.0] * 48,
            "ref_hist_28d": [100.0] * 48,
        }
    )


def test_blocos_so_dentro_da_janela_e_completos():
    blocks = block_table(_day([0.0] * 48, set()), 0.1)
    assert blocks["inicio"].min() == FIRST_START
    assert blocks["inicio"].max() == LAST_START
    assert blocks.height == LAST_START - FIRST_START + 1


def test_zelo_escolhe_o_bloco_em_alerta_e_poupa_energia():
    cut = {22, 23, 24, 25}
    p = [0.9 if s in cut else 0.05 for s in range(48)]
    choices = choose(block_table(_day(p, cut), 0.1), {"eolica": 0.3})
    row = choices.row(0, named=True)
    assert row["inicio_zelo"] == 22
    assert row["zelo"] == 0.0
    assert row["oraculo"] == 0.0
    assert row["fixo_08h"] == pytest.approx(4 * 10 * 0.5)
    assert row["dia_com_alerta"]
    assert row["zelo_so_alerta"] == 0.0


def test_sem_alerta_politica_mantem_menor_potencial():
    p = [0.1] * 48
    choices = choose(block_table(_day(p, set()), 0.1), {"eolica": 0.3})
    row = choices.row(0, named=True)
    assert not row["dia_com_alerta"]
    assert row["zelo_so_alerta"] == row["menor_potencial"]


def test_cobertura_pondera_por_energia_e_conta_sem_previsao_como_nao_avisada():
    frame = pl.DataFrame(
        {
            "fonte": ["eolica"] * 4,
            "id_ons": ["U1"] * 4,
            "dia": [date(2026, 9, 1)] * 4,
            "slot": [0, 1, 2, 3],
            "corte": [True, True, False, True],
            "energia_mwh": [30.0, 10.0, 0.0, 60.0],
            "p_corte": [0.9, 0.1, 0.8, None],
            "hist_28d": [0.1, 0.9, 0.2, 0.5],
        }
    )
    row = coverage(frame, {"eolica": 0.5}).row(0, named=True)
    assert row["fracao_energia_avisada"] == pytest.approx(0.3)
    assert row["recall_meia_hora"] == pytest.approx(1 / 3)
    assert row["meias_horas_cortadas_sem_previsao"] == 1
    assert row["fracao_usina_dias_avisados"] == 1.0
    assert row["taxa_alerta"] == pytest.approx(2 / 3)
    # histórico com 2 alertas: slots 1 (0,9) e 2 (0,2) → só 10 MWh de 100
    assert row["fracao_energia_historico_mesmo_n"] == pytest.approx(0.1)
