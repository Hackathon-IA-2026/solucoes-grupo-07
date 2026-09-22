"""Trechos originais (commit e389332) de ``curtamap.experimental.models``, preservados como oráculo.

``transform`` codificava categorias com um laço Python por valor e ``optimize_f2_threshold``
recalculava a matriz de confusão para cada probabilidade distinta (custo quadrático). Os corpos
abaixo são cópias literais usadas apenas em testes de igualdade.
"""

from __future__ import annotations

import numpy as np
import polars as pl
from scipy import sparse


def transform(self, frame: pl.DataFrame) -> sparse.csr_matrix:
    if not self.fitted_:
        raise RuntimeError("pré-processador ainda não ajustado")
    numeric_parts: list[np.ndarray] = []
    for name in self.numeric:
        values = frame[name].cast(pl.Float64).to_numpy()
        values = np.where(np.isnan(values), self.numeric_medians_[name], values)
        numeric_parts.append(
            ((values - self.numeric_means_[name]) / self.numeric_scales_[name]).reshape(-1, 1)
        )
    numeric = (
        sparse.csr_matrix(np.hstack(numeric_parts))
        if numeric_parts
        else sparse.csr_matrix((frame.height, 0))
    )
    categorical_parts: list[sparse.csr_matrix] = []
    for name in self.categorical:
        categories = self.categories_[name]
        mapping = {value: position for position, value in enumerate(categories)}
        missing = mapping["<MISSING>"]
        unknown = mapping["<UNKNOWN>"]
        columns = []
        for value in frame[name].to_list():
            if value is None:
                columns.append(missing)
            else:
                columns.append(mapping.get(str(value), unknown))
        categorical_parts.append(
            sparse.csr_matrix(
                (np.ones(frame.height), (np.arange(frame.height), columns)),
                shape=(frame.height, len(categories)),
            )
        )
    return sparse.hstack([numeric, *categorical_parts], format="csr")


def optimize_f2_threshold(target: np.ndarray, probabilities: np.ndarray) -> float:
    if np.unique(target).size < 2:
        return 0.5
    best_score, best_threshold = -1.0, 0.5
    for threshold in sorted(set(np.asarray(probabilities).tolist())):
        predicted = probabilities >= threshold
        true_positive = int(np.sum((target == 1) & predicted))
        false_positive = int(np.sum((target == 0) & predicted))
        false_negative = int(np.sum((target == 1) & ~predicted))
        denominator = 5 * true_positive + 4 * false_negative + false_positive
        score = 5 * true_positive / denominator if denominator else 0.0
        if score > best_score or (score == best_score and threshold > best_threshold):
            best_score, best_threshold = score, float(threshold)
    return best_threshold
