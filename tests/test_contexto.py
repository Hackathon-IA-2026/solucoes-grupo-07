import math
import pickle
from datetime import datetime, timedelta

import numpy as np
import polars as pl
import pytest

from curtamap.contexto import (
    BASELINE_FEATURES,
    BOOLEAN,
    CATEGORICAL,
    NUMERIC,
    SYSTEMIC,
    Encoder,
    baseline_cause,
    historico_offset,
    predict_causa,
    predict_corte,
    probability_with_offset,
    systemic_state,
)


def _frame(ids: list[str | None]) -> pl.DataFrame:
    rows = len(ids)
    data = {name: [1.0] * rows for name in (*NUMERIC, *BASELINE_FEATURES)}
    data.update({name: [True] * rows for name in BOOLEAN})
    data.update({name: ["x"] * rows for name in CATEGORICAL})
    data["id_ons"] = ids
    return pl.DataFrame(data)


def test_categoria_desconhecida_e_ausente_viram_nan():
    encoder = Encoder().fit(_frame(["A", "B"]))
    matrix = encoder.matrix(_frame(["B", "NOVA", None]))
    column = encoder.columns.index("id_ons")
    assert matrix[0, column] == 1.0
    assert math.isnan(matrix[1, column])
    assert math.isnan(matrix[2, column])
    assert encoder.categorical_indices == list(
        range(len(encoder.columns) - len(CATEGORICAL), len(encoder.columns))
    )


def test_drop_remove_colunas_e_mantem_categoricas_no_fim():
    encoder = Encoder(drop=("tau_month", "tau_day_of_year")).fit(_frame(["A"]))
    assert "tau_month" not in encoder.columns
    assert encoder.matrix(_frame(["A"])).shape == (1, len(encoder.columns))
    assert encoder.columns[-len(CATEGORICAL) :] == list(CATEGORICAL)


def test_drop_tambem_remove_categoricas():
    encoder = Encoder(drop=("id_ons", "last_cause")).fit(_frame(["A"]))
    assert "id_ons" not in encoder.columns
    assert "last_cause" not in encoder.columns
    assert encoder.matrix(_frame(["A"])).shape == (1, len(encoder.columns))
    assert encoder.categorical_indices == list(
        range(len(encoder.columns) - len(CATEGORICAL) + 2, len(encoder.columns))
    )


def test_encoder_antigo_sem_lista_de_categoricas_mantem_todas():
    encoder = Encoder().fit(_frame(["A"]))
    del encoder.__dict__["categorical"]
    assert encoder.columns[-len(CATEGORICAL) :] == list(CATEGORICAL)
    assert encoder.matrix(_frame(["A"])).shape == (1, len(encoder.columns))


def test_encoder_serializavel_fora_do_script():
    encoder = Encoder().fit(_frame(["A"]))
    restored = pickle.loads(pickle.dumps(encoder))
    np.testing.assert_array_equal(restored.matrix(_frame(["A"])), encoder.matrix(_frame(["A"])))


def test_offset_e_logit_limitado_do_historico():
    frame = pl.DataFrame({"b_historico_prob_positive": [0.5, 0.0, 1.0, None]})
    offset = historico_offset(frame, "corte_positivo")
    assert offset[0] == pytest.approx(0.0)
    assert np.isfinite(offset).all()
    assert offset[1] < -9 and offset[2] > 9
    assert offset[3] == pytest.approx(0.0)


class _Raw:
    def predict(self, matrix, raw_score=False):
        assert raw_score
        return np.zeros(len(matrix))


def test_probabilidade_com_offset_reproduz_o_historico_sem_correcao():
    frame = pl.DataFrame({"b_historico_prob_positive": [0.2, 0.7]})
    probability = probability_with_offset(
        _Raw(), np.zeros((2, 1)), historico_offset(frame, "corte_positivo")
    )
    np.testing.assert_allclose(probability, [0.2, 0.7])


