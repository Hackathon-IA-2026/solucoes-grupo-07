"""Faixas de volume da v3 no produto: treino, features de serviço e composição por limiar.

A composição servida vem do backtest da frente A (diário 11/n), com a regra pré-registrada
(diário 8/n): P(fração > k) vem do modelo onde ele venceu o `historico` e da frequência
histórica da própria usina (`historico`) onde não venceu. Na meia-hora, k₀ é a ocorrência
servida (`p_corte`); no nível diário, k₀ é um classificador diário de "algum corte no dia".
As excedências são monotonizadas e as faixas saem por diferença, com proveniência por
limiar em `tipo_saida_faixas` e `tipo_saida_faixas_dia`.

O `historico` de faixa usa o rótulo de cada dia passado d ∈ (L − 28, L] com o `cap_91d` do
seu próprio L(d); por isso o serviço precisa de ~130 dias de histórico antes do corte.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier

from curtamap.previsao.calendario import Calendar
from curtamap.previsao.faixas import (
    agregar_diario,
    cap_91d,
    fracao,
    frequencia_excedencia,
    monotonizar,
    probabilidades_faixas,
    rotulo_diario,
)
from curtamap.previsao.features import (
    KEY,
    OCCURRENCE,
    SLOT_KEY,
    attach_targets,
    build_features,
    release_map,
)
from curtamap.previsao.modelo import PARAMS, DailyModel, _matrix, fit, training_rows

MODEL_VERSION_V3 = "diario_hgb_v3"
HIST_DAYS = 28
ORDER = ["fonte", "id_ons", "dia", "slot"]
LEVELS = ("meia_hora", "diario")
# Composição decidida pela regra (diário 11/n): o modelo só onde venceu o `historico` em AP.
SERVICO = {
    "meia_hora": {
        "eolica": ["modelo", "historico", "historico"],
        "fotovoltaica": ["modelo", "modelo", "modelo"],
    },
    "diario": {
        "eolica": ["modelo", "historico", "historico"],
        "fotovoltaica": ["modelo", "modelo", "modelo"],
    },
}
POR_SLOT = ["hist_7d", "hist_28d", "hist_91d", "ultimo_slot", "vol_hist_7d", "vol_hist_28d"]
DIARIAS = [
    "usina_nivel_ultimo",
    "usina_nivel_7d",
    "estado_nivel_ultimo",
    "estado_nivel_7d",
    "estado_nivel_28d",
    "estado_ene_7d",
    "idade",
    "dia_semana",
    "feriado",
]
DAILY_FEATURES = [*(f"{c}_{s}" for c in POR_SLOT for s in ("media", "max")), *DIARIAS]
NAMES = ("sem_corte", "leve", "moderada", "severa")


def excedencias(
    labels: pl.DataFrame, mapping: pl.DataFrame, ks: list[float], chave: list[str]
) -> pl.DataFrame:
    """`exc_hist_k{j}` (frequência em 28 d até L) e `exc_ult_k{j}` (indicador em L)."""
    out = None
    for j, k in enumerate(ks):
        part = frequencia_excedencia(labels, mapping, k, HIST_DAYS, chave).rename(
            {"freq": f"exc_hist_k{j}", "ultimo": f"exc_ult_k{j}"}
        )
        out = part if out is None else out.join(part, on=[*chave, "dia"], how="left")
    return out


def _ks(faixas: dict, level: str, source: str) -> list[float]:
    values = faixas[level][source]
    return [values["k0"], values["k1"], values["k2"]]


def _with_cap(rows: pl.DataFrame, base: pl.DataFrame) -> pl.DataFrame:
    cap = cap_91d(base, rows["ultimo_dia"].unique().to_list())
    return rows.join(cap, on=[*KEY, "ultimo_dia"], how="left").with_columns(
        fracao(pl.col("y_volume"), pl.col("cap_91d")).alias("y_fracao")
    )


def _daily_table(rows: pl.DataFrame) -> pl.DataFrame:
    return (
        agregar_diario(rows, POR_SLOT, ["ultimo_dia", *DIARIAS])
        .join(rotulo_diario(rows).select(*KEY, "dia", "fracao_dia", "cap_91d"), on=[*KEY, "dia"])
        .sort([*KEY, "dia"])
    )


def features_faixas(
    base: pl.DataFrame,
    mapping: pl.DataFrame,
    faixas: dict,
    calendar: Calendar,
    features: pl.DataFrame | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Features de serviço das faixas para os dias-alvo de `mapping`, só com dados até L.

    Devolve (meia-hora, diário): `cap_91d` e os baselines de excedência por limiar e, no
    diário, as features agregadas do classificador diário.
    """
    base = base.filter(pl.col("dia") <= mapping["ultimo_dia"].max())
    if features is None:
        features = build_features(base, mapping)
    lasts = mapping["ultimo_dia"].unique().to_list()
    days = sorted({last - timedelta(days=i) for last in lasts for i in range(HIST_DAYS)})
    past = attach_targets(build_features(base, release_map(days, calendar)), base).filter(
        pl.col("y_corte").is_not_null()
    )
    past = _with_cap(past, base)
    past_daily = rotulo_diario(past)
    target = mapping.select("dia", "ultimo_dia")
    slot_parts, day_parts = [], []
    for source in features["fonte"].unique().sort().to_list():
        labels = past.filter(pl.col("fonte") == source).select(
            *SLOT_KEY, "dia", pl.col("y_fracao").alias("fracao")
        )
        daily_labels = past_daily.filter(pl.col("fonte") == source).select(
            *KEY, "dia", pl.col("fracao_dia").alias("fracao")
        )
        slot_parts.append(excedencias(labels, target, _ks(faixas, "meia_hora", source), SLOT_KEY))
        day_parts.append(excedencias(daily_labels, target, _ks(faixas, "diario", source), KEY))
    rows = features.with_columns(pl.lit(None, pl.Float32).alias("y_volume"))
    rows = _with_cap(rows, base).drop("y_volume", "y_fracao")
    slot = rows.select(*SLOT_KEY, "dia", "cap_91d").join(
        pl.concat(slot_parts, how="diagonal_relaxed"), on=[*SLOT_KEY, "dia"], how="left"
    )
    daily = (
        agregar_diario(rows, POR_SLOT, ["ultimo_dia", "cap_91d", *DIARIAS])
        .join(pl.concat(day_parts, how="diagonal_relaxed"), on=[*KEY, "dia"], how="left")
        .sort([*KEY, "dia"])
    )
    return slot.sort([*SLOT_KEY, "dia"]), daily


