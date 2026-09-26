"""Figuras Plotly. Cor segue a entidade (estado da janela, causa), nunca a posição.

Paleta de referência validada para daltonismo; estados e causas sempre têm rótulo na
legenda ou no tooltip, nunca só a cor. Energia e probabilidade ficam em gráficos
separados, sem eixo duplo.
"""

import plotly.graph_objects as go
import polars as pl

from curtamap.contracts import STEP
from curtamap.painel.historico import MISSING, OTHERS
from curtamap.painel.ranking import STATUS_ALERT, STATUS_NO_ALERT, STATUS_NO_EVIDENCE

STATUS_COLORS = {STATUS_ALERT: "#d03b3b", STATUS_NO_ALERT: "#9ec5f4"}
NO_EVIDENCE_FILL = "rgba(137, 135, 129, 0.18)"
CAUSE_COLORS = {
    "ENE": "#2a78d6",
    "CNF": "#eb6834",
    "REL": "#1baf7a",
    "PAR": "#eda100",
    "DESCONHECIDA": "#898781",
}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]
NEUTRAL = "#898781"
_HOUR_FORMAT = "%H:%M<br>%d/%m"
_LAYOUT = {
    "margin": {"l": 10, "r": 10, "t": 50, "b": 10},
    "hovermode": "x unified",
    "showlegend": True,
    # Legenda abaixo do gráfico, para não disputar espaço com o título.
    "legend": {"orientation": "h", "yanchor": "top", "y": -0.18, "x": 0},
    "bargap": 0.15,
}


def _no_evidence_bands(fig: go.Figure, profile: pl.DataFrame) -> None:
    for tau in profile.filter(pl.col("status") == STATUS_NO_EVIDENCE)["tau"]:
        fig.add_vrect(
            x0=tau, x1=tau + STEP, line_width=0, fillcolor=NO_EVIDENCE_FILL, layer="below"
        )


def energy_profile(profile: pl.DataFrame, *, has_interval: bool) -> go.Figure:
    """Energia esperada por janela; janelas sem evidência ficam sombreadas, sem barra."""
    fig = go.Figure()
    for status in (STATUS_ALERT, STATUS_NO_ALERT):
        part = profile.filter(pl.col("status") == status)
        error = None
        if has_interval and part.height:
            low = (part["volume_p10_mwmed"] * 0.5).fill_null(0)
            high = (part["volume_p90_mwmed"] * 0.5).fill_null(0)
            energy = part["energia_esperada_mwh"].fill_null(0)
            error = {
                "type": "data",
                "array": (high - energy).clip(lower_bound=0).to_list(),
                "arrayminus": (energy - low).clip(lower_bound=0).to_list(),
                "color": "#52514e",
                "thickness": 1,
                "width": 2,
            }
        fig.add_bar(
            x=part["tau"].to_list(),
            y=part["energia_esperada_mwh"].to_list(),
            name=status,
            marker={"color": STATUS_COLORS[status], "cornerradius": 4},
            error_y=error,
            hovertemplate="%{y:.1f} MWh<extra>" + status + "</extra>",
        )
    if profile.filter(pl.col("status") == STATUS_NO_EVIDENCE).height:
        _no_evidence_bands(fig, profile)
        # Entrada de legenda para as faixas sombreadas.
        fig.add_scatter(
            x=[None],
            y=[None],
            mode="markers",
            name=STATUS_NO_EVIDENCE,
            marker={"color": "#c3c2b7", "size": 12, "symbol": "square"},
        )
    fig.update_layout(
        title="Energia esperada por janela de 30 min (MWh)"
        + (" · barra de erro = p10–p90" if has_interval else ""),
        yaxis_title="MWh",
        xaxis_tickformat=_HOUR_FORMAT,
        **_LAYOUT,
    )
    return fig


def probability_profile(profile: pl.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(
        x=profile["tau"].to_list(),
        y=profile["p_corte"].to_list(),
        mode="lines+markers",
        name="p(corte)",
        line={"color": "#2a78d6", "width": 2, "shape": "hv"},
        marker={"size": 6},
        connectgaps=False,
        hovertemplate="p(corte) %{y:.0%}<extra></extra>",
    )
    fig.add_scatter(
        x=profile["tau"].to_list(),
        y=profile["limiar_alerta"].to_list(),
        mode="lines",
        name="limiar de alerta",
        line={"color": "#52514e", "width": 1, "dash": "dash"},
        hovertemplate="limiar %{y:.0%}<extra></extra>",
    )
    _no_evidence_bands(fig, profile)
    fig.update_layout(
        title="Probabilidade de corte por janela",
        yaxis={"range": [0, 1.05], "tickformat": ".0%"},
        xaxis_tickformat=_HOUR_FORMAT,
        **_LAYOUT,
    )
    return fig


def _group_color(group: str, dimension: str, order: list[str]) -> str:
    if dimension == "causa":
        return CAUSE_COLORS.get(group, NEUTRAL)
    if group in (OTHERS, MISSING):
        return NEUTRAL
    named = [g for g in order if g not in (OTHERS, MISSING)]
    return SERIES[named.index(group) % len(SERIES)]


def losses_chart(losses: pl.DataFrame, dimension: str, grain_label: str) -> go.Figure:
    """Barras empilhadas de energia cortada; períodos parciais ficam translúcidos."""
    order = (
        losses.group_by("grupo")
        .agg(pl.col("energia_mwh").sum())
        .sort(["energia_mwh", "grupo"], descending=[True, False])["grupo"]
        .to_list()
    )
    fig = go.Figure()
    for group in order:
        part = losses.filter(pl.col("grupo") == group).sort("periodo")
        opacity = [0.45 if p else 1.0 for p in part["periodo_parcial"].fill_null(False)]
        fig.add_bar(
            x=part["periodo"].to_list(),
            y=part["energia_mwh"].to_list(),
            name=group,
            marker={
                "color": _group_color(group, dimension, order),
                "opacity": opacity,
                "line": {"width": 1, "color": "rgba(252,252,251,0.9)"},
            },
            hovertemplate="%{y:,.0f} MWh<extra>" + group + "</extra>",
        )
    fig.update_layout(
        barmode="stack",
        title=f"Energia cortada observada por {grain_label} (MWh)",
        yaxis_title="MWh",
        xaxis_tickformat="%m/%Y" if grain_label == "mês" else "%d/%m/%Y",
        separators=",.",
        **_LAYOUT,
    )
    return fig
