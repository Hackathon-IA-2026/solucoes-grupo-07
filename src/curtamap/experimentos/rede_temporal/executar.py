"""Executa as dobras do experimento e grava previsões individuais em parquet.

Uso (a partir da raiz do worktree, com `CURTAMAP_DATA_DIR` apontando para os Parquet):

    uv run python -m curtamap.experimentos.rede_temporal.executar hgb \
        --meses 2026-01 2026-02 --variantes B0_original B1_mudanca
    uv run python -m curtamap.experimentos.rede_temporal.executar rede \
        --meses 2026-01 --sementes 0 1 2

Cada arquivo `pred/{mes}_{fonte}.parquet` guarda as linhas avaliadas daquele mês e fonte,
os rótulos, as colunas dos baselines e uma coluna `p_<candidato>`/`v_<candidato>` por
candidato. Rodar de novo acrescenta ou substitui colunas; as linhas são sempre as mesmas.
Os tempos vão para `tempos.jsonl`.
"""

import argparse
import json
import platform
import time
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from curtamap.contracts import SOURCES
from curtamap.experimentos.rede_temporal import hgb
from curtamap.experimentos.rede_temporal.dados import (
    HOLDOUT_DAY,
    OUTPUT,
    SEPTEMBER,
    build_base,
    fold_cutoff,
    month_days,
    month_key,
    without_holdout,
)
from curtamap.previsao.calendario import load_calendar
from curtamap.previsao.features import attach_targets, release_map

KEY = ["fonte", "id_ons", "dia", "slot"]
KEEP = [
    *KEY,
    "id_estado",
    "idade",
    "y_corte",
    "y_volume",
    "hist_28d",
    "vol_hist_28d",
    "cobertura_28d",
]


def target_days(month: date) -> list[date]:
    if month == HOLDOUT_DAY:
        return [HOLDOUT_DAY]
    days = month_days(month)
    return without_holdout(days) if month == SEPTEMBER else days


def cutoff_for(month: date, calendar) -> date:
    """O dia reservado é previsto pelos mesmos modelos da dobra de setembro."""
    return fold_cutoff(SEPTEMBER if month == HOLDOUT_DAY else month, calendar)


def _base(output: Path, months: list[date]) -> pl.DataFrame:
    return build_base(output, include_holdout=HOLDOUT_DAY in months)


def _prediction_path(output: Path, month: date, source: str, family: str = "") -> Path:
    prefix = f"{family}_" if family else ""
    return output / "pred" / f"{prefix}{month_key(month)}_{source}.parquet"


def _wait_for(path: Path, poll_seconds: int = 30) -> None:
    """A rede usa as linhas avaliadas gravadas pelo HGB; espera o arquivo existir."""
    while not path.exists():
        time.sleep(poll_seconds)


