"""Visão tática: perdas históricas observadas por período e recorte."""

from datetime import datetime, time, timedelta

import polars as pl
import streamlit as st

from curtamap.painel.historico import fold_small_groups, historical_losses
from curtamap.painel.rotulos import SOURCE_LABELS, format_mwh
from curtamap.ui import contexto, dados, graficos

_DIMENSIONS = {
    "causa": "Causa",
    "fonte": "Fonte",
    "id_estado": "UF",
    "id_subsistema": "Subsistema",
    "usina": "Usina",
}
_GRAINS = {"semana": "semana", "mes": "mês"}
_WINDOWS = {"12 semanas": 84, "6 meses": 183, "12 meses": 365}
_KEEP = 7


def render() -> None:
    context = contexto.current()
    if context is None:
        return
    st.title("Visão tática")
    st.caption(
        "Perdas **observadas** (GNR analítica: max(referência − geração, 0) nas meias-horas "
        "com limitação), não previstas. O recorte termina no corte de dados da emissão "
        "escolhida, para não mostrar nada que o gerador ainda não saberia."
    )
    a, b, c, d = st.columns(4)
    window = a.selectbox("Janela", list(_WINDOWS), index=1)
    grain = b.selectbox("Período", list(_GRAINS), format_func=_GRAINS.get, index=1)
    dimension = c.selectbox("Recorte", list(_DIMENSIONS), format_func=_DIMENSIONS.get)
    fontes = d.multiselect(
        "Fonte",
        ["eolica", "fotovoltaica"],
        format_func=lambda s: SOURCE_LABELS.get(s, s),
        placeholder="Todas",
    )

    end = context.bundle.data_cutoff
    start = max(
        end - timedelta(days=_WINDOWS[window]),
        datetime.combine(dados.data_range()[0].date(), time()),
    )
    history = dados.observed_history(start, end)
    if fontes:
        history = history.filter(pl.col("fonte").is_in(fontes))
    losses = historical_losses(history, grain=grain, dimension=dimension, window=(start, end))
    if losses.is_empty():
        st.info("Nenhuma limitação registrada neste recorte.")
        return
    shown = fold_small_groups(losses, keep=_KEEP)

    total = losses["energia_mwh"].sum()
    invalid = losses["janelas_volume_nulo"].sum()
    k1, k2, k3 = st.columns(3)
    k1.metric("Energia cortada no recorte", format_mwh(total))
    k2.metric("Meias-horas com corte", f"{losses['janelas_com_corte'].sum():,}".replace(",", "."))
    k3.metric(
        "Meias-horas com volume inválido",
        invalid,
        help="Limitação registrada sem volume calculável; ficam fora da soma, nunca como zero.",
    )
    st.plotly_chart(
        graficos.losses_chart(shown, dimension, _GRAINS[grain]), use_container_width=True
    )
    notes = [f"Dados de {start:%d/%m/%Y} até {end:%d/%m/%Y %H:%M} (exclusivo)."]
    if shown["periodo_parcial"].any():
        notes.append("Barras translúcidas são períodos cortados pela janela (parciais).")
    if shown.height != losses.height:
        notes.append(f"Além dos {_KEEP} maiores grupos, o resto está somado em “Outros”.")
    st.caption(" ".join(notes))
    with st.expander("Tabela"):
        st.dataframe(
            losses.rename({"grupo": _DIMENSIONS[dimension]}),
            hide_index=True,
            use_container_width=True,
            column_config={"energia_mwh": st.column_config.NumberColumn(format="%.1f")},
        )
