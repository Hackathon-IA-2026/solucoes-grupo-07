"""Escolha do limiar de alerta só entre limiares realizáveis.

A função original (`curtamap.previsao.avaliacao.choose_threshold`) ordena as probabilidades
e avalia o F1 em cada posição. Com probabilidades empatadas, uma posição pode separar linhas
que têm a mesma probabilidade, o que nenhum limiar real consegue fazer: a inferência alerta
com `p >= limiar` e inclui o grupo empatado inteiro. Aqui, cada candidato é um valor distinto
de probabilidade, e o F1 é calculado com a mesma comparação `>=` da inferência.
"""

import math

import numpy as np


def _validate(y: np.ndarray, p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    if y.size == 0 or y.shape != p.shape:
        raise ValueError("y e p precisam ter o mesmo tamanho, maior que zero")
    if np.isnan(p).any() or np.isnan(y).any():
        raise ValueError("probabilidades ou rótulos nulos")
    return y, p


def alert_counts(y: np.ndarray, p: np.ndarray, threshold: float) -> dict[str, int]:
    """Matriz de confusão do alerta `p >= threshold`."""
    y = np.asarray(y) == 1
    alert = np.asarray(p) >= threshold
    return {
        "vp": int((alert & y).sum()),
        "fp": int((alert & ~y).sum()),
        "fn": int((~alert & y).sum()),
        "vn": int((~alert & ~y).sum()),
    }


def f1_at(y: np.ndarray, p: np.ndarray, threshold: float) -> float:
    c = alert_counts(y, p, threshold)
    denominator = 2 * c["vp"] + c["fp"] + c["fn"]
    return 2 * c["vp"] / denominator if denominator else 0.0


def choose_threshold_fixed(y: np.ndarray, p: np.ndarray) -> float:
    """Valor distinto de `p` que maximiza o F1 de `p >= limiar`.

    Empates de F1 ficam com o maior limiar (menos alertas). Sem nenhum positivo, devolve
    `inf`: não há limiar com F1 positivo, e não alertar é a escolha coerente.
    """
    y, p = _validate(y, p)
    positives = y.sum()
    if positives == 0:
        return math.inf
    values, inverse = np.unique(-p, return_inverse=True)  # ordem decrescente de p
    hits = np.bincount(inverse, weights=y, minlength=len(values))
    sizes = np.bincount(inverse, minlength=len(values))
    tp = np.cumsum(hits)
    alerts = np.cumsum(sizes)
    f1 = 2 * tp / (alerts + positives)
    best = int(np.argmax(f1))  # primeira ocorrência = maior limiar entre os empatados
    return float(-values[best])


def round_preserving(threshold: float, p: np.ndarray, decimals: int = 4) -> float:
    """Arredonda para baixo só se nenhum `p` cair entre o valor arredondado e o limiar.

    Arredondar para o mais próximo pode subir o limiar e excluir o grupo escolhido; arredondar
    para baixo pode incluir valores intermediários. Se não houver arredondamento seguro, o
    limiar volta com a precisão completa.
    """
    if not math.isfinite(threshold):
        return threshold
    scale = 10**decimals
    rounded = math.floor(threshold * scale) / scale
    p = np.asarray(p, dtype=float)
    changed = ((p >= rounded) & (p < threshold)).any()
    return threshold if changed else rounded