def test_estado_sistemico_agrega_uma_linha_por_usina_no_mesmo_t0():
    t0 = datetime(2025, 5, 1, 20)
    rows = []
    for id_ons, sub, last, freq in (
        ("A", "NE", True, 0.5),
        ("B", "NE", False, 0.1),
        ("C", "NE", None, 0.3),
        ("D", "S", True, 1.0),
    ):
        for horizon in (1, 2, 3):  # vários tau por usina não podem pesar mais
            rows.append(
                {
                    "fonte": "eolica",
                    "id_ons": id_ons,
                    "id_subsistema": sub,
                    "t0": t0,
                    "horizon": horizon,
                    "last_positive": last,
                    "positive_frequency_7d": freq,
                    "true_positive": True,  # verdade futura nunca entra no agregado
                }
            )
    rows.append({**rows[0], "t0": t0 + timedelta(minutes=30), "last_positive": False})
    state = systemic_state(pl.DataFrame(rows).lazy()).collect().sort("id_subsistema", "t0")
    assert state.columns == ["fonte", "id_subsistema", "t0", *SYSTEMIC]
    ne = state.filter((pl.col("id_subsistema") == "NE") & (pl.col("t0") == t0)).row(0, named=True)
    assert ne["sys_last_positive_share"] == pytest.approx(0.5)  # A e B; C nulo fica fora
    assert ne["sys_positive_frequency_7d_mean"] == pytest.approx(0.3)
    later = state.filter(pl.col("t0") == t0 + timedelta(minutes=30)).row(0, named=True)
    assert later["sys_last_positive_share"] == 0.0
    assert state.filter(pl.col("id_subsistema") == "S")["sys_last_positive_share"].item() == 1.0


def test_encoder_aceita_features_extras_densas():
    frame = _frame(["A"]).with_columns(pl.lit(0.25).alias("sys_last_positive_share"))
    encoder = Encoder(extra=("sys_last_positive_share",)).fit(frame)
    column = encoder.columns.index("sys_last_positive_share")
    assert column < encoder.categorical_indices[0]
    assert encoder.matrix(frame)[0, column] == pytest.approx(0.25)


class _Proba:
    def __init__(self, proba, classes=(False, True)):
        self.proba = np.asarray(proba, dtype=float)
        self.classes_ = np.asarray(classes)

    def predict_proba(self, matrix):
        assert len(matrix) == len(self.proba)
        return self.proba


class _Half:
    def predict(self, scores):
        return np.asarray(scores) * 0.5


def _inference_frame(eligible: list[bool]) -> pl.DataFrame:
    rows = len(eligible)
    frame = _frame(["A"] * rows).with_columns(
        pl.Series("eligible_history", eligible),
        pl.Series("b_historico_prob_positive", [0.9] * rows),
        pl.Series("b_historico_cause_REL", [0.2] * rows),
        pl.Series("b_historico_cause_CNF", [0.2] * rows),
        pl.Series("b_historico_cause_ENE", [0.1] * rows),
    )
    return frame


def test_inferencia_de_corte_calibra_elegiveis_e_usa_historico_nos_demais():
    frame = _inference_frame([True, False])
    bundle = {
        "model": _Proba([[0.4, 0.6], [0.2, 0.8]]),
        "encoder": Encoder().fit(frame),
        "calibrator": _Half(),
    }
    np.testing.assert_allclose(predict_corte(bundle, frame), [0.3, 0.9])


def test_inferencia_de_causa_usa_argmax_e_historico_com_desempate_fixo():
    frame = _inference_frame([True, False])
    bundle = {
        "model": _Proba([[0.1, 0.7, 0.2], [0.8, 0.1, 0.1]], classes=("CNF", "ENE", "REL")),
        "encoder": Encoder().fit(frame),
    }
    labels, proba = predict_causa(bundle, frame)
    # Linha inelegível: empate CNF = REL no historico resolve para CNF (ordem CNF, ENE, REL).
    assert labels.tolist() == ["ENE", "CNF"]
    assert proba.shape == (2, 3)
    assert baseline_cause(frame, "historico").tolist() == ["CNF", "CNF"]
