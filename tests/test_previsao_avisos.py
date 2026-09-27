from datetime import date, datetime
from types import SimpleNamespace

import polars as pl

from zelo.contracts import validate_forecast
from zelo.previsao.avisos import build_archive
from zelo.previsao.modelo import DailyForecaster


def _rows(dia: date, ultimo: date, fonte: str, id_ons: str) -> list[dict]:
    return [
        {
            "dia": dia,
            "ultimo_dia": ultimo,
            "idade": (dia - ultimo).days,
            "fonte": fonte,
            "id_ons": id_ons,
            "slot": slot,
            "p_corte": slot / 100,
            "restricao_hist_28d": 0.2,
            "causa_rel_28d": 0.1,
            "causa_cnf_28d": 0.2,
            "causa_ene_28d": 0.7,
            "estado_rel_7d": 0.3,
            "estado_cnf_7d": 0.3,
            "estado_ene_7d": 0.4,
            "origem_sis_28d": 0.8,
            "cobertura_28d": 1.0,
            "hist_28d": 0.5,
            "ref_hist_28d": 10.0 if 12 <= slot < 36 else 0.0,
        }
        for slot in range(48)
    ]


def _forecaster() -> DailyForecaster:
    fonte = SimpleNamespace(threshold=0.3)
    model = SimpleNamespace(model_id="teste", sources={"eolica": fonte, "fotovoltaica": fonte})
    return DailyForecaster(model)


def test_arquivo_emite_um_aviso_por_dia_as_20h_da_vespera_sem_repontuar():
    predictions = pl.DataFrame(
        _rows(date(2026, 9, 2), date(2026, 8, 30), "eolica", "E1")
        + _rows(date(2026, 9, 3), date(2026, 9, 1), "eolica", "E1")
        + _rows(date(2026, 9, 3), date(2026, 9, 1), "fotovoltaica", "S1")
    )
    attributes = pl.DataFrame(
        {"fonte": ["eolica"], "id_ons": ["E1"], "nom_usina": ["Usina Um"],
         "id_estado": ["RN"], "id_subsistema": ["NE"]}
    )  # fmt: skip
    archive = build_archive(predictions, attributes, _forecaster())
    validate_forecast(archive)
    assert archive.height == 3 * 48
    dia3 = archive.filter(pl.col("t0") == datetime(2026, 9, 3))
    assert dia3["emitido_em"].unique().to_list() == [datetime(2026, 9, 2, 20)]
    assert dia3["corte_dados"].unique().to_list() == [datetime(2026, 9, 2)]
    # p_corte idêntico ao avaliado; alerta pelo limiar congelado.
    assert (
        archive.sort("fonte", "id_ons", "t0", "horizonte")["p_corte"].to_list()
        == [s / 100 for s in range(48)] * 3
    )
    assert archive.filter(pl.col("p_corte") >= 0.3)["alerta"].all()
    assert archive["potencial_referencia_mwmed"].max() == 10.0
    assert archive.filter(pl.col("id_ons") == "E1")["nom_usina"].unique().to_list() == ["Usina Um"]
    assert archive.filter(pl.col("id_ons") == "S1")["nom_usina"].null_count() == 48
