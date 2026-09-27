from datetime import datetime, timedelta

import polars as pl
import pytest

from curtamap.contracts import HORIZONS, RESERVED_TEST_START, validate_forecast
from curtamap.forecasting import (
    SameSlotRecentBaseline,
    known_entities,
    load_history,
    nightly_cutoff,
)
from curtamap.targets import derive_targets

T0 = datetime(2025, 3, 11, 10, 0)  # terça-feira
CUTOFF = datetime(2025, 3, 10)  # fim de domingo, liberado segunda às 19h30
GENERATED = datetime(2026, 9, 22, 12, 0)


def _row(when, *, id_ons="BAUSI1", fonte="eolica", limit=None, ref=20.0, gen=20.0, cause=None):
    return {
        "fonte": fonte,
        "id_ons": id_ons,
        "nom_usina": f"Usina {id_ons}",
        "id_estado": "BA",
        "id_subsistema": "NE",
        "din_instante": when,
        "val_geracaolimitada": limit,
        "val_geracaoreferencia": ref,
        "val_geracao": gen,
        "cod_razaorestricao": cause,
        "cod_origemrestricao": "SIS" if cause else None,
    }


RAW_TYPES = {
    "din_instante": pl.Datetime("us"),
    "val_geracaolimitada": pl.Float64,
    "val_geracaoreferencia": pl.Float64,
    "val_geracao": pl.Float64,
    "cod_razaorestricao": pl.String,
    "cod_origemrestricao": pl.String,
}


def _history(*rows) -> pl.DataFrame:
    return derive_targets(pl.DataFrame(list(rows), schema_overrides=RAW_TYPES))


def _predict(history: pl.DataFrame, **kwargs) -> pl.DataFrame:
    return SameSlotRecentBaseline().predict(
        history, T0, kwargs.pop("cutoff", CUTOFF), generated_at=GENERATED, **kwargs
    )


def _h1(frame: pl.DataFrame, id_ons: str = "BAUSI1", fonte: str = "eolica") -> dict:
    return frame.filter(
        (pl.col("id_ons") == id_ons) & (pl.col("fonte") == fonte) & (pl.col("horizonte") == 1)
    ).row(0, named=True)


@pytest.mark.parametrize(
    ("t0", "expected"),
    [
        (datetime(2025, 3, 11, 10), datetime(2025, 3, 10)),  # terça antes das 19h30
        (datetime(2025, 3, 11, 19, 30), datetime(2025, 3, 11)),  # terça: libera segunda
        (datetime(2025, 3, 14, 20), datetime(2025, 3, 14)),  # sexta: libera quinta
        (datetime(2025, 3, 15, 12), datetime(2025, 3, 14)),  # sábado conserva quinta
        (datetime(2025, 3, 17, 10), datetime(2025, 3, 14)),  # segunda antes das 19h30
        (datetime(2025, 3, 17, 19, 30), datetime(2025, 3, 17)),  # libera sex, sáb e dom
    ],
)
def test_nightly_cutoff_follows_business_day_release(t0, expected):
    assert nightly_cutoff(t0) == expected


def test_forecast_has_48_horizons_per_entity_and_honours_contract():
    history = _history(
        _row(datetime(2025, 3, 9, 10), limit=5.0, ref=30.0, gen=10.0, cause="ENE"),
        _row(datetime(2025, 3, 9, 10), id_ons="PISOL1", fonte="fotovoltaica"),
    )
    forecast = _predict(history)
    assert forecast.height == 2 * HORIZONS
    assert validate_forecast(forecast).equals(forecast)
    assert forecast["tipo_saida"].unique().to_list() == ["baseline"]
    assert forecast["corte_dados"].unique().to_list() == [CUTOFF]


