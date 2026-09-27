"""Gráficos do painel: mapa do portfólio e linha do dia de uma usina."""

import plotly.graph_objects as go
import polars as pl

from zelo.ui import estilo

# Metade de baixo da escala: horas livres (verde); metade de cima: alerta (vermelho).
_ESCALA = [
    [0.0, estilo.LIVRE_CLARO],
    [0.49, "#A9CDB7"],
    [0.5, estilo.ALERTA_CLARO],
    [0.75, estilo.ALERTA],
    [1.0, estilo.ALERTA_FORTE],
]
_HORAS = [f"{h:02d}h" for h in range(24)]


def _rotulo_slot(h: int) -> str:
    return f"{(h - 1) // 2:02d}:{30 * ((h - 1) % 2):02d}"


def _layout(fig: go.Figure, altura: int) -> go.Figure:
    fig.update_layout(
        height=altura,
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": estilo.FONTE_TEXTO, "color": estilo.TINTA, "size": 13},
        hoverlabel={"font": {"family": estilo.FONTE_TEXTO}},
    )
    return fig


def mapa_portfolio(aviso: pl.DataFrame, ordem: list[tuple[str, str, str]]) -> go.Figure:
    """Usinas × 48 meias-horas; cor = chance de corte, vazio = sem geração prevista."""
    linhas, textos, chances = [], [], []
    for fonte, id_ons, _ in ordem:
        usina = aviso.filter((pl.col("fonte") == fonte) & (pl.col("id_ons") == id_ons)).sort(
            "horizonte"
        )
        z, texto, chance = [], [], []
        for p, alerta, pot in zip(
            usina["p_corte"], usina["alerta"], usina["potencial_referencia_mwmed"], strict=True
        ):
            if p is None or (not alerta and (pot is None or pot <= 0)):
                z.append(None)
                texto.append("sem geração prevista")
            elif alerta:
                z.append(0.5 + 0.5 * p)
                texto.append("em alerta")
            else:
                z.append(0.49 * p)
                texto.append("livre")
            chance.append(0.0 if p is None else p)
        linhas.append(z)
        textos.append(texto)
        chances.append(chance)
    nomes = [nome for _, _, nome in ordem]
    fig = go.Figure(
        go.Heatmap(
            z=linhas,
            x=[_rotulo_slot(h) for h in range(1, 49)],
            y=nomes,
            text=textos,
            customdata=chances,
            colorscale=_ESCALA,
            showscale=False,
            zmin=0,
            zmax=1,
            xgap=1,
            ygap=4,
            hovertemplate="<b>%{y}</b><br>%{x} · %{text} · risco de corte %{customdata:.0%}"
            "<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(
        tickvals=[_rotulo_slot(h) for h in range(1, 49, 4)],
        ticktext=[_HORAS[i] for i in range(0, 24, 2)],
        showgrid=False,
    )
    return _layout(fig, 90 + 30 * len(ordem))


def linha_do_dia(usina: pl.DataFrame) -> go.Figure:
    """Chance de corte por meia-hora, colorida pelo que o aviso diz daquele horário."""
    usina = usina.sort("horizonte")
    cores, estados = [], []
    for p, alerta, pot in zip(
        usina["p_corte"], usina["alerta"], usina["potencial_referencia_mwmed"], strict=True
    ):
        if p is None:
            cores.append(estilo.SEM_GERACAO)
            estados.append("sem previsão")
        elif alerta:
            cores.append(estilo.ALERTA)
            estados.append("em alerta")
        elif pot is not None and pot > 0:
            cores.append("#8DB89F")
            estados.append("livre")
        else:
            cores.append(estilo.SEM_GERACAO)
            estados.append("sem geração prevista")
    x = [_rotulo_slot(h) for h in usina["horizonte"]]
    fig = go.Figure(
        go.Bar(
            x=x,
            y=usina["p_corte"].fill_null(0).to_list(),
            marker={"color": cores},
            customdata=estados,
            hovertemplate="%{x} · risco %{y:.0%} · %{customdata}<extra></extra>",
        )
    )
    limiar = usina["limiar_alerta"].drop_nulls()
    if limiar.len():
        fig.add_hline(
            y=float(limiar[0]),
            line_dash="dot",
            line_color=estilo.TEXTO_SUAVE,
            annotation_text="limiar do alerta",
            annotation_position="top left",
            annotation_font_color=estilo.TEXTO_SUAVE,
        )
    fig.update_yaxes(range=[0, 1], tickformat=".0%", gridcolor=estilo.FILETE, title=None)
    fig.update_xaxes(
        tickvals=[_rotulo_slot(h) for h in range(1, 49, 4)],
        ticktext=[_HORAS[i] for i in range(0, 24, 2)],
        showgrid=False,
    )
    fig.update_layout(bargap=0.12, showlegend=False)
    return _layout(fig, 280)
