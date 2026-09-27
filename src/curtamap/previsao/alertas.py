"""Replay explícito do classificador vigente, sem treinar ou servir volume.

Saída própria para demonstração retrospectiva; não substitui FORECAST_SCHEMA.
O treino reutiliza exatamente a receita de ocorrência da v1/v3.
"""

import argparse
import gc
import hashlib
import json
import os
import platform
import subprocess
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import joblib
import polars as pl
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, brier_score_loss

from curtamap.config import settings
from curtamap.data_contract import SPECS
from curtamap.forecasting import load_history
from curtamap.previsao.calendario import load_calendar
from curtamap.previsao.features import (
    OCCURRENCE,
    attach_targets,
    base_from_history,
    build_features,
    release_map,
)
from curtamap.previsao.modelo import PARAMS, TRAIN_DAYS, _matrix

KEY = ["fonte", "id_ons", "dia"]
SCORES = {
    "hgb_servido": "p_corte",
    "historico_28d": "hist_28d",
    "mesmo_slot_ultimo_dia": "ultimo_slot",
    "ultimo_valor": "ultimo_valor_corte",
}


def validate_alerts(frame: pl.DataFrame) -> pl.DataFrame:
    """Grade completa de 48 slots por entidade/dia; nulo é ausência de previsão."""
    required = {*KEY, "tau", "p_corte", "limiar_alerta", "alerta"}
    if required - set(frame.columns) or frame.is_empty():
        raise ValueError("Replay vazio ou sem colunas obrigatórias")
    if frame.select(pl.col([*KEY, "tau", "limiar_alerta"]).null_count()).row(0) != (0,) * 5:
        raise ValueError("Chaves, datas e limiares não podem ser nulos")
    for name in ("p_corte", "limiar_alerta"):
        invalid = ~pl.col(name).is_finite() | ~pl.col(name).is_between(0, 1)
        if frame.filter(invalid).height:
            raise ValueError(f"{name} fora de [0, 1]")
    expected = pl.col("p_corte") >= pl.col("limiar_alerta")
    if frame.filter(~pl.col("alerta").eq_missing(expected)).height:
        raise ValueError("Alerta incompatível com probabilidade/limiar")
    invalid_time = (
        (pl.col("tau").dt.date() != pl.col("dia"))
        | (pl.col("tau").dt.minute() % 30 != 0)
        | (pl.col("tau").dt.second() != 0)
        | (pl.col("tau").dt.microsecond() != 0)
    )
    groups = frame.group_by(KEY).agg(pl.len().alias("n"), pl.col("tau").n_unique().alias("u"))
    if (
        frame.filter(invalid_time).height
        or groups.filter((pl.col("n") != 48) | (pl.col("u") != 48)).height
    ):
        raise ValueError("Cada usina/dia deve ter exatamente 48 meias-horas únicas")
    return frame


def rank_alerts(frame: pl.DataFrame) -> pl.DataFrame:
    """Prioriza duração dos alertas e maior p(corte); não estima probabilidade diária."""
    validate_alerts(frame)
    alert = pl.col("alerta").fill_null(False)
    return (
        frame.group_by(KEY)
        .agg(
            alert.sum().alias("janelas_alerta"),
            pl.col("p_corte").null_count().alias("janelas_sem_previsao"),
            pl.col("p_corte").max().alias("probabilidade_maxima"),
            pl.col("tau").filter(alert).min().alias("primeiro_alerta"),
        )
        .with_columns(
            pl.when(pl.col("janelas_sem_previsao") < 48)
            .then(pl.col("janelas_alerta") * 0.5)
            .alias("horas_alerta"),
            pl.when(pl.col("janelas_sem_previsao") == 48)
            .then(pl.lit("sem previsão"))
            .when(pl.col("janelas_alerta") > 0)
            .then(pl.lit("em alerta"))
            .otherwise(pl.lit("sem alerta"))
            .alias("status"),
        )
        .sort(
            ["janelas_alerta", "probabilidade_maxima", *KEY],
            descending=[True, True, False, False, False],
            nulls_last=True,
        )
    )


