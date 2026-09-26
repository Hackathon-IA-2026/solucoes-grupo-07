"""HGB do produto (controle) e variantes com ajustes limitados.

As médias de 7 e 28 dias (`hist_7d`, `hist_28d`, `vol_hist_7d`, `vol_hist_28d`) já existem no
produto. O que este módulo acrescenta são funções delas e de janelas equivalentes, todas
calculadas com dados até o último dia liberado L, com a mesma semântica de
`curtamap.previsao.features`:

- **mudança recente:** diferenças 7 d − 28 d do perfil do slot, do nível estadual e do nível
  da usina; razão em log com tratamento de zero, `log1p(v7) − log1p(v28)`, que é 0 quando
  as duas médias são zero em vez de indefinida;
- **variabilidade:** desvio padrão do volume do slot em 28 d e coeficiente de variação
  `std / (média + 1 MWmed)`;
- **cobertura:** fração das meias-horas da usina com volume válido em 28 d (`cobertura_28d`,
  calculada no produto, mas não usada como feature) e dias observados do slot em 28 d.
  Ausência reduz a cobertura; não vira corte zero;
- **nível de volume da usina:** média diária do volume em 7 e 28 d.

**Janela da feature ≠ janela de treino.** A janela da feature (7, 28 ou 91 d) é o passado de
cada linha até L. A janela de treino (`train_days`) é quantos dias-alvo rotulados, até o corte
da dobra, entram no ajuste do modelo. `half_life` dá peso maior aos dias-alvo recentes.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from curtamap.previsao.features import KEY, OCCURRENCE, SLOT_KEY, VOLUME, build_features
from curtamap.previsao.modelo import PARAMS, TRAIN_DAYS

CHANGE = ["d_hist_7_28", "d_estado_7_28", "d_usina_ult_7"]
COVERAGE = ["cobertura_28d", "n_dias_slot_28d"]
VOLUME_CHANGE = [
    "d_vol_7_28",
    "lr_vol_7_28",
    "vol_std_28d",
    "cv_vol_28d",
    "usina_vol_7d",
    "usina_vol_28d",
    "lr_usina_vol_7_28",
]
NEW_FEATURES = [*CHANGE, *COVERAGE, *VOLUME_CHANGE]
EXT_OCCURRENCE = [*OCCURRENCE, *CHANGE, *COVERAGE]
EXT_VOLUME = [*VOLUME, *CHANGE, *COVERAGE, *VOLUME_CHANGE]


@dataclass(frozen=True)
class Variant:
    occurrence: list[str]
    volume: list[str]
    params: dict = field(default_factory=lambda: dict(PARAMS))
    train_days: int = TRAIN_DAYS
    half_life: int | None = None
    description: str = ""


_FAST = {**PARAMS, "learning_rate": 0.1, "max_leaf_nodes": 63, "min_samples_leaf": 100}
_SMOOTH = {**PARAMS, "max_iter": 500, "max_leaf_nodes": 15, "min_samples_leaf": 1000}
VARIANTS = {
    "B0_original": Variant(OCCURRENCE, VOLUME, description="receita do produto, controle"),
    "B1_mudanca": Variant(EXT_OCCURRENCE, EXT_VOLUME, description="+ mudança, cobertura"),
    "B2_janela180": Variant(
        EXT_OCCURRENCE, EXT_VOLUME, train_days=180, description="B1, treino de 180 dias"
    ),
    "B3_recencia60": Variant(
        EXT_OCCURRENCE, EXT_VOLUME, half_life=60, description="B1, peso com meia-vida 60 d"
    ),
    "B4_hp_rapido": Variant(
        EXT_OCCURRENCE, EXT_VOLUME, params=_FAST, description="B1, lr 0,1, 63 folhas, msl 100"
    ),
    "B5_hp_suave": Variant(
        EXT_OCCURRENCE, EXT_VOLUME, params=_SMOOTH, description="B1, 500 it, 15 folhas, msl 1000"
    ),
}


def _rolling(column: str, window: str, keys: list[str]) -> pl.Expr:
    return pl.col(column).rolling_mean_by("dia", window_size=window).over(keys)


def _extra_slot(base: pl.DataFrame) -> pl.DataFrame:
    return (
        base.sort([*SLOT_KEY, "dia"])
        .with_columns(pl.lit(1, pl.Int16).alias("_um"))
        .with_columns(
            pl.col("volume").rolling_std_by("dia", window_size="28d").over(SLOT_KEY)
            .fill_null(0.0).alias("vol_std_28d"),
            pl.col("_um").rolling_sum_by("dia", window_size="28d").over(SLOT_KEY)
            .alias("n_dias_slot_28d"),
        )
        .select(*SLOT_KEY, pl.col("dia").alias("ultimo_dia"), "vol_std_28d", "n_dias_slot_28d")
    )  # fmt: skip


def _extra_plant(base: pl.DataFrame) -> pl.DataFrame:
    daily = base.group_by([*KEY, "dia"]).agg(pl.col("volume").mean().alias("_vol"))
    return (
        daily.sort([*KEY, "dia"])
        .with_columns(
            _rolling("_vol", "7d", KEY).alias("usina_vol_7d"),
            _rolling("_vol", "28d", KEY).alias("usina_vol_28d"),
        )
        .select(*KEY, pl.col("dia").alias("ultimo_dia"), "usina_vol_7d", "usina_vol_28d")
    )


def _asof(grid: pl.DataFrame, table: pl.DataFrame, by: list[str]) -> pl.DataFrame:
    return grid.sort("ultimo_dia").join_asof(
        table.sort("ultimo_dia"),
        on="ultimo_dia",
        by=by,
        strategy="backward",
        check_sortedness=False,
    )


def build_rows(base: pl.DataFrame, mapping: pl.DataFrame) -> pl.DataFrame:
    """`build_features` do produto mais as variáveis novas, com dados até L."""
    grid = build_features(base, mapping)
    if grid.is_empty():
        return grid
    horizon = base.filter(pl.col("dia") <= mapping["ultimo_dia"].max())
    grid = _asof(grid, _extra_slot(horizon), SLOT_KEY)
    grid = _asof(grid, _extra_plant(horizon), KEY)
    log = pl.col  # abreviação
    return grid.with_columns(
        (log("hist_7d") - log("hist_28d")).alias("d_hist_7_28"),
        (log("estado_nivel_7d") - log("estado_nivel_28d")).alias("d_estado_7_28"),
        (log("usina_nivel_ultimo") - log("usina_nivel_7d")).alias("d_usina_ult_7"),
        (log("vol_hist_7d") - log("vol_hist_28d")).alias("d_vol_7_28"),
        (log("vol_hist_7d").log1p() - log("vol_hist_28d").log1p()).alias("lr_vol_7_28"),
        (log("vol_std_28d") / (log("vol_hist_28d") + 1.0)).alias("cv_vol_28d"),
        (log("usina_vol_7d").log1p() - log("usina_vol_28d").log1p()).alias("lr_usina_vol_7_28"),
    ).sort([*KEY, "dia", "slot"])


def recency_weights(days: pl.Series, last_label: date, half_life: int | None):
    if half_life is None:
        return None
    age = np.array([(last_label - d).days for d in days.to_list()], dtype=float)
    return 0.5 ** (age / half_life)


def _matrix(frame: pl.DataFrame, columns: list[str]) -> np.ndarray:
    return frame.select(pl.col(columns).cast(pl.Float32)).to_numpy()


@dataclass
class FittedVariant:
    occurrence: HistGradientBoostingClassifier
    volume: HistGradientBoostingRegressor
    variant: Variant


def fit_variant(rows: pl.DataFrame, variant: Variant, last_label: date) -> FittedVariant:
    """Ajusta ocorrência (binária) e volume esperado (Poisson), como o produto."""
    rows = rows.filter(
        pl.col("y_corte").is_not_null(),
        pl.col("dia") <= last_label,
        pl.col("dia") > last_label - timedelta(days=variant.train_days),
    )
    weights = recency_weights(rows["dia"], last_label, variant.half_life)
    occurrence = HistGradientBoostingClassifier(**variant.params).fit(
        _matrix(rows, variant.occurrence), rows["y_corte"].to_numpy(), sample_weight=weights
    )
    volume = HistGradientBoostingRegressor(loss="poisson", **variant.params).fit(
        _matrix(rows, variant.volume), rows["y_volume"].to_numpy(), sample_weight=weights
    )
    return FittedVariant(occurrence, volume, variant)


def predict_variant(model: FittedVariant, rows: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    p = model.occurrence.predict_proba(_matrix(rows, model.variant.occurrence))[:, 1]
    v = np.clip(model.volume.predict(_matrix(rows, model.variant.volume)), 0, None)
    return p, v
