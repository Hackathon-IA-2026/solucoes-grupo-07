import numpy as np
import pytest

from curtamap.experimentos.rede_temporal.limiar import (
    alert_counts,
    choose_threshold_fixed,
    f1_at,
    round_preserving,
)
from curtamap.previsao.avaliacao import choose_threshold

Y = np.array([1, 0, 0, 1])
P = np.array([0.9, 0.9, 0.9, 0.1])


def test_original_function_evaluates_a_group_split_inside_a_tie() -> None:
    # Documenta o defeito: a posição 1 da ordenação separa um empate que nenhum limiar separa.
    threshold = choose_threshold(Y, P)

    assert threshold == pytest.approx(0.9)
    assert f1_at(Y, P, threshold) == pytest.approx(0.4)


def test_fixed_function_only_evaluates_real_thresholds() -> None:
    threshold = choose_threshold_fixed(Y, P)

    assert threshold == pytest.approx(0.1)
    assert f1_at(Y, P, threshold) == pytest.approx(2 / 3)


def test_fixed_function_matches_brute_force_with_many_ties() -> None:
    rng = np.random.default_rng(0)
    for _ in range(200):
        n = int(rng.integers(1, 40))
        p = rng.choice([0.1, 0.2, 0.35, 0.5, 0.8], size=n)
        y = rng.integers(0, 2, size=n)
        if not y.any():
            continue
        best = max(f1_at(y, p, v) for v in np.unique(p))
        assert f1_at(y, p, choose_threshold_fixed(y, p)) == pytest.approx(best)


def test_ties_between_thresholds_prefer_fewer_alerts() -> None:
    # Limiares 0.8 e 0.3 dão F1 = 0,5; o maior gera menos alertas.
    y = np.array([1, 0, 1, 0, 0, 0])
    p = np.array([0.8, 0.8, 0.3, 0.3, 0.3, 0.3])

    assert f1_at(y, p, 0.8) == pytest.approx(f1_at(y, p, 0.3))
    assert choose_threshold_fixed(y, p) == pytest.approx(0.8)


def test_all_equal_probabilities_alert_everything() -> None:
    y = np.array([1, 0, 0])
    p = np.full(3, 0.4)

    assert choose_threshold_fixed(y, p) == pytest.approx(0.4)


def test_no_positive_never_alerts() -> None:
    assert choose_threshold_fixed(np.zeros(5), np.linspace(0, 1, 5)) == np.inf


def test_all_positive_alerts_everything() -> None:
    p = np.array([0.2, 0.7, 0.9])

    assert choose_threshold_fixed(np.ones(3), p) == pytest.approx(0.2)


@pytest.mark.parametrize(
    ("y", "p"),
    [(np.array([]), np.array([])), (np.array([1, 0]), np.array([0.5, np.nan]))],
)
def test_invalid_inputs_are_refused(y: np.ndarray, p: np.ndarray) -> None:
    with pytest.raises(ValueError):
        choose_threshold_fixed(y, p)


def test_counts_use_the_inference_comparison() -> None:
    counts = alert_counts(Y, P, 0.9)

    assert counts == {"vp": 1, "fp": 2, "fn": 1, "vn": 0}


def test_naive_rounding_can_drop_the_chosen_group() -> None:
    y = np.array([0, 1, 0])
    p = np.array([0.34612, 0.34615, 0.1])
    threshold = choose_threshold_fixed(y, p)

    assert threshold == pytest.approx(0.34615)
    assert alert_counts(y, p, round(threshold, 4))["vp"] == 0
    assert alert_counts(y, p, round_preserving(threshold, p, 4)) == alert_counts(y, p, threshold)


def test_round_preserving_keeps_precision_when_no_short_value_is_safe() -> None:
    p = np.array([0.30001, 0.30004])

    assert round_preserving(0.30004, p, 4) == pytest.approx(0.30004)
