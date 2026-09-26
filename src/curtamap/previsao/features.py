"""Features da emissão diária, indexadas pelo último dia liberado.

Unidade: `fonte + id_ons + dia-alvo + slot` (48 meias-horas). Toda feature de uma linha é
calculada com dados até o fim do último dia liberado `ultimo_dia` (L), nunca do dia-alvo T.
As janelas móveis terminam em L e, portanto, não andam junto com a emissão sobre dias sem
dado novo (erro da Etapa 2 anterior). A idade `T − L` entra como feature explícita.

Poucas features, cada uma com significado físico ou operacional:

- perfil da usina no slot: frequência de corte e volume médio em 7, 28 e 91 dias, e o
  próprio slot em L;
- nível recente da usina e do estado (fração de meias-horas cortadas em L, em 7 e em 28 dias);
- regime de causa: participação de ENE, CNF e REL entre as ordens com causa conhecida;
- calendário do dia-alvo: dia da semana, feriado nacional (carga baixa) e idade da informação.

Não há `mês` nem `dia do ano`: com menos de dois anos de solar, eles ensinam tendência como
estação (Etapa 2 anterior).
"""

from collections.abc import Iterable
from datetime import date, timedelta

import polars as pl

from curtamap.contracts import PREDICTABLE_CAUSES
from curtamap.previsao.calendario import Calendar, emission_cutoff

KEY = ["fonte", "id_ons"]
SLOT_KEY = [*KEY, "slot"]
STATE_KEY = ["fonte", "id_estado"]
# Entidade sem nenhuma observação nos 91 dias até L não recebe previsão.
ENTITY_LOOKBACK_DAYS = 91

OCCURRENCE = [
    "hist_7d",
    "hist_28d",
    "hist_91d",
    "ultimo_slot",
    "usina_nivel_ultimo",
    "usina_nivel_7d",
    "estado_nivel_ultimo",
    "estado_nivel_7d",
    "estado_nivel_28d",
    "estado_ene_7d",
    "idade",
    "dia_semana",
    "feriado",
    "slot",
]
VOLUME = [
    *OCCURRENCE,
    "vol_hist_7d",
    "vol_hist_28d",
    "vol_ultimo_slot",
    "ref_hist_28d",
    "usina_vol_ultimo",
]
CAUSE = [
    "causa_rel_28d",
    "causa_cnf_28d",
    "causa_ene_28d",
    "estado_rel_7d",
    "estado_cnf_7d",
    "estado_ene_7d",
    "hist_28d",
    "estado_nivel_ultimo",
    "estado_nivel_7d",
    "idade",
    "dia_semana",
    "feriado",
    "slot",
]
FEATURES = sorted({*VOLUME, *CAUSE, "restricao_hist_28d", "origem_sis_28d"} - {"slot", "idade"})


