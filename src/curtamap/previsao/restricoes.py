"""Sinal de restrição física para a v3 (frente B), sempre com dados até o último dia liberado.

- `normalizar_restricao`: reduz `dsc_restricao` à restrição física, sem SGI, "Conforme …",
  sufixos de instrução de operação (IO-ON…, revisão, MOP) e variantes de circuito (C1(V7)).
- `grupo_restricao`: a restrição normalizada mais frequente da usina nas meias-horas com
  corte local (CNF/REL) em (L − 91, L]; sem corte local no período, a usina não tem grupo.
- `nivel_grupo`: fração das meias-horas cortadas das usinas do mesmo grupo (membros em L)
  no dia L e média diária em (L − 7, L].
- `regime_nacional`: participação de ENE nas ordens com causa conhecida do SIN em L e em
  (L − 7, L], por fonte e com as duas fontes juntas.

`dsc_restricao` só é publicada a partir de 01/09/2025; antes disso não há grupo.
"""

import re
import unicodedata
from collections.abc import Iterable
from datetime import date

import polars as pl

from curtamap.previsao.faixas import KEY, por_janela

GROUP_DAYS = 91
LEVEL_DAYS = 7
_CIRCUIT = r"C\d(?:\s*\([A-Z0-9.]+\))?"
_RULES = [
    (re.compile(r"[-,]?\s*\bCONFORME\b.*$"), ""),
    (re.compile(r"\bSGI\s*(?:N[°O]?\s*)?[\d.]+-\d+\s*:?"), ""),
    (re.compile(r"[-\s]*\bSGI\s*$"), ""),
    (re.compile(r"\s*-?\s*\bIO-ON\S*.*$"), ""),
    (re.compile(r"\s+E\s+MOP\b.*$"), ""),
    (re.compile(rf"\s*-?\s*\b{_CIRCUIT}(?:\s+(?:E|OU)\s+{_CIRCUIT})*(?=[\s,.;)]|$)"), ""),
    (re.compile(r"\s*\(\s*\d[A-Z0-9.]*\s*\)"), ""),
    (re.compile(r"^CONTROLE DO FLUXO:\s*([A-Z0-9_<>]+)\s*#.*$"), r"FLUXO \1"),
    (re.compile(r"^CONTROLE DO ([A-Z0-9_]+)$"), r"FLUXO \1"),
]


def _sem_acento(texto: str) -> str:
    decomposed = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def normalizar_restricao(texto: str | None) -> str | None:
    """Texto da restrição física, em caixa alta, sem acentos, referências e variantes."""
    if texto is None or not texto.strip():
        return None
    out = _sem_acento(texto).upper().replace("–", "-").replace("—", "-")
    out = re.sub(r"\s+", " ", out).strip()
    for pattern, replacement in _RULES:
        out = re.sub(r"\s+", " ", pattern.sub(replacement, out)).strip(" .-,:;")
    return out or None


def grupo_restricao(eventos: pl.DataFrame, ultimos: Iterable[date]) -> pl.DataFrame:
    """Restrição mais frequente por usina em (L − 91, L]; empate pela ordem alfabética.

    `eventos` tem uma linha por meia-hora com corte local: `fonte`, `id_ons`, `dia` e
    `restricao` (já normalizada).
    """
    found = por_janela(
        eventos.filter(pl.col("restricao").is_not_null()),
        ultimos,
        GROUP_DAYS,
        lambda part: (
            part.group_by([*KEY, "restricao"])
            .agg(pl.len().alias("_n"))
            .sort(["_n", "restricao"], descending=[True, False])
            .group_by(KEY, maintain_order=True)
            .agg(pl.col("restricao").first().alias("grupo_restricao"))
        ),
    )
    if found.is_empty():
        return pl.DataFrame(
            schema={
                "fonte": pl.String,
                "id_ons": pl.String,
                "ultimo_dia": pl.Date,
                "grupo_restricao": pl.String,
            }
        )
    return found.select(*KEY, "ultimo_dia", "grupo_restricao").sort([*KEY, "ultimo_dia"])


