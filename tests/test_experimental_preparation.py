from datetime import date, datetime
from pathlib import Path

import polars as pl

from curtamap.experimental.preparation import prepare_target_partitions
from curtamap.experimental.temporal import AvailabilityScenario, BusinessCalendar


def raw_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "fonte": ["eolica", "eolica"],
            "id_ons": ["A", "A"],
            "id_estado": ["RJ", "RJ"],
            "id_subsistema": ["SE", "SE"],
            "ceg": ["-", "-"],
            "din_instante": [datetime(2025, 1, 2), datetime(2025, 2, 2)],
            "val_geracaolimitada": [1.0, None],
            "val_geracaoreferencia": [20.0, 20.0],
            "val_geracao": [5.0, 5.0],
            "cod_razaorestricao": ["ENE", None],
            "cod_origemrestricao": ["SIS", None],
        }
    )


def test_preparation_is_partitioned_columnar_and_does_not_modify_original(tmp_path: Path) -> None:
    root = tmp_path / "disco externo com espaços"
    raw = root / "dados originais" / "source.parquet"
    raw.parent.mkdir(parents=True)
    raw_frame().write_parquet(raw)
    before = raw.read_bytes()
    output = root / "cache experimental"
    calendar = BusinessCalendar(frozenset({date(2025, 1, 1)}), "synthetic")

    summary = prepare_target_partitions(
        raw,
        output,
        AvailabilityScenario.main(),
        calendar,
        temp_dir=root / "temporarios duckdb",
        memory_limit="1GB",
        threads=1,
    )

    assert raw.read_bytes() == before
    files = sorted(output.glob("source=eolica/year=*/month=*/*.parquet"))
    assert len(files) == 2
    result = pl.read_parquet(files)
    assert result["volume_mwmed"].to_list() == [15.0, 0.0]
    assert result["corte_positivo"].to_list() == [True, False]
    assert result["disponivel_em"][0] == datetime(2025, 1, 3, 19, 30)
    assert summary["rows"] == 2
    assert len(summary["input_sha256"]) == 64
    assert summary["partitions"] == 2
