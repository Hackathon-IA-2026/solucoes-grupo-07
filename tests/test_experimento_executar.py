from datetime import date
from pathlib import Path

import polars as pl
import pytest

from curtamap.experimentos.rede_temporal.executar import KEY, save_columns


def _rows() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "fonte": ["eolica", "eolica"],
            "id_ons": ["A", "A"],
            "dia": [date(2026, 2, 1)] * 2,
            "slot": [0, 1],
        }
    )


def test_key_only_file_for_the_network(tmp_path: Path) -> None:
    path = tmp_path / "rede_2026-02_eolica.parquet"

    save_columns(path, _rows(), {"p_x": [0.1, 0.2], "v_x": [1.0, 2.0]}, with_base=False)

    saved = pl.read_parquet(path)
    assert saved.columns == [*KEY, "p_x", "v_x"]


def test_new_columns_are_merged_and_replaced(tmp_path: Path) -> None:
    path = tmp_path / "rede.parquet"
    save_columns(path, _rows(), {"p_x": [0.1, 0.2]}, with_base=False)
    save_columns(path, _rows(), {"p_x": [0.3, 0.4], "p_y": [0.5, 0.6]}, with_base=False)

    saved = pl.read_parquet(path).sort(KEY)

    assert saved["p_x"].to_list() == [0.3, 0.4]
    assert saved["p_y"].to_list() == [0.5, 0.6]


def test_different_rows_are_refused(tmp_path: Path) -> None:
    path = tmp_path / "rede.parquet"
    save_columns(path, _rows(), {"p_x": [0.1, 0.2]}, with_base=False)

    with pytest.raises(ValueError, match="linhas diferentes"):
        save_columns(path, _rows().head(1), {"p_x": [0.1]}, with_base=False)
