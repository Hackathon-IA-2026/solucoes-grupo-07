from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient

from curtamap.data_contract import SPECS

ROOT = Path(__file__).parents[1]
NOTEBOOK = ROOT / "notebooks" / "01_eda_fundamentos_dados.ipynb"
RAW = ROOT / "data" / "raw"


@pytest.mark.skip(reason="Outputs antigos abrangem teste reservado; aguardar Etapa 2C")
def test_eda_notebook_is_versioned_with_executed_outputs():
    nb = nbformat.read(NOTEBOOK, as_version=4)
    code = [c for c in nb.cells if c.cell_type == "code"]
    assert code and all(c.execution_count for c in code)
    images = sum("image/png" in o.get("data", {}) for c in code for o in c.outputs)
    assert images >= 12
    assert not any(o.output_type == "error" for c in code for o in c.outputs)


@pytest.mark.skip(reason="EDA integral abrange teste reservado; aguardar Etapa 2C")
@pytest.mark.skipif(
    not all((RAW / SPECS[s].filename).exists() for s in ["eolica", "fotovoltaica"]),
    reason="Parquet principais ausentes em data/raw",
)
def test_eda_notebook_runs_end_to_end_on_local_data():
    nb = nbformat.read(NOTEBOOK, as_version=4)
    client = NotebookClient(
        nb,
        timeout=600,
        kernel_name="python3",
        resources={"metadata": {"path": str(NOTEBOOK.parent)}},
    )
    client.execute()  # levanta CellExecutionError se qualquer célula ou assert falhar
