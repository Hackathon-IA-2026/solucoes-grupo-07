import duckdb

from zelo.public_reference import validate_official_formula


def test_official_comparison_keeps_null_coverage_and_detects_difference():
    with duckdb.connect() as con:
        con.execute("""CREATE TABLE official(val_geracaolimitada DOUBLE,
            val_geracaoreferencia DOUBLE,val_geracao DOUBLE,
            val_geracaonaorealizadaapurada DOUBLE)""")
        con.execute(
            "INSERT INTO official VALUES (0,10,4,6),(NULL,10,4,NULL),"
            "(1,10,4,7),(1,NULL,4,2),(1,10,4,NULL)"
        )
        r = validate_official_formula(con)
    assert r["rows"] == 5
    assert r["published_nonnull"] == 3
    assert r["comparable"] == 2
    assert r["different_over_001_mw"] == 1
    assert r["limited_missing_published"] == 1


def test_reference_totals_compare_all_dimensions(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from test_audit import write_main

    from zelo.data_contract import SPECS
    from zelo.public_reference import compare_reference

    manifest = []
    for source in ["eolica", "fotovoltaica"]:
        p = write_main(
            tmp_path / SPECS[source].filename,
            [{"fonte": source, "val_geracaolimitada": 1.0, "cod_razaorestricao": "ENE"}],
        )
        table = pq.read_table(p).drop(["fonte"])
        table = table.append_column("val_geracaonaorealizadaapurada", pa.array([8.0]))
        official = tmp_path / f"{source}_official.parquet"
        pq.write_table(table, official)
        manifest.append({"fonte": source, "file": str(official)})
    r = compare_reference(tmp_path, manifest)
    assert r["formula_validation"]["different_over_001_mw"] == 0
    assert set(r["comparisons"]) == {"fonte", "year", "causa", "id_estado", "id_subsistema"}
    assert all(row["delta_mwh"] == 0 for rows in r["comparisons"].values() for row in rows)


def test_incomplete_reference_is_not_an_equivalent_total():
    from zelo.public_reference import comparison_delta

    assert comparison_delta(
        {"mwh": 10.0, "unknown": 0, "rows": 2}, {"mwh": 1.0, "unknown": 1, "rows": 2}
    ) == (None, None)
    assert comparison_delta(
        {"mwh": 10.0, "unknown": 0, "rows": 2}, {"mwh": 5.0, "unknown": 0, "rows": 2}
    ) == (5.0, 100.0)


def test_row_level_revision_check_separates_missing_rows_and_changed_values():
    from datetime import datetime

    from zelo.public_reference import revision_check
    from zelo.targets import target_sql

    t = datetime(2024, 1, 1)
    with duckdb.connect() as con:
        cols = """fonte VARCHAR,id_ons VARCHAR,din_instante TIMESTAMP,val_geracao DOUBLE,
            val_geracaolimitada DOUBLE,val_geracaoreferencia DOUBLE,
            cod_razaorestricao VARCHAR,cod_origemrestricao VARCHAR"""
        con.execute(f"CREATE TABLE local({cols})")
        con.execute(f"CREATE TABLE official({cols})")
        con.executemany(
            "INSERT INTO local VALUES (?,?,?,?,?,?,?,?)",
            [
                ("eolica", "A", t, 2.0, 1.0, 10.0, "ENE", "SIS"),  # igual
                ("eolica", "B", t, 2.0, 1.0, 10.0, "ENE", "SIS"),  # geração revisada
                ("eolica", "C", t, 2.0, None, 10.0, None, None),  # só no snapshot
                ("eolica", "E", t, 2.0, None, 10.0, None, None),  # nulo local
            ],
        )
        con.executemany(
            "INSERT INTO official VALUES (?,?,?,?,?,?,?,?)",
            [
                ("eolica", "A", t, 2.0, 1.0, 10.0, "ENE", "SIS"),
                ("eolica", "B", t, 4.0, 1.0, 10.0, "ENE", "SIS"),
                ("eolica", "D", t, 2.0, 1.0, 10.0, "CNF", "LOC"),  # só na publicação
                ("eolica", "E", t, 2.0, None, 10.0, "", " "),  # vazio publicado não é revisão
            ],
        )
        for view in ["local", "official"]:
            con.execute(f"CREATE VIEW {view}_t AS SELECT *,{target_sql()} FROM {view}")
        rows = revision_check(con, "local_t", "official_t", {("eolica", "2024-01"): "x"})
    assert len(rows) == 1
    r = rows[0]
    assert (r["fonte"], r["period"], r["last_modified"]) == ("eolica", "2024-01", "x")
    assert r["local_rows"] == 4 and r["official_rows"] == 4
    assert r["only_local"] == 1 and r["only_official"] == 1 and r["matched"] == 3
    assert r["changed_inputs"] == 1
    assert r["changed_numeric"] == 1 and r["changed_labels"] == 0
    assert r["changed_energy"] == 1
    assert r["matched_delta_mwh"] == 1.0  # (8-6)*0.5: snapshot menos publicação atual
    assert r["revised"] is True