def alert_metrics(frame: pl.DataFrame, thresholds: dict[str, float]) -> pl.DataFrame:
    """Comparações na interseção de rótulo e scores conhecidos; nulos são reportados."""
    frame = frame.with_columns(pl.col("dia").dt.strftime("%Y-%m").alias("mes"))
    out = []
    for (source, month), group in frame.partition_by(["fonte", "mes"], as_dict=True).items():
        subsets = [("mes", "todos", group)]
        subsets += [
            ("idade", str(age[0]), part)
            for age, part in group.partition_by("idade", as_dict=True).items()
        ]
        for slice_name, value, part in subsets:
            labelled = part.filter(pl.col("y_corte").is_not_null())
            common = labelled.filter(
                pl.all_horizontal(
                    pl.col(c).is_not_null() & pl.col(c).is_finite() for c in SCORES.values()
                )
            )
            for name, column in SCORES.items():
                threshold = (
                    0.5 if name in ("ultimo_valor", "mesmo_slot_ultimo_dia") else thresholds[source]
                )
                y = common["y_corte"].to_numpy() == 1
                p = common[column].to_numpy()
                alert = p >= threshold
                tp, fp = int((alert & y).sum()), int((alert & ~y).sum())
                fn, tn = int((~alert & y).sum()), int((~alert & ~y).sum())
                out.append(
                    {
                        "fonte": source,
                        "mes": month,
                        "recorte": slice_name,
                        "valor": value,
                        "modelo": name,
                        "limiar": threshold,
                        "linhas_grade": part.height,
                        "linhas_rotuladas": labelled.height,
                        "n": common.height,
                        "nulos_score_rotulado": labelled[column].null_count(),
                        "cobertura_comum": common.height / labelled.height
                        if labelled.height
                        else None,
                        "prevalencia": float(y.mean()) if len(y) else None,
                        "ap": float(average_precision_score(y, p))
                        if 0 < y.sum() < len(y)
                        else None,
                        "brier": float(brier_score_loss(y, p)) if len(y) else None,
                        "precisao": tp / (tp + fp) if tp + fp else None,
                        "recall": tp / (tp + fn) if tp + fn else None,
                        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
                        "alertas": tp + fp,
                        "tp": tp,
                        "fp": fp,
                        "fn": fn,
                        "tn": tn,
                    }
                )
    return pl.DataFrame(out).sort(["fonte", "mes", "recorte", "valor", "modelo"])


def reproduce(
    base: pl.DataFrame, first: date, last: date, threshold: float, train_days: int = TRAIN_DAYS
) -> tuple[pl.DataFrame, object, dict]:
    """Treino congelado antes do recorte; features respeitam cada emissão às 20h."""
    if first > last or train_days < 1:
        raise ValueError("Período inválido")
    calendar = load_calendar()
    target_map = release_map(pl.date_range(first, last, eager=True).to_list(), calendar)
    last_label = target_map["ultimo_dia"][0]
    days = pl.date_range(last_label - timedelta(days=train_days - 1), last_label, eager=True)
    train = attach_targets(
        build_features(
            base.filter(pl.col("dia") <= last_label),
            release_map(days, calendar),
            feature_columns=OCCURRENCE,
        ),
        base,
    ).filter(pl.col("y_corte").is_not_null())
    info = {
        "treino_ate": str(last_label),
        "treino_dias": train_days,
        "linhas_treino": train.height,
        "nulos_features_treino": train.select(OCCURRENCE).null_count().row(0, named=True),
    }
    model = HistGradientBoostingClassifier(**PARAMS).fit(
        _matrix(train, OCCURRENCE), train["y_corte"].to_numpy()
    )
    del train
    gc.collect()
    rows = attach_targets(
        build_features(base, target_map, feature_columns=[*OCCURRENCE, "ultimo_valor_corte"]), base
    )
    info["nulos_features_avaliacao"] = rows.select(OCCURRENCE).null_count().row(0, named=True)
    rows = rows.with_columns(
        pl.Series("p_corte", model.predict_proba(_matrix(rows, OCCURRENCE))[:, 1])
    )
    result = rows.select(
        *KEY, "id_estado", "slot", "idade", "ultimo_dia", "y_corte", *SCORES.values()
    ).with_columns(
        (
            pl.col("dia").cast(pl.Datetime("us"))
            + pl.duration(minutes=pl.col("slot").cast(pl.Int64) * 30)
        ).alias("tau"),
        (pl.col("dia").cast(pl.Datetime("us")) - pl.duration(hours=4)).alias("emitido_em"),
        (pl.col("ultimo_dia").cast(pl.Datetime("us")) + pl.duration(days=1)).alias("corte_dados"),
        pl.lit(last_label).alias("treino_ate"),
        pl.lit(threshold).alias("limiar_alerta"),
        (pl.col("p_corte") >= threshold).alias("alerta"),
        pl.lit("reproducao_retrospectiva").alias("tipo_saida"),
        pl.lit("hgb_ocorrencia_v1_v3").alias("modelo_id"),
    )
    return validate_alerts(result), model, info


