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

## 2. Resultados do backtest (jan–ago/2026, desenvolvimento)

Médias das 8 dobras mensais, nas mesmas linhas. A tabela completa por mês está em
`metricas_backtest.csv`.

| Célula | Métrica | Modelo | `historico` | Meses vencidos* | Servido |
|---|---|---|---|---|---|
| Corte eólico | AP | **0,788** | 0,740 | 8/8 | modelo |
| Corte solar | AP | **0,813** | 0,747 | 8/8 | modelo |
| Volume solar | WAPE meia-hora | **0,851** | 0,950 | 7/8 | modelo |
| Volume eólico | WAPE meia-hora | 1,083 | 1,214 | 5/8 | `historico` (baseline) |
| Causa eólica | macro-F1 | 0,631 | moda da usina 0,649 | 2/8 | moda da usina (baseline) |
| Causa solar | macro-F1 | 0,504 | moda da usina 0,462 | 5/8 | moda da usina (baseline) |

\* Contra o melhor baseline **de cada mês**, como a regra foi codificada antes dos resultados.
Com o `historico` como baseline fixo, o volume eólico venceria em 6/8 meses, com margens de
0,002 a 0,07 fora de fevereiro, o que é um empate técnico. A decisão não mudou. As outras
cinco células são iguais nas duas leituras.

**Outras medidas:**

- **Brier:** 0,123 contra 0,128 na eólica e 0,076 contra 0,083 na solar. O modelo fica
  ligeiramente pior que o `historico` na eólica em março e junho.
- **Alerta:** com o limiar F1-ótimo escolhido em jan–abr (0,30 na eólica e 0,32 na solar),
  mai–ago (fora da amostra) teve recall de 0,85 e precisão de 0,72 na eólica, e recall de 0,90
  e precisão de 0,73 na solar.
- **WAPE diário** por usina × dia, a métrica de planejamento: 0,853 contra 0,981 na eólica e
  0,701 contra 0,808 na solar.
- **Intervalo p10–p90** nas meias-horas com corte: cobertura de 0,72 na eólica e 0,76 na solar,
  para 80% nominais, ou seja, levemente estreito. Contando as linhas sem corte, a cobertura
  fica entre 0,87 e 0,97, número inflado e sem valor informativo.
- **Preditor zero:** tem WAPE 1,0 por construção e vence **todos** os preditores da eólica em
  fev, mar, abr e jun. O MAE e o WAPE premiam a mediana, que é zero num alvo inflado de zeros,
  enquanto a recomendação precisa da média (energia esperada). Por isso o volume eólico não
  foi otimizado para WAPE.

**Tentativa de causa** (hipótese registrada antes, detalhes no diário):

- na eólica, nem o HGB só com as participações da usina empata com a moda (0,638 contra
  0,649);
- na solar, uma variante sem peso venceria em 6/8 meses (0,483 contra 0,462), mas foi a melhor
  de 4 variantes nas mesmas dobras, por isso não foi adotada.

## 3. Validação independente: setembro de 2026

- **Protocolo:** o código da receita está no commit `e89be0f` (registrado no manifesto como
  `commit_receita`). O congelamento documental, com o manifesto `modelo-congelado.json`
  (SHA-256 do artefato, limiares e composição), está no commit `7b64b46`.
- **Dados:** baixados depois do congelamento, com o manifesto `setembro/manifesto.json`
  (publicação de 25/09, dias-alvo de 01 a 24/09).
- **Ordem:** as previsões sem rótulo foram gravadas antes da avaliação, com o hash em
  `setembro/previsoes.json`.
- **Histórico usado como feature:** o snapshot até 31/08 mais os dias de setembro já
  liberados em cada emissão.

Resultado do mês (tabela semanal em `setembro/metricas_setembro.csv`):

| Célula | Modelo | `historico` | Outros baselines | Semanas vencidas |
|---|---|---|---|---|
| Corte eólico, AP | **0,921** | 0,899 | mesmo slot 0,766; último valor 0,629 | 3/4 (a perdida por 0,002) |
| Corte solar, AP | **0,907** | 0,867 | mesmo slot 0,658 | 4/4 |
| Volume solar, WAPE | **0,607** | 0,652 | mesmo slot 0,799 | 3/4 |
| Volume solar, WAPE diário | **0,517** | 0,565 | — | 3/4 |
| Volume eólico (servido `historico`), WAPE | modelo 0,738 | **0,754 servido** | mesmo slot 0,838 | — |
| Causa eólica, macro-F1 (servida a moda) | modelo 0,765 | moda **0,839** | estado 0,523 | moda 4/4 |
| Causa solar, macro-F1 (servida a moda) | modelo 0,447 | moda **0,501** | estado 0,321 | moda 2/4 (vence no mês) |

- **Alerta:** com o limiar congelado, o recall foi de 0,94 na eólica e 0,90 na solar, com
  precisão de 0,82 e 0,81.
- **Brier:** 0,095 contra 0,095 na eólica e 0,068 contra 0,073 na solar.

**Leitura:** as escolhas congeladas se confirmaram fora da amostra.

- O modelo de ocorrência mantém a vantagem sobre o `historico`.
- O volume solar do modelo vence.
- Nas duas células de causa, servir a moda da usina foi a decisão certa no mês. Na solar, ela
  vence só 2 de 4 semanas.
- No volume eólico, o modelo teria ficado levemente à frente em setembro (0,738 contra
  0,754), coerente com o "empate técnico" do backtest.

