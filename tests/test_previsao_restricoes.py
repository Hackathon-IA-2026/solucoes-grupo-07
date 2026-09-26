from datetime import date, timedelta

import polars as pl
import pytest

from curtamap.previsao.restricoes import (
    causa_slot,
    grupo_restricao,
    nivel_grupo,
    normalizar_restricao,
    regime_nacional,
)

L = date(2026, 3, 31)


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("Controle de frequência do SIN.", "CONTROLE DE FREQUENCIA DO SIN"),
        (
            "Controle do fluxo: FNESE # Fluxo Nordeste/Sudeste - Conforme SGI 67.632-25",
            "FLUXO FNESE",
        ),
        ("Controle do fluxo: FNESE # Fluxo Nordeste/Sudeste", "FLUXO FNESE"),
        ("Controle do fluxo: FNESE # Fluxo Nordeste/Sudeste - Conforme IO-ON.SENE", "FLUXO FNESE"),
        ("Controle do FNESE, conforme SGI 43.225-26", "FLUXO FNESE"),
        (
            "Controle de inequação: LIMITAÇÃO DA TRANSMISSÃO NA LT 500 KV AÇU III / "
            "JAGUARUANA II – C1(V7) - IO-ON.NE.5NE",
            "CONTROLE DE INEQUACAO: LIMITACAO DA TRANSMISSAO NA LT 500 KV ACU III / JAGUARUANA II",
        ),
        (
            "Controle de inequação: LIMITE DE FJUSC EM FUNÇÃO DA POTÊNCIA TRANSMITIDA PELOS "
            "BIPOLOS XINGU / ESTREITO E XINGU / TERMINAL RIO - IO-ON.SENE revisão 84",
            "CONTROLE DE INEQUACAO: LIMITE DE FJUSC EM FUNCAO DA POTENCIA TRANSMITIDA PELOS "
            "BIPOLOS XINGU / ESTREITO E XINGU / TERMINAL RIO",
        ),
        (
            "Controle de inequação: SGI 26786-26: LT 230 kV ALAGOINHAS II / CICERO DANTAS C L8 "
            "BA (04L8) - SGI",
            "CONTROLE DE INEQUACAO: LT 230 KV ALAGOINHAS II / CICERO DANTAS C L8 BA",
        ),
        (
            "Desligamento das LT 525 kV Povo Novo / Marmeleiro C2. SGI N° 46.066-26",
            "DESLIGAMENTO DAS LT 525 KV POVO NOVO / MARMELEIRO",
        ),
        (
            "Controle de inequação: CONTROLE DE CARREGAMENTO DA LT 230 KV IRECÊ / MORRO DO "
            "CHAPÉU II – C1(S5), PREVENINDO\nA PERDA DA LT 500 KV MORRO DO CHAPÉU II / "
            "OUROLÂNDIA II – C1(N4) - IO-ON.NE.2SO e MOP 442-S/2025",
            "CONTROLE DE INEQUACAO: CONTROLE DE CARREGAMENTO DA LT 230 KV IRECE / MORRO DO "
            "CHAPEU II, PREVENINDO A PERDA DA LT 500 KV MORRO DO CHAPEU II / OUROLANDIA II",
        ),
        (
            "Controle de inequação: LIMITAÇÃO DO FLUXO BAHIA SUDOESTE e MOP 489-R - "
            "Conforme SGI 16.426-26",
            "CONTROLE DE INEQUACAO: LIMITACAO DO FLUXO BAHIA SUDOESTE",
        ),
        ("  ", None),
        (None, None),
    ],
)
def test_normalizar_restricao(bruto, esperado):
    assert normalizar_restricao(bruto) == esperado


def test_normalizar_restricao_une_variantes_de_sgi_e_revisao():
    textos = [
        "Controle do fluxo: FNESE # Fluxo Nordeste/Sudeste - Conforme SGI 67.632-25",
        "Controle do fluxo: FNESE # Fluxo Nordeste/Sudeste - Conforme SGI 67632-25",
        "Controle do fluxo: FNESE # Fluxo Nordeste/Sudeste - Conforme SGI 80.675-25",
    ]
    assert len({normalizar_restricao(t) for t in textos}) == 1


def _eventos(rows):
    return pl.DataFrame(
        rows,
        schema={"fonte": pl.String, "id_ons": pl.String, "dia": pl.Date, "restricao": pl.String},
        orient="row",
    )


def test_grupo_restricao_e_a_mais_frequente_em_91_dias_ate_l():
    rows = [("eolica", "A", L - timedelta(days=i), "X") for i in range(3)]
    rows += [("eolica", "A", L - timedelta(days=i), "Y") for i in range(2)]
    rows += [("eolica", "A", L - timedelta(days=100 + i), "Y") for i in range(10)]  # fora
    rows += [("eolica", "A", L + timedelta(days=1), "Y")] * 10  # futuro
    out = grupo_restricao(_eventos(rows), [L])
    assert out.columns == ["fonte", "id_ons", "ultimo_dia", "grupo_restricao"]
    assert out["grupo_restricao"].to_list() == ["X"]


def test_grupo_restricao_empate_e_deterministico_e_sem_evento_nao_aparece():
    rows = [("eolica", "A", L, "Y"), ("eolica", "A", L, "X")]
    rows += [("eolica", "B", L - timedelta(days=200), "Z")]
    out = grupo_restricao(_eventos(rows), [L]).sort("id_ons")
    assert out["id_ons"].to_list() == ["A"]
    assert out["grupo_restricao"].to_list() == ["X"]