def base_from_history(history: pl.DataFrame) -> pl.DataFrame:
    """Tabela compacta a partir da saída de `derive_targets` (ex.: `load_history`).

    Linhas com volume indeterminado (inválido) saem: não são rótulo nem histórico.
    """
    moment = pl.col("din_instante")
    known = pl.col("causa").is_in(PREDICTABLE_CAUSES)
    return (
        history.filter(pl.col("volume_valido") & pl.col("volume_mwmed").is_not_null())
        .select(
            *KEY,
            "id_estado",
            moment.dt.date().alias("dia"),
            (moment.dt.hour() * 2 + moment.dt.minute() // 30).cast(pl.Int8).alias("slot"),
            pl.col("corte_positivo").cast(pl.Float32).alias("corte"),
            pl.col("volume_mwmed").cast(pl.Float32).alias("volume"),
            pl.col("val_geracaoreferencia").cast(pl.Float32).alias("referencia"),
            pl.col("restricao_registrada").cast(pl.Float32).alias("restricao"),
            pl.when(known).then(pl.col("causa")).alias("causa"),
            *(
                pl.when(known).then((pl.col("causa") == c).cast(pl.Float32)).alias(f"_{c}")
                for c in PREDICTABLE_CAUSES
            ),
            pl.when(pl.col("origem").is_in(["LOC", "SIS"]))
            .then((pl.col("origem") == "SIS").cast(pl.Float32))
            .alias("_sis"),
        )
        .sort([*KEY, "dia", "slot"])
    )


def release_map(days: Iterable[date], calendar: Calendar) -> pl.DataFrame:
    """Dia-alvo → último dia liberado na emissão das 20h da véspera, idade e calendário."""
    rows = []
    for day in sorted(set(days)):
        last = emission_cutoff(day, calendar).date() - timedelta(days=1)
        rows.append(
            {
                "dia": day,
                "ultimo_dia": last,
                "idade": (day - last).days,
                "dia_semana": day.weekday(),
                "feriado": int(calendar.is_national_holiday(day)),
            }
        )
    return pl.DataFrame(
        rows,
        schema={
            "dia": pl.Date,
            "ultimo_dia": pl.Date,
            "idade": pl.Int8,
            "dia_semana": pl.Int8,
            "feriado": pl.Int8,
        },
    )


def _rolling(column: str, window: str, keys: list[str]) -> pl.Expr:
    # Janela (L − window, L]; nulos (ex.: causa fora de ordem) são ignorados.
    return pl.col(column).rolling_mean_by("dia", window_size=window).over(keys)


def _slot_table(base: pl.DataFrame) -> pl.DataFrame:
    return (
        base.sort([*SLOT_KEY, "dia"])
        .with_columns(
            _rolling("corte", "7d", SLOT_KEY).alias("hist_7d"),
            _rolling("corte", "28d", SLOT_KEY).alias("hist_28d"),
            _rolling("corte", "91d", SLOT_KEY).alias("hist_91d"),
            _rolling("volume", "7d", SLOT_KEY).alias("vol_hist_7d"),
            _rolling("volume", "28d", SLOT_KEY).alias("vol_hist_28d"),
            _rolling("referencia", "28d", SLOT_KEY).alias("ref_hist_28d"),
            _rolling("restricao", "28d", SLOT_KEY).alias("restricao_hist_28d"),
            _rolling("_sis", "28d", SLOT_KEY).alias("origem_sis_28d"),
            *(
                _rolling(f"_{c}", "28d", SLOT_KEY).alias(f"causa_{c.lower()}_28d")
                for c in PREDICTABLE_CAUSES
            ),
        )
        .select(
            *SLOT_KEY,
            pl.col("dia").alias("ultimo_dia"),
            pl.col("corte").alias("ultimo_slot"),
            pl.col("volume").alias("vol_ultimo_slot"),
            "hist_7d",
            "hist_28d",
            "hist_91d",
            "vol_hist_7d",
            "vol_hist_28d",
            "ref_hist_28d",
            "restricao_hist_28d",
            "origem_sis_28d",
            *(f"causa_{c.lower()}_28d" for c in PREDICTABLE_CAUSES),
        )
    )


def _plant_table(base: pl.DataFrame) -> pl.DataFrame:
    daily = base.group_by([*KEY, "dia"]).agg(
        pl.col("corte").mean().alias("usina_nivel_ultimo"),
        pl.col("volume").mean().alias("usina_vol_ultimo"),
    )
    return (
        daily.sort([*KEY, "dia"])
        .with_columns(_rolling("usina_nivel_ultimo", "7d", KEY).alias("usina_nivel_7d"))
        .rename({"dia": "ultimo_dia"})
    )


def _state_table(base: pl.DataFrame) -> pl.DataFrame:
    daily = base.group_by([*STATE_KEY, "dia"]).agg(
        pl.col("corte").mean().alias("estado_nivel_ultimo"),
        *(pl.col(f"_{c}").mean().alias(f"_estado_{c}") for c in PREDICTABLE_CAUSES),
    )
    return (
        daily.sort([*STATE_KEY, "dia"])
        .with_columns(
            _rolling("estado_nivel_ultimo", "7d", STATE_KEY).alias("estado_nivel_7d"),
            _rolling("estado_nivel_ultimo", "28d", STATE_KEY).alias("estado_nivel_28d"),
            *(
                _rolling(f"_estado_{c}", "7d", STATE_KEY).alias(f"estado_{c.lower()}_7d")
                for c in PREDICTABLE_CAUSES
            ),
        )
        .drop([f"_estado_{c}" for c in PREDICTABLE_CAUSES])
        .rename({"dia": "ultimo_dia"})
    )


def _entities(base: pl.DataFrame, mapping: pl.DataFrame) -> pl.DataFrame:
    """Entidades vistas nos 91 dias até L de cada dia-alvo, com o estado mais recente."""
    seen = (
        base.group_by([*KEY, "dia"])
        .agg(pl.col("id_estado").last())
        .rename({"dia": "visto_em"})
        .sort("visto_em")
    )
    pairs = (
        mapping.select("ultimo_dia")
        .unique()
        .join(seen.select(KEY).unique(), how="cross")
        .sort("ultimo_dia")
    )
    return (
        pairs.join_asof(
            seen,
            left_on="ultimo_dia",
            right_on="visto_em",
            by=KEY,
            strategy="backward",
            check_sortedness=False,
        )
        .filter(pl.col("visto_em") > pl.col("ultimo_dia") - timedelta(days=ENTITY_LOOKBACK_DAYS))
        .drop("visto_em")
    )


def _asof(grid: pl.DataFrame, table: pl.DataFrame, by: list[str]) -> pl.DataFrame:
    # Valor mais recente até L (inclusive); cobre dias sem dado da entidade.
    return grid.sort("ultimo_dia").join_asof(
        table.sort("ultimo_dia"),
        on="ultimo_dia",
        by=by,
        strategy="backward",
        check_sortedness=False,
    )


def build_features(base: pl.DataFrame, mapping: pl.DataFrame) -> pl.DataFrame:
    """Grade entidade × dia-alvo × 48 slots com as features até o último dia liberado."""
    horizon = base.filter(
        pl.col("dia") <= mapping["ultimo_dia"].max(),
        pl.col("dia") > mapping["ultimo_dia"].min() - timedelta(days=ENTITY_LOOKBACK_DAYS + 1),
    )
    if horizon.is_empty():
        return pl.DataFrame()
    slots = pl.DataFrame({"slot": pl.int_range(0, 48, eager=True).cast(pl.Int8)})
    grid = mapping.join(_entities(horizon, mapping), on="ultimo_dia").join(slots, how="cross")
    grid = _asof(grid, _slot_table(horizon), SLOT_KEY)
    grid = _asof(grid, _plant_table(horizon), KEY)
    grid = _asof(grid, _state_table(horizon), STATE_KEY)
    return grid.sort([*KEY, "dia", "slot"])


def attach_targets(features: pl.DataFrame, base: pl.DataFrame) -> pl.DataFrame:
    """Acrescenta os rótulos observados do dia-alvo (avaliação e treino)."""
    targets = base.select(
        *SLOT_KEY,
        "dia",
        pl.col("corte").alias("y_corte"),
        pl.col("volume").alias("y_volume"),
        pl.col("restricao").alias("y_restricao"),
        pl.col("causa").alias("y_causa"),
    )
    return features.join(targets, on=[*SLOT_KEY, "dia"], how="left")