def sha256(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inicio", type=date.fromisoformat)
    parser.add_argument("fim", type=date.fromisoformat)
    parser.add_argument("--fonte", choices=["eolica", "fotovoltaica"], required=True)
    parser.add_argument("--dados", type=Path, default=settings.data_dir)
    parser.add_argument("--saida", type=Path, default=Path("data/interim/alertas"))
    parser.add_argument(
        "--treino-dias", type=int, default=TRAIN_DAYS, help="Menor só para ensaio de custo"
    )
    args = parser.parse_args()
    if args.inicio < date(2026, 5, 1) or args.fim >= date(2026, 9, 1) or args.inicio > args.fim:
        parser.error("Use maio–agosto/2026, após os limiares jan–abr; setembro já foi examinado")
    started = time.perf_counter()
    thresholds_path = Path("docs/reports/nova-abordagem/limiares.json")
    thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))["jan_abr"]
    raw = args.dados / "raw" / SPECS[args.fonte].filename
    digest = sha256(raw)
    audit = json.loads(Path("docs/reports/stage1/audit.json").read_text(encoding="utf-8"))
    last_label = release_map([args.inicio], load_calendar())["ultimo_dia"].item()
    # Mesma borda usada por build_features: 91 dias + margem para publicação.
    start = datetime.combine(
        last_label - timedelta(days=args.treino_dias + 100), datetime.min.time()
    )
    end = datetime.combine(args.fim + timedelta(days=1), datetime.min.time())
    history = load_history(args.dados, start, end, sources=(args.fonte,))
    attributes = history.select("fonte", "id_ons", "nom_usina").unique(
        subset=["fonte", "id_ons"], keep="last"
    )
    base = base_from_history(history)
    info = {"linhas_raw_recorte": history.height, "linhas_base_validas": base.height}
    del history
    gc.collect()
    print(f"{args.fonte}: {base.height} linhas válidas; treino até {last_label}", flush=True)
    forecasts, model, training = reproduce(
        base, args.inicio, args.fim, thresholds[args.fonte], args.treino_dias
    )
    del base
    forecasts = forecasts.join(attributes, on=["fonte", "id_ons"], how="left")
    args.saida.mkdir(parents=True, exist_ok=True)
    prefix = args.saida / f"{args.fonte}_{args.inicio}_{args.fim}"
    forecasts.write_parquet(prefix.with_suffix(".parquet"))
    metrics = alert_metrics(forecasts, thresholds)
    metrics.write_csv(prefix.with_suffix(".csv"))
    joblib.dump(model, prefix.with_suffix(".joblib"))
    manifest = {
        "natureza": "ensaio_custo"
        if args.treino_dias != TRAIN_DAYS
        else "reproducao_retrospectiva",
        "inicio": str(args.inicio),
        "fim": str(args.fim),
        "fonte": args.fonte,
        "gerado_em": datetime.now().isoformat(),
        "dados": str(raw.resolve()),
        "sha256_dados": digest,
        "bytes_dados": raw.stat().st_size,
        "hash_confere_auditoria": digest == audit["files"][args.fonte]["sha256"],
        "revisao": "snapshot local; data da revisão do ONS desconhecida",
        "periodo_lido": [str(start), str(end)],
        "periodo_snapshot": audit["files"][args.fonte]["keys"],
        "parametros": PARAMS,
        "features": OCCURRENCE,
        "limiar": thresholds[args.fonte],
        "origem_limiar": "jan_abr",
        "sha256_limiares": sha256(thresholds_path),
        "sha256_calendario": sha256(Path("configs/calendario-2023-2026.json")),
        "python": platform.python_version(),
        "sklearn": sklearn.__version__,
        "polars": pl.__version__,
        "threads": {key: os.getenv(key) for key in ("OMP_NUM_THREADS", "POLARS_MAX_THREADS")},
        "commit_base": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "sha256_script": sha256(Path(__file__)),
        "sha256_replay": sha256(prefix.with_suffix(".parquet")),
        "sha256_modelo": sha256(prefix.with_suffix(".joblib")),
        "segundos": time.perf_counter() - started,
        "linhas_previsao": forecasts.height,
        **info,
        **training,
    }
    prefix.with_suffix(".json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        metrics.filter(pl.col("recorte") == "mes").select(
            "modelo", "n", "ap", "brier", "precisao", "recall", "f1"
        )
    )
    print(f"Artefatos em {prefix}; {manifest['segundos']:.1f}s", flush=True)


if __name__ == "__main__":
    main()