def save_columns(
    path: Path, rows: pl.DataFrame, columns: dict[str, object], *, with_base: bool = True
) -> None:
    """Acrescenta colunas de previsão ao arquivo do mês, conferindo que as linhas batem.

    `with_base=False` grava só a chave e as colunas (arquivos da rede, separados dos do HGB
    para que processos paralelos não escrevam no mesmo arquivo).
    """
    new = rows.select(KEY).with_columns(
        pl.Series(k, v, dtype=pl.Float64) for k, v in columns.items()
    )
    if path.exists():
        current = pl.read_parquet(path)
        if current.select(KEY).sort(KEY).equals(rows.select(KEY).sort(KEY)) is False:
            raise ValueError(f"linhas diferentes das já gravadas em {path}")
        current = current.drop([c for c in columns if c in current.columns])
        frame = current.join(new, on=KEY, how="left")
    elif not with_base:
        frame = new
    else:
        frame = (
            rows.select(KEEP)
            .with_columns(
                pl.col("hist_28d").fill_null(0.0).cast(pl.Float64).alias("p_historico"),
                pl.col("vol_hist_28d").fill_null(0.0).cast(pl.Float64).alias("v_historico"),
            )
            .join(new, on=KEY, how="left")
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.sort(KEY).write_parquet(path)


def log_time(output: Path, record: dict) -> None:
    record |= {"maquina": platform.processor() or platform.machine()}
    with (output / "tempos.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def fold_rows(base: pl.DataFrame, month: date, source: str, calendar, train_days: int):
    """Linhas de treino (até o corte da dobra) e de avaliação de uma fonte."""
    cutoff = cutoff_for(month, calendar)
    data = base.filter(pl.col("fonte") == source)
    known = data.filter(pl.col("dia") <= cutoff)
    train_mapping = release_map(
        pl.date_range(cutoff - timedelta(days=train_days - 1), cutoff, eager=True).to_list(),
        calendar,
    )
    train = attach_targets(hgb.build_rows(known, train_mapping), known)
    evaluation = attach_targets(
        hgb.build_rows(data, release_map(target_days(month), calendar)), data
    ).filter(pl.col("y_corte").is_not_null())
    return cutoff, train, evaluation


def run_hgb(months: list[date], names: list[str], output: Path) -> None:
    calendar = load_calendar()
    base = _base(output, months)
    longest = max(hgb.VARIANTS[n].train_days for n in names)
    for month in months:
        for source in SOURCES:
            started = time.time()
            cutoff, train, evaluation = fold_rows(base, month, source, calendar, longest)
            log_time(
                output,
                {
                    "etapa": "linhas",
                    "mes": month,
                    "fonte": source,
                    "segundos": round(time.time() - started, 1),
                    "linhas_treino": train.height,
                    "linhas_avaliadas": evaluation.height,
                },
            )
            columns = {}
            for name in names:
                started = time.time()
                model = hgb.fit_variant(train, hgb.VARIANTS[name], cutoff)
                fit_seconds = time.time() - started
                started = time.time()
                p, v = hgb.predict_variant(model, evaluation)
                columns |= {f"p_{name}": p, f"v_{name}": v}
                log_time(
                    output,
                    {
                        "etapa": "hgb",
                        "candidato": name,
                        "mes": month,
                        "fonte": source,
                        "treino_ate": cutoff,
                        "segundos_treino": round(fit_seconds, 1),
                        "segundos_inferencia": round(time.time() - started, 2),
                    },
                )
                print(f"{month:%Y-%m} {source} {name}: {fit_seconds:.0f} s", flush=True)
            save_columns(_prediction_path(output, month, source), evaluation, columns)


NETS = {
    "C_gru64_k28": {"window_days": 28, "hidden": 64},
    "C_gru32_k14": {"window_days": 14, "hidden": 32},
}


def run_rede(months: list[date], seeds: list[int], name: str, output: Path) -> None:
    import torch

    from curtamap.experimentos.rede_temporal import rede

    torch.set_num_threads(6)
    calendar = load_calendar()
    config = rede.NetConfig(**NETS[name])
    started = time.time()
    tensor = rede.DailyTensor.from_base(_base(output, months))
    log_time(output, {"etapa": "tensor", "segundos": round(time.time() - started, 1)})
    for month in months:
        for source in SOURCES:
            _wait_for(_prediction_path(output, month, source))
        cutoff = cutoff_for(month, calendar)
        history_days = pl.date_range(
            cutoff - timedelta(days=config.train_days - 1), cutoff, eager=True
        ).to_list()
        mapping = release_map(history_days, calendar)
        targets = release_map(target_days(month), calendar)
        for seed in seeds:
            started = time.time()
            net = rede.fit_net(tensor, mapping, cutoff, config, seed)
            fit_seconds = time.time() - started
            for source in SOURCES:
                rows_path = _prediction_path(output, month, source)
                _wait_for(rows_path)
                rows = pl.read_parquet(rows_path).select(KEY)
                path = _prediction_path(output, month, source, "rede")
                samples = rows.select("fonte", "id_ons", "dia").unique().join(targets, on="dia")
                started = time.time()
                predicted = rede.predict_net(net, tensor, samples)
                seconds = time.time() - started
                joined = rows.select(KEY).join(
                    predicted.with_columns(pl.col("slot").cast(rows["slot"].dtype)),
                    on=KEY,
                    how="left",
                )
                candidate = f"{name}_s{seed}"
                save_columns(
                    path,
                    rows,
                    {f"p_{candidate}": joined["p"], f"v_{candidate}": joined["v"]},
                    with_base=False,
                )
                log_time(
                    output,
                    {
                        "etapa": "rede",
                        "candidato": candidate,
                        "mes": month,
                        "fonte": source,
                        "treino_ate": cutoff,
                        "segundos_treino": round(fit_seconds, 1),
                        "segundos_inferencia": round(seconds, 2),
                        "epocas": net.best_epochs,
                        "historico": net.history,
                    },
                )
            print(f"{month:%Y-%m} {name} semente {seed}: {fit_seconds:.0f} s, "
                  f"{net.best_epochs} épocas", flush=True)  # fmt: skip


def _months(values: list[str]) -> list[date]:
    """`AAAA-MM` é uma dobra mensal; `2026-09-25` é o dia reservado."""
    return [date.fromisoformat(v if len(v) == 10 else v + "-01") for v in values]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    h = sub.add_parser("hgb")
    h.add_argument("--meses", nargs="+", required=True)
    h.add_argument("--variantes", nargs="+", default=list(hgb.VARIANTS))
    h.add_argument("--saida", type=Path, default=OUTPUT)
    r = sub.add_parser("rede")
    r.add_argument("--meses", nargs="+", required=True)
    r.add_argument("--sementes", nargs="+", type=int, default=[0])
    r.add_argument("--config", choices=list(NETS), default="C_gru64_k28")
    r.add_argument("--saida", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.comando == "hgb":
        run_hgb(_months(args.meses), args.variantes, args.saida)
    else:
        run_rede(_months(args.meses), args.sementes, args.config, args.saida)


if __name__ == "__main__":
    main()