def nivel_grupo(base: pl.DataFrame, grupos: pl.DataFrame, ultimos: Iterable[date]) -> pl.DataFrame:
    """Nível do grupo de restrição da usina em L e em 7 dias, com os membros definidos em L."""
    rows = base.select(*KEY, "dia", "corte").sort("dia")
    parts = []
    for last in sorted(set(ultimos)):
        members = grupos.filter(pl.col("ultimo_dia") == last).select(*KEY, "grupo_restricao")
        if members.is_empty():
            continue
        window = por_janela(
            rows,
            [last],
            LEVEL_DAYS,
            lambda part, members=members: (
                part.join(members, on=KEY)
                .group_by("fonte", "grupo_restricao", "dia")
                .agg(pl.col("corte").mean().alias("_nivel"))
            ),
        )
        levels = window.group_by("fonte", "grupo_restricao").agg(
            pl.col("_nivel").filter(pl.col("dia") == last).first().alias("grupo_nivel_ultimo"),
            pl.col("_nivel").mean().alias("grupo_nivel_7d"),
        )
        sizes = members.group_by("fonte", "grupo_restricao").agg(
            pl.len().cast(pl.Int32).alias("grupo_tamanho")
        )
        parts.append(
            members.join(levels, on=["fonte", "grupo_restricao"], how="left")
            .join(sizes, on=["fonte", "grupo_restricao"])
            .with_columns(pl.lit(last, pl.Date).alias("ultimo_dia"))
        )
    columns = [
        *KEY,
        "ultimo_dia",
        "grupo_nivel_ultimo",
        "grupo_nivel_7d",
        "grupo_tamanho",
    ]
    if not parts:
        return pl.DataFrame(
            schema={
                "fonte": pl.String,
                "id_ons": pl.String,
                "ultimo_dia": pl.Date,
                "grupo_nivel_ultimo": pl.Float64,
                "grupo_nivel_7d": pl.Float64,
                "grupo_tamanho": pl.Int32,
            }
        )
    return (
        pl.concat(parts, how="vertical_relaxed")
        .with_columns(pl.col("grupo_nivel_ultimo", "grupo_nivel_7d").cast(pl.Float64))
        .select(columns)
        .sort([*KEY, "ultimo_dia"])
    )


def regime_nacional(base: pl.DataFrame, ultimos: Iterable[date]) -> pl.DataFrame:
    """Participação de ENE nas ordens com causa conhecida do SIN, por fonte e total."""
    known = base.filter(pl.col("_ENE").is_not_null()).select("fonte", "dia", "_ENE")
    by_source = known.group_by("fonte", "dia").agg(pl.col("_ENE").mean().alias("_share"))
    total = known.group_by("dia").agg(pl.col("_ENE").mean().alias("_share_total"))

    def summarize(daily: pl.DataFrame, column: str, keys: list[str]) -> pl.DataFrame:
        found = por_janela(
            daily,
            ultimos,
            LEVEL_DAYS,
            lambda part: (
                part.group_by(keys).agg(pl.col(column).mean().alias("_7d"))
                if keys
                else part.select(pl.col(column).mean().alias("_7d"))
            ),
        )
        last = daily.select(*keys, pl.col("dia").alias("ultimo_dia"), pl.col(column).alias("_u"))
        return found.join(last, on=[*keys, "ultimo_dia"], how="left")

    per_source = summarize(by_source, "_share", ["fonte"]).rename(
        {"_7d": "sin_ene_7d", "_u": "sin_ene_ultimo"}
    )
    national = summarize(total, "_share_total", []).rename(
        {"_7d": "sin_ene_7d_total", "_u": "sin_ene_ultimo_total"}
    )
    return (
        per_source.join(national, on="ultimo_dia", how="left")
        .select(
            "fonte",
            "ultimo_dia",
            *(
                pl.col(c).cast(pl.Float64)
                for c in (
                    "sin_ene_ultimo",
                    "sin_ene_7d",
                    "sin_ene_ultimo_total",
                    "sin_ene_7d_total",
                )
            ),
        )
        .sort(["fonte", "ultimo_dia"])
    )


def causa_slot(base: pl.DataFrame, ultimos: Iterable[date], janela: int = 91) -> pl.DataFrame:
    """Participação de REL, CNF e ENE nas ordens com causa conhecida da usina no slot.

    Janela exata (L − janela, L]; sem ordem com causa conhecida, as três ficam nulas.
    """
    causes = ("REL", "CNF", "ENE")
    found = por_janela(
        base.select(*KEY, "slot", "dia", *(f"_{c}" for c in causes)),
        ultimos,
        janela,
        lambda part: part.group_by([*KEY, "slot"]).agg(
            pl.col(f"_{c}").mean().cast(pl.Float64).alias(f"causa_{c.lower()}_{janela}d")
            for c in causes
        ),
    )
    return found.select(
        *KEY, "slot", "ultimo_dia", *(f"causa_{c.lower()}_{janela}d" for c in causes)
    ).sort([*KEY, "slot", "ultimo_dia"])
