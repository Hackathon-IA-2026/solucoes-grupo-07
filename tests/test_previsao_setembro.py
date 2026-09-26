from datetime import date, datetime

import polars as pl

from curtamap.previsao.setembro import read_september, week_start


def _official(path, source, rows):
    pl.DataFrame(
        {
            "id_subsistema": "NE",
            "id_estado": "BA",
            "nom_usina": "U",
            "id_ons": [r[0] for r in rows],
            "din_instante": [r[1] for r in rows],
            "val_geracao": [r[2] for r in rows],
            "val_geracaolimitada": [r[3] for r in rows],
            "val_geracaoreferencia": 30.0,
            "cod_razaorestricao": [r[4] for r in rows],
            "cod_origemrestricao": [r[5] for r in rows],
            "val_geracaonaorealizadaapurada": 0.0,
        }
    ).with_columns(pl.col("din_instante").cast(pl.Datetime("ns"))).write_parquet(
        path / f"{source}_2026_09.parquet"
    )


def test_current_publication_is_normalized_like_the_snapshot(tmp_path):
    _official(
        tmp_path,
        "eolica",
        [
            ("A", datetime(2026, 8, 31, 23, 30), 30.0, None, "", ""),
            ("A", datetime(2026, 9, 1, 12), 30.0, None, "", ""),
            ("A", datetime(2026, 9, 1, 12, 30), 10.0, 10.0, "ENE", "SIS"),
        ],
    )
    _official(tmp_path, "fotovoltaica", [("B", datetime(2026, 9, 2, 12), 5.0, None, "", "")])
    frame = read_september(tmp_path).sort("fonte", "din_instante")
    assert frame.height == 3  # 31/08 fica de fora: agosto vem do snapshot
    assert frame["fonte"].to_list() == ["eolica", "eolica", "fotovoltaica"]
    assert frame["causa"].to_list() == [None, "ENE", None]
    assert frame["rotulo_sem_limite"].to_list() == [False, False, False]
    assert frame["volume_mwmed"].to_list() == [0.0, 20.0, 0.0]
    assert frame.schema["din_instante"] == pl.Datetime("us")


def test_weeks_start_on_monday():
    days = pl.DataFrame({"dia": [date(2026, 9, 1), date(2026, 9, 6), date(2026, 9, 7)]})
    assert days.select(week_start(pl.col("dia")))["dia"].to_list() == [
        date(2026, 8, 31),
        date(2026, 8, 31),
        date(2026, 9, 7),
    ]
