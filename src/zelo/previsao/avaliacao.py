"""Backtest com origem expandindo, dobras mensais e baselines nas mesmas linhas.

Para cada mês M, o modelo é treinado com rótulos até o último dia liberado na emissão da
véspera do primeiro dia de M e avaliado em todos os dias-alvo de M, com as features que cada
emissão diária das 20h teria. Os baselines usam exatamente as mesmas linhas:

- `historico`: frequência de corte da usina no slot em 28 dias até L;
- `mesmo_slot_ultimo_dia`: o mesmo slot no último dia liberado L;
- `ultimo_valor`: a última meia-hora observada da usina em L;
- causa (servida sem modelo): moda da usina no slot em 28 dias e moda do estado em 7 dias.

Volume não é avaliado: o produto não o prevê desde 26/09/2026. As métricas de volume e do
modelo de causa da v1 estão em `docs/reports/nova-abordagem/metricas_backtest.csv`.

"Mesmo horário do dia anterior" (T − 1) não é baseline possível: na emissão das 20h, T − 1
nunca está liberado (idade mínima de 2 dias). A cobertura é 0% e isso é reportado assim.

Uso: `uv run python -m zelo.previsao.avaliacao 2026-01 2026-08`.
"""

import argparse
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score

from zelo.config import settings
from zelo.contracts import PREDICTABLE_CAUSES, SOURCES
from zelo.forecasting import load_history
from zelo.previsao.calendario import load_calendar
from zelo.previsao.features import (
    attach_targets,
    base_from_history,
    build_features,
    release_map,
)
from zelo.previsao.modelo import fit, predict_source

FIRST_DAY = date(2023, 10, 1)
_CAUSE_SHARES = [f"causa_{c.lower()}_28d" for c in PREDICTABLE_CAUSES]
_STATE_SHARES = [f"estado_{c.lower()}_7d" for c in PREDICTABLE_CAUSES]
KEEP = [
    "fonte",
    "id_ons",
    "id_estado",
    "dia",
    "slot",
    "idade",
    "y_corte",
    "y_causa",
    "p_corte",
    "hist_28d",
    "ultimo_slot",
    "ultimo_valor_corte",
    *_CAUSE_SHARES,
    *_STATE_SHARES,
]


def load_base(data_dir: Path, end: datetime) -> pl.DataFrame:
    """Base compacta das duas fontes em `[FIRST_DAY, end)`, uma fonte por vez (memória)."""
    start = datetime.combine(FIRST_DAY, datetime.min.time())
    return pl.concat(
        [
            base_from_history(load_history(data_dir, start, end, sources=(source,)))
            for source in SOURCES
        ]
    ).sort(["fonte", "id_ons", "dia", "slot"])


def _argmax(columns: list[str]) -> pl.Expr:
    present = pl.any_horizontal(pl.col(c).is_not_null() for c in columns)
    choice = pl.concat_list(pl.col(c).fill_null(-1.0) for c in columns).list.arg_max()
    return (
        pl.when(present)
        .then(choice.replace_strict(dict(enumerate(PREDICTABLE_CAUSES))))
        .otherwise(None)
    )


def backtest_month(base: pl.DataFrame, month: date, calendar) -> pl.DataFrame:
    """Previsões do modelo e baselines para os dias-alvo de `month`."""
    following = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    target_days = pl.date_range(month, following - timedelta(days=1), eager=True).to_list()
    last_label = release_map([month], calendar)["ultimo_dia"].item()
    history_days = pl.date_range(FIRST_DAY, last_label, eager=True).to_list()
    model = fit(
        base.filter(pl.col("dia") <= last_label),
        release_map(history_days, calendar),
        last_label,
    )
    rows = attach_targets(build_features(base, release_map(target_days, calendar)), base)
    parts = [
        predict_source(model.sources[s], rows.filter(pl.col("fonte") == s)) for s in model.sources
    ]
    predicted = pl.concat(parts, how="diagonal_relaxed").filter(pl.col("y_corte").is_not_null())
    return predicted.select(KEEP).with_columns(
        pl.lit(month).alias("mes"), pl.lit(last_label).alias("treino_ate")
    )


