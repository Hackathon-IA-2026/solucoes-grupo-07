from datetime import datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from zelo.audit import audit_directory, audit_file, compare_main_integrated
from zelo.data_contract import MAIN_SCHEMA, SPECS, schema_issues


def write_main(path: Path, rows: list[dict]) -> Path:
    normalized = []
    for r in rows:
        base = {name: None for name in MAIN_SCHEMA.names}
        base.update(
            fonte="eolica",
            id_ons="A",
            din_instante=datetime(2024, 1, 1),
            id_estado="BA",
            id_subsistema="NE",
            val_geracao=2.0,
            val_geracaoreferencia=10.0,
            ceg="-",
        )
        base.update(r)
        normalized.append(base)
    pq.write_table(pa.Table.from_pylist(normalized, schema=MAIN_SCHEMA), path)
    return path


def test_schema_contract_detects_missing_wrong_and_extra():
    assert schema_issues(MAIN_SCHEMA, SPECS["eolica"]) == []
    schema = pa.schema([("id_ons", pa.int64()), ("unexpected", pa.string())])
    issues = schema_issues(schema, SPECS["eolica"])
    assert any("id_ons" in x and "tipo" in x for x in issues)
    assert any("din_instante" in x for x in issues)
    assert any("unexpected" in x for x in issues)


def test_audit_anomalies_and_composite_key(tmp_path):
    t = datetime(2024, 1, 1)
    p = write_main(
        tmp_path / "x.parquet",
        [
            {"val_geracaolimitada": 0.0, "cod_razaorestricao": "ENE"},
            {"val_geracaolimitada": 0.0, "cod_razaorestricao": "ENE"},
            {
                "din_instante": t + timedelta(hours=1),
                "val_geracao": -2.0,
                "val_geracaolimitada": 1.0,
                "cod_razaorestricao": "XXX",
            },
            {"fonte": "fotovoltaica", "val_geracao": float("inf")},
            {"id_ons": None, "val_geracaolimitada": 0.0},
            {"din_instante": None},
            {"id_ons": "B", "din_instante": t + timedelta(minutes=7)},
        ],
    )
    r = audit_file(p, SPECS["integrada"])
    assert r["rows"] == 7
    assert r["keys"]["null_id"] == 1
    assert r["keys"]["null_time"] == 1
    assert r["temporal"]["duplicate_excess"] == 1
    assert r["temporal"]["duplicate_groups"] == 1
    assert r["temporal"]["missing_slots_between_observations"] == 1
    assert r["temporal"]["off_grid"] == 1
    assert r["keys"]["ids_shared_across_sources"] == 1
    assert r["numeric"]["val_geracao"]["negative"] == 1
    assert r["numeric"]["val_geracao"]["nonfinite"] == 1
    assert r["nulls"]["cod_razaorestricao"]["limited_nulls"] == 1
    assert r["domains"]["cod_razaorestricao"]["invalid_rows"] == 1
    assert r["status"] == "issues"


def test_empty_and_wrong_schema_are_reported(tmp_path):
    p = write_main(tmp_path / "empty.parquet", [])
    r = audit_file(p, SPECS["eolica"])
    assert r["rows"] == 0
    assert r["status"] == "issues"
    pq.write_table(pa.table({"wrong": [1]}), p)
    r = audit_file(p, SPECS["eolica"])
    assert r["schema_issues"]
    assert r["status"] == "invalid_schema"


def test_missing_files_reported_without_crash(tmp_path):
    r = audit_directory(tmp_path)
    assert len(r["files"]) == 5
    assert all(x["status"] == "missing" for x in r["files"].values())


def test_multiset_comparison_detects_missing_duplicate_and_changed_values(tmp_path):
    main = write_main(tmp_path / "main.parquet", [{}, {}, {"id_ons": "B"}])
    integrated = write_main(
        tmp_path / "integrated.parquet", [{}, {"id_ons": "B", "val_geracao": 9.0}]
    )
    r = compare_main_integrated([main], integrated)
    assert r["main_minus_integrated"] == 2
    assert r["integrated_minus_main"] == 1


def test_identity_drift_and_label_contradiction(tmp_path):
    p = write_main(
        tmp_path / "drift.parquet",
        [
            {"nom_usina": "antes", "cod_razaorestricao": "ENE"},
            {"nom_usina": "depois", "id_estado": "CE", "val_geracaolimitada": 1.0},
        ],
    )
    r = audit_file(p, SPECS["eolica"])
    assert r["identity_drift"][0]["states"] == 2
    assert r["label_consistency"]["label_without_limit"] == 1
    assert r["label_consistency"]["limit_without_cause"] == 1


def test_detail_flag_and_missing_weather(tmp_path):
    spec = SPECS["eolica_detail"]
    row = {name: None for name in spec.schema.names}
    row.update(
        fonte="eolica", id_ons="A", din_instante=datetime(2024, 1, 1), flg_dadoventoinvalido=3.0
    )
    p = tmp_path / "detail.parquet"
    pq.write_table(pa.Table.from_pylist([row], schema=spec.schema), p)
    r = audit_file(p, spec)
    assert r["domains"]["flg_dadoventoinvalido"]["invalid_rows"] == 1
    assert r["nulls"]["val_ventoverificado"]["nulls"] == 1
    assert r["nulls"]["val_ventoverificado"]["limited_nulls"] is None


def test_identity_drift_counts_change_between_null_and_value(tmp_path):
    p = write_main(tmp_path / "null_drift.parquet", [{"ceg": None}, {"ceg": "EOL.X"}])
    r = audit_file(p, SPECS["eolica"])
    assert r["identity_drift"][0]["cegs"] == 2


def test_detail_comparison_reports_join_multiplicity(tmp_path):
    from zelo.audit import compare_detail

    t = datetime(2024, 1, 1)
    main = write_main(
        tmp_path / "main.parquet",
        [
            {"id_ons": "IND", "ceg": "EOL.1", "val_geracao": 5.0},
            {"id_ons": "IND", "ceg": "EOL.1", "din_instante": t + timedelta(minutes=30)},
            {"id_ons": "CONJ", "ceg": "-"},
        ],
    )
    spec = SPECS["eolica_detail"]
    rows = []
    for minutes, value in [(0, 5.0), (0, 5.0), (30, 3.0)]:
        row = {name: None for name in spec.schema.names}
        row.update(
            fonte="eolica",
            id_ons="IND",
            din_instante=t + timedelta(minutes=minutes),
            val_geracaoverificada=value,
        )
        rows.append(row)
    detail = tmp_path / "detail.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=spec.schema), detail)
    r = compare_detail(main, detail)
    assert r["individual_overlap"] == {"main_individual_ids": 1, "matched_ids": 1}
    v = r["individual_values"]
    assert v["join_rows"] == 3
    assert v["matched_intervals"] == 2
    assert v["duplicated_join_rows"] == 1
    assert v["generation_different"] == 1
