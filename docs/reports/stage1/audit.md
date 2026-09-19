# Auditoria dos cinco Parquet

Execução: 2026-09-19T20:41:22.851358+00:00.

Fonte: ONS, snapshot tratado fornecido pelo hackathon. SHA-256 e schemas no JSON.
Nulos condicionais usam limite não nulo. Detail não possui limite (N/A).
Lacunas são internas à vida observada da entidade; não provam falha de coleta.
Quantis são aproximados. Extremos e negativos são evidências para investigação,
não regras automáticas de remoção. Fuso horário não consta nos Parquet.

| Base | Linhas | Entidades | Início | Fim | Duplicadas excedentes | Lacunas | Estado |
|---|---:|---:|---|---|---:|---:|---|
| eolica | 7951920 | 180 | 2023-10-01 00:00:00 | 2026-08-31 23:30:00 | 0 | 0 | issues |
| fotovoltaica | 2854800 | 87 | 2024-04-01 00:00:00 | 2026-08-31 23:30:00 | 0 | 0 | issues |
| integrada | 9441168 | 265 | 2024-04-01 00:00:00 | 2026-08-31 23:30:00 | 0 | 0 | issues |
| eolica_detail | 63429221 | 1060 | 2023-01-01 00:00:00 | 2026-08-31 23:30:00 | 385 | 819 | issues |
| fotovoltaica_detail | 19061960 | 560 | 2024-04-01 00:00:00 | 2026-08-31 23:30:00 | 56 | 43 | issues |

## Comparações entre bases

```json
{
  "integrated": {
    "main_minus_integrated_by_month": [
      {
        "fonte": "eolica",
        "period": "2023-10",
        "rows": 227664
      },
      {
        "fonte": "eolica",
        "period": "2023-11",
        "rows": 220320
      },
      {
        "fonte": "eolica",
        "period": "2023-12",
        "rows": 230016
      },
      {
        "fonte": "eolica",
        "period": "2024-01",
        "rows": 231984
      },
      {
        "fonte": "eolica",
        "period": "2024-02",
        "rows": 219888
      },
      {
        "fonte": "eolica",
        "period": "2024-03",
        "rows": 235680
      }
    ],
    "main_minus_integrated": 1365552,
    "integrated_minus_main_by_month": [],
    "integrated_minus_main": 0
  },
  "eolica_detail": {
    "method": "interseção direta apenas de ids individuais; conjuntos não são usinas",
    "individual_overlap": {
      "main_individual_ids": 11,
      "matched_ids": 11
    },
    "individual_values": {
      "join_rows": 562848,
      "matched_intervals": 562848,
      "duplicated_join_rows": 0,
      "generation_different": 0,
      "generation_missing": 0,
      "max_abs_difference_mw": 0.0
    },
    "detail_membership": [
      {
        "fonte": "eolica",
        "individuals": 1060,
        "group_names": 180,
        "rows_without_group": 706992
      }
    ],
    "limitation": "Snapshot detail não tem id_ons_conjuntousina. Nome do conjunto não é chave validada; sem rateio ou soma automática entre níveis."
  },
  "fotovoltaica_detail": {
    "method": "interseção direta apenas de ids individuais; conjuntos não são usinas",
    "individual_overlap": {
      "main_individual_ids": 4,
      "matched_ids": 4
    },
    "individual_values": {
      "join_rows": 169536,
      "matched_intervals": 169536,
      "duplicated_join_rows": 0,
      "generation_different": 0,
      "generation_missing": 0,
      "max_abs_difference_mw": 0.0
    },
    "detail_membership": [
      {
        "fonte": "fotovoltaica",
        "individuals": 560,
        "group_names": 97,
        "rows_without_group": 169536
      }
    ],
    "limitation": "Snapshot detail não tem id_ons_conjuntousina. Nome do conjunto não é chave validada; sem rateio ou soma automática entre níveis."
  }
}
```

## Como interpretar

`audit.json` contém nulos por campo/mês (denominadores explícitos), domínios,
negativos/não finitos/mínimos/máximos/quantis, cobertura por fonte, entidade,
UF, subsistema e mês, schema e divergências de calendário auxiliar.
Status `issues` exige investigação e não significa que todas as linhas são inválidas.
Nenhum dado é imputado ou corrigido pela auditoria. A base integrada é comparada
como multiconjunto, em todas as colunas, com a união das principais.
