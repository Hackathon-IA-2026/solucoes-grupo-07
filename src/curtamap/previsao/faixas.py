"""Faixas relativas de volume de corte (v3, frente A).

O volume da meia-hora (`y_volume`, MWmed) é normalizado por `cap_91d`: o p99 de
`val_geracaoreferencia` da usina nos 91 dias que terminam no último dia liberado L,
conhecido no instante da previsão. A fração diária é a energia cortada no dia sobre
`cap_91d × 24 h` e exige as 48 meias-horas com volume determinado.

As faixas são sem corte (fração = 0), leve (0, k₁], moderado (k₁, k₂] e severo (> k₂). O
modelo estima probabilidades de excedência P(fração > k) por limiar; `monotonizar` impõe
que elas não cresçam com k e `probabilidades_faixas` obtém as faixas por diferença.

Janelas são exatas: (L − janela, L], mesmo quando a usina não tem dado em L.
"""

from collections.abc import Callable, Iterable
from datetime import date, timedelta

import numpy as np
import polars as pl

KEY = ["fonte", "id_ons"]
CAP_DAYS = 91
CAP_QUANTILE = 0.99
SLOTS_PER_DAY = 48
FAIXAS = ("sem_corte", "leve", "moderado", "severo")


def por_janela(
    frame: pl.DataFrame,
    ultimos: Iterable[date],
    janela: int,
    agregar: Callable[[pl.DataFrame], pl.DataFrame],
) -> pl.DataFrame:
    """Aplica `agregar` às linhas com `dia` em (L − janela, L] para cada L."""
    frame = frame.sort("dia")
    dias = frame["dia"].to_numpy()
    parts = []
    for last in sorted(set(ultimos)):
        lo = np.searchsorted(dias, np.datetime64(last - timedelta(days=janela - 1)), "left")
        hi = np.searchsorted(dias, np.datetime64(last), "right")
        part = agregar(frame.slice(lo, hi - lo))
        parts.append(part.with_columns(pl.lit(last, pl.Date).alias("ultimo_dia")))
    return pl.concat(parts, how="vertical_relaxed") if parts else pl.DataFrame()


def cap_91d(base: pl.DataFrame, ultimos: Iterable[date]) -> pl.DataFrame:
    """p99 de `referencia` por usina em (L − 91, L]; nulo se não houver dado na janela."""
    ultimos = sorted(set(ultimos))
    found = por_janela(
        base.select(*KEY, "dia", "referencia"),
        ultimos,
        CAP_DAYS,
        lambda part: part.group_by(KEY).agg(
            pl.col("referencia").quantile(CAP_QUANTILE, interpolation="linear").alias("cap_91d")
        ),
    )
    grid = (
        base.select(KEY)
        .unique()
        .join(pl.DataFrame({"ultimo_dia": ultimos}, schema={"ultimo_dia": pl.Date}), how="cross")
    )
    if found.is_empty():
        return grid.with_columns(pl.lit(None, pl.Float64).alias("cap_91d"))
    return (
        grid.join(found, on=[*KEY, "ultimo_dia"], how="left")
        .with_columns(pl.col("cap_91d").cast(pl.Float64))
        .sort([*KEY, "ultimo_dia"])
    )


def fracao(volume: pl.Expr, cap: pl.Expr) -> pl.Expr:
    """Volume sobre a capacidade, nunca negativa; nula sem capacidade positiva."""
    return pl.when(cap > 0).then((volume / cap).clip(lower_bound=0.0)).otherwise(None)


def rotulo_diario(rows: pl.DataFrame) -> pl.DataFrame:
    """Fração diária = energia cortada / (cap_91d × 24 h); nula sem os 48 slots válidos."""
    daily = rows.group_by([*KEY, "dia"]).agg(
        pl.col("y_volume").is_not_null().sum().alias("slots_validos"),
        (pl.col("y_volume").sum() * 0.5).alias("energia_mwh"),
        pl.col("cap_91d").first(),
    )
    complete = pl.col("slots_validos") == SLOTS_PER_DAY
    return daily.with_columns(
        pl.when(complete)
        .then(fracao(pl.col("energia_mwh"), pl.col("cap_91d") * 24.0))
        .alias("fracao_dia")
    ).sort([*KEY, "dia"])


