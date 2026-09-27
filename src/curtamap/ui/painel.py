"""Tela única do produto: o aviso das 20h para o portfólio e para cada usina."""

from datetime import date, timedelta
from html import escape

import polars as pl
import streamlit as st

from curtamap.aviso import (
    MOTIVOS,
    STATUS_ALERTA,
    STATUS_SEM_PREVISAO,
    carregar_desempenho,
    formatar_janela,
    horas_livres,
    janelas_alerta,
    motivo_texto,
    resumo_usinas,
    sugestao,
)
from curtamap.ui import dados, estilo, graficos

FONTES = {"eolica": "Eólica", "fotovoltaica": "Solar"}
_FONTES_PLURAL = {"eolica": "eólicas", "fotovoltaica": "solares"}
_DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
_TOP_MAPA = 18


def _dia_extenso(dia: date) -> str:
    return f"{_DIAS_SEMANA[dia.weekday()]}, {dia:%d/%m/%Y}"


def _horas(valor: float | None) -> str:
    if valor is None:
        return "—"
    texto = f"{valor:.1f}".replace(".", ",").removesuffix(",0")
    return f"{texto} h"


def _nome(row: dict) -> str:
    return row.get("nom_usina") or f"{row['fonte']}/{row['id_ons']}"


def _cabecalho(dia: date, emitido) -> None:
    estilo.html(
        f"""<div class="cm-topo">
  <div class="cm-marca">Curta<b>Map</b> · aviso diário de cortes</div>
  <div class="cm-titulo">Amanhã, {escape(_dia_extenso(dia))}</div>
  <div class="cm-sub">Emitido às {emitido:%Hh} de {emitido:%d/%m} com os dados públicos do ONS
  já liberados. Mostra em quais horas cada usina deve ser cortada, por qual motivo e quanto
  o aviso costuma acertar.</div></div>"""
    )


def _seletores(dias: list[date]):
    a, b, c = st.columns([2, 2, 3])
    dia = a.selectbox(
        "Aviso para o dia",
        dias,
        index=len(dias) - 1,
        format_func=_dia_extenso,
    )
    fontes = b.segmented_control(
        "Fonte",
        list(FONTES),
        format_func=FONTES.get,
        selection_mode="multi",
        default=list(FONTES),
    )
    return dia, fontes or list(FONTES), c


def _cards(resumo: pl.DataFrame) -> None:
    previstas = resumo.filter(pl.col("status") != STATUS_SEM_PREVISAO)
    em_alerta = previstas.filter(pl.col("status") == STATUS_ALERTA)
    total = previstas.height
    mediana_alerta = em_alerta["horas_alerta"].median() if em_alerta.height else None
    mediana_livre = previstas["horas_livres"].median() if total else None
    motivos = em_alerta["motivo"].drop_nulls()
    motivo = motivos.mode().sort()[0] if motivos.len() else None
    parcela = (motivos == motivo).mean() if motivo else None
    cols = st.columns(4)
    cols[0].markdown(
        estilo.card(
            "Usinas em alerta",
            f"{em_alerta.height}<small> de {total}</small>",
            "com pelo menos uma janela de corte provável",
        ),
        unsafe_allow_html=True,
    )
    cols[1].markdown(
        estilo.card(
            "Horas em alerta",
            _horas(mediana_alerta),
            "por usina em alerta (mediana)",
        ),
        unsafe_allow_html=True,
    )
    cols[2].markdown(
        estilo.card(
            "Horas livres",
            _horas(mediana_livre),
            "com geração e sem alerta, por usina (mediana)",
        ),
        unsafe_allow_html=True,
    )
    cols[3].markdown(
        estilo.card(
            "Motivo mais frequente",
            f'<span class="cm-motivo">{escape(MOTIVOS.get(motivo, "—"))}</span>',
            f"na janela principal de {parcela:.0%} das usinas em alerta" if motivo else "",
        ),
        unsafe_allow_html=True,
    )


def _faixa_acerto(fontes: list[str]) -> None:
    desempenho = carregar_desempenho()
    blocos = []
    for fonte in fontes:
        item = desempenho["fontes"][fonte]
        blocos.append(
            f'<div><div class="fonte">{FONTES[fonte]}</div>'
            f'<b>{round(item["precisao"] * 10)} em 10</b> <span class="t">horas avisadas '
            f'tiveram corte</span><br><b>{item["energia_avisada"]:.0%}</b> <span class="t">'
            "da energia cortada caiu em horas avisadas</span></div>"
        )
    estilo.html(
        f'<div class="cm-acerto" style="--n:{len(blocos)}"><div class="t">'
        '<b style="font-size:17px">Quanto o aviso acerta</b><br>'
        f"medido de {escape(desempenho['periodo'])}, com dados que o modelo nunca tinha "
        f"visto</div>{''.join(blocos)}</div>"
    )