def _fit(rows: pl.DataFrame, columns: list[str], target: np.ndarray):
    return HistGradientBoostingClassifier(**PARAMS).fit(_matrix(rows, columns), target)


def _compose(
    frame: pl.DataFrame, scores: list[np.ndarray], serving: list[str], suffix: str
) -> pl.DataFrame:
    exceed = monotonizar(np.column_stack(scores))
    bands = probabilities = probabilidades_faixas(exceed)
    return frame.with_columns(
        *(
            pl.Series(f"p_faixa{suffix}_{name}", probabilities[:, i], dtype=pl.Float64)
            for i, name in enumerate(NAMES)
        ),
        pl.Series(
            f"faixa_provavel{suffix}", [NAMES[i] for i in bands.argmax(axis=1)], dtype=pl.String
        ),
        pl.lit(",".join(f"k{j}:{s}" for j, s in enumerate(serving))).alias(
            f"tipo_saida_faixas{suffix}"
        ),
    )


@dataclass
class BandModel:
    """Classificadores de excedência por nível, fonte e limiar, com a composição servida."""

    faixas: dict
    servico: dict = field(default_factory=lambda: SERVICO)
    meia_hora: dict = field(default_factory=dict)
    diario: dict = field(default_factory=dict)

    def predict_half(self, rows: pl.DataFrame) -> pl.DataFrame:
        """Faixas da meia-hora; `rows` tem `p_corte`, `OCCURRENCE` e `exc_hist_k*`."""
        parts = []
        for source, group in rows.partition_by("fonte", as_dict=True, maintain_order=True).items():
            source = source[0]
            serving = self.servico["meia_hora"][source]
            scores = []
            for j, kind in enumerate(serving):
                if kind == "historico":
                    scores.append(group[f"exc_hist_k{j}"].fill_null(0.0).to_numpy())
                elif j == 0:
                    scores.append(group["p_corte"].to_numpy())
                else:
                    model = self.meia_hora[source][j]
                    scores.append(model.predict_proba(_matrix(group, OCCURRENCE))[:, 1])
            parts.append(_compose(group, scores, serving, ""))
        return pl.concat(parts, how="diagonal_relaxed")

    def predict_daily(self, daily: pl.DataFrame) -> pl.DataFrame:
        """Faixas usina × dia a partir da tabela de `features_faixas`."""
        parts = []
        for source, group in daily.partition_by("fonte", as_dict=True, maintain_order=True).items():
            source = source[0]
            serving = self.servico["diario"][source]
            scores = [
                group[f"exc_hist_k{j}"].fill_null(0.0).to_numpy()
                if kind == "historico"
                else self.diario[source][j].predict_proba(_matrix(group, DAILY_FEATURES))[:, 1]
                for j, kind in enumerate(serving)
            ]
            parts.append(_compose(group.select(*KEY, "dia"), scores, serving, "_dia"))
        return pl.concat(parts, how="diagonal_relaxed").sort([*KEY, "dia"])

    def augment(
        self,
        predicted: pl.DataFrame,
        base: pl.DataFrame,
        mapping: pl.DataFrame,
        features: pl.DataFrame,
        calendar: Calendar,
    ) -> pl.DataFrame:
        """Acrescenta às previsões da meia-hora as colunas de faixa dos dois níveis."""
        slot, daily = features_faixas(base, mapping, self.faixas, calendar, features)
        rows = predicted.join(slot, on=[*SLOT_KEY, "dia"], how="left")
        rows = self.predict_half(rows).drop(slot.columns[4:])
        return rows.join(self.predict_daily(daily), on=[*KEY, "dia"], how="left")


