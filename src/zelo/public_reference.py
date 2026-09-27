"""Confere GNR contra publicação direta ONS, mantendo revisões separadas do snapshot."""

import argparse
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from zelo.audit import connect, literal, records, sha256
from zelo.data_contract import SPECS
from zelo.targets import BLANKS_SQL, target_sql

DATASETS = {"eolica": "restricao_coff_eolica_usi", "fotovoltaica": "restricao_coff_fotovoltaica"}


def validate_official_formula(con) -> dict:
    return records(
        con,
        """WITH calc AS (SELECT *,
        val_geracaoreferencia IS NOT NULL AND val_geracao IS NOT NULL
            AND isfinite(val_geracaoreferencia) AND isfinite(val_geracao)
            AND (val_geracaolimitada IS NULL OR isfinite(val_geracaolimitada)) computable,
        CASE WHEN val_geracaolimitada IS NULL THEN 0
            ELSE greatest(val_geracaoreferencia-val_geracao,0) END formula
        FROM official)
        SELECT count(*) AS rows,
        count(*) FILTER(WHERE val_geracaonaorealizadaapurada IS NOT NULL) published_nonnull,
        count(*) FILTER(WHERE val_geracaonaorealizadaapurada IS NOT NULL AND computable) comparable,
        count(*) FILTER(WHERE val_geracaonaorealizadaapurada IS NOT NULL AND computable AND
            abs(val_geracaonaorealizadaapurada-formula)>0.001) different_over_001_mw,
        max(abs(val_geracaonaorealizadaapurada-formula)) FILTER(WHERE computable) max_difference_mw,
        count(*) FILTER(WHERE val_geracaolimitada IS NOT NULL AND
            val_geracaonaorealizadaapurada IS NULL) limited_missing_published
        FROM calc""",
    )[0]


REVISION_NUMERIC = ("val_geracao", "val_geracaolimitada", "val_geracaoreferencia")
REVISION_LABELS = ("cod_razaorestricao", "cod_origemrestricao")


def revision_check(con, local: str, official: str, last_modified: dict) -> list[dict]:
    """Junção linha a linha pela chave composta; mostra revisões em vez de inferi-las."""
    numeric = " OR ".join(f"l.{c} IS DISTINCT FROM o.{c}" for c in REVISION_NUMERIC)
    # NULL no snapshot e '' na publicação atual são a mesma ausência de rótulo.
    labels = " OR ".join(
        f"nullif(upper(trim(l.{c},{BLANKS_SQL})),'') IS DISTINCT FROM "
        f"nullif(upper(trim(o.{c},{BLANKS_SQL})),'')"
        for c in REVISION_LABELS
    )
    both = "l.id_ons IS NOT NULL AND o.id_ons IS NOT NULL"
    rows = records(
        con,
        f"""SELECT coalesce(l.fonte,o.fonte) AS fonte,
        strftime(coalesce(l.din_instante,o.din_instante),'%Y-%m') AS period,
        count(l.id_ons) AS local_rows,count(o.id_ons) AS official_rows,
        count(*) FILTER(WHERE o.id_ons IS NULL) AS only_local,
        count(*) FILTER(WHERE l.id_ons IS NULL) AS only_official,
        count(*) FILTER(WHERE l.id_ons IS NOT NULL AND o.id_ons IS NOT NULL) AS matched,
        count(*) FILTER(WHERE {both} AND ({numeric} OR {labels})) AS changed_inputs,
        count(*) FILTER(WHERE {both} AND ({numeric})) AS changed_numeric,
        count(*) FILTER(WHERE {both} AND ({labels})) AS changed_labels,
        count(*) FILTER(WHERE l.id_ons IS NOT NULL AND o.id_ons IS NOT NULL AND (
            (l.energia_mwh IS NULL) <> (o.energia_mwh IS NULL)
            OR abs(l.energia_mwh-o.energia_mwh)>0.0005)) AS changed_energy,
        sum(l.energia_mwh-o.energia_mwh) AS matched_delta_mwh
        FROM {local} l FULL OUTER JOIN {official} o USING(fonte,id_ons,din_instante)
        GROUP BY ALL ORDER BY 1,2""",
    )
    for r in rows:
        r["last_modified"] = last_modified.get((r["fonte"], r["period"]))
        r["revised"] = bool(
            r["only_local"] or r["only_official"] or r["changed_inputs"] or r["changed_energy"]
        )
    return rows