def _tabela(resumo: pl.DataFrame) -> dict | None:
    tabela = resumo.select(
        pl.struct("nom_usina", "fonte", "id_ons")
        .map_elements(_nome, return_dtype=pl.String)
        .alias("Usina"),
        pl.col("fonte").replace_strict(FONTES).alias("Fonte"),
        pl.col("id_estado").alias("UF"),
        pl.col("horas_alerta").alias("Horas em alerta"),
        pl.struct("janela_inicio", "janela_fim")
        .map_elements(
            lambda r: (
                formatar_janela(r["janela_inicio"], r["janela_fim"]) if r["janela_inicio"] else "—"
            ),
            return_dtype=pl.String,
        )
        .alias("Janela principal"),
        pl.struct("motivo", "origem")
        .map_elements(
            lambda r: (
                motivo_texto(r["motivo"], r["origem"]).split(" · ")[0] if r["motivo"] else "—"
            ),
            return_dtype=pl.String,
        )
        .alias("Motivo típico"),
        pl.col("chance_max").alias("Chance máxima"),
        pl.col("horas_livres").alias("Horas livres"),
    )
    evento = st.dataframe(
        tabela,
        hide_index=True,
        width="stretch",
        height=430,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Horas em alerta": st.column_config.NumberColumn(format="%.1f h"),
            "Horas livres": st.column_config.NumberColumn(format="%.1f h"),
            "Chance máxima": st.column_config.ProgressColumn(
                format="percent", min_value=0.0, max_value=1.0
            ),
        },
    )
    linhas = evento.selection.rows if evento else []
    indice = linhas[0] if linhas else 0
    return resumo.row(indice, named=True) if resumo.height else None


def _detalhe(aviso: pl.DataFrame, usina: dict) -> None:
    filtro = (pl.col("fonte") == usina["fonte"]) & (pl.col("id_ons") == usina["id_ons"])
    linhas = aviso.filter(filtro)
    janelas = janelas_alerta(linhas)
    livres = horas_livres(linhas)
    desempenho = carregar_desempenho()["fontes"][usina["fonte"]]
    local = " · ".join(
        x for x in (FONTES[usina["fonte"]], usina.get("id_estado"), usina.get("id_subsistema")) if x
    )
    classe = "" if janelas.height else " livre"
    partes = [
        f'<div class="cm-aviso{classe}"><h3>{escape(_nome(usina))}</h3>',
        f'<div class="cm-meta">{escape(local)} · código ONS {escape(usina["id_ons"])}</div>',
    ]
    if usina["status"] == STATUS_SEM_PREVISAO:
        partes.append(
            '<span class="cm-pill neutra">sem previsão</span> Não há histórico recente '
            "suficiente desta usina para emitir o aviso."
        )
    elif not janelas.height:
        partes.append(
            '<span class="cm-pill livre">sem alerta</span> Nenhuma hora com corte provável amanhã.'
        )
    for janela in janelas.iter_rows(named=True):
        partes.append(
            f'<div class="cm-janela"><div class="cm-hora">'
            f"{formatar_janela(janela['inicio'], janela['fim'])}</div>"
            f'<div class="cm-detalhe"><span class="cm-pill">chance de até '
            f"{janela['chance_max']:.0%}</span> "
            f"{escape(motivo_texto(janela['causa'], janela['origem']))}"
            f"<br><span>{escape(sugestao(janela['horas']))}</span></div></div>"
        )
    if livres.height:
        texto = ", ".join(
            formatar_janela(r["inicio"], r["fim"]) for r in livres.iter_rows(named=True)
        )
        partes.append(
            f'<div class="cm-janela"><div class="cm-hora livre">Horas livres</div>'
            f'<div class="cm-detalhe">{escape(texto)}<br><span>Geração esperada sem '
            "alerta de corte.</span></div></div>"
        )
    partes.append(
        f'<div class="cm-janela"><div class="cm-hora livre" style="color:{estilo.TINTA}">'
        f'Acerto</div><div class="cm-detalhe">De cada 10 horas avisadas nas usinas '
        f"{_FONTES_PLURAL[usina['fonte']]}, {round(desempenho['precisao'] * 10)} tiveram "
        f"corte.<br><span>O motivo vem das ordens desta usina, neste horário, nas últimas "
        "4 semanas.</span></div></div></div>"
    )
    estilo.html("".join(partes))
    st.plotly_chart(graficos.linha_do_dia(linhas), width="stretch")


