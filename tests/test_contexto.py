import math
import pickle

import numpy as np
import polars as pl
import pytest

from curtamap.contexto import (
    BASELINE_FEATURES,
    BOOLEAN,
    CATEGORICAL,
    NUMERIC,
    Encoder,
    historico_offset,
    probability_with_offset,
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
