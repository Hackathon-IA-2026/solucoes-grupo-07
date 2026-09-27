"""Contrato versionado do snapshot do hackathon, distinto do schema ONS atual."""

from dataclasses import dataclass

import pyarrow as pa

TEXT = pa.string()
COMMON = [(x, TEXT) for x in ["id_subsistema", "id_estado", "nom_usina", "id_ons", "ceg"]]
AUX = [
    ("fonte", TEXT),
    ("ano", pa.int32()),
    ("mes", pa.int32()),
    ("data", pa.date32()),
    ("hora", pa.int32()),
    ("minuto", pa.int32()),
    ("ano_mes", TEXT),
    ("arquivo_origem", TEXT),
]
MAIN_SCHEMA = pa.schema(
    COMMON
    + [("nom_subsistema", TEXT), ("nom_estado", TEXT), ("din_instante", pa.timestamp("ns"))]
    + [
        (c, pa.float64())
        for c in [
            "val_geracao",
            "val_geracaolimitada",
            "val_disponibilidade",
            "val_geracaoreferencia",
            "val_geracaoreferenciafinal",
        ]
    ]
    + [(c, TEXT) for c in ["cod_razaorestricao", "cod_origemrestricao", "dsc_restricao"]]
    + AUX
)


def detail_schema(source: str) -> pa.Schema:
    weather = [("val_ventoverificado", pa.float64()), ("flg_dadoventoinvalido", pa.float64())]
    if source == "fotovoltaica":
        weather = [
            ("val_irradianciaverificado", pa.float64()),
            ("flg_dadoirradianciainvalido", pa.bool_()),
        ]
    return pa.schema(
        COMMON
        + [
            ("nom_modalidadeoperacao", TEXT),
            ("nom_conjuntousina", TEXT),
            ("din_instante", pa.timestamp("ns")),
        ]
        + weather
        + [("val_geracaoestimada", pa.float64()), ("val_geracaoverificada", pa.float64())]
        + AUX
    )


@dataclass(frozen=True)
class DatasetSpec:
    filename: str
    sources: tuple[str, ...]
    detail: bool = False

    @property
    def schema(self) -> pa.Schema:
        return detail_schema(self.sources[0]) if self.detail else MAIN_SCHEMA


SPECS = {
    "eolica": DatasetSpec("constrained_off_eolica_tm.parquet", ("eolica",)),
    "fotovoltaica": DatasetSpec("constrained_off_fotovoltaica_tm.parquet", ("fotovoltaica",)),
    "integrada": DatasetSpec(
        "constrained_off_eolica_fotovoltaica_tm.parquet", ("eolica", "fotovoltaica")
    ),
    "eolica_detail": DatasetSpec("constrained_off_eolica_detail.parquet", ("eolica",), True),
    "fotovoltaica_detail": DatasetSpec(
        "constrained_off_fotovoltaica_detail.parquet", ("fotovoltaica",), True
    ),
}


def schema_issues(schema: pa.Schema, spec: DatasetSpec) -> list[str]:
    actual, expected = (
        dict(zip(schema.names, schema.types, strict=True)),
        dict(zip(spec.schema.names, spec.schema.types, strict=True)),
    )
    issues = [f"ausente: {name}" for name in expected.keys() - actual.keys()]
    issues += [f"inesperada: {name}" for name in actual.keys() - expected.keys()]
    issues += [
        f"tipo: {name}: {actual[name]} != {expected[name]}"
        for name in expected.keys() & actual.keys()
        if actual[name] != expected[name]
    ]
    return sorted(issues)