São só 24 dias, então nenhum número isolado é conclusivo.

## 4. Problema simples ou complexo?

**Estrutura simples e sinal difícil.**

- O perfil horário vem do histórico da usina, e o corte é regional e simultâneo.
- O oráculo "fração do estado cortada naquele slot" daria AP de 0,94. O "histórico × nível
  estadual realizado do dia" daria de 0,88 a 0,91.
- A parte difícil é o **nível do dia-alvo**, que depende de vento, sol e carga daqui a 2–4
  dias.
- A correlação do nível estadual entre o último dia liberado e o alvo é só 0,57 na eólica e
  0,28 na solar.
- **Interpretação, não medida:** 14 features e um HGB sem busca de hiperparâmetros parecem
  capturar a maior parte do que é previsível com os dados liberados. O que foi medido é mais
  estreito: o clima já liberado não acrescenta nada, e o clima do dia-alvo acrescenta
  (seção 6). O caminho do ganho é a previsão meteorológica, não mais complexidade de pipeline.

## 5. Limitações

- Maio a agosto de 2026 foi visto pela receita anterior e aqui é desenvolvimento. Só
  setembro é teste, com 24 dias.
- **Não há previsão meteorológica.** O nível do dia é estimado pela persistência regional e
  pelo calendário.
- `p_restricao` e a origem são baselines. A causa servida é baseline. O volume eólico servido
  é baseline.
- O intervalo p10–p90 é levemente estreito nas meias-horas com corte. No volume eólico servido
  pelo `historico`, a banda é alargada para conter a média servida (ajuste de serviço
  pós-congelamento, commit `04113b8`, que não altera as métricas).
- O modelo é treinado em uma janela de 365 dias sem recalibração. A prevalência de setembro
  foi parecida com a de agosto (0,49 contra 0,49 na eólica e 0,30 contra 0,28 na solar), então
  setembro não testou uma mudança de regime.
- Usinas novas só recebem previsão depois que o primeiro dia delas é liberado.
- A disponibilidade simula a publicação do ONS (19h30 do dia útil seguinte) com calendário
  conservador. Não é a escala real do ONS.

## 6. H5: quanto valeria uma previsão meteorológica? (oráculo, fora do produto)

- **Experimento:** o vento e a irradiância **verificados** (`*_detail`), agregados por estado ×
  slot, entram como se fossem uma previsão perfeita para o dia-alvo.
- **Rótulo:** é um **oráculo**. Mede um teto e **nunca** é feature D+1 do produto.
- **Execução:** dobras de mai–ago/2026 com o mesmo protocolo do backtest, só ocorrência e
  volume. Script em `scripts/experimentos/oraculo_h5.py`; números em `oraculo_h5.csv`.

| Variante (média mai–ago) | AP eólica | WAPE eólica | WAPE diário eólica | AP solar | WAPE solar | WAPE diário solar |
|---|---|---|---|---|---|---|
| Produto (14/19 features) | 0,826 | 0,905 | 0,711 | 0,860 | 0,728 | 0,611 |
| + clima médio do estado em L (legítimo) | 0,829 | 0,914 | 0,718 | 0,863 | 0,728 | 0,610 |
| + clima do estado no dia-alvo (oráculo) | **0,872** | **0,723** | **0,540** | 0,869 | 0,692 | 0,579 |

**Leitura:**

- O clima já observado (em L) não ajuda, porque não persiste por 2–4 dias. Por isso não
  entra no produto.
- Com o clima do próprio dia-alvo, a eólica ganha +0,05 de AP e reduz ~24% do erro diário de
  volume, justamente na célula em que o modelo não bate o `historico`.
- Na solar, o ganho é pequeno: o nível solar parece mais ligado a carga e calendário do que à
  irradiância média do estado. Isso é uma interpretação, não algo medido.
- **Para o pitch:** "com um feed de previsão de vento, o erro de volume eólico do dia seguinte
  cairia até ~24%". É um **teto**: previsões reais têm erro, e o ganho real será menor.

## 7. v3: faixas de volume, sinal de restrição e causa (desenvolvimento, jan–ago/2026)

Protocolo pré-registrado no diário (8/n); resultados em 9/n a 12/n; arquivos em `v3/`.

| Frente | Pergunta | Resultado pela regra (média e ≥ 6/8 meses acima do ruído) |
|---|---|---|
| A: faixas relativas de volume | P(fração cortada > k) melhor que a frequência da usina? | **Adotada** em k₀ (duas fontes) e em k₁/k₂ da **solar**, nos dois níveis. AP de "severo" diário na solar: 0,426 contra 0,336. Na eólica, k₁/k₂ ficam com o `historico` |
| B: regime nacional e grupo de restrição | O AP de ocorrência melhora? | Não adotada: ganha em meses estáveis, perde na virada de fevereiro (−0,06 na eólica) |
| C: causa | Um modelo vence a moda da usina nas trocas de regime? | Não adotada: no máximo 5/8 meses, sem ganho de acurácia; a causa troca em só 16–17% dos casos |

- **Artefato:** `diario_hgb_v3_2026-08-30`, com manifesto em `modelo-congelado-v3.json`.
  Ocorrência, volume e causa são os da v1; a v3 acrescenta as colunas `p_faixa_*`.
- **Contradições registradas:**
  - o `id_ons` do tm já é o conjunto, então não há agrupamento de conjunto acima dele;
  - `dsc_restricao` só existe desde 09/2025.
- **Confirmação:** depende de dias ainda não vistos. Setembro já foi gasto com a v1.