def _base(rows):
    return pl.DataFrame(
        rows,
        schema={
            "fonte": pl.String,
            "id_ons": pl.String,
            "dia": pl.Date,
            "slot": pl.Int8,
            "corte": pl.Float32,
        },
        orient="row",
    )


def test_nivel_grupo_usa_membros_do_grupo_em_l_e_media_de_7_dias():
    grupos = pl.DataFrame(
        {
            "fonte": ["eolica"] * 3,
            "id_ons": ["A", "B", "C"],
            "ultimo_dia": [L] * 3,
            "grupo_restricao": ["X", "X", "Y"],
        }
    )
    rows = []
    for i in range(7):
        day = L - timedelta(days=i)
        rows += [
            ("eolica", "A", day, 0, 1.0),
            ("eolica", "B", day, 0, 0.0 if i else 1.0),
            ("eolica", "C", day, 0, 0.0),  # outro grupo: não entra em X
        ]
    rows += [("eolica", "A", L + timedelta(days=1), 0, 0.0)]  # futuro
    rows += [("eolica", "A", L - timedelta(days=7), 0, 0.0)]  # fora dos 7 dias
    out = nivel_grupo(_base(rows), grupos, [L]).sort("id_ons")
    assert out.columns == [
        "fonte",
        "id_ons",
        "ultimo_dia",
        "grupo_nivel_ultimo",
        "grupo_nivel_7d",
        "grupo_tamanho",
    ]
    a = out.row(0, named=True)
    assert a["grupo_nivel_ultimo"] == pytest.approx(1.0)
    # dias: L com (1 + 1)/2 = 1; seis dias com (1 + 0)/2 = 0,5 → média 4/7.
    assert a["grupo_nivel_7d"] == pytest.approx((1 + 6 * 0.5) / 7)
    assert a["grupo_tamanho"] == 2
    assert out.row(2, named=True)["grupo_nivel_ultimo"] == pytest.approx(0.0)


def test_nivel_grupo_sem_dado_em_l_e_nulo():
    grupos = pl.DataFrame(
        {"fonte": ["eolica"], "id_ons": ["A"], "ultimo_dia": [L], "grupo_restricao": ["X"]}
    )
    rows = [("eolica", "A", L - timedelta(days=2), 0, 1.0)]
    out = nivel_grupo(_base(rows), grupos, [L])
    assert out["grupo_nivel_ultimo"].to_list() == [None]
    assert out["grupo_nivel_7d"].to_list() == [pytest.approx(1.0)]


def test_regime_nacional_por_fonte_e_total():
    def row(fonte, day, ene, cnf):
        return {"fonte": fonte, "dia": day, "_ENE": ene, "_CNF": cnf, "_REL": 0.0}

    rows = [
        row("eolica", L, 1.0, 0.0),
        row("eolica", L, 0.0, 1.0),
        row("fotovoltaica", L, 1.0, 0.0),
        row("eolica", L - timedelta(days=1), 1.0, 0.0),
        row("eolica", L + timedelta(days=1), 0.0, 1.0),  # futuro
        {"fonte": "eolica", "dia": L, "_ENE": None, "_CNF": None, "_REL": None},  # sem causa
    ]
    base = pl.DataFrame(rows, schema_overrides={"_ENE": pl.Float32, "_CNF": pl.Float32})
    out = regime_nacional(base, [L]).sort("fonte")
    assert out.columns == [
        "fonte",
        "ultimo_dia",
        "sin_ene_ultimo",
        "sin_ene_7d",
        "sin_ene_ultimo_total",
        "sin_ene_7d_total",
    ]
    eol = out.row(0, named=True)
    assert eol["sin_ene_ultimo"] == pytest.approx(0.5)
    assert eol["sin_ene_7d"] == pytest.approx((0.5 + 1.0) / 2)
    assert eol["sin_ene_ultimo_total"] == pytest.approx(2 / 3)
    assert out.row(1, named=True)["sin_ene_ultimo"] == pytest.approx(1.0)


def test_causa_slot_participacao_em_91_dias_ate_l_ignora_sem_causa():
    def row(day, slot, rel, cnf, ene):
        return {
            "fonte": "eolica",
            "id_ons": "A",
            "dia": day,
            "slot": slot,
            "_REL": rel,
            "_CNF": cnf,
            "_ENE": ene,
        }

    rows = [
        row(L, 5, 0.0, 1.0, 0.0),
        row(L - timedelta(days=90), 5, 0.0, 0.0, 1.0),
        row(L - timedelta(days=91), 5, 1.0, 0.0, 0.0),  # fora
        row(L + timedelta(days=1), 5, 1.0, 0.0, 0.0),  # futuro
        row(L, 5, None, None, None),  # sem causa conhecida
        row(L, 6, None, None, None),
    ]
    base = pl.DataFrame(rows, schema_overrides={c: pl.Float32 for c in ("_REL", "_CNF", "_ENE")})
    out = causa_slot(base, [L]).sort("slot")
    assert out.columns == [
        "fonte",
        "id_ons",
        "slot",
        "ultimo_dia",
        "causa_rel_91d",
        "causa_cnf_91d",
        "causa_ene_91d",
    ]
    assert out.row(0)[4:] == (pytest.approx(0.0), pytest.approx(0.5), pytest.approx(0.5))
    assert out.row(1)[4:] == (None, None, None)
