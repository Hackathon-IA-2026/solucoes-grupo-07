"""Recomendações de exemplo, até o módulo da Etapa 3 chegar ao `main`.

Servem só para desenhar o painel de ações. São `simulado` no contrato, usam usinas
fictícias (`EXEMPLO-*`) que nunca casam com uma usina real e não seguem nenhuma regra de
recomendação: os números foram escritos à mão. A tela precisa exibir o aviso de exemplo.
"""

from datetime import datetime

import polars as pl

from curtamap.contracts import RECOMMENDATION_SCHEMA, STEP, validate_recommendations

EXAMPLE_PREFIX = "EXEMPLO-"
EXAMPLE_MODEL = "exemplo_interface"
EXAMPLE_ASSUMPTIONS = "exemplo_sem_premissas"

# (fonte, id, início em janelas após t0, duração em janelas, causa, ação, descrição,
#  energia em risco, recuperável, valor R$, CO2 t)
_ROWS = [
    ("eolica", "01", 4, 8, "ENE", "AVALIAR_ARMAZENAMENTO",
     "Exemplo: simular carga de bateria durante a janela e descarga posterior.",
     120.0, 40.0, 12_000.0, 16.0),
    ("fotovoltaica", "02", 22, 6, "CNF", "COORDENAR_OPERACAO",
     "Exemplo: alinhar o centro de operação e deslocar manutenção flexível.",
     45.0, 0.0, None, None),
    ("eolica", "03", 30, 4, None, "VALIDAR_CAUSA",
     "Exemplo: causa indeterminada; confirmar a mensagem do ONS antes de agir.",
     18.0, 0.0, None, None),
]  # fmt: skip


def example_recommendations(t0: datetime) -> pl.DataFrame:
    rows = [
        {
            "fonte": fonte,
            "id_ons": EXAMPLE_PREFIX + suffix,
            "t0": t0,
            "inicio": t0 + start * STEP,
            "fim": t0 + (start + length) * STEP,
            "causa_base": cause,
            "acao_codigo": code,
            "acao_descricao": text,
            "energia_em_risco_mwh": risk,
            "energia_recuperavel_mwh": recoverable,
            "valor_estimado_brl": value,
            "co2_evitado_t": co2,
            "premissas_versao": EXAMPLE_ASSUMPTIONS,
            "tipo_saida": "simulado",
            "modelo_id": EXAMPLE_MODEL,
        }
        for fonte, suffix, start, length, cause, code, text, risk, recoverable, value, co2 in _ROWS
    ]
    return validate_recommendations(pl.DataFrame(rows, schema=RECOMMENDATION_SCHEMA))
