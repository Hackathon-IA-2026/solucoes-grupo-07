import math

import duckdb
import polars as pl
import pytest

from zelo.targets import derive_targets, target_sql

CASES = [
    (None, 20.0, 5.0, None, None, False, 0.0, None, False),
    (0.0, 20.0, 5.0, "REL", "LOC", True, 7.5, "REL", False),
    (0.0, 0.0, 0.0, "ENE", "SIS", True, 0.0, "ENE", False),
    (100.0, 5.0, 10.0, "CNF", "SIS", True, 0.0, "CNF", False),
    (1.0, 20.0, 5.0, " par ", " loc ", True, 7.5, "PAR", False),
    (1.0, 20.0, 5.0, None, None, True, 7.5, "DESCONHECIDA", True),
    (1.0, 20.0, 5.0, "XXX", "XXX", True, 7.5, "DESCONHECIDA", True),
    (1.0, None, 5.0, "ENE", "LOC", True, None, "ENE", False),
    (1.0, 20.0, None, "ENE", "LOC", True, None, "ENE", False),
    (1.0, math.nan, 5.0, "ENE", "LOC", True, None, "ENE", False),
    (1.0, 20.0, math.inf, "ENE", "LOC", True, None, "ENE", False),
    (-1.0, 20.0, 5.0, "REL", "LOC", True, None, "REL", False),
    (1.0, -20.0, 5.0, "REL", "LOC", True, None, "REL", False),
    (1.0, 20.0, -5.0, "REL", "LOC", True, None, "REL", False),
    (math.inf, 20.0, 5.0, "REL", "LOC", True, None, "REL", False),
    (math.nan, 20.0, 5.0, "REL", "LOC", True, None, "REL", False),
    (None, None, -5.0, "REL", "LOC", False, 0.0, None, False),
    (5.0, 10.0, 10.0, "CNF", "LOC", True, 0.0, "CNF", False),
    (None, 20.0, 5.0, "", " ", False, 0.0, None, False),
    (1.0, 20.0, 5.0, "", "", True, 7.5, "DESCONHECIDA", True),
    (1.0, 20.0, 5.0, "\tREL\n", "\r\nSIS\t", True, 7.5, "REL", False),
    (None, 20.0, 5.0, "\t", "\n", False, 0.0, None, False),
]


def frame(rows, source="eolica"):
    return pl.DataFrame(
        [
            dict(
                fonte=source,
                val_geracaolimitada=x[0],
                val_geracaoreferencia=x[1],
                val_geracao=x[2],
                cod_razaorestricao=x[3],
                cod_origemrestricao=x[4],
            )
            for x in rows
        ],
        schema_overrides={
            "val_geracaolimitada": pl.Float64,
            "val_geracaoreferencia": pl.Float64,
            "val_geracao": pl.Float64,
            "cod_razaorestricao": pl.String,
            "cod_origemrestricao": pl.String,
        },
    )


@pytest.mark.parametrize("source", ["eolica", "fotovoltaica"])
@pytest.mark.parametrize("case", CASES)
def test_target_domain_edges_and_backend_parity(source, case):
    df = frame([case], source)
    result = derive_targets(df).row(0, named=True)
    assert result["restricao_registrada"] == case[5]
    assert result["energia_mwh"] == case[6]
    assert result["causa"] == case[7]
    assert result["razao_desconhecida"] == case[8]
    if case[6] is not None:
        assert result["volume_mwmed"] == case[6] * 2
        assert result["corte_positivo"] == (case[6] > 0)
    else:
        assert result["corte_positivo"] is None
    has_label = any((x or "").strip() for x in case[3:5])
    assert result["rotulo_sem_limite"] == (case[0] is None and has_label)
    known_origin = (case[4] or "").strip().upper() in ("LOC", "SIS")
    assert result["origem_desconhecida"] == (case[5] and not known_origin)
    with duckdb.connect() as con:
        con.register("d", df.to_arrow())
        cur = con.execute("SELECT " + target_sql() + " FROM d")
        sql_result = dict(zip([c[0] for c in cur.description], cur.fetchone(), strict=True))
    for k, v in sql_result.items():
        assert result[k] == v, k


def test_negative_preserved_and_brute_sensitivity():
    df = frame([(1.0, 20.0, -5.0, "REL", "LOC")])
    r = derive_targets(df).row(0, named=True)
    assert r["val_geracao"] == -5.0
    assert r["entrada_negativa"]
    assert r["energia_bruta_mwh"] == 12.5
    assert r["energia_mwh"] is None


def test_does_not_fill_missing_intervals_or_mutate_input():
    df = frame([CASES[0], CASES[1]])
    before = df.clone()
    assert derive_targets(df).height == 2
    assert df.equals(before)
    assert derive_targets(df.head(0)).height == 0


def test_rejects_wrong_source():
    with pytest.raises(ValueError, match="fonte"):
        derive_targets(frame([CASES[0]], "hidraulica"))


def test_mwmed_to_mwh_known_value_and_zero_volume_is_command_not_cut():
    r = derive_targets(frame([(50.0, 130.0, 30.0, "ENE", "SIS"), (80.0, 30.0, 30.0, "ENE", "SIS")]))
    assert r["volume_mwmed"].to_list() == [100.0, 0.0]
    assert r["energia_mwh"].to_list() == [50.0, 0.0]
    assert r["restricao_registrada"].to_list() == [True, True]
    assert r["corte_positivo"].to_list() == [True, False]


def test_incomplete_grid_stays_incomplete():
    from datetime import datetime, timedelta

    t = datetime(2025, 1, 1)
    df = frame([CASES[0], CASES[1]]).with_columns(
        id_ons=pl.lit("A"), din_instante=pl.Series([t, t + timedelta(hours=2)])
    )
    r = derive_targets(df)
    assert r["din_instante"].to_list() == [t, t + timedelta(hours=2)]
    assert r.filter(pl.col("energia_mwh") == 0).height == 1
