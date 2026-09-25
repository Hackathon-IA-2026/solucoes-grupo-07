# Teste de simplicidade: regra fixada antes dos resultados (25/09/2026)

Estado: **pré-registro**, escrito e commitado antes das runs. Exploratório, fora do protocolo
completo. O teste reservado continua fechado.

## Pergunta (levantada pelo responsável)

Complicamos demais? O ganho do modelo com contexto (cerca de 87 features, árvores de 63
folhas) sobre a regra `historico` pode vir de poucas variáveis. Se um modelo pequeno empatar,
a complexidade não se paga. O §11.2 manda preferir a solução mais simples quando não há
diferença material, e ela também é mais fácil de explicar, manter e colocar em container.

## Variante `s01` (simples)

- **Árvores:** `num_leaves` 15 e `max_depth` 4. O resto da receita é igual: segmentos,
  amostragem, early stopping, calibração, fallback e validação completa.
- **Corte solar**, 8 features:
  - `b_historico_prob_positive`, `horizon`, `tau_hour_sin` e `tau_hour_cos`;
  - `tau_weekend_or_holiday`, `same_hour_1d_positive`, `same_hour_7d_positive` e
    `positive_frequency_7d`;
  - sem categóricas.
  - Referência: `003`.
- **Causa eólica**, 14 features:
  - as probabilidades de causa do `historico` e do `ultimo_valor`;
  - `cause_{rel,cnf,ene}_share_28d` e `last_cause`;
  - `horizon`, `tau_hour_sin`, `tau_hour_cos` e `tau_weekend_or_holiday`;
  - classes balanceadas.
  - Referência: `005`.

## Ordem

V2 e V4 primeiro (`jobs-g.txt`). V1 e V3 só se a variante passar nessas duas.

## Regra de decisão (mesmas linhas, contra a referência da mesma rodada)

**A simples é preferida** se, nas rodadas testadas:

- a perda média na métrica principal (AP no corte, macro-F1 na causa) for ≤ 0,005;
- nenhuma rodada perder mais de 0,01;
- no corte, o Brier não piorar mais de 0,005 em nenhuma rodada.

Se ela **superar** a referência dentro dessas condições, também é preferida.

**Caso contrário**, a complexidade se justifica e fica a referência. Resultado negativo é
válido: nenhum outro conjunto de features será testado para salvar a hipótese.
