import re
from pathlib import Path

import polars as pl

from curtamap.data_contract import SPECS
from curtamap.targets import derive_targets

INVENTORY = Path(__file__).parents[1] / "docs" / "feature-inventory.md"
CLASSES = {
    "identificador",
    "conhecida",
    "defasagem",
    "meteorologia futura",
    "alvo",
    "pós-evento",
    "auxiliar",
    "proibido",
}


def classified_fields() -> dict[str, str]:
    rows = re.findall(r"^\| `([a-z_]+)` \| ([^|]+) \|", INVENTORY.read_text(), re.M)
    return {name: cls.strip() for name, cls in rows}


def test_every_snapshot_and_target_field_is_classified_once():
    fields = classified_fields()
    expected = {name for spec in SPECS.values() for name in spec.schema.names}
    sample = pl.DataFrame(
        {
            "fonte": ["eolica"],
            "val_geracaolimitada": [None],
            "val_geracaoreferencia": [1.0],
            "val_geracao": [1.0],
            "cod_razaorestricao": [None],
            "cod_origemrestricao": [None],
        },
        schema_overrides={
            "val_geracaolimitada": pl.Float64,
            "cod_razaorestricao": pl.String,
            "cod_origemrestricao": pl.String,
        },
    )
    expected |= set(derive_targets(sample).columns)
    assert expected - fields.keys() == set()
    assert {cls for cls in fields.values()} <= CLASSES
