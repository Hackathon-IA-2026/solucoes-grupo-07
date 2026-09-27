from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).parents[1] / "src/curtamap/alertas_app.py"


def test_app_missing_artifact_explains_how_to_generate(tmp_path, monkeypatch):
    monkeypatch.setenv("CURTAMAP_ALERTAS_DIR", str(tmp_path))
    app = AppTest.from_file(str(APP)).run(timeout=15)
    assert not app.exception
    assert app.warning
    assert "reprodução" in app.warning[0].value.lower()


def test_app_loads_replay_and_shows_probability_without_volume(tmp_path, monkeypatch):
    import polars as pl
    from test_alertas import sample

    frame = sample().with_columns(
        pl.lit("Parque A").alias("nom_usina"),
        pl.lit("BA").alias("id_estado"),
        pl.lit(2).alias("idade"),
        pl.lit("2026-08-02 20:00").alias("emitido_em"),
        pl.lit("2026-08-02 00:00").alias("corte_dados"),
        pl.lit(0).alias("y_corte"),
        pl.lit(0.2).alias("hist_28d"),
        pl.lit("2026-07-30").alias("treino_ate"),
    )
    frame.write_parquet(tmp_path / "eolica_2026-08-03_2026-08-03.parquet")
    monkeypatch.setenv("CURTAMAP_ALERTAS_DIR", str(tmp_path))
    app = AppTest.from_file(str(APP)).run(timeout=15)
    assert not app.exception
    assert [m.label for m in app.metric] == [
        "Usinas em alerta",
        "Janelas em alerta",
        "Janelas sem previsão",
    ]
    assert app.metric[1].value == "1"
    assert "MWh" not in str([m.label for m in app.metric])
