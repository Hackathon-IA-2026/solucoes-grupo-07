"""Contexto comum a todas as telas: escolha da emissão `t0` e selo de proveniência."""

from dataclasses import dataclass
from datetime import datetime

import streamlit as st

from curtamap.painel.emissao import Bounds, check_emission, emission_bounds, slots_for_day
from curtamap.painel.proveniencia import Provenance, summarize_provenance
from curtamap.painel.rotulos import COMPONENT_LABELS
from curtamap.previsao.produto import HISTORY_DAYS
from curtamap.ui import dados

_T0_KEY = "t0"
_CONTEXT_KEY = "_contexto"


@dataclass(frozen=True)
class Context:
    t0: datetime
    bounds: Bounds
    bundle: dados.ForecastBundle
    provenance: Provenance


def _pick_emission(bounds: Bounds) -> datetime:
    earliest, latest = bounds
    chosen = st.session_state.get(_T0_KEY, latest)
    st.sidebar.subheader("Emissão da previsão")
    day = st.sidebar.date_input(
        "Dia de t0",
        value=chosen.date(),
        min_value=earliest.date(),
        max_value=latest.date(),
        format="DD/MM/YYYY",
        help="As 48 janelas de 30 min começam em t0. O limite superior protege o teste "
        "reservado: as 24 h precisam terminar antes dele.",
    )
    slots = slots_for_day(day, bounds)
    default = chosen.time() if chosen.time() in slots else slots[0]
    hour = st.sidebar.selectbox(
        "Hora de t0",
        slots,
        index=slots.index(default),
        format_func=lambda moment: moment.strftime("%H:%M"),
        help="Uso previsto: emissão às 20h da véspera com t0 = 00:00.",
    )
    t0 = check_emission(datetime.combine(day, hour), bounds)
    st.session_state[_T0_KEY] = t0
    return t0


def load() -> Context | None:
    """Desenha a barra lateral e devolve o contexto, ou `None` sem dados locais."""
    missing = dados.missing_files()
    if missing:
        st.error(
            "Dados do ONS ausentes em `data/raw`: "
            + ", ".join(f"`{path.name}`" for path in missing)
            + ". Rode `uv sync --extra data --dev` e `uv run python -m curtamap.download_data`,"
            " ou aponte `CURTAMAP_DATA_DIR` para a pasta com os Parquet. A interface não "
            "mostra números simulados no lugar deles."
        )
        return None
    start, end = dados.data_range()
    bounds = emission_bounds(start, end, history_days=HISTORY_DAYS)
    t0 = _pick_emission(bounds)
    st.sidebar.caption(
        f"Dados locais de {start:%d/%m/%Y} a {end:%d/%m/%Y %H:%M}. "
        f"Emissões possíveis: {bounds[0]:%d/%m/%Y} a {bounds[1]:%d/%m/%Y %H:%M}."
    )
    bundle = dados.forecast_for(t0)
    return Context(t0, bounds, bundle, summarize_provenance(bundle.forecast))


def seal(context: Context) -> None:
    """Selo visível em todas as telas com a natureza da previsão."""
    prov = context.provenance
    header = (
        f"**t0 {prov.t0:%d/%m/%Y %H:%M}** · dados liberados até "
        f"{prov.data_cutoff:%d/%m/%Y %H:%M} · {', '.join(prov.model_ids)}"
    )
    if prov.is_baseline:
        st.warning(
            f"⚠️ **Preditor provisório (baseline).** Repete o mesmo horário do dia liberado "
            f"mais recente; probabilidades 0 ou 1, sem calibração nem intervalo. {header}",
        )
        return
    parts = [
        f"{name}: " + ", ".join(COMPONENT_LABELS.get(kind, kind) for kind in counts)
        for name, counts in prov.components.items()
    ]
    detail = f" Componentes servidos — {'; '.join(parts)}." if parts else ""
    st.info(f"🧮 **Modelo treinado** (ocorrência de corte).{detail} {header}")


def current() -> Context | None:
    """Contexto calculado pelo `app.py` nesta execução, para as telas."""
    return st.session_state.get(_CONTEXT_KEY)


def store(context: Context | None) -> None:
    st.session_state[_CONTEXT_KEY] = context