def fetch_reference(raw: Path, cache: Path) -> list[dict]:
    cache.mkdir(parents=True, exist_ok=True)
    jobs = []
    with connect() as con:
        for source, slug in DATASETS.items():
            periods = {
                r[0]
                for r in con.execute(
                    "SELECT DISTINCT strftime(din_instante,'%Y-%m') "
                    f"FROM read_parquet({literal(raw / SPECS[source].filename)})"
                ).fetchall()
            }
            with urllib.request.urlopen(
                "https://dados.ons.org.br/api/3/action/package_show?id=" + slug, timeout=60
            ) as response:
                resources = json.load(response)["result"]["resources"]
            for period in sorted(periods):
                matches = [
                    r
                    for r in resources
                    if r.get("format", "").upper() == "PARQUET" and r["name"].endswith(period)
                ]
                if len(matches) != 1:
                    raise ValueError(f"Recurso ONS ambíguo/ausente: {source} {period}")
                resource = matches[0]
                if not resource["url"].startswith(
                    "https://ons-aws-prod-opendata.s3.amazonaws.com/"
                ):
                    raise ValueError("Host ONS inesperado")
                jobs.append(
                    dict(
                        fonte=source,
                        period=period,
                        url=resource["url"],
                        file=str(cache / f"{source}_{period}.parquet"),
                    )
                )

    def download(job):
        path = Path(job["file"])
        meta_path = path.with_suffix(".json")
        if not path.exists():
            with urllib.request.urlopen(job["url"], timeout=90) as response:
                payload = response.read()
                meta = {
                    "downloaded_at": datetime.now(UTC).isoformat(),
                    "last_modified": response.headers.get("Last-Modified"),
                }
            temporary = path.with_suffix(".part")
            temporary.write_bytes(payload)
            temporary.replace(path)
            meta_path.write_text(json.dumps(meta))
        meta = json.loads(meta_path.read_text())
        return job | meta | {"sha256": sha256(path), "bytes": path.stat().st_size}

    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(download, jobs))


def compare_reference(raw: Path, manifest: list[dict]) -> dict:
    with connect() as con:
        parts = []
        for source in DATASETS:
            paths = [r["file"] for r in manifest if r["fonte"] == source]
            parts.append(
                f"SELECT {literal(source)} AS fonte,* FROM read_parquet("
                f"[{','.join(literal(p) for p in paths)}], union_by_name=true)"
            )
        con.execute("CREATE VIEW official AS " + " UNION ALL BY NAME ".join(parts))
        local = " UNION ALL ".join(
            f"SELECT * FROM read_parquet({literal(raw / SPECS[s].filename)})" for s in DATASETS
        )
        con.execute("CREATE VIEW local AS " + local)
        con.execute("CREATE VIEW targets AS SELECT *," + target_sql() + " FROM local")
        con.execute("CREATE VIEW official_targets AS SELECT *," + target_sql() + " FROM official")
        # A GNRa publicada costuma ser nula fora da limitação: apenas nesse caso normaliza zero.
        official_energy = (
            "CASE WHEN val_geracaolimitada IS NULL THEN 0 ELSE "
            "val_geracaonaorealizadaapurada*0.5 END"
        )
        result = {
            "status": "provisional",
            "scope": "fórmula GNRa validada nos arquivos oficiais; snapshot comparado linha a "
            "linha e por agregados. Não é reconciliação financeira, comercial nem CCEE.",
            "formula_validation": validate_official_formula(con),
            "revision_check": revision_check(
                con,
                "targets",
                "official_targets",
                {(r["fonte"], r.get("period")): r.get("last_modified") for r in manifest},
            ),
            "comparisons": {},
        }
        for dimension in ["fonte", "year", "causa", "id_estado", "id_subsistema"]:
            dims = ["fonte", "year"] + ([] if dimension in ("fonte", "year") else [dimension])
            cols = ",".join(dims)
            public = records(
                con,
                f"""SELECT {cols},count(*) AS rows,
                count(*) FILTER(WHERE published_mwh IS NULL) AS unknown,
                sum(published_mwh) mwh FROM (SELECT *,year(din_instante) AS year,
                {official_energy} published_mwh FROM official_targets)
                GROUP BY ALL ORDER BY ALL""",
            )
            local_rows = records(
                con,
                f"""SELECT {cols},count(*) AS rows,
                count(*) FILTER(WHERE energia_mwh IS NULL) AS unknown,
                sum(energia_mwh) mwh,sum(energia_bruta_mwh) brute_mwh FROM (
                SELECT *,year(din_instante) AS year FROM targets) GROUP BY ALL ORDER BY ALL""",
            )
            local_map = {tuple(r[k] for k in dims): r for r in local_rows}
            public_map = {tuple(r[k] for k in dims): r for r in public}
            compared = []
            for key in sorted(local_map.keys() | public_map.keys(), key=str):
                a, b = local_map.get(key, {}), public_map.get(key, {})
                delta, percent = comparison_delta(a, b)
                compared.append(
                    dict(zip(dims, key, strict=True))
                    | {
                        "local": a,
                        "official": b,
                        "delta_mwh": delta,
                        "delta_percent": percent,
                        "totals_comparable": delta is not None,
                    }
                )
            result["comparisons"][dimension] = compared
        return result


def comparison_delta(local: dict, official: dict) -> tuple[float | None, float | None]:
    """Não compara como totais equivalentes somas com cobertura de volume incompleta."""
    if (
        local.get("mwh") is None
        or official.get("mwh") is None
        or local.get("unknown", 0)
        or official.get("unknown", 0)
    ):
        return None, None
    delta = local["mwh"] - official["mwh"]
    return delta, delta / official["mwh"] * 100 if official["mwh"] else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--cache", type=Path, default=Path("data/interim/official"))
    parser.add_argument("--output", type=Path, default=Path("docs/reports/stage1"))
    args = parser.parse_args()
    manifest = fetch_reference(args.raw, args.cache)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "official-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    result = compare_reference(args.raw, manifest)
    (args.output / "official-comparison.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(result["formula_validation"], indent=2))


if __name__ == "__main__":
    main()