def choose_threshold(y: np.ndarray, p: np.ndarray) -> float:
    """Limiar que maximiza F1 do alerta; usado só com previsões fora da amostra.

    O alerta é `p >= limiar`, então cada limiar inclui o grupo empatado inteiro: o F1 só é
    avaliado no fim de cada grupo de probabilidades iguais.
    """
    order = np.argsort(-p, kind="stable")
    ranked = p[order]
    hits = np.cumsum(y[order])
    alerts = np.arange(1, len(y) + 1)
    group_end = np.append(ranked[1:] != ranked[:-1], True)
    hits, alerts = hits[group_end], alerts[group_end]
    precision = hits / alerts
    recall = hits / max(y.sum(), 1)
    f1 = 2 * precision * recall / np.clip(precision + recall, 1e-12, None)
    return float(ranked[group_end][int(np.argmax(f1))])


def _occurrence(frame: pl.DataFrame, threshold: float) -> dict:
    y = frame["y_corte"].to_numpy()
    out = {"n": len(y), "prevalencia": float(y.mean())}
    if 0 < y.sum() < len(y):
        for name, column in [
            ("modelo", "p_corte"),
            ("historico", "hist_28d"),
            ("mesmo_slot_ultimo_dia", "ultimo_slot"),
            ("ultimo_valor", "ultimo_valor_corte"),
        ]:
            score = frame[column].fill_null(0.0).to_numpy()
            out[f"ap_{name}"] = float(average_precision_score(y, score))
            out[f"brier_{name}"] = float(brier_score_loss(y, np.clip(score, 0, 1)))
    alert = frame["p_corte"].to_numpy() >= threshold
    out["recall_alerta"] = float((alert & (y == 1)).sum() / max(y.sum(), 1))
    out["precisao_alerta"] = float((alert & (y == 1)).sum() / max(alert.sum(), 1))
    return out


def _cause(frame: pl.DataFrame) -> dict:
    rows = frame.filter(pl.col("y_causa").is_not_null())
    out = {"n_causa": rows.height}
    if rows.is_empty():
        return out
    rows = rows.with_columns(
        _argmax(_CAUSE_SHARES).alias("_usina"),
        _argmax(_STATE_SHARES).alias("_estado"),
    )
    y = rows["y_causa"].to_numpy()
    for name, column in [("usina_28d", "_usina"), ("estado_7d", "_estado")]:
        predicted = rows[column].fill_null("SEM").to_numpy()
        out[f"f1_{name}"] = float(
            f1_score(
                y, predicted, labels=list(PREDICTABLE_CAUSES), average="macro", zero_division=0
            )
        )
    return out


def metrics(predictions: pl.DataFrame, thresholds: dict[str, float]) -> pl.DataFrame:
    """Métricas por fonte × mês (e agregado 'todos') contra os baselines."""
    rows = []
    groups = predictions.partition_by(["fonte", "mes"], as_dict=True)
    for (source, month), frame in sorted(groups.items()):
        rows.append(
            {
                "fonte": source,
                "periodo": month.isoformat(),
                **_occurrence(frame, thresholds.get(source, 0.5)),
                **_cause(frame),
            }
        )
    return pl.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inicio", help="primeiro mês avaliado, AAAA-MM")
    parser.add_argument("fim", help="último mês avaliado, AAAA-MM")
    parser.add_argument("--saida", type=Path, default=settings.data_dir / "interim" / "previsao")
    args = parser.parse_args()
    first = date.fromisoformat(args.inicio + "-01")
    last = date.fromisoformat(args.fim + "-01")
    calendar = load_calendar()
    end = datetime.combine(
        (last.replace(day=28) + timedelta(days=4)).replace(day=1), datetime.min.time()
    )
    base = load_base(settings.data_dir, end)
    args.saida.mkdir(parents=True, exist_ok=True)
    month = first
    while month <= last:
        started = time.time()
        path = args.saida / f"backtest_{month:%Y-%m}.parquet"
        backtest_month(base, month, calendar).sort(
            ["fonte", "id_ons", "dia", "slot"]
        ).write_parquet(path)
        print(
            json.dumps({"mes": f"{month:%Y-%m}", "segundos": round(time.time() - started)}),
            flush=True,
        )
        month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)


if __name__ == "__main__":
    main()
