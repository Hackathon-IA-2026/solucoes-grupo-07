from datetime import datetime, timedelta

import polars as pl
import pytest

from curtamap.aviso import (
    STATUS_ALERTA,
    STATUS_SEM_ALERTA,
    STATUS_SEM_PREVISAO,
    carregar_desempenho,
    formatar_janela,
    horas_livres,
    janelas_alerta,
    motivo_texto,
    resumo_usinas,
    sugestao,
)

T0 = datetime(2026, 9, 10)
STEP = timedelta(minutes=30)


def usina(
    id_ons: str,
    *,
    fonte: str = "eolica",
    alertas: set[int] = frozenset(),
    sem_previsao: set[int] = frozenset(),
    sem_potencial: set[int] = frozenset(),
    causa: str | None = "ENE",
    origem: str | None = "SIS",
) -> pl.DataFrame:
    rows = []
    for h in range(1, 49):
        nulo = h in sem_previsao
        p = None if nulo else (0.9 if h in alertas else 0.1)
        rows.append(
            {
                "fonte": fonte,
                "id_ons": id_ons,
                "t0": T0,
                "horizonte": h,
                "tau": T0 + (h - 1) * STEP,
                "p_corte": p,
                "limiar_alerta": 0.5,
                "alerta": None if nulo else h in alertas,
                "causa_prevista": causa,
                "origem_prevista": origem,
                "potencial_referencia_mwmed": 0.0 if h in sem_potencial else 50.0,
            }
        )
    return pl.DataFrame(rows)


def test_janelas_agrupam_meias_horas_consecutivas_em_alerta():
    forecast = usina("A", alertas={23, 24, 25, 26, 30})
    janelas = janelas_alerta(forecast)
    assert janelas.height == 2
    primeira = janelas.row(0, named=True)
    assert primeira["inicio"] == T0 + 22 * STEP
    assert primeira["fim"] == T0 + 26 * STEP
    assert primeira["horas"] == pytest.approx(2.0)
    assert primeira["chance_max"] == pytest.approx(0.9)
    assert primeira["causa"] == "ENE"
    assert janelas.row(1, named=True)["horas"] == pytest.approx(0.5)


def test_meia_hora_sem_previsao_quebra_a_janela_e_nunca_vira_alerta_nem_livre():
    forecast = usina("A", alertas={10, 11, 13}, sem_previsao={12})
    assert janelas_alerta(forecast).height == 2
    livres = horas_livres(forecast)
    livres_slots = sum(livres["horas"]) * 2
    assert livres_slots == 48 - 3 - 1


def test_horas_livres_exigem_potencial_de_geracao():
    # Solar à noite: sem potencial, não é "hora livre", é hora sem geração.
    forecast = usina("S", fonte="fotovoltaica", alertas={25, 26}, sem_potencial=set(range(1, 13)))
    livres = horas_livres(forecast)
    assert livres["inicio"].min() == T0 + 12 * STEP
    assert sum(livres["horas"]) == pytest.approx((48 - 12 - 2) / 2)


def test_causa_da_janela_e_a_mais_frequente_e_empate_e_marcado_como_misto():
    forecast = usina("A", alertas={1, 2, 3}).with_columns(
        pl.when(pl.col("horizonte") == 1).then(pl.lit("CNF")).otherwise(pl.col("causa_prevista"))
        .alias("causa_prevista")
    )  # fmt: skip
    assert janelas_alerta(forecast)["causa"].to_list() == ["ENE"]
    empate = usina("B", alertas={1, 2}).with_columns(
        pl.when(pl.col("horizonte") == 1).then(pl.lit("CNF")).otherwise(pl.col("causa_prevista"))
        .alias("causa_prevista")
    )  # fmt: skip
    assert janelas_alerta(empate)["causa"].to_list() == ["MISTA"]


def test_resumo_ordena_por_horas_em_alerta_e_separa_sem_previsao():
    forecast = pl.concat(
        [
            usina("POUCO", alertas={20}),
            usina("MUITO", alertas=set(range(20, 30))),
            usina("NADA"),
            usina("CEGO", sem_previsao=set(range(1, 49))),
        ]
    )
    resumo = resumo_usinas(forecast)
    assert resumo["id_ons"].to_list() == ["MUITO", "POUCO", "NADA", "CEGO"]
    assert resumo["status"].to_list() == [
        STATUS_ALERTA,
        STATUS_ALERTA,
        STATUS_SEM_ALERTA,
        STATUS_SEM_PREVISAO,
    ]
    muito = resumo.row(0, named=True)
    assert muito["horas_alerta"] == pytest.approx(5.0)
    assert muito["primeiro_alerta"] == T0 + 19 * STEP
    assert muito["motivo"] == "ENE"
    cego = resumo.row(3, named=True)
    assert cego["horas_alerta"] is None and cego["horas_livres"] is None


def test_formatar_janela_usa_horas_legiveis_e_24h_no_fim_do_dia():
    assert formatar_janela(T0 + 22 * STEP, T0 + 30 * STEP) == "11h às 15h"
    assert formatar_janela(T0 + 21 * STEP, T0 + 48 * STEP) == "10h30 às 24h"


def test_motivo_em_linguagem_simples_com_origem():
    assert motivo_texto("ENE", "SIS") == "sobra de energia no sistema · origem sistêmica"
    assert motivo_texto("CNF", "LOC").startswith("limite de segurança da rede")
    assert motivo_texto(None, None) == "sem ordens recentes com motivo conhecido"
    assert motivo_texto("MISTA", "SIS").startswith("motivos variados")


def test_sugestao_sem_numeros_e_manutencao_so_em_janela_longa():
    curta = sugestao(1.0)
    longa = sugestao(2.0)
    assert "manutenção" not in curta and "manutenção" in longa
    assert not any(ch.isdigit() for ch in curta + longa)


def test_desempenho_versionado_cita_origem_e_fica_entre_zero_e_um():
    desempenho = carregar_desempenho()
    for fonte in ("eolica", "fotovoltaica"):
        item = desempenho["fontes"][fonte]
        assert 0 < item["precisao"] <= 1 and 0 < item["recall"] <= 1
        assert 0 < item["energia_avisada"] <= 1
    assert desempenho["origem"] and desempenho["periodo"]
