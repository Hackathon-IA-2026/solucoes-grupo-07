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
_MOTIVO_CURTO = {
    "ENE": "sobra de energia",
    "CNF": "limite da rede",
    "REL": "rede externa",
    "MISTA": "variados",
}
_FONTES_PLURAL = {"eolica": "eólicas", "fotovoltaica": "solares"}
_DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
          "setembro", "outubro", "novembro", "dezembro"]  # fmt: skip
_TOP_MAPA = 18


def _dia_extenso(dia: date) -> str:
    return f"{_DIAS_SEMANA[dia.weekday()]}, {dia:%d/%m/%Y}"


def _dia_titulo(dia: date) -> str:
    semana = _DIAS_SEMANA[dia.weekday()]
    semana += "" if dia.weekday() >= 5 else "-feira"
    return f"{semana}, {dia.day} de {_MESES[dia.month - 1]}"


def _horas(valor: float | None) -> str:
    if valor is None:
        return "—"
    texto = f"{valor:.1f}".replace(".", ",").removesuffix(",0")
    return f"{texto} h"


def _nome(row: dict) -> str:
    return row.get("nom_usina") or f"{row['fonte']}/{row['id_ons']}"


def _cabecalho(dia: date, emitido) -> None:
    estilo.html(
        f"""<div class="cm-mast">
<div class="cm-kicker"><b>CurtaMap</b> &nbsp;·&nbsp; aviso diário de cortes &nbsp;·&nbsp;
emitido às {emitido:%Hh} de {emitido:%d/%m}</div>
<h1>Amanhã, <em>{escape(_dia_titulo(dia))}</em></h1>
<div class="cm-lede">Em quais horas cada usina deve ser cortada, por qual motivo e quanto
este aviso costuma acertar. Calculado com os dados públicos do ONS já liberados na noite
anterior.</div></div>"""
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
    estilo.html(
        '<div class="cm-stats">'
        + estilo.stat(
            "Usinas em alerta",
            f"{em_alerta.height}<small> de {total}</small>",
            "com pelo menos uma janela de corte provável",
        )
        + estilo.stat("Horas em alerta", _horas(mediana_alerta), "por usina em alerta, mediana")
        + estilo.stat(
            "Horas livres", _horas(mediana_livre), "com geração e sem alerta, mediana por usina"
        )
        + estilo.stat(
            "Motivo mais frequente",
            escape(MOTIVOS.get(motivo, "—")),
            f"na janela principal de {parcela:.0%} das usinas em alerta" if motivo else "",
            texto=True,
        )
        + "</div>"
    )


def _faixa_acerto(fontes: list[str]) -> None:
    desempenho = carregar_desempenho()
    blocos = []
    for fonte in fontes:
        item = desempenho["fontes"][fonte]
        blocos.append(
            f'<div><div class="cm-rotulo">{FONTES[fonte]}</div>'
            f'<span class="num">{round(item["precisao"] * 10)} em 10</span>'
            '<div class="t">horas avisadas tiveram corte</div>'
            f'<span class="num">{item["energia_avisada"]:.0%}</span>'
            '<div class="t">da energia cortada caiu em horas avisadas</div></div>'
        )
    estilo.html(
        f'<div class="cm-acerto" style="--n:{len(blocos)}"><div><h4>Quanto o aviso acerta</h4>'
        f'<div class="t">Medido de {escape(desempenho["periodo"])}, com dados que o modelo '
        f"nunca tinha visto.</div></div>{''.join(blocos)}</div>"
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
        pl.col("motivo").replace_strict(_MOTIVO_CURTO, default="—").alias("Motivo típico"),
        pl.col("chance_max").alias("Risco máximo"),
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
            "Risco máximo": st.column_config.ProgressColumn(
                format="percent", min_value=0.0, max_value=1.0
            ),
        },
    )
    linhas = evento.selection.rows if evento else []
    indice = linhas[0] if linhas and linhas[0] < resumo.height else 0
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
    partes = [
        f'<div class="cm-aviso"><h3>{escape(_nome(usina))}</h3>',
        f'<div class="cm-meta">{escape(local)} · código ONS {escape(usina["id_ons"])}</div>',
    ]
    if usina["status"] == STATUS_SEM_PREVISAO:
        partes.append(
            '<span class="cm-tag neutra">sem previsão</span> Não há histórico recente '
            "suficiente desta usina para emitir o aviso."
        )
    elif not janelas.height:
        partes.append(
            '<span class="cm-tag livre">sem alerta</span> Nenhuma hora com corte provável amanhã.'
        )
    for janela in janelas.iter_rows(named=True):
        partes.append(
            '<div class="cm-janela"><div class="cm-hora">'
            f"{formatar_janela(janela['inicio'], janela['fim'])}</div>"
            '<div class="cm-detalhe"><span class="cm-tag">risco até '
            f"{janela['chance_max']:.0%}</span>"
            f"{escape(motivo_texto(janela['causa'], janela['origem']))}"
            f'<br><span class="s">{escape(sugestao(janela["horas"]))}</span></div></div>'
        )
    if livres.height:
        texto = ", ".join(
            formatar_janela(r["inicio"], r["fim"]) for r in livres.iter_rows(named=True)
        )
        partes.append(
            '<div class="cm-janela"><div class="cm-hora livre">Horas livres</div>'
            f'<div class="cm-detalhe">{escape(texto)}<br><span class="s">Geração esperada '
            "sem alerta de corte.</span></div></div>"
        )
    partes.append(
        '<div class="cm-janela"><div class="cm-hora neutra">Acerto</div>'
        '<div class="cm-detalhe">De cada 10 horas avisadas nas usinas '
        f"{_FONTES_PLURAL[usina['fonte']]}, {round(desempenho['precisao'] * 10)} tiveram "
        'corte.<br><span class="s">O motivo vem das ordens desta usina, neste horário, nas '
        "últimas 4 semanas.</span></div></div></div>"
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
Modelo <code>{escape(info[2])}</code>, que calcula o risco de corte
(um índice que ordena as horas; o número validado é o
acerto "8 em 10"); o motivo é a regra do
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
    _faixa_acerto(fontes)

    estilo.html(
        '<div class="cm-secao">Usinas com mais horas em alerta amanhã</div>'
        f'<div class="cm-legenda"><span><i style="background:{estilo.ALERTA}"></i>em alerta'
        f'</span><span><i style="background:{estilo.LIVRE_CLARO}"></i>livre</span>'
        f'<span><i style="background:{estilo.SEM_GERACAO}"></i>sem geração prevista</span>'
        "</div>"
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
        estilo.html(
            '<div class="cm-secao">Portfólio</div>'
            '<div class="cm-legenda">Clique numa usina para ver o aviso dela.</div>'
        )
        escolhida = _tabela(resumo)
    with direita:
        estilo.html('<div class="cm-secao">Aviso da usina</div>')
        if escolhida:
            _detalhe(aviso, escolhida)
    _rodape(aviso, resumo)
