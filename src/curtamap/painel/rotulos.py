"""Rótulos em português para códigos do contrato e da base ONS."""

CAUSE_LABELS = {
    "REL": "REL · indisponibilidade externa",
    "CNF": "CNF · confiabilidade elétrica",
    "ENE": "ENE · excedente energético",
    "PAR": "PAR · parecer de acesso",
    "DESCONHECIDA": "Causa não informada pelo ONS",
}
SOURCE_LABELS = {"eolica": "Eólica", "fotovoltaica": "Solar"}
OUTPUT_KIND_LABELS = {
    "baseline": "Preditor provisório (baseline)",
    "modelo": "Modelo treinado",
    "simulado": "Exemplo simulado",
}
COMPONENT_LABELS = {
    "modelo": "modelo treinado",
    "historico": "média da usina no horário em 28 dias (baseline)",
    "baseline_historico_28d": "média da usina no horário em 28 dias (baseline)",
    "baseline_usina_28d": "participação das causas na usina em 28 dias (baseline)",
    "baseline_estado_7d": "participação das causas no estado em 7 dias (baseline)",
}
_REASONS = {
    "sem_observacao_valida_no_horario_28d": (
        "sem observação válida neste horário nos 28 dias anteriores ao corte de dados"
    ),
    "sem_ordem_reconhecida_no_horario_28d": (
        "sem ordem de limitação com causa reconhecida neste horário nos últimos 28 dias"
    ),
}


def describe_reason(code: str | None) -> str:
    """Texto para um motivo de ausência; códigos novos aparecem como vieram."""
    if code is None:
        return ""
    return _REASONS.get(code, code)


def cause_label(code: str | None) -> str:
    return CAUSE_LABELS.get(code, code) if code else "indeterminada"


def format_number(value: float, decimals: int = 1) -> str:
    """Número no padrão brasileiro: milhar com ponto e decimal com vírgula."""
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def format_mwh(value: float) -> str:
    return f"{format_number(value)} MWh"


def plural(count: int, singular: str, plural_form: str) -> str:
    return f"{count} {singular if count == 1 else plural_form}"