def _rodape(aviso: pl.DataFrame, resumo: pl.DataFrame) -> None:
    info = aviso.select(
        pl.col("emitido_em").max(), pl.col("corte_dados").max(), pl.col("modelo_id").first()
    ).row(0)
    sem = resumo.filter(pl.col("status") == STATUS_SEM_PREVISAO).height
    liberado = info[1] - timedelta(minutes=30)
    desempenho = carregar_desempenho()
    with st.expander("Sobre este aviso"):
        estilo.html(
            f"""<div class="cm-rodape">
<b>Fonte:</b> dados abertos do ONS sobre restrição de geração eólica e solar
(constrained-off), por usina e meia-hora.<br>
<b>Emissão:</b> {info[0]:%d/%m/%Y %H:%M}, com dados liberados até {liberado:%d/%m/%Y}.
Modelo <code>{escape(info[2])}</code>, que calcula a chance de corte; o motivo é a regra do
histórico da usina.<br>
<b>Acerto:</b> medido em {escape(desempenho["periodo"])}, por usina e meia-hora
({escape(desempenho["origem"])}).<br>
<b>O aviso não informa</b> quanto será cortado, quanto isso custa nem se a ordem do ONS
será mantida. Ainda não usa previsão do tempo. {sem} usina(s) sem histórico suficiente
ficam sem aviso, e nunca aparecem como livres.</div>"""
        )


def render() -> None:
    estilo.aplicar()
    if dados.arquivo_ausente():
        st.error(
            "Nenhum aviso emitido encontrado em `data/processed/avisos.parquet`. Gere o arquivo "
            "com `uv run python -m curtamap.previsao.avisos --modelo "
            "models/previsao/<artefato>.joblib`. O painel não mostra números simulados."
        )
        return
    arquivo = dados.avisos()
    topo_pagina = st.container()
    dia, fontes, coluna_uf = _seletores(dados.dias(arquivo))
    aviso = dados.aviso_do_dia(arquivo, dia).filter(pl.col("fonte").is_in(fontes))
    ufs = coluna_uf.multiselect(
        "UF", sorted(aviso["id_estado"].drop_nulls().unique().to_list()), placeholder="Todas"
    )
    if ufs:
        aviso = aviso.filter(pl.col("id_estado").is_in(ufs))
    with topo_pagina:
        _cabecalho(dia, aviso["emitido_em"].max())
    resumo = resumo_usinas(aviso)
    _cards(resumo)
    st.write("")
    _faixa_acerto(fontes)

    estilo.html(
        '<div class="cm-secao">Usinas com mais horas em alerta amanhã</div>'
        '<div class="cm-legenda"><span><i style="background:#E4572E"></i>em alerta</span>'
        '<span><i style="background:#7FD1C6"></i>livre</span>'
        '<span><i style="background:#E3E8EF"></i>sem geração prevista</span></div>'
    )
    # Vagas divididas entre as fontes escolhidas, para o mapa não mostrar só uma delas.
    em_alerta = resumo.filter(pl.col("status") == STATUS_ALERTA)
    vagas = _TOP_MAPA // max(em_alerta["fonte"].n_unique(), 1)
    topo = pl.concat([em_alerta.filter(pl.col("fonte") == f).head(vagas) for f in fontes])
    if topo.height:
        ordem = [(r["fonte"], r["id_ons"], _nome(r)) for r in topo.iter_rows(named=True)]
        st.plotly_chart(graficos.mapa_portfolio(aviso, ordem), width="stretch")
    else:
        st.info("Nenhuma usina em alerta com os filtros atuais.")

    esquerda, direita = st.columns([1.15, 1], gap="large")
    with esquerda:
        estilo.html('<div class="cm-secao">Portfólio · clique numa usina</div>')
        escolhida = _tabela(resumo)
    with direita:
        estilo.html('<div class="cm-secao">Aviso da usina</div>')
        if escolhida:
            _detalhe(aviso, escolhida)
    _rodape(aviso, resumo)
