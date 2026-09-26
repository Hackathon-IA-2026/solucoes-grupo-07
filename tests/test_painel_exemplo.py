from datetime import datetime

import polars as pl

from curtamap.contracts import RECOMMENDATION_SCHEMA, validate_recommendations
from curtamap.painel.exemplo import EXAMPLE_PREFIX, example_recommendations
from curtamap.painel.rotulos import CAUSE_LABELS, describe_reason

T0 = datetime(2026, 8, 20)


def test_example_recommendations_pass_the_contract_and_are_marked_simulated() -> None:
    example = example_recommendations(T0)

    assert example.schema == RECOMMENDATION_SCHEMA
    validate_recommendations(example)
    assert example["tipo_saida"].unique().to_list() == ["simulado"]
    assert (example["t0"] == T0).all()
    assert (example["inicio"] >= T0).all()


def test_example_ids_can_never_match_a_real_plant() -> None:
    example = example_recommendations(T0)

    assert example["id_ons"].str.starts_with(EXAMPLE_PREFIX).all()
    assert example.filter(pl.col("causa_base").is_null()).height >= 1


def test_labels_cover_every_cause_and_unknown_reasons_fall_back() -> None:
    assert set(CAUSE_LABELS) >= {"REL", "CNF", "ENE", "PAR", "DESCONHECIDA"}
    assert "28 dias" in describe_reason("sem_observacao_valida_no_horario_28d")
    assert describe_reason("codigo_novo") == "codigo_novo"
    assert describe_reason(None) == ""
