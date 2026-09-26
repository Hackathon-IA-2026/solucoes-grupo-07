from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from curtamap.previsao.faixas import (
    agregar_diario,
    cap_91d,
    faixa,
    fracao,
    frequencia_excedencia,
    monotonizar,
    probabilidades_faixas,
    rotulo_diario,
    rps,
    tercis,
)

L = date(2026, 3, 31)


def _base(values: dict[date, float], id_ons="A", fonte="eolica") -> pl.DataFrame:
    return pl.DataFrame(
        {
            "fonte": [fonte] * len(values),
            "id_ons": [id_ons] * len(values),
            "dia": list(values),
            "referencia": list(values.values()),
        },
        schema={"fonte": pl.String, "id_ons": pl.String, "dia": pl.Date, "referencia": pl.Float32},
    )


def test_cap_91d_janela_termina_em_l_e_exclui_dias_fora():
    values = {L - timedelta(days=i): 10.0 for i in range(91)}
    values[L - timedelta(days=91)] = 1000.0  # fora de (L − 91, L]
    values[L + timedelta(days=1)] = 1000.0  # futuro: vazamento se entrar
    out = cap_91d(_base(values), [L])
    assert out.columns == ["fonte", "id_ons", "ultimo_dia", "cap_91d"]
    assert out["cap_91d"].to_list() == [pytest.approx(10.0)]


def test_cap_91d_e_o_p99_da_janela():
    values = {L - timedelta(days=i): float(i) for i in range(91)}
    out = cap_91d(_base(values), [L])
    assert out["cap_91d"].item() == pytest.approx(np.quantile(np.arange(91.0), 0.99))


def test_cap_91d_usina_sem_dado_em_l_nao_desloca_a_janela():
    # Último dado 10 dias antes de L: a janela continua (L − 91, L], não (d − 91, d].
    values = {L - timedelta(days=10): 5.0, L - timedelta(days=95): 1000.0}
    out = cap_91d(_base(values), [L])
    assert out["cap_91d"].item() == pytest.approx(5.0)


def test_cap_91d_sem_historico_e_nulo_e_nao_zero():
    values = {L - timedelta(days=200): 5.0}
    out = cap_91d(_base(values), [L])
    assert out["cap_91d"].to_list() == [None]


def test_cap_91d_ignora_referencia_nula_e_separa_fonte():
    base = pl.concat(
        [
            _base({L: 8.0, L - timedelta(days=1): None}),
            _base({L: 99.0}, fonte="fotovoltaica"),
        ]
    )
    out = cap_91d(base, [L]).sort("fonte")
    assert out["cap_91d"].to_list() == [pytest.approx(8.0), pytest.approx(99.0)]


def test_fracao_nao_negativa_e_nula_sem_capacidade():
    frame = pl.DataFrame({"v": [5.0, -1.0, 5.0, 5.0, None], "cap": [10.0, 10.0, None, 0.0, 10.0]})
    out = frame.select(fracao(pl.col("v"), pl.col("cap"))).to_series().to_list()
    assert out == [pytest.approx(0.5), 0.0, None, None, None]


def _slots(n: int, volume: float, cap: float | None = 10.0, dia=L) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "fonte": ["eolica"] * n,
            "id_ons": ["A"] * n,
            "dia": [dia] * n,
            "slot": list(range(n)),
            "y_volume": [volume] * n,
            "cap_91d": [cap] * n,
        }
    )


def test_rotulo_diario_e_energia_sobre_cap_vezes_24h():
    out = rotulo_diario(_slots(48, 2.0))
    # energia = 48 × 2 MWmed × 0,5 h = 48 MWh; cap × 24 h = 240 MWh.
    assert out["fracao_dia"].item() == pytest.approx(0.2)
    assert out["slots_validos"].item() == 48


def test_rotulo_diario_exige_48_slots_com_volume():
    incompleto = _slots(47, 2.0)
    com_nulo = _slots(48, 2.0).with_columns(
        pl.when(pl.col("slot") == 3).then(None).otherwise(pl.col("y_volume")).alias("y_volume")
    )
    assert rotulo_diario(incompleto)["fracao_dia"].to_list() == [None]
    assert rotulo_diario(com_nulo)["fracao_dia"].to_list() == [None]


def test_rotulo_diario_sem_cap_e_nulo():
    assert rotulo_diario(_slots(48, 2.0, cap=None))["fracao_dia"].to_list() == [None]


