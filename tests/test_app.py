"""Fumaça da interface com `AppTest`: a tela renderiza sem exceção e sem números simulados."""

from datetime import datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
from streamlit.testing.v1 import AppTest

from zelo.ui import painel

T0 = datetime(2026, 9, 10)


def _arquivo(path: Path) -> Path:
    rows = []
    for fonte, id_ons, nome in (
        ("eolica", "E1", "Usina Vento"),
        ("fotovoltaica", "S1", "Usina Sol"),
    ):
        for h in range(1, 49):
            alerta = 22 <= h <= 30
            rows.append(
                {
                    "fonte": fonte,
                    "id_ons": id_ons,
                    "nom_usina": nome,
                    "id_estado": "RN",
                    "id_subsistema": "NE",
                    "t0": T0,
                    "horizonte": h,
                    "tau": T0 + (h - 1) * timedelta(minutes=30),
                    "p_corte": 0.9 if alerta else 0.1,
                    "limiar_alerta": 0.33,
                    "alerta": alerta,
                    "causa_prevista": "ENE",
                    "origem_prevista": "SIS",
                    "potencial_referencia_mwmed": 20.0 if 12 <= h <= 36 else 0.0,
                    "emitido_em": T0 - timedelta(hours=4),
                    "corte_dados": T0 - timedelta(days=1),
                    "modelo_id": "teste",
                }
            )
    pl.DataFrame(rows).write_parquet(path)
    return path


def _render(path: str) -> None:
    from pathlib import Path

    from zelo.ui import dados, painel

    dados.ARCHIVE_OVERRIDE = Path(path)
    painel.render()


def test_painel_renderiza_o_aviso_do_dia(tmp_path: Path) -> None:
    arquivo = _arquivo(tmp_path / "avisos.parquet")
    app = AppTest.from_function(_render, args=(str(arquivo),), default_timeout=60).run()
    assert not app.exception
    texto = " ".join(m.value for m in app.markdown)
    assert "Usina Vento" in texto and "10h30 às 15h" in texto
    assert "sobra de energia no sistema" in texto
    assert "Horas livres" in texto


def test_sem_arquivo_mostra_instrucao_em_vez_de_numeros(tmp_path: Path) -> None:
    app = AppTest.from_function(
        _render, args=(str(tmp_path / "ausente.parquet"),), default_timeout=60
    ).run()
    assert not app.exception
    assert "zelo.previsao.avisos" in app.error[0].value


def test_fontes_do_painel_cobrem_as_do_contrato() -> None:
    from zelo.contracts import SOURCES

    assert set(painel.FONTES) == set(SOURCES)


@pytest.fixture(autouse=True)
def _limpa_cache():
    from zelo.ui import dados

    yield
    dados.ARCHIVE_OVERRIDE = None
