# Estado sistêmico recente: regra fixada antes dos resultados (25/09/2026)

Estado: **pré-registro**, commitado antes das runs. Exploratório, fora do protocolo completo.
O teste reservado continua fechado.

## Pergunta

O relatório (§3.3) levantou a hipótese de que o corte eólico é mais sistêmico e de que um
indicador do estado recente do subsistema ajudaria. Esse indicador também pode informar o
nível do regime (V2).

## Fato medido antes de definir a feature (junho/2025)

- **Idade da informação:** a mais nova disponível em `t0` tem cerca de 39 h
  (`history_age_hours`).
- **Colunas de 24 h** (`positive_frequency_24h`): 87% nulas. `same_hour_1d_positive` é 99%
  nula.
- **`last_positive`:** sempre falso na solar, porque o último valor liberado é noturno. Na
  eólica, a média é 0,16.
- **`positive_frequency_7d`:** sem nulos nas duas fontes.

## Variante `sys`

É a referência `003` mais duas features agregadas por fonte + subsistema + `t0`, com todas as
usinas e uma linha por usina:

- `sys_last_positive_share`: fração de usinas com `last_positive`;
- `sys_positive_frequency_7d_mean`: média de `positive_frequency_7d`.

Código: `curtamap.contexto.systemic_state` (commit anterior a este) e
`treinar_contexto.py --systemic`.

## Ordem

- Corte solar V2 e V4 (`rapido-fv-v{2,4}-corte-sys`).
- Corte eólico V2 e V4 (`rapido-eol-v{2,4}-corte-sys`).
- V1 e V3 da mesma fonte só se a variante passar nas duas rodadas.

## Regra de decisão (idêntica à do `q12`/`j6`; contra a `003` da mesma fonte e rodada)

**Adota a variante** somente se:

- o ganho médio de AP for ≥ +0,005;
- nenhuma rodada piorar mais de 0,01 em AP;
- o Brier não piorar mais de 0,005 em nenhuma rodada.

**Também adota** se o Brier da V2 cair pelo menos 0,02 com AP não pior que −0,005 em todas as
rodadas testadas.

**Caso contrário**, fica a `003`. Nenhuma outra definição de feature sistêmica será testada
para salvar a hipótese.
