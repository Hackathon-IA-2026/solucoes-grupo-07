"""Paridade semântica entre a geração vetorizada e a implementação original (oráculo)."""

import math
import random
from datetime import date, datetime, timedelta

import polars as pl
import pytest
import reference_stage2b as reference

from curtamap.experimental.baselines import generate_baselines
from curtamap.experimental.data import add_release_times
from curtamap.experimental.features import build_feature_batch
from curtamap.experimental.temporal import AvailabilityScenario, BusinessCalendar

CALENDAR = BusinessCalendar(
    frozenset({date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 4)}), "fixture-paridade"
)
KEYS_FEATURES = ["fonte", "id_ons", "t0", "horizon"]


def synthetic_source(scenario: AvailabilityScenario, *, seed: int = 7) -> pl.DataFrame:
    """Grade de meia hora com lacunas, entidade nova, entidade silenciosa e UF nula."""
    rng = random.Random(seed)
    entities = [
        ("A", "BA", "NE", "-", datetime(2024, 12, 20), None),
        ("B", "BA", "NE", "CEG.B", datetime(2024, 12, 20), None),
        ("C", "RN", "NE", "-", datetime(2024, 12, 20), datetime(2025, 2, 1)),
        ("D", "RN", "NE", "CEG.D", datetime(2025, 1, 25), None),
        ("E", None, "N", "-", datetime(2024, 12, 20), None),
        # Poucas linhas: forçam os níveis fonte/UF e fonte do fallback estatístico.
        ("F", "PI", "NE", "-", datetime(2025, 2, 1, 10), datetime(2025, 2, 1, 11, 30)),
        ("G", "BA", "NE", "-", datetime(2025, 2, 1, 10), datetime(2025, 2, 1, 11)),
    ]
    end = datetime(2025, 2, 13)
    rows = []
    for id_ons, estado, subsistema, ceg, first, last in entities:
        current = first
        stop = last or end
        restricted = False
        while current < stop:
            if rng.random() < 0.04:
                current += timedelta(minutes=30)
                continue
            # Restrições persistentes produzem episódios longos e quebras por lacuna.
            restricted = rng.random() < (0.85 if restricted else 0.12)
            if restricted:
                draw = rng.random()
                if draw < 0.2:
                    volume = 0.0
                elif draw < 0.24:
                    volume = None
                else:
                    volume = round(rng.uniform(0.1, 80.0), 3)
                cause = rng.choice(["REL", "CNF", "ENE", "ENE", "CNF", "DESCONHECIDA"])
            else:
                volume, cause = 0.0, None
            rows.append(
                {
                    "fonte": "eolica",
                    "id_ons": id_ons,
                    "id_estado": estado,
                    "id_subsistema": subsistema,
                    "ceg": ceg,
                    "din_instante": current,
                    "restricao_registrada": restricted,
                    "volume_mwmed": volume,
                    "corte_positivo": None if volume is None else volume > 0,
                    "volume_valido": (not restricted) or volume is not None,
                    "causa": cause,
                }
            )
            current += timedelta(minutes=30)
    frame = pl.DataFrame(rows, infer_schema_length=None).sort("id_ons", "din_instante")
    return add_release_times(frame, scenario, CALENDAR)


def _assert_equivalent(new: pl.DataFrame, old: pl.DataFrame) -> None:
    assert new.columns == old.columns
    assert new.height == old.height
    for name in old.columns:
        expected = old[name]
        actual = new[name]
        if expected.dtype == pl.Null:
            assert actual.null_count() == actual.len(), name
            continue
        if isinstance(expected.dtype, pl.Struct):
            _assert_equivalent(actual.struct.unnest(), expected.struct.unnest())
            continue
        for position, (got, want) in enumerate(
            zip(actual.to_list(), expected.to_list(), strict=True)
        ):
            if isinstance(want, float) and want is not None and got is not None:
                assert math.isclose(got, want, rel_tol=1e-9, abs_tol=1e-12), (
                    name,
                    position,
                    got,
                    want,
                )
            else:
                assert got == want, (name, position, got, want)


