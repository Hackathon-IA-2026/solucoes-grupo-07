"""Consolida somente métricas e manifestos pequenos; dados/modelos ficam locais."""

import json
from pathlib import Path

import polars as pl

from curtamap.alertas_negocio import summarize
from curtamap.previsao.alertas import sha256

out = Path("docs/reports/alertas")
out.mkdir(parents=True, exist_ok=True)
occurrence, impact, weeks, manifests, parity = [], [], [], [], []
reference = pl.read_csv("docs/reports/nova-abordagem/metricas_backtest.csv")
for source in ("eolica", "fotovoltaica"):
    stem = f"{source}_2026-08-01_2026-08-31"
    forecast = Path("data/interim/alertas") / stem
    business = Path("data/interim/negocio") / stem
    metrics = pl.read_csv(forecast.with_suffix(".csv"))
    occurrence.append(metrics)
    impact.append(pl.read_csv(business.with_suffix(".csv")))
    rows = pl.read_parquet(business.with_suffix(".parquet")).with_columns(
        pl.col("dia").dt.truncate("1w").alias("semana")
    )
    for (week,), part in rows.partition_by("semana", as_dict=True).items():
        weeks.append(summarize(part).with_columns(pl.lit(week).alias("semana")))
    manifest = json.loads(forecast.with_suffix(".json").read_text(encoding="utf-8"))
    manifest["dados"] = "data/raw/" + Path(manifest["dados"]).name
    manifest["recursos"] = json.loads(
        Path(f"{forecast}.recursos.json").read_text(encoding="utf-8-sig")
    )
    manifest["negocio"] = json.loads(business.with_suffix(".json").read_text(encoding="utf-8"))
    manifests.append(manifest)
    old = reference.filter((pl.col("fonte") == source) & (pl.col("periodo") == "2026-08-01")).row(
        0, named=True
    )
    new = metrics.filter((pl.col("recorte") == "mes") & (pl.col("modelo") == "hgb_servido")).row(
        0, named=True
    )
    parity.append(
        {
            "fonte": source,
            "n_referencia": old["n"],
            "n_reproduzido": new["n"],
            "ap_referencia": old["ap_modelo"],
            "ap_reproduzido": new["ap"],
            "delta_ap": new["ap"] - old["ap_modelo"],
            "brier_referencia": old["brier_modelo"],
            "brier_reproduzido": new["brier"],
        }
    )
pl.concat(occurrence).write_csv(out / "metricas_ocorrencia.csv")
pl.concat(impact).write_csv(out / "impacto_manutencao.csv")
pl.concat(weeks).write_csv(out / "impacto_semanas.csv")
pl.DataFrame(parity).write_csv(out / "paridade.csv")
snapshot = {
    "execucoes": manifests,
    "sha256_lock": sha256(Path("uv.lock")),
    "sha256_features": sha256(Path("src/curtamap/previsao/features.py")),
    "hardware": {
        "cpu": "AMD Ryzen 5 4600G, 6 núcleos / 12 threads",
        "ram_gib": 15.89,
        "ram_livre_inicio_gib": 4.98,
        "disco_livre_inicio_gib": 27.06,
        "gpu": "GTX 1660, 6 GiB, não utilizada",
    },
    "limites": {"threads": 2, "memoria_privada_gib": 3, "segundos_por_fonte": 1200},
    "origem": "fd0a70b; origin/main e branches atualizadas via git fetch --all --prune",
    "fontes": [
        "https://dadosabertos.ccee.org.br/dataset/pld_horario",
        "https://dados.ons.org.br/dataset/restricao_coff_eolica_usi",
        "https://epe.gov.br/pt/publicacoes-dados-abertos/ferramentas-interativas",
        "https://sonda.ccst.inpe.br/sobre_base.html",
    ],
}
(out / "manifesto.json").write_text(
    json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)
print(pl.DataFrame(parity).write_csv())
print(
    pl.concat(weeks)
    .filter(
        (pl.col("cenario") == "PLD_CCEE_observado")
        & (pl.col("baseline") == "menor_geracao_historica")
    )
    .select("fonte", "semana", "diferenca_media_brl", "melhores", "piores")
    .write_csv()
)
