"""Validação estrutural de premissas; não certifica a fonte nem a adequação ao ativo."""

from datetime import date
from math import isfinite
from typing import Any
from urllib.parse import urlparse

SCENARIOS = ("baixo", "base", "alto")


def nonnegative(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label}: numero finito nao negativo obrigatorio")
    if not isfinite(value) or value < 0:
        raise ValueError(f"{label}: numero finito nao negativo obrigatorio")
    return float(value)


def _text(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: texto obrigatorio")


def _date(value: Any) -> None:
    _text(value, "consultado_em")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("consultado_em: data ISO invalida") from exc
    if parsed.isoformat() != value or parsed > date.today():
        raise ValueError("consultado_em: data invalida ou futura")


def _keys(value: Any, required: set[str], optional: set[str], label: str) -> None:
    if not isinstance(value, dict) or required - value.keys() or value.keys() - required - optional:
        raise ValueError(f"{label}: schema incompleto ou campos desconhecidos")


def _parameter(item: Any, unit: str, label: str) -> None:
    _keys(item, {"valor", "unidade", "fonte", "url", "consultado_em"}, {"lacuna"}, label)
    if item["unidade"] != unit:
        raise ValueError(f"{label}: unidade deve ser {unit}")
    _text(item["fonte"], "fonte")
    _text(item["url"], "url")
    url = urlparse(item["url"])
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or any(c.isspace() for c in item["url"])
    ):
        raise ValueError(f"{label}: URL HTTPS invalida")
    _date(item["consultado_em"])
    if item["valor"] is None:
        _text(item.get("lacuna"), "lacuna para valor nulo")
    else:
        value = nonnegative(item["valor"], label)
        if unit == "fracao" and value > 1:
            raise ValueError(f"{label}: eficiencia fora de [0, 1]")


def validate_assumptions(assumptions: Any) -> dict[str, Any]:
    _keys(
        assumptions,
        {"versao", "consultado_em", "aviso", "cenarios"},
        {"base_capacidade"},
        "premissas",
    )
    _text(assumptions["versao"], "versao")
    _text(assumptions["aviso"], "aviso")
    _date(assumptions["consultado_em"])
    if assumptions.get("base_capacidade", "entrada") not in {"entrada", "saida_util"}:
        raise ValueError("base_capacidade invalida")
    scenarios = assumptions["cenarios"]
    _keys(scenarios, set(SCENARIOS), set(), "cenarios")
    for name, scenario in scenarios.items():
        _keys(
            scenario,
            {"preco_energia_brl_mwh", "fator_emissao_tco2_mwh", "armazenamento"},
            set(),
            name,
        )
        _parameter(scenario["preco_energia_brl_mwh"], "BRL/MWh", "preco_energia_brl_mwh")
        _parameter(scenario["fator_emissao_tco2_mwh"], "tCO2/MWh", "fator_emissao_tco2_mwh")
        storage = scenario["armazenamento"]
        _keys(storage, {"potencia_mw", "capacidade_mwh", "eficiencia"}, set(), "armazenamento")
        for key, unit in [
            ("potencia_mw", "MW"),
            ("capacidade_mwh", "MWh"),
            ("eficiencia", "fracao"),
        ]:
            _parameter(storage[key], unit, key)
    return assumptions
