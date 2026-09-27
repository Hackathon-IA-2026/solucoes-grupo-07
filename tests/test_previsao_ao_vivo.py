from datetime import date, datetime, timedelta

import polars as pl
import pytest

from curtamap.previsao.ao_vivo import (
    anexar,
    corte_efetivo,
    dias_pendentes,
    meses_necessarios,
    proximo_horario,
    url_publicacao,
)
from curtamap.previsao.calendario import load_calendar


def test_url_segue_o_padrao_do_ons():
    assert url_publicacao("eolica", date(2026, 7, 1)).endswith(
        "restricao_coff_eolica_tm/RESTRICAO_COFF_EOLICA_2026_07.parquet"
    )


def test_meses_cobrem_o_historico_do_modelo():
    meses = meses_necessarios(date(2026, 9, 28))
    assert meses[0] <= date(2026, 6, 28) and meses[-1] == date(2026, 9, 1)
    assert meses == sorted(set(meses)) and all(m.day == 1 for m in meses)


def _historia(ultimo: datetime) -> pl.DataFrame:
    return pl.DataFrame({"din_instante": [ultimo - timedelta(hours=5), ultimo]})


def test_corte_usa_o_calendario_quando_os_dados_chegaram():
    calendar = load_calendar()
    # Emissão das 20h de segunda, 28/09: o lote das 19h30 libera domingo, 27/09.
    corte = corte_efetivo(date(2026, 9, 29), _historia(datetime(2026, 9, 27, 23, 30)), calendar)
    assert corte == datetime(2026, 9, 28)


def test_corte_recua_quando_o_ons_atrasa():
    calendar = load_calendar()
    corte = corte_efetivo(date(2026, 9, 29), _historia(datetime(2026, 9, 26, 23, 30)), calendar)
    assert corte == datetime(2026, 9, 27)
    # Dia incompleto não conta como liberado.
    corte = corte_efetivo(date(2026, 9, 29), _historia(datetime(2026, 9, 27, 12, 0)), calendar)
    assert corte == datetime(2026, 9, 27)


def test_pendentes_param_em_amanha_so_depois_das_20h():
    ultimo = date(2026, 9, 25)
    assert dias_pendentes(ultimo, datetime(2026, 9, 27, 11, 0)) == [
        date(2026, 9, 26),
        date(2026, 9, 27),
    ]
    assert dias_pendentes(ultimo, datetime(2026, 9, 27, 20, 0))[-1] == date(2026, 9, 28)
    assert dias_pendentes(date(2026, 9, 28), datetime(2026, 9, 27, 21, 0)) == []


def test_pendentes_tem_limite_de_recuperacao():
    pendentes = dias_pendentes(date(2026, 1, 1), datetime(2026, 9, 27, 21, 0), limite=7)
    assert len(pendentes) == 7 and pendentes[-1] == date(2026, 9, 28)


def test_proximo_horario_vira_o_dia():
    assert proximo_horario(datetime(2026, 9, 27, 11, 0), 19, 30) == datetime(2026, 9, 27, 19, 30)
    assert proximo_horario(datetime(2026, 9, 27, 19, 30), 19, 30) == datetime(2026, 9, 28, 19, 30)


def _aviso(dia: date, p: float) -> pl.DataFrame:
    t0 = datetime.combine(dia, datetime.min.time())
    return pl.DataFrame({"fonte": ["eolica"], "id_ons": ["E1"], "t0": [t0], "p_corte": [p]})


def test_anexar_substitui_o_dia_e_preserva_os_outros(tmp_path):
    caminho = tmp_path / "avisos.parquet"
    anexar(caminho, _aviso(date(2026, 9, 25), 0.1))
    anexar(caminho, _aviso(date(2026, 9, 26), 0.2))
    anexar(caminho, _aviso(date(2026, 9, 26), 0.3))
    salvo = pl.read_parquet(caminho).sort("t0")
    assert salvo["p_corte"].to_list() == [0.1, 0.3]
    assert not list(tmp_path.glob("*.tmp"))


def test_anexar_recusa_aviso_vazio(tmp_path):
    with pytest.raises(ValueError):
        anexar(tmp_path / "avisos.parquet", _aviso(date(2026, 9, 25), 0.1).clear())