FEATURE_T0 = [
    datetime(2025, 2, 10, 0, 0),  # segunda: sexta ainda não liberada
    datetime(2025, 2, 10, 19, 0),  # antes da liberação das 19h30
    datetime(2025, 2, 10, 19, 30),  # exatamente na liberação
    datetime(2025, 2, 5, 20, 0),  # quarta após feriado de terça
    datetime(2025, 2, 8, 13, 30),  # sábado
    datetime(2025, 1, 26, 10, 0),  # entidade nova logo após o primeiro registro
]


@pytest.mark.parametrize(
    "scenario", [AvailabilityScenario.main(), AvailabilityScenario.delayed_24h()]
)
@pytest.mark.parametrize("t0", FEATURE_T0)
def test_vectorized_features_match_reference(scenario: AvailabilityScenario, t0) -> None:
    source = synthetic_source(scenario)
    expected = reference.build_feature_batch(source, t0)
    actual = build_feature_batch(source, t0)
    _assert_equivalent(actual.sort(KEYS_FEATURES), expected.sort(KEYS_FEATURES))


BASELINE_T0 = [
    datetime(2025, 2, 10, 19, 30),
    datetime(2025, 2, 5, 20, 0),
    datetime(2025, 1, 26, 10, 0),
]


def _requests(source: pl.DataFrame, t0: datetime) -> pl.DataFrame:
    return build_feature_batch(source, t0).select(
        "fonte", "id_ons", "id_estado", "t0", "tau", "horizon"
    )


@pytest.mark.parametrize(
    "scenario", [AvailabilityScenario.main(), AvailabilityScenario.delayed_24h()]
)
@pytest.mark.parametrize("t0", BASELINE_T0)
def test_vectorized_baselines_match_reference(scenario: AvailabilityScenario, t0) -> None:
    source = synthetic_source(scenario).with_columns(
        # O oráculo lança TypeError se o último registro de uma entidade for indeterminado;
        # essa divergência intencional é coberta em teste próprio.
        pl.col("volume_mwmed").fill_null(0.0),
        pl.col("corte_positivo").fill_null(False),
    )
    requests = _requests(source, t0)
    expected = reference.generate_baselines(source, requests)
    actual = generate_baselines(source, requests)
    _assert_equivalent(actual, expected)


def test_baselines_accept_several_t0_in_request_order() -> None:
    source = synthetic_source(AvailabilityScenario.main()).with_columns(
        pl.col("volume_mwmed").fill_null(0.0), pl.col("corte_positivo").fill_null(False)
    )
    requests = pl.concat(
        [
            _requests(source, datetime(2025, 2, 10, 20)).head(30),
            _requests(source, datetime(2025, 2, 6, 11)).head(30),
        ]
    )
    _assert_equivalent(
        generate_baselines(source, requests), reference.generate_baselines(source, requests)
    )


def test_nanosecond_timestamps_from_duckdb_match_reference() -> None:
    """Os alvos preparados pelo DuckDB chegam como ``datetime[ns]``."""
    t0 = datetime(2025, 2, 10, 19, 30)
    source = (
        synthetic_source(AvailabilityScenario.main())
        .with_columns(
            pl.col("volume_mwmed").fill_null(0.0), pl.col("corte_positivo").fill_null(False)
        )
        .with_columns(pl.col("din_instante", "disponivel_em").cast(pl.Datetime("ns")))
    )
    expected_features = reference.build_feature_batch(source, t0)
    actual_features = build_feature_batch(source, t0)
    _assert_equivalent(actual_features, expected_features.sort(KEYS_FEATURES))
    requests = actual_features.select("fonte", "id_ons", "id_estado", "t0", "tau", "horizon")
    _assert_equivalent(
        generate_baselines(source, requests), reference.generate_baselines(source, requests)
    )


