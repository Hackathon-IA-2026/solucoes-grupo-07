from curtamap.experimental.decision import assess_candidate


def occurrence_round(candidate: float, baseline: float, brier_delta: float = 0.0) -> dict:
    return {
        "candidate_primary": candidate,
        "baseline_primary": baseline,
        "candidate_brier": 0.15 + brier_delta,
        "baseline_brier": 0.15,
    }


def test_occurrence_requires_margin_and_three_improved_rounds_without_calling_winner() -> None:
    rounds = {
        "V1": occurrence_round(0.53, 0.50),
        "V2": occurrence_round(0.54, 0.50),
        "V3": occurrence_round(0.52, 0.50),
        "V4": occurrence_round(0.50, 0.50),
    }
    result = assess_candidate("occurrence", rounds, weekly_interval=(-0.01, 0.04))
    assert result["status"] == "requer_analise"
    assert "incerteza_inclui_zero" in result["reasons"]
    assert result["final_selection"] is False


def test_occurrence_brier_and_round_degradation_veto_automatic_adoption() -> None:
    rounds = {
        "V1": occurrence_round(0.54, 0.50),
        "V2": occurrence_round(0.54, 0.50, brier_delta=0.02),
        "V3": occurrence_round(0.54, 0.50),
        "V4": occurrence_round(0.47, 0.50),
    }
    result = assess_candidate("occurrence", rounds, weekly_interval=(0.01, 0.05))
    assert result["status"] == "requer_analise"
    assert "piora_primaria_em_rodada" in result["reasons"]
    assert "piora_brier" in result["reasons"]


def test_volume_requires_five_percent_mae_reduction_without_wape_worsening() -> None:
    rounds = {
        f"V{i}": {
            "candidate_primary": candidate,
            "baseline_primary": 100.0,
            "candidate_wape": 0.19,
            "baseline_wape": 0.20,
        }
        for i, candidate in enumerate([90.0, 92.0, 94.0, 100.0], 1)
    }
    result = assess_candidate("volume", rounds, weekly_interval=(-12.0, -1.0))
    assert result["status"] == "elegivel_para_decisao_2c"
    assert result["material_margin_met"] is True
    assert result["improved_rounds"] == 3


def test_missing_round_or_reproduction_failure_is_inconclusive_or_ineligible() -> None:
    incomplete = {"V1": occurrence_round(0.6, 0.5)}
    assert assess_candidate("occurrence", incomplete)["status"] == "inconclusivo"
    complete = {f"V{i}": occurrence_round(0.6, 0.5) for i in range(1, 5)}
    result = assess_candidate("occurrence", complete, failures=["falha_reproducao"])
    assert result["status"] == "inelegivel"
    assert result["final_selection"] is False
