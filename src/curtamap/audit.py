"""Auditoria colunar reproduzível. Não altera nem deduplica arquivos originais."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from curtamap.data_contract import SPECS, DatasetSpec, schema_issues
from curtamap.download_data import DATASET_FOLDER_URL

NULL_TOKEN = "'<NULL>'"


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(config={"memory_limit": "4GB", "threads": 4})
    con.execute("SET preserve_insertion_order=false")
    return con


def literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def records(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    names = [c[0] for c in cur.description]
    return [dict(zip(names, row, strict=True)) for row in cur.fetchall()]


def sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def audit_file(path: Path, spec: DatasetSpec) -> dict:
    if not path.exists():
        return {"status": "missing", "path": str(path)}
    try:
        metadata = pq.ParquetFile(path)
    except (pa.ArrowInvalid, OSError) as error:
        return {"status": "unreadable", "path": str(path), "error": str(error)}
    schema = metadata.schema_arrow
    r = {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "rows": metadata.metadata.num_rows,
        "schema": {f.name: str(f.type) for f in schema},
        "schema_issues": schema_issues(schema, spec),
    }
    if r["schema_issues"]:
        return r | {"status": "invalid_schema"}
    with connect() as con:
        con.execute(f"CREATE VIEW d AS SELECT * FROM read_parquet({literal(path)})")
        limited = "false" if spec.detail else "val_geracaolimitada IS NOT NULL"
        r["keys"] = records(
            con,
            f"""SELECT count(*) FILTER(WHERE id_ons IS NULL) null_id,
            count(*) FILTER(WHERE din_instante IS NULL) null_time,
            count(*) FILTER(WHERE fonte IS NULL) null_source,
            count(*) FILTER(WHERE fonte IS NULL OR fonte NOT IN
                ({",".join(literal(x) for x in spec.sources)})) invalid_source,
            count(DISTINCT (fonte,id_ons)) entities,
            min(din_instante) AS start, max(din_instante) AS end,
            count(*) FILTER(WHERE {limited}) limited_rows FROM d""",
        )[0]
        r["keys"]["ids_shared_across_sources"] = con.execute("""SELECT count(*) FROM (
            SELECT id_ons FROM d WHERE id_ons IS NOT NULL
            GROUP BY id_ons HAVING count(DISTINCT fonte)>1)""").fetchone()[0]
        r["temporal"] = records(
            con,
            """WITH ordered AS (
            SELECT din_instante,
                lag(din_instante) OVER w prev,
                lead(din_instante) OVER w nxt
            FROM d WHERE id_ons IS NOT NULL AND fonte IS NOT NULL AND din_instante IS NOT NULL
            WINDOW w AS (PARTITION BY fonte,id_ons ORDER BY din_instante)),
            deltas AS (SELECT *, epoch(din_instante)-epoch(prev) AS seconds FROM ordered)
            SELECT count(*) FILTER(WHERE seconds=0) duplicate_excess,
                count(*) FILTER(WHERE seconds=0 AND (nxt IS NULL OR nxt<>din_instante))
                    duplicate_groups,
                count(*) FILTER(WHERE epoch_ns(din_instante)%1800000000000<>0) off_grid,
                count(*) FILTER(WHERE seconds>1800) gaps,
                coalesce(sum(floor(seconds/1800)-1) FILTER(WHERE seconds>1800),0)
                    missing_slots_between_observations,
                count(*) FILTER(WHERE seconds>0 AND seconds%1800<>0) irregular_steps,
                max(seconds) max_step_seconds FROM deltas""",
        )[0]
        fields = []
        for name in schema.names:
            q = ident(name)
            fields += [
                f"count(*) FILTER(WHERE {q} IS NULL) AS {ident(name + '__nulls')}",
                f"count(*) FILTER(WHERE {q} IS NULL AND {limited}) "
                f"AS {ident(name + '__limited_nulls')}",
            ]
        null_row = records(con, "SELECT " + ",".join(fields) + " FROM d")[0]
        r["nulls"] = {
            name: {
                "nulls": null_row[name + "__nulls"],
                "limited_nulls": None if spec.detail else null_row[name + "__limited_nulls"],
            }
            for name in schema.names
        }
        r["nulls_by_month"] = records(
            con,
            "SELECT fonte, strftime(din_instante,'%Y-%m') period,"
            f"count(*) AS rows,count(*) FILTER(WHERE {limited}) limited_rows,"
            + ",".join(fields)
            + " FROM d GROUP BY ALL ORDER BY fonte,period",
        )
        r["numeric"] = {}
        for field in schema:
            if not pa.types.is_floating(field.type):
                continue
            q = ident(field.name)
            r["numeric"][field.name] = records(
                con,
                f"""SELECT
                count(*) FILTER(WHERE {q}<0 AND isfinite({q})) negative,
                count(*) FILTER(WHERE NOT isfinite({q})) nonfinite,
                min({q}) FILTER(WHERE isfinite({q})) min,
                max({q}) FILTER(WHERE isfinite({q})) max,
                approx_quantile({q},[0.01,0.5,0.99,0.999])
                    FILTER(WHERE isfinite({q})) quantiles_approx
                FROM d""",
            )[0]
        r["domains"] = {}
        domains = {"fonte": spec.sources, "id_subsistema": ("N", "NE", "SE", "S")}
        if not spec.detail:
            domains |= {
                "cod_razaorestricao": ("REL", "CNF", "ENE", "PAR"),
                "cod_origemrestricao": ("LOC", "SIS"),
            }
        else:
            domains |= {
                (
                    "flg_dadoventoinvalido"
                    if spec.sources[0] == "eolica"
                    else "flg_dadoirradianciainvalido"
                ): (0, 1)
            }
        for name, allowed in domains.items():
            values = records(
                con,
                f"SELECT {ident(name)} AS value,count(*) AS rows FROM d "
                "GROUP BY ALL ORDER BY value",
            )
            r["domains"][name] = {
                "counts": values,
                "invalid_rows": sum(
                    x["rows"]
                    for x in values
                    if x["value"] is not None and x["value"] not in allowed
                ),
            }
        r["coverage"] = {}
        for key, group in {
            "source": "fonte",
            "entity": "fonte,id_ons",
            "state": "fonte,id_estado",
            "subsystem": "fonte,id_subsistema",
            "month": "fonte,strftime(din_instante,'%Y-%m')",
        }.items():
            # Aliases explícitos para serialização estável.
            selection = group if key != "month" else group + " AS period"
            r["coverage"][key] = records(
                con,
                f"""SELECT {selection},count(*) AS rows,
                count(DISTINCT id_ons) entities,
                min(din_instante) AS start,max(din_instante) AS end,
                count(*) FILTER(WHERE {limited}) limited_rows
                FROM d GROUP BY ALL ORDER BY 1,2""",
            )
        r["granularity"] = records(
            con,
            """SELECT fonte,
            CASE WHEN ceg='-' THEN 'conjunto' WHEN ceg IS NULL THEN 'desconhecida'
            ELSE 'individual' END AS level, count(*) AS rows,count(DISTINCT id_ons) entities
            FROM d GROUP BY ALL ORDER BY 1,2""",
        )
        r["identity_drift"] = records(
            con,
            # coalesce: troca entre NULL e valor também é mudança de identidade.
            f"""SELECT fonte,id_ons,
            count(DISTINCT coalesce(nom_usina,{NULL_TOKEN})) AS names,
            count(DISTINCT coalesce(id_estado,{NULL_TOKEN})) AS states,
            count(DISTINCT coalesce(id_subsistema,{NULL_TOKEN})) AS subsystems,
            count(DISTINCT coalesce(ceg,{NULL_TOKEN})) AS cegs
            FROM d GROUP BY ALL HAVING names>1 OR states>1 OR subsystems>1 OR cegs>1
            ORDER BY 1,2""",
        )
        if not spec.detail:
            r["label_consistency"] = records(
                con,
                """SELECT
                count(*) FILTER(WHERE val_geracaolimitada IS NULL AND
                    (cod_razaorestricao IS NOT NULL OR cod_origemrestricao IS NOT NULL))
                    label_without_limit,
                count(*) FILTER(WHERE val_geracaolimitada IS NOT NULL AND
                    cod_razaorestricao IS NULL) limit_without_cause,
                count(*) FILTER(WHERE val_geracaoreferenciafinal IS NOT NULL AND
                    cod_razaorestricao IS DISTINCT FROM 'REL') final_reference_without_rel
                FROM d""",
            )[0]
        r["calendar_mismatches"] = records(
            con,
            """SELECT
            count(*) FILTER(WHERE ano IS DISTINCT FROM year(din_instante)) ano,
            count(*) FILTER(WHERE mes IS DISTINCT FROM month(din_instante)) mes,
            count(*) FILTER(WHERE data IS DISTINCT FROM CAST(din_instante AS DATE)) AS data,
            count(*) FILTER(WHERE hora IS DISTINCT FROM hour(din_instante)) hora,
            count(*) FILTER(WHERE minuto IS DISTINCT FROM minute(din_instante)) minuto,
            count(*) FILTER(WHERE ano_mes IS DISTINCT FROM strftime(din_instante,'%Y-%m')) ano_mes
            FROM d""",
        )[0]
    # Nulos em limite/referência final são estruturais: não geram falha por si sós.
    issues = (
        r["rows"] == 0
        or any(r["keys"][k] for k in ["null_id", "null_time", "null_source", "invalid_source"])
        or any(
            r["temporal"][k] for k in ["duplicate_excess", "off_grid", "gaps", "irregular_steps"]
        )
        or any(x["negative"] or x["nonfinite"] for x in r["numeric"].values())
        or any(x["invalid_rows"] for x in r["domains"].values())
        or any(r["calendar_mismatches"].values())
    )
    r["status"] = "issues" if issues else "ok"
    return r


def compare_main_integrated(main_paths: list[Path], integrated: Path) -> dict:
    with connect() as con:
        union = " UNION ALL ".join(f"SELECT * FROM read_parquet({literal(p)})" for p in main_paths)
        con.execute("CREATE VIEW m AS " + union)
        con.execute(f"CREATE VIEW i AS SELECT * FROM read_parquet({literal(integrated)})")
        cols = ",".join(ident(c) for c in SPECS["integrada"].schema.names)
        # EXCEPT ALL compara todos os valores e a multiplicidade; não apenas hash/chave.
        periods = con.execute("""SELECT DISTINCT date_trunc('month',din_instante) FROM (
            SELECT din_instante FROM m UNION ALL SELECT din_instante FROM i) ORDER BY 1""")
        periods = periods.fetchall()
        result = {}
        for key, a, b in [("main_minus_integrated", "m", "i"), ("integrated_minus_main", "i", "m")]:
            summaries = []
            for (period,) in periods:
                where = (
                    "din_instante IS NULL"
                    if period is None
                    else f"din_instante >= TIMESTAMP {literal(str(period))} AND "
                    f"din_instante < TIMESTAMP {literal(str(period))} + INTERVAL 1 MONTH"
                )
                summaries.extend(
                    records(
                        con,
                        f"""SELECT fonte,
                    strftime(din_instante,'%Y-%m') period,count(*) AS rows FROM (
                    SELECT {cols} FROM {a} WHERE {where} EXCEPT ALL
                    SELECT {cols} FROM {b} WHERE {where}) GROUP BY ALL ORDER BY 1,2""",
                    )
                )
            result[key + "_by_month"] = summaries
            result[key] = sum(row["rows"] for row in summaries)
        return result


def compare_detail(main: Path, detail: Path) -> dict:
    with connect() as con:
        con.execute(f"CREATE VIEW m AS SELECT * FROM read_parquet({literal(main)})")
        con.execute(f"CREATE VIEW d AS SELECT * FROM read_parquet({literal(detail)})")
        result = {"method": "interseção direta apenas de ids individuais; conjuntos não são usinas"}
        result["individual_overlap"] = records(
            con,
            """WITH mi AS (
            SELECT DISTINCT fonte,id_ons FROM m WHERE ceg<>'-'), di AS (
            SELECT DISTINCT fonte,id_ons FROM d)
            SELECT count(*) main_individual_ids,
            count(*) FILTER(WHERE di.id_ons IS NOT NULL) matched_ids
            FROM mi LEFT JOIN di USING(fonte,id_ons)""",
        )[0]
        result["individual_values"] = records(
            con,
            # Duplicatas do detail multiplicam o join; a contagem distinta expõe isso.
            """SELECT count(*) AS join_rows,
            count(DISTINCT (fonte,id_ons,din_instante)) AS matched_intervals,
            count(*)-count(DISTINCT (fonte,id_ons,din_instante)) AS duplicated_join_rows,
            count(*) FILTER(WHERE abs(m.val_geracao-d.val_geracaoverificada)>0.001)
                AS generation_different,
            count(*) FILTER(WHERE m.val_geracao IS NULL OR d.val_geracaoverificada IS NULL)
                generation_missing,
            max(abs(m.val_geracao-d.val_geracaoverificada)) max_abs_difference_mw
            FROM m JOIN d USING(fonte,id_ons,din_instante) WHERE m.ceg<>'-' """,
        )[0]
        result["detail_membership"] = records(
            con,
            """SELECT fonte,
            count(DISTINCT id_ons) individuals,count(DISTINCT nom_conjuntousina) group_names,
            count(*) FILTER(WHERE nom_conjuntousina IS NULL) AS rows_without_group
            FROM d GROUP BY ALL""",
        )
        result["limitation"] = (
            "Snapshot detail não tem id_ons_conjuntousina. "
            "Nome do conjunto não é chave validada; sem rateio ou soma automática entre níveis."
        )
        return result


def audit_directory(raw: Path) -> dict:
    result = {
        "audit_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "provenance": DATASET_FOLDER_URL,
        "duckdb_version": duckdb.__version__,
        "files": {},
        "comparisons": {},
    }
    for key, spec in SPECS.items():
        print(f"auditando {key}", flush=True)
        result["files"][key] = audit_file(raw / spec.filename, spec)

    def usable(k):
        return result["files"][k]["status"] in ("ok", "issues")

    if all(usable(k) for k in ["eolica", "fotovoltaica", "integrada"]):
        print("comparando integrada", flush=True)
        result["comparisons"]["integrated"] = compare_main_integrated(
            [raw / SPECS[k].filename for k in ["eolica", "fotovoltaica"]],
            raw / SPECS["integrada"].filename,
        )
    for source in ["eolica", "fotovoltaica"]:
        if usable(source) and usable(source + "_detail"):
            print(f"comparando detail {source}", flush=True)
            result["comparisons"][source + "_detail"] = compare_detail(
                raw / SPECS[source].filename, raw / SPECS[source + "_detail"].filename
            )
    return result


def write_report(result: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "audit.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str, allow_nan=False) + "\n"
    )
    lines = [
        "# Auditoria dos cinco Parquet",
        "",
        f"Execução: {result['generated_at']}.",
        "",
        "Fonte: ONS, snapshot tratado fornecido pelo hackathon. SHA-256 e schemas no JSON.",
        "Nulos condicionais usam limite não nulo. Detail não possui limite (N/A).",
        "Lacunas são internas à vida observada da entidade; não provam falha de coleta.",
        "Quantis são aproximados. Extremos e negativos são evidências para investigação,",
        "não regras automáticas de remoção. Fuso horário não consta nos Parquet.",
        "",
        "| Base | Linhas | Entidades | Início | Fim | Duplicadas excedentes | Lacunas | Estado |",
        "|---|---:|---:|---|---|---:|---:|---|",
    ]
    for key, r in result["files"].items():
        k, t = r.get("keys", {}), r.get("temporal", {})
        lines.append(
            f"| {key} | {r.get('rows', '—')} | {k.get('entities', '—')} | "
            f"{k.get('start', '—')} | {k.get('end', '—')} | "
            f"{t.get('duplicate_excess', '—')} | {t.get('gaps', '—')} | {r['status']} |"
        )
    lines += [
        "",
        "## Comparações entre bases",
        "",
        "```json",
        json.dumps(result["comparisons"], indent=2, ensure_ascii=False, default=str),
        "```",
        "",
        "## Como interpretar",
        "",
        "`audit.json` contém nulos por campo/mês (denominadores explícitos), domínios,",
        "negativos/não finitos/mínimos/máximos/quantis, cobertura por fonte, entidade,",
        "UF, subsistema e mês, schema e divergências de calendário auxiliar.",
        "Status `issues` exige investigação e não significa que todas as linhas são inválidas.",
        "Nenhum dado é imputado ou corrigido pela auditoria. A base integrada é comparada",
        "como multiconjunto, em todas as colunas, com a união das principais.",
        "",
    ]
    (output / "audit.md").write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("docs/reports/stage1"))
    parser.add_argument(
        "--strict", action="store_true", help="retorna 1 se algum arquivo não for ok"
    )
    args = parser.parse_args()
    result = audit_directory(args.raw)
    write_report(result, args.output)
    if args.strict and any(r["status"] != "ok" for r in result["files"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