def test_uses_most_recent_available_day_in_same_slot():
    history = _history(
        _row(datetime(2025, 3, 8, 10), limit=5.0, ref=30.0, gen=10.0, cause="CNF"),
        _row(datetime(2025, 3, 9, 10), limit=5.0, ref=50.0, gen=10.0, cause="ENE"),
    )
    first = _h1(_predict(history))
    assert first["p_corte"] == 1.0
    assert first["alerta"] is True
    assert first["volume_esperado_mwmed"] == 40.0
    assert first["energia_esperada_mwh"] == 20.0
    assert first["causa_prevista"] == "ENE"
    assert (first["p_causa_ene"], first["p_causa_cnf"], first["p_causa_rel"]) == (1.0, 0.0, 0.0)


def test_rows_after_cutoff_are_never_read():
    history = _history(
        _row(datetime(2025, 3, 9, 10)),
        _row(datetime(2025, 3, 10, 10), limit=5.0, ref=30.0, gen=10.0, cause="ENE"),
    )
    first = _h1(_predict(history))
    assert first["p_corte"] == 0.0
    assert first["volume_esperado_mwmed"] == 0.0
    assert first["causa_prevista"] is None


def test_observations_older_than_28_days_are_not_used():
    history = _history(
        _row(CUTOFF - timedelta(days=28, minutes=-600)),
        _row(CUTOFF - timedelta(days=29) + timedelta(hours=10), limit=1.0, ref=9.0, gen=1.0),
    )
    first = _h1(_predict(history))
    assert first["p_corte"] == 0.0
    later = _history(_row(CUTOFF - timedelta(days=29) + timedelta(hours=10)))
    missing = _h1(_predict(later))
    assert missing["p_corte"] is None
    assert missing["motivo_sem_previsao"] == "sem_observacao_valida_no_horario_28d"


def test_invalid_volume_falls_back_to_previous_valid_observation_in_same_slot():
    history = _history(
        _row(datetime(2025, 3, 8, 10), limit=5.0, ref=30.0, gen=10.0, cause="CNF"),
        _row(datetime(2025, 3, 9, 10), limit=5.0, ref=30.0, gen=-1.0, cause="CNF"),
    )
    first = _h1(_predict(history))
    assert first["p_restricao"] == 1.0
    assert first["volume_esperado_mwmed"] == 20.0


def test_unknown_and_par_causes_are_not_predicted():
    history = _history(
        _row(datetime(2025, 3, 7, 10), limit=5.0, ref=30.0, gen=10.0, cause="REL"),
        _row(datetime(2025, 3, 8, 10), limit=5.0, ref=30.0, gen=10.0, cause="PAR"),
        _row(datetime(2025, 3, 9, 10), limit=5.0, ref=30.0, gen=10.0, cause="XYZ"),
    )
    assert _h1(_predict(history))["causa_prevista"] == "REL"


def test_zero_volume_order_is_command_without_curtailment():
    history = _history(_row(datetime(2025, 3, 9, 10), limit=30.0, ref=20.0, gen=20.0, cause="ENE"))
    first = _h1(_predict(history))
    assert (first["p_restricao"], first["p_corte"]) == (1.0, 0.0)
    assert first["volume_condicional_mwmed"] is None


def test_each_horizon_reads_its_own_slot():
    history = _history(
        _row(datetime(2025, 3, 9, 10)),
        _row(datetime(2025, 3, 9, 9, 30), limit=5.0, ref=30.0, gen=10.0, cause="ENE"),
    )
    forecast = _predict(history).sort("horizonte")
    assert forecast["tau"][-1] == datetime(2025, 3, 12, 9, 30)
    assert forecast["p_corte"][-1] == 1.0
    assert forecast["p_corte"][0] == 0.0


def test_source_is_part_of_identity():
    history = _history(
        _row(datetime(2025, 3, 9, 10), limit=5.0, ref=30.0, gen=10.0, cause="ENE"),
        _row(datetime(2025, 3, 9, 10), fonte="fotovoltaica"),
    )
    forecast = _predict(history)
    assert _h1(forecast)["p_corte"] == 1.0
    assert _h1(forecast, fonte="fotovoltaica")["p_corte"] == 0.0


