from datetime import datetime, timedelta

import polars as pl

from curtamap.experimental.features import build_feature_batch


def source_data() -> pl.DataFrame:
    t0 = datetime(2025, 1, 10)
    historical = [t0 - timedelta(days=day) for day in range(1, 9)]
    return pl.DataFrame(
        {
            "fonte": ["eolica"] * 12,
            "id_ons": ["A"] * 11 + ["NOVA"],
            "id_estado": ["RJ"] * 12,
            "id_subsistema": ["SE"] * 12,
            "ceg": ["-"] * 12,
            "din_instante": historical
            + [t0, t0 + timedelta(hours=1), t0 + timedelta(hours=23, minutes=30), t0],
            "disponivel_em": [t0 - timedelta(hours=1)] * 8 + [t0 + timedelta(days=2)] * 4,
            "restricao_registrada": [True, False] * 4 + [True, True, True, True],
            "corte_positivo": [True, False] * 4 + [False, None, True, True],
            "volume_mwmed": [10.0, 0.0] * 4 + [0.0, None, 999.0, 9999.0],
            "volume_valido": [True] * 9 + [False, True, True],
            "causa": ["ENE", None] * 4 + ["CNF", "REL", "ENE", "ENE"],
        }
    )


def test_feature_batch_has_48_direct_horizons_and_correct_first_last_labels() -> None:
    t0 = datetime(2025, 1, 10)
    frame = build_feature_batch(source_data(), t0)
    assert frame.height == 48
    assert frame["horizon"].to_list() == list(range(1, 49))
    assert frame.row(0, named=True)["tau"] == t0
    assert frame.row(-1, named=True)["tau"] == t0 + timedelta(hours=23, minutes=30)
    assert frame.row(0, named=True)["target_observed"] is True
    assert frame.row(-1, named=True)["true_volume_mwmed"] == 999.0


def test_future_features_and_new_entity_are_not_visible_at_t0() -> None:
    frame = build_feature_batch(source_data(), datetime(2025, 1, 10))
    assert frame["id_ons"].unique().to_list() == ["A"]
    assert frame["last_volume_mwmed"].max() == 10.0
    assert frame["last_volume_mwmed"].max() != 999.0
    assert frame["eligible_history"].all() is False


def test_absent_row_valid_zero_and_invalid_volume_keep_separate_masks() -> None:
    frame = build_feature_batch(source_data(), datetime(2025, 1, 10))
    first = frame.filter(pl.col("horizon") == 1).row(0, named=True)
    second = frame.filter(pl.col("horizon") == 2).row(0, named=True)
    third = frame.filter(pl.col("horizon") == 3).row(0, named=True)
    assert first["target_observed"] is True and first["true_volume_mwmed"] == 0.0
    assert second["target_observed"] is False and second["true_volume_mwmed"] is None
    assert third["target_observed"] is True and third["true_volume_mwmed"] is None
    assert third["true_volume_valid"] is False


def test_calendar_history_same_hour_rolling_regional_and_episode_features_are_present() -> None:
    row = build_feature_batch(source_data(), datetime(2025, 1, 10)).row(0, named=True)
    required = {
        "t0_hour_sin",
        "tau_hour_cos",
        "horizon",
        "last_positive",
        "same_hour_1d_positive",
        "positive_frequency_7d",
        "positive_frequency_28d",
        "mean_volume_28d",
        "state_positive_frequency_28d",
        "subsystem_positive_frequency_28d",
        "observed_episode_length",
        "history_coverage_28d",
        "history_age_hours",
    }
    assert required <= row.keys()
    assert row["same_hour_1d_positive"] is True
    assert row["observed_episode_length"] == 1
