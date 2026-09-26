# Nova abordagem da Etapa 2: previsão diária do dia seguinte

Relatório da modelagem refeita do zero em 26/09/2026. Os números vêm de
`metricas_backtest.csv`, `decisao_celulas.csv` e `limiares.json` (nesta pasta), gerados por
`uv run python -m curtamap.previsao.relatorio data/interim/previsao docs/reports/nova-abordagem`
sobre o backtest `uv run python -m curtamap.previsao.avaliacao 2026-01 2026-08`.

## 1. Desenho

**Unidade.** Uma linha por `fonte + id_ons` × dia-alvo × meia-hora (48 slots), emitida
**uma vez por dia**, às 20h da véspera. No contrato, `t0` = 00h do dia-alvo, `horizonte`
1..48 e `emitido_em` = 20h da véspera. A Etapa 2 anterior expandia emissão × horizonte
(48 emissões por dia com a mesma informação) e chegava a mais de 100 M de linhas. Aqui são
~4,4 M de linhas de treino por ano, e o backtest roda num notebook de 8 GB.

**Informação disponível.** Os dados de um dia saem às 19h30 do dia útil seguinte, com
feriados e pontos facultativos, inclusive os do Rio (`configs/calendario-2023-2026.json`).
Na emissão das 20h, o último dia liberado L fica 2 dias antes do alvo em 67% dos dias e até
7 dias perto de feriados. Todas as features são janelas que **terminam em L**, e a idade
`T − L` é uma feature.

**Features (14 para ocorrência, 19 para volume, 13 para causa):**

| Grupo | Features | Significado |
|---|---|---|
| Perfil da usina no slot | `hist_7d`, `hist_28d`, `hist_91d`, `ultimo_slot` | Em que horas esta usina costuma ser cortada |
| Nível recente | `usina_nivel_ultimo`, `usina_nivel_7d`, `estado_nivel_ultimo`, `estado_nivel_7d`, `estado_nivel_28d` | O regime regional atual, já que o corte é simultâneo no estado |
| Regime de causa | `estado_ene_7d`; para causa, `causa_*_28d` da usina e `estado_*_7d` | Excedente energético (ENE) contra restrição elétrica (CNF/REL) |
| Calendário do alvo | `dia_semana`, `feriado` (nacional), `idade`, `slot` | Carga baixa em fins de semana e feriados; defasagem da informação |
| Escala de volume | `vol_hist_7d`, `vol_hist_28d`, `vol_ultimo_slot`, `ref_hist_28d`, `usina_vol_ultimo` | Tamanho da usina e do corte típico |

Não há `mês` nem `dia do ano`. Com menos de dois anos de solar, eles ensinariam tendência
como estação.

**Modelos.** `HistGradientBoosting` do scikit-learn, um por fonte, todos com os mesmos
hiperparâmetros fixos (sem busca):

- ocorrência: classificador binário;
- volume esperado: regressão Poisson direta;
- volume condicional: Poisson nas meias-horas com corte;
- p10/p90: regressão quantílica;
- causa: multiclasse REL/CNF/ENE com peso balanceado, treinada só com as ordens de causa
  conhecida.

`p_restricao` e a origem são baselines declarados.

**Validação.** Dobras mensais de jan a ago/2026, com origem expandindo. Cada mês M é treinado
com os rótulos até o último dia liberado na emissão da véspera do dia 1º de M, usando uma
janela de 365 dias. Os baselines são avaliados nas mesmas linhas:

- `historico`: frequência ou volume médio da usina no slot em 28 d;
- `mesmo_slot_ultimo_dia`: o mesmo slot em L;
- `ultimo_valor`: a última meia-hora de L;
- `zero`: referência só para o volume.

O "mesmo horário do dia anterior" não é possível na emissão das 20h, porque T − 1 nunca está
liberado. A cobertura dele é 0%. Maio–agosto/2026 já foi visto pela receita anterior e aqui
conta como desenvolvimento.

**Regra de decisão, registrada antes dos resultados.** O modelo substitui o melhor baseline
de uma célula se vencer na média **e** em pelo menos 6 de 8 meses.

<!-- resultados abaixo -->