def test_cutoff_after_issue_time_is_rejected():
    with pytest.raises(ValueError, match="corte"):
        _predict(_history(_row(datetime(2025, 3, 9, 10))), cutoff=T0 + timedelta(minutes=30))


def test_issue_time_must_be_on_half_hour_grid():
    with pytest.raises(ValueError, match="30 minutos"):
        SameSlotRecentBaseline().predict(
            _history(_row(datetime(2025, 3, 9, 10))), T0 + timedelta(minutes=5), CUTOFF
        )


def test_reserved_test_period_is_blocked_by_default():
    t0 = RESERVED_TEST_START - timedelta(hours=10)
    history = _history(_row(datetime(2026, 4, 20, 10)))
    with pytest.raises(ValueError, match="teste reservado"):
        SameSlotRecentBaseline().predict(history, t0, nightly_cutoff(t0))
    boundary = RESERVED_TEST_START - timedelta(days=1)
    allowed = SameSlotRecentBaseline().predict(history, boundary, nightly_cutoff(boundary))
    assert allowed.height == HORIZONS


def test_known_entities_use_last_attributes_before_cutoff():
    history = _history(
        _row(datetime(2025, 3, 1, 10)),
        {**_row(datetime(2025, 3, 9, 10)), "nom_usina": "Nome novo"},
        {**_row(datetime(2025, 3, 10, 10)), "nom_usina": "Nome futuro"},
    )
    entities = known_entities(history, CUTOFF)
    assert entities.select("fonte", "id_ons", "nom_usina").rows() == [
        ("eolica", "BAUSI1", "Nome novo")
    ]


def _write_source(path, rows):
    frame = pl.DataFrame(rows).with_columns(
        pl.col("din_instante").cast(pl.Datetime("ns")),
        pl.col("val_geracaolimitada").cast(pl.Float64),
        pl.col("cod_razaorestricao").cast(pl.String),
        pl.col("cod_origemrestricao").cast(pl.String),
    )
    frame.write_parquet(path)


def test_load_history_reads_window_and_derives_targets(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    _write_source(
        raw / "constrained_off_eolica_tm.parquet",
        [
            _row(datetime(2025, 3, 1, 10)),
            _row(datetime(2025, 3, 9, 10), limit=5.0, ref=30.0, gen=10.0, cause="ENE"),
        ],
    )
    history = load_history(tmp_path, datetime(2025, 3, 5), CUTOFF, sources=("eolica",))
    assert history.height == 1
    assert history["volume_mwmed"].to_list() == [20.0]
    assert history.schema["din_instante"] == pl.Datetime("us")


def test_load_history_refuses_reserved_period(tmp_path):
    with pytest.raises(ValueError, match="teste reservado"):
        load_history(tmp_path, datetime(2026, 8, 1), datetime(2026, 9, 2))


def test_reserved_period_is_september_2026_after_may_august_was_consumed():
    # Maio–agosto/2026 foi consumido pela Etapa 2 anterior em 25/09/2026; setembro de 2026,
    # publicado depois do snapshot do hackathon, é o novo teste independente.
    assert datetime(2026, 9, 1) == RESERVED_TEST_START


def test_forecast_exposes_observation_used_and_history_coverage():
    history = _history(
        _row(datetime(2025, 3, 8, 10), limit=5.0, ref=30.0, gen=10.0, cause="CNF"),
        _row(datetime(2025, 3, 9, 10), limit=5.0, ref=30.0, gen=-1.0, cause="CNF"),
    )
    first = _h1(_predict(history))
    assert first["instante_observacao"] == datetime(2025, 3, 8, 10)
    assert first["cobertura_historico"] == pytest.approx(2 / (28 * 48))
    assert first["cenario_disponibilidade"] == "noturno_fim_de_semana"