def faixa(valor: pl.Expr, k1: float, k2: float) -> pl.Expr:
    """0 sem corte, 1 leve (0, k₁], 2 moderado (k₁, k₂], 3 severo (> k₂)."""
    return (
        pl.when(valor.is_null())
        .then(None)
        .when(valor <= 0)
        .then(0)
        .when(valor <= k1)
        .then(1)
        .when(valor <= k2)
        .then(2)
        .otherwise(3)
        .cast(pl.Int8)
    )


def tercis(valores: np.ndarray, casas: int = 2) -> tuple[float, float]:
    """p33 e p67 das frações positivas, arredondados; erro se os limiares colapsarem."""
    positive = valores[np.isfinite(valores) & (valores > 0)]
    k1, k2 = (round(float(np.quantile(positive, q)), casas) for q in (1 / 3, 2 / 3))
    if not 0 < k1 < k2:
        raise ValueError(f"limiares colapsados com {casas} casas: k1={k1}, k2={k2}")
    return k1, k2


def monotonizar(excedencia: np.ndarray) -> np.ndarray:
    """P(> k) não crescente em k: mínimo acumulado ao longo dos limiares (colunas)."""
    return np.minimum.accumulate(np.clip(excedencia, 0.0, 1.0), axis=1)


def probabilidades_faixas(excedencia: np.ndarray) -> np.ndarray:
    """Probabilidades das faixas a partir de P(> k₀), P(> k₁), P(> k₂) já monótonas."""
    upper = np.hstack([np.ones((len(excedencia), 1)), excedencia])
    lower = np.hstack([excedencia, np.zeros((len(excedencia), 1))])
    return upper - lower


def rps(probabilidades: np.ndarray, faixa_real: np.ndarray) -> float:
    """Ranked Probability Score médio, normalizado por (K − 1) para ficar em [0, 1]."""
    classes = probabilidades.shape[1]
    observed = np.eye(classes)[faixa_real.astype(int)]
    forecast_cdf = np.cumsum(probabilidades, axis=1)[:, :-1]
    observed_cdf = np.cumsum(observed, axis=1)[:, :-1]
    return float(np.mean(np.sum((forecast_cdf - observed_cdf) ** 2, axis=1) / (classes - 1)))


def frequencia_excedencia(
    rotulos: pl.DataFrame, mapping: pl.DataFrame, k: float, janela: int, chave: list[str]
) -> pl.DataFrame:
    """Baseline por limiar: frequência de `fracao > k` em (L − janela, L] e o indicador em L.

    `rotulos` tem `chave`, `dia` e `fracao` (o próprio rótulo de cada dia passado, sem
    vazamento porque só entram dias até L). Rótulos nulos ficam fora; sem nenhum rótulo na
    janela a frequência é nula.
    """
    labelled = rotulos.filter(pl.col("fracao").is_not_null()).with_columns(
        (pl.col("fracao") > k).cast(pl.Float64).alias("_acima")
    )
    ultimos = mapping["ultimo_dia"].unique().to_list()
    window = por_janela(
        labelled,
        ultimos,
        janela,
        lambda part: part.group_by(chave).agg(pl.col("_acima").mean().alias("freq")),
    )
    last = labelled.select(
        *chave, pl.col("dia").alias("ultimo_dia"), pl.col("_acima").alias("ultimo")
    )
    grid = mapping.select("dia", "ultimo_dia").join(rotulos.select(chave).unique(), how="cross")
    if not window.is_empty():
        grid = grid.join(window, on=[*chave, "ultimo_dia"], how="left")
    else:
        grid = grid.with_columns(pl.lit(None, pl.Float64).alias("freq"))
    return (
        grid.join(last, on=[*chave, "ultimo_dia"], how="left")
        .select(*chave, "dia", "freq", "ultimo")
        .sort([*chave, "dia"])
    )


def agregar_diario(rows: pl.DataFrame, por_slot: list[str], diarias: list[str]) -> pl.DataFrame:
    """Features usina × dia: média e máximo das colunas por slot; as diárias passam direto."""
    return (
        rows.group_by([*KEY, "dia"])
        .agg(
            *(
                expr
                for c in por_slot
                for expr in (
                    pl.col(c).mean().alias(f"{c}_media"),
                    pl.col(c).max().alias(f"{c}_max"),
                )
            ),
            *(pl.col(c).first() for c in diarias),
        )
        .sort([*KEY, "dia"])
    )
