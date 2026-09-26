from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

torch = pytest.importorskip("torch", reason="extra experimento não instalado")

from curtamap.experimentos.rede_temporal.rede import (  # noqa: E402
    DailyTensor,
    GRUForecaster,
    NetConfig,
    batch_inputs,
    masked_loss,
    samples_for_days,
)

D0 = date(2026, 1, 1)


def _base(rows: list[tuple]) -> pl.DataFrame:
    """(fonte, id_ons, estado, dia, slot, corte, volume, referencia)."""
    frame = pl.DataFrame(
        rows,
        schema=["fonte", "id_ons", "id_estado", "dia", "slot", "corte", "volume", "referencia"],
        orient="row",
    )
    return frame.with_columns(
        pl.col("dia").cast(pl.Date),
        pl.col("slot").cast(pl.Int8),
        pl.col(["corte", "volume", "referencia"]).cast(pl.Float32),
    )


def _grid(days: int = 40) -> pl.DataFrame:
    rows = []
    for k in range(days):
        day = D0 + timedelta(days=k)
        for slot in (0, 1):
            cut = float(k % 2 == 0 and slot == 1)
            rows.append(("eolica", "A", "RN", day, slot, cut, 20.0 * cut, 100.0))
            rows.append(("fotovoltaica", "A", "RN", day, slot, 0.0, 0.0, 50.0))
    return _base(rows)


def _sample(target: date, released: date) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "fonte": ["eolica"],
            "id_ons": ["A"],
            "dia": [target],
            "ultimo_dia": [released],
            "idade": [(target - released).days],
            "dia_semana": [target.weekday()],
            "feriado": [0],
        }
    )


def test_tensor_places_values_and_marks_missing_slots() -> None:
    tensor = DailyTensor.from_base(_grid())
    p = tensor.plant_index[("eolica", "A")]
    d = tensor.day_index[D0]

    assert tensor.corte[p, d, 1] == 1.0
    assert tensor.volume[p, d, 1] == pytest.approx(20.0)
    assert tensor.mask[p, d, 1] == 1.0
    # Slot 5 nunca foi observado: fica mascarado, não é corte zero observado.
    assert tensor.mask[p, d, 5] == 0.0
    assert ("fotovoltaica", "A") in tensor.plant_index  # mesmo id_ons, outra fonte


def test_state_share_uses_plants_of_the_same_source_and_state() -> None:
    tensor = DailyTensor.from_base(_grid())
    p = tensor.plant_index[("eolica", "A")]
    q = tensor.plant_index[("fotovoltaica", "A")]
    d = tensor.day_index[D0]

    assert tensor.state_share[p, d, 1] == 1.0
    assert tensor.state_share[q, d, 1] == 0.0


def test_inputs_end_at_the_last_released_day() -> None:
    config = NetConfig(window_days=7)
    target = D0 + timedelta(days=30)
    released = D0 + timedelta(days=27)
    base = _grid()
    changed = base.with_columns(
        pl.when(pl.col("dia") > released).then(999.0).otherwise(pl.col("volume")).alias("volume")
    )
    samples = _sample(target, released)

    a = batch_inputs(DailyTensor.from_base(base), samples, config)
    b = batch_inputs(DailyTensor.from_base(changed), samples, config)

    assert np.array_equal(a["sequence"], b["sequence"])
    assert np.array_equal(a["scale"], b["scale"])


def test_scale_comes_from_the_window_reference() -> None:
    samples = _sample(D0 + timedelta(days=30), D0 + timedelta(days=27))

    inputs = batch_inputs(DailyTensor.from_base(_grid()), samples, NetConfig(window_days=7))

    assert inputs["scale"][0] == pytest.approx(100.0)
    assert inputs["sequence"].shape[:2] == (1, 7)


def test_samples_keep_only_target_days_with_labels() -> None:
    tensor = DailyTensor.from_base(_grid(40))
    mapping = pl.DataFrame(
        {
            "dia": [D0 + timedelta(days=35), D0 + timedelta(days=45)],
            "ultimo_dia": [D0 + timedelta(days=33), D0 + timedelta(days=43)],
            "idade": [2, 2],
            "dia_semana": [0, 1],
            "feriado": [0, 0],
        }
    ).with_columns(pl.col("dia", "ultimo_dia").cast(pl.Date))

    samples = samples_for_days(tensor, mapping, require_labels=True)

    assert set(samples["dia"]) == {D0 + timedelta(days=35)}
    assert samples.height == 2  # duas usinas (eólica e solar)


def test_model_outputs_probabilities_and_non_negative_volume() -> None:
    config = NetConfig(window_days=7, hidden=8)
    model = GRUForecaster(config, n_plants=3)
    batch = {
        "sequence": torch.zeros(4, 7, config.input_size),
        "plant": torch.tensor([0, 1, 2, 0]),
        "source": torch.tensor([0, 1, 0, 1]),
        "calendar": torch.zeros(4, config.calendar_size),
    }

    logits, log_rate = model(batch)
    probability, volume = torch.sigmoid(logits), torch.exp(log_rate)

    assert logits.shape == (4, 48) and log_rate.shape == (4, 48)
    assert ((probability > 0) & (probability < 1)).all()
    assert (volume >= 0).all()


def test_masked_targets_do_not_change_the_loss() -> None:
    logits = torch.zeros(2, 48)
    log_rate = torch.zeros(2, 48)
    mask = torch.ones(2, 48)
    mask[:, 10:] = 0
    y_cut = torch.zeros(2, 48)
    y_vol = torch.zeros(2, 48)
    garbage_cut, garbage_vol = y_cut.clone(), y_vol.clone()
    garbage_cut[:, 10:] = 1
    garbage_vol[:, 10:] = 999

    clean = masked_loss(logits, log_rate, y_cut, y_vol, mask, volume_weight=1.0)
    noisy = masked_loss(logits, log_rate, garbage_cut, garbage_vol, mask, volume_weight=1.0)

    assert torch.allclose(clean, noisy)
