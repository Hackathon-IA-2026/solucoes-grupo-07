from pathlib import Path
from types import SimpleNamespace

import pytest

from curtamap.download_data import build_download_plan


def test_plan_selects_only_ons_files_by_default(tmp_path: Path) -> None:
    files = [
        SimpleNamespace(id="ons-1", path="Dados - ONS/eolica.parquet"),
        SimpleNamespace(id="era-1", path="ERA5 - Tutorial/tutorial.ipynb"),
    ]

    plan = build_download_plan(files, output_dir=tmp_path)

    assert [(item.file_id, item.target) for item in plan] == [
        ("ons-1", tmp_path / "eolica.parquet")
    ]


def test_plan_can_include_tutorials_without_losing_subdirectories(tmp_path: Path) -> None:
    files = [SimpleNamespace(id="era-1", path="ERA5 - Tutorial/tutorial.ipynb")]

    plan = build_download_plan(files, output_dir=tmp_path, include_tutorials=True)

    assert plan[0].target == tmp_path / "ERA5 - Tutorial" / "tutorial.ipynb"


def test_plan_rejects_unsafe_remote_paths(tmp_path: Path) -> None:
    files = [SimpleNamespace(id="bad", path="Dados - ONS/../../fora.parquet")]

    with pytest.raises(ValueError, match="inseguro"):
        build_download_plan(files, output_dir=tmp_path)