@pytest.mark.parametrize("released_rows", [9, 5])
def test_sparse_history_reaches_generic_fallbacks_like_reference(released_rows: int) -> None:
    """Nove linhas em horários distintos: fonte_todos_horarios; cinco: sem_evidencia."""
    start = datetime(2025, 1, 6, 1)
    history = pl.DataFrame(
        {
            "fonte": ["eolica"] * released_rows,
            "id_ons": ["X", "Y"] * (released_rows // 2) + ["X"] * (released_rows % 2),
            "id_estado": ["RJ"] * released_rows,
            "din_instante": [start + timedelta(hours=2 * i) for i in range(released_rows)],
            "disponivel_em": [datetime(2025, 1, 7, 19, 30)] * released_rows,
            "restricao_registrada": [i % 2 == 0 for i in range(released_rows)],
            "corte_positivo": [i % 4 == 0 for i in range(released_rows)],
            "volume_mwmed": [float(i % 4 == 0) * 3.0 for i in range(released_rows)],
            "volume_valido": [True] * released_rows,
            "causa": [("ENE" if i % 2 == 0 else None) for i in range(released_rows)],
        }
    )
    t0 = datetime(2025, 1, 8, 10)
    requests = pl.DataFrame(
        {
            "fonte": ["eolica"] * 3,
            "id_ons": ["X", "Y", "NOVO"],
            "id_estado": ["RJ", "RJ", "SP"],
            "t0": [t0] * 3,
            "tau": [t0, t0 + timedelta(hours=1), t0 + timedelta(minutes=30)],
            "horizon": [1, 3, 2],
        }
    )
    expected = reference.generate_baselines(history, requests)
    actual = generate_baselines(history, requests)
    _assert_equivalent(actual, expected)
    level = "fonte_todos_horarios" if released_rows == 9 else "sem_evidencia"
    assert level in expected["fallback_level"].to_list()


def test_indeterminate_last_volume_is_null_instead_of_type_error() -> None:
    """Divergência intencional: o oráculo compara ``None > 0`` e lança TypeError."""
    start = datetime(2025, 1, 6, 10)
    history = pl.DataFrame(
        {
            "fonte": ["eolica"] * 8,
            "id_ons": ["A"] * 8,
            "id_estado": ["RJ"] * 8,
            "din_instante": [start + timedelta(hours=i) for i in range(8)],
            "disponivel_em": [start + timedelta(days=1)] * 8,
            "restricao_registrada": [True] * 8,
            "corte_positivo": [True] * 7 + [None],
            "volume_mwmed": [5.0] * 7 + [None],
            "volume_valido": [True] * 7 + [False],
            "causa": ["ENE"] * 8,
        }
    )
    requests = pl.DataFrame(
        {
            "fonte": ["eolica"],
            "id_ons": ["A"],
            "id_estado": ["RJ"],
            "t0": [start + timedelta(days=2)],
            "tau": [start + timedelta(days=2)],
            "horizon": [1],
        }
    )
    with pytest.raises(TypeError):
        reference.generate_baselines(history, requests)
    row = (
        generate_baselines(history, requests)
        .filter(pl.col("baseline_id") == "ultimo_valor")
        .row(0, named=True)
    )
    assert row["native_available"] is True
    assert row["prob_positive"] == 0.5
    assert row["volume_positive_mean"] is None
    assert row["volume_expected"] == 0.0


def test_feature_schema_is_stable_even_when_a_column_is_all_null() -> None:
    """Divergência intencional: o oráculo infere ``Null`` e muda o schema entre dias."""
    source = synthetic_source(AvailabilityScenario.main()).with_columns(
        pl.lit(False).alias("corte_positivo")
    )
    frame = build_feature_batch(source, datetime(2025, 2, 10, 20))
    assert frame["hours_since_positive"].null_count() == frame.height
    assert frame["hours_since_positive"].dtype == pl.Float64
    assert frame["mean_volume_24h"].dtype == pl.Float64
    assert frame["last_cause"].dtype == pl.String
