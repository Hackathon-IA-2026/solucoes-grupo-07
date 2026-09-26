"""Fumaça da interface com `AppTest`: cada tela renderiza sem exceção.

Com os Parquet do ONS em `data/raw`, as telas rodam sobre dados reais; sem eles, só o
aviso de dados ausentes é verificado.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from curtamap.config import settings
from curtamap.ui import dados

APP = str(Path(__file__).parents[1] / "src" / "curtamap" / "app.py")
HAS_DATA = not dados.missing_files()
needs_data = pytest.mark.skipif(not HAS_DATA, reason="Parquet do ONS ausentes em data/raw")


def _page(module: str) -> None:
    # Mesmo roteiro do app.py, para uma tela só (páginas registradas por função).
    import importlib

    from curtamap.ui import contexto

    context = contexto.load()
    contexto.store(context)
    if context is not None:
        contexto.seal(context)
        importlib.import_module(module).render()


def _run_page(module: str) -> AppTest:
    app = AppTest.from_function(_page, args=(module,), default_timeout=180)
    return app.run()


def test_missing_data_shows_instructions_instead_of_numbers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    app = AppTest.from_file(APP, default_timeout=60).run()

    assert not app.exception
    assert any("Dados do ONS ausentes" in e.value for e in app.error)
    assert not app.metric


@needs_data
def test_operation_page_opens_with_the_decision() -> None:
    app = AppTest.from_file(APP, default_timeout=180).run()

    assert not app.exception, app.exception
    assert app.title[0].value == "Operação D+1"
    assert [m.label for m in app.metric][:2] == ["Usinas em risco", "Energia em risco (24 h)"]
    assert any("EXEMPLO SIMULADO" in w.value for w in app.warning)
    assert any("t0" in s.value for s in [*app.warning, *app.info])


@needs_data
@pytest.mark.parametrize("module", ["curtamap.ui.tatica", "curtamap.ui.metodologia"])
def test_other_pages_render_with_the_seal(module: str) -> None:
    app = _run_page(module)

    assert not app.exception, app.exception
    assert any("t0" in s.value for s in [*app.warning, *app.info])