def fit_v3(
    base: pl.DataFrame,
    mapping: pl.DataFrame,
    last_label_day: date,
    faixas: dict,
    calendar: Calendar,
    **metadata,
) -> DailyModel:
    """Componentes da v1 (mesma receita) mais os classificadores de faixa servidos."""
    model = fit(base, mapping, last_label_day, **metadata)
    labelled = base.filter(pl.col("dia") <= last_label_day)
    rows = _with_cap(training_rows(labelled, mapping, last_label_day), labelled).sort(ORDER)
    daily = _daily_table(rows)
    bands = BandModel(faixas)
    counts: dict = {level: {} for level in LEVELS}
    for source in model.sources:
        half = rows.filter(pl.col("fonte") == source, pl.col("y_fracao").is_not_null())
        day = daily.filter(pl.col("fonte") == source, pl.col("fracao_dia").is_not_null())
        ks_half, ks_day = _ks(faixas, "meia_hora", source), _ks(faixas, "diario", source)
        bands.meia_hora[source] = {
            j: _fit(half, OCCURRENCE, (half["y_fracao"].to_numpy() > k).astype(int))
            for j, k in enumerate(ks_half)
            if j > 0 and SERVICO["meia_hora"][source][j] == "modelo"
        }
        bands.diario[source] = {
            j: _fit(day, DAILY_FEATURES, (day["fracao_dia"].to_numpy() > k).astype(int))
            for j, k in enumerate(ks_day)
            if SERVICO["diario"][source][j] == "modelo"
        }
        counts["meia_hora"][source] = half.height
        counts["diario"][source] = day.height
    model.faixas = bands
    model.metadata.update(
        versao=MODEL_VERSION_V3,
        faixas={
            "limiares": faixas,
            "servico": SERVICO,
            "treino_ate": last_label_day.isoformat(),
            "features_meia_hora": OCCURRENCE,
            "features_diario": DAILY_FEATURES,
            "linhas_treino": counts,
        },
    )
    return model