def test_faixa_limites_e_nulo():
    frame = pl.DataFrame({"f": [0.0, 1e-6, 0.1, 0.10001, 0.3, 0.30001, None]})
    out = frame.select(faixa(pl.col("f"), 0.1, 0.3)).to_series().to_list()
    assert out == [0, 1, 1, 2, 2, 3, None]


def test_tercis_usa_so_fracoes_positivas_e_arredonda():
    values = np.array([0.0] * 1000 + list(np.linspace(0.01, 0.99, 99)))
    k1, k2 = tercis(values, casas=2)
    assert (k1, k2) == (
        round(float(np.quantile(values[values > 0], 1 / 3)), 2),
        round(float(np.quantile(values[values > 0], 2 / 3)), 2),
    )
    assert 0 < k1 < k2


def test_tercis_rejeita_limiares_colapsados():
    with pytest.raises(ValueError):
        tercis(np.array([0.001, 0.002, 0.003]), casas=2)


def test_monotonizar_impoe_excedencia_nao_crescente():
    p = np.array([[0.5, 0.6, 0.2], [0.9, 0.3, 0.4]])
    out = monotonizar(p)
    assert out.tolist() == [[0.5, 0.5, 0.2], [0.9, 0.3, 0.3]]


def test_probabilidades_faixas_somam_um_e_nao_negativas():
    p = monotonizar(np.array([[0.8, 0.5, 0.1], [0.0, 0.0, 0.0]]))
    out = probabilidades_faixas(p)
    assert out.shape == (2, 4)
    assert np.allclose(out.sum(axis=1), 1.0)
    assert (out >= 0).all()
    assert out[0].tolist() == pytest.approx([0.2, 0.3, 0.4, 0.1])


def test_rps_perfeito_e_pior_caso():
    y = np.array([0, 3])
    perfeito = np.array([[1.0, 0, 0, 0], [0, 0, 0, 1.0]])
    pior = np.array([[0, 0, 0, 1.0], [1.0, 0, 0, 0]])
    assert rps(perfeito, y) == pytest.approx(0.0)
    assert rps(pior, y) == pytest.approx(1.0)


def test_frequencia_excedencia_usa_so_dias_ate_l():
    days = [L - timedelta(days=i) for i in range(40)]
    labels = pl.DataFrame(
        {
            "fonte": ["eolica"] * 41,
            "id_ons": ["A"] * 41,
            "dia": [*days, L + timedelta(days=2)],
            "fracao": [0.5 if i < 7 else 0.0 for i in range(40)] + [0.9],
        }
    )
    mapping = pl.DataFrame({"dia": [L + timedelta(days=2)], "ultimo_dia": [L]})
    out = frequencia_excedencia(labels, mapping, k=0.1, janela=28, chave=["fonte", "id_ons"])
    assert out.columns == ["fonte", "id_ons", "dia", "freq", "ultimo"]
    # 7 de 28 dias acima de k em (L − 28, L]; o dia-alvo (0,9) não entra; L está acima.
    assert out["freq"].item() == pytest.approx(7 / 28)
    assert out["ultimo"].item() == 1.0


def test_frequencia_excedencia_ignora_rotulo_nulo_e_sem_historico_e_nulo():
    labels = pl.DataFrame(
        {
            "fonte": ["eolica"] * 2,
            "id_ons": ["A"] * 2,
            "dia": [L, L - timedelta(days=1)],
            "fracao": [None, 0.5],
        },
        schema_overrides={"fracao": pl.Float64},
    )
    mapping = pl.DataFrame(
        {"dia": [L + timedelta(days=2), date(2027, 1, 1)], "ultimo_dia": [L, date(2026, 12, 1)]}
    )
    out = frequencia_excedencia(labels, mapping, k=0.1, janela=28, chave=["fonte", "id_ons"])
    out = out.sort("dia")
    assert out["freq"].to_list() == [pytest.approx(1.0), None]
    assert out["ultimo"].to_list() == [None, None]


def test_agregar_diario_media_maximo_e_colunas_diarias():
    rows = pl.DataFrame(
        {
            "fonte": ["eolica"] * 3,
            "id_ons": ["A"] * 3,
            "dia": [L] * 3,
            "slot": [0, 1, 2],
            "hist_7d": [0.0, 0.5, None],
            "idade": [2, 2, 2],
        }
    )
    out = agregar_diario(rows, por_slot=["hist_7d"], diarias=["idade"])
    assert out.columns == ["fonte", "id_ons", "dia", "hist_7d_media", "hist_7d_max", "idade"]
    assert out.row(0)[3:] == (pytest.approx(0.25), pytest.approx(0.5), 2)
