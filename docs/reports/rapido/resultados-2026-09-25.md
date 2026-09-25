# Treino rápido exploratório — resultados da madrugada de 25/09/2026

Estado: **exploratório, fora do protocolo completo** (sem busca de configurações, sem família
linear, rodadas parciais em algumas tarefas). Nada aqui aprova um modelo pelo §11 nem libera o
teste reservado, que continua fechado. Os resultados completos de cada run estão em
`experiments/stage2b/experimentos/rapido-*/resultado.json`. Para a tabela atualizada, rode
`uv run python scripts/rapido/resumir.py`.

## 1. Por que este treino existe

A Etapa 2C (`docs/reports/stage2c/decision.md`) mostrou que os modelos da 2B receberam só 12
das cerca de 50 features dos datasets e perderam para o baseline `historico`: a frequência e o
volume recentes da própria usina naquele horário. Com o evento começando no fim de semana, a
decisão foi treinar um modelo focado, que parte do baseline e aprende a corrigi-lo, em vez de
refazer a campanha inteira.

## 2. Desenho

- **Script e código:**
  - script `scripts/rapido/treinar_contexto.py`;
  - código reutilizável em `src/curtamap/contexto.py`, com testes em
    `tests/test_contexto.py`.
- **Modelo:** LightGBM com as features do §8 que já existem nos datasets (hora do dia, mesmo
  horário 1/2/3/7 dias antes, últimos valores, frequências e volumes 24h/7d/28d, composição de
  causas, agregados por UF e subsistema, episódio e idade). Recebe também **as saídas dos
  quatro baselines como features**, auditadas sem vazamento na 2C, e categorias nativas.
- **Mantido da 2B:**
  - segmentos temporais initial, tuning, refit e calibração;
  - disponibilidade dos rótulos;
  - amostragem `t0_sistematico_diario_v1` com semente 42;
  - early stopping no tuning;
  - calibração sigmoide e limiar F2 no trecho de calibração;
  - fallback `historico` para entidades sem histórico elegível;
  - validação **completa** da rodada.
- **Comparação:** sempre com os baselines **nas mesmas linhas**. O `historico` reproduz
  exatamente os números da 2B, o que confere a avaliação.
- **Variantes:**
  - `001`: todas as features;
  - `002`: `001` + offset (o modelo parte do logit do `historico`);
  - `003`: `001` sem mês e dia do ano;
  - `004`: `003` + offset;
  - `005`: causa com classes balanceadas;
  - `q12`: 12/48 emissões por dia no treino;
  - `j6`: treino só nos últimos 6 meses.
- **Volume** (`volume_total`): Tweedie sobre todos os volumes válidos, com offset
  `log(volume_expected do historico)`. A previsão é o baseline × a correção aprendida.

## 3. Resultados

### 3.1 Corte positivo, solar (AP; modelo − `historico` nas mesmas linhas)

| Variante | V1 | V2 | V3 | V4 | Média | Rodadas melhores | Brier pior que o baseline em |
|---|---|---|---|---|---|---|---|
| 001 | +0,138 | +0,022 | −0,007 | +0,071 | +0,056 | 3/4 | 4 rodadas |
| 002 | +0,117 | +0,016 | −0,008 | −0,035 | +0,022 | 2/4 | V1, V2, V4 |
| **003 (escolhida)** | **+0,168** | **+0,011** | **+0,006** | **+0,064** | **+0,062** | **4/4** | **só V2** (0,162 contra 0,077) |
| 004 | +0,093 | +0,022 | +0,007 | +0,055 | +0,044 | 4/4 | só V2 (0,123 contra 0,077) |

- **AP absoluto da 003:** 0,596 / 0,846 / 0,857 / 0,775, contra 0,429 / 0,835 / 0,851 / 0,711
  do `historico`.
- **Incerteza semanal:** IC 95% da diferença semanal de AP na V4 de [+0,043, +0,107], com 16 de
  18 semanas melhores; na V1, de [+0,056, +0,206].
- **Critérios do §11 para AP:** a 003 passa todos (ganho médio ≥ 0,02, 4/4 rodadas melhores,
  nenhuma piora maior que 0,02). **Falha a proteção de Brier na V2.**

### 3.2 Testes de quantidade e janela (regra fixada antes; referência 003)

| Teste | V2 | V4 | Decisão |
|---|---|---|---|
| `q12`: 1/4 dos dados (12/48) | +0,0014 de AP; Brier ≈ igual; pico 19 GiB | −0,0001; pico 25 GiB | **Reprovado** (ganho médio +0,0007 < +0,005). Fica 4/48. |
| `j6`: só os últimos 6 meses | −0,0121 de AP; Brier pior | −0,026 de AP; Brier pior | **Reprovado** (piora > 0,01). Fica o histórico completo. |

**Interpretação:** triplicar os dados não muda nada, e cortar o histórico piora. **A quantidade
de dados não é o gargalo**, e treinar com o dataset inteiro (que nem cabe nos 32 GB) não
traria ganho relevante.

### 3.3 Corte positivo, eólica (V4; 2/48)

| Variante | AP (modelo / `historico`) | Diferença | Brier | Árvores | Pico |
|---|---|---|---|---|---|
| 003 | 0,713 / 0,705 | +0,008 | 0,132 / 0,133 | 8 | 21 GiB |
| 004 (offset) | 0,710 / 0,705 | +0,005 | 0,128 / 0,133 | 46 | 24 GiB |

**V1–V4 da variante 003 (fila R):**

| Rodada | AP (modelo / `historico`) | Diferença | Brier (modelo / `historico`) | IC semanal |
|---|---|---|---|---|
| V1 | 0,485 / 0,385 | +0,100 | 0,138 / 0,151 | [+0,061, +0,206] |
| V2 | 0,780 / 0,782 | −0,001 | **0,213 / 0,144** | [−0,018, +0,032] |
| V3 | 0,871 / 0,887 | −0,015 | 0,129 / 0,116 | [−0,033, −0,003] |
| V4 | 0,713 / 0,705 | +0,008 | 0,132 / 0,133 | [−0,008, +0,139] |
| **Média** | | **+0,023** | | |

- **§11:** a média passa de +0,02, mas o modelo vence só em **2 de 4 rodadas**, e o Brier piora
  na V2 e na V3. **Não aprova.**
- **Na eólica, o baseline continua preferível.** O ganho do modelo se concentra na V1
  (jan–abr/2025).
- **Interpretação (hipótese):** o corte eólico é mais sistêmico, e a regra histórica já captura
  a maior parte do sinal. A feature de estado sistêmico recente do subsistema, não
  implementada, seria o próximo candidato.

### 3.4 Volume total, solar (MAE em MWmed; Tweedie + offset)

| Rodada | Modelo | `historico` | Redução | WAPE (modelo / `historico`) | Viés |
|---|---|---|---|---|---|
| V1 | 13,04 | 15,44 | −15,6% | 1,004 / 1,189 | −6,53 |
| V2 | 17,27 | 15,13 | **+14,1% (piora)** | 0,791 / 0,693 | −14,64 |
| V3 | 14,79 | 16,09 | −8,1% | 0,684 / 0,744 | −3,66 |
| V4 | 12,16 | 13,59 | −10,5% | 0,878 / 0,981 | −1,23 |
| **Média** | **14,32** | **15,06** | **−4,97%** | 0,839 / 0,902 | |

- **§11, completo:**
  - vence em 3 de 4 rodadas, com WAPE médio melhor;
  - fica **por um fio abaixo da margem de 5%**;
  - a V2 dispara a proteção de piora acima de 10%;
  - portanto, **não aprovaria**. É um ganho real, mas modesto e concentrado fora dos saltos de
    regime.
- **V2:** repete o padrão do corte. Mesmo partindo do baseline, o modelo aplica uma correção para
  baixo, aprendida antes do salto de maio–agosto de 2025.
- **§11:** a V2 dispara a proteção de piora acima de 10% em uma rodada. O ganho médio pode
  existir, mas a adoção automática fica bloqueada. A proposta de recalibração periódica (§4,
  item 3) também valeria para o volume.

- **Tentativa descartada:** o pipeline `P(corte) × volume condicional` com LightGBM Gamma
  (`rapido-fv-v4-vol-003`) teve MAE de 37,8 contra 13,6. O Gamma produziu previsões enormes em
  algumas linhas.
- **Tentativa anterior com categóricas nativas:** falhou com um erro interno do LightGBM
  (`best_split_info.left_count > 0`); por isso o volume usa `--no-categorical`.

### 3.4b Volume total, eólica (MAE em MWmed; comparador `mesmo_horario_dia_anterior`)

| Rodada | Modelo | Comparador | Variação | WAPE (modelo / comparador) | Viés |
|---|---|---|---|---|---|
| V1 | 11,57 | 13,63 | −15,1% | 1,133 / 1,337 | −6,38 |
| V2 | 17,23 | 16,72 | +3,0% | 0,886 / 0,860 | −12,93 |
| V3 | 22,20 | 20,09 | **+10,5%** | 0,786 / 0,712 | −13,96 |
| V4 | 12,51 | 13,01 | −3,8% | 1,065 / 1,107 | −1,07 |
| **Média** | **15,88** | **15,86** | **+0,1%** | | |

- **§11:** é empate na média, com 2 de 4 rodadas melhores, e a V3 dispara a proteção de piora
  acima de 10%. **Não aprova.**
- **Na eólica, o baseline continua preferível também no volume.**
- **Padrão:** o viés negativo cresce em V2 e V3, justamente os períodos de alta do corte.

### 3.5 Causa, solar V4 (macro-F1, mesmas linhas)

| Variante | Modelo | `ultimo_valor` | `historico` | Recall de REL |
|---|---|---|---|---|
| 003 | 0,455 | 0,502 | 0,434 | 0,023 |
| 005 (balanceada) | **0,494** | 0,502 | 0,434 | 0,158 |

O balanceamento ajuda, mas ainda **não supera** o `ultimo_valor` na V4.

**Solar V1–V4, variante 005** (comparador `ultimo_valor`, conforme a 2C):

| Rodada | Modelo | `ultimo_valor` | `historico` | Diferença | Recall de REL |
|---|---|---|---|---|---|
| V1 | 0,436 | 0,520 | 0,437 | −0,084 | 0,057 |
| V2 | 0,487 | 0,401 | 0,511 | +0,086 | 0,135 |
| V3 | 0,532 | 0,492 | 0,522 | +0,040 | 0,176 |
| V4 | 0,494 | 0,502 | 0,434 | −0,008 | 0,158 |
| **Média** | **0,487** | **0,479** | | **+0,009** | |

**§11:** ganho médio abaixo de 0,02, 2 de 4 rodadas melhores e piora acima de 0,02 na V1.
**Não aprova**, e o resultado é instável: **na causa solar, o baseline continua preferível.**

**Eólica V4, variante 005:**
- macro-F1 de **0,638**, contra 0,517 do `historico` e 0,511 do `ultimo_valor` (+0,121);
- recall de REL de 0,436;
- é o maior ganho relativo da noite.

**Eólica V1–V4, variante 005** (comparador `historico`, conforme a 2C):

| Rodada | Modelo | `historico` | `ultimo_valor` | Diferença | Recall de REL |
|---|---|---|---|---|---|
| V1 | 0,636 | 0,525 | 0,608 | +0,111 | 0,507 |
| V2 | 0,564 | 0,577 | 0,503 | −0,012 | 0,318 |
| V3 | 0,507 | 0,501 | 0,432 | +0,005 | 0,002 |
| V4 | 0,638 | 0,517 | 0,511 | +0,121 | 0,436 |
| **Média** | **0,586** | **0,530** | | **+0,056** | |

- **§11:** **passa as margens** (ganho médio ≥ 0,02, 3 de 4 rodadas melhores, nenhuma piora
  acima de 0,02).
- **Falta:** a incerteza semanal, que o script não calcula para causa.
- **Ponto fraco:** o recall de REL na V3 (0,002).

## 3.6 Quadro final (§11 aplicado como diagnóstico, filas Q, R e S concluídas às 03h06)

| Fonte | Tarefa | Receita testada | Ganho médio sobre o comparador | Rodadas melhores | Estado diagnóstico |
|---|---|---|---|---|---|
| Solar | corte | 003 | AP +0,062 | 4/4 | AP aprovado; **Brier falha na V2** |
| Solar | volume | `volume_total` 004 | MAE −4,97% | 3/4 | **Não aprova** (margem por um fio; V2 +14%) |
| Solar | causa | 005 | macro-F1 +0,009 | 2/4 | **Não aprova**; baseline preferível |
| Eólica | corte | 003 | AP +0,023 | 2/4 | **Não aprova**; baseline preferível |
| Eólica | volume | `volume_total` 004 | MAE +0,1% | 2/4 | **Não aprova**; baseline preferível |
| Eólica | causa | 005 | macro-F1 +0,056 | 3/4 | **Passa as margens** (IC semanal calculado depois: §3.7 e §3.11) |

- **Onde a IA é defensável:**
  - **alerta de corte solar**, com a ressalva de calibração;
  - **causa eólica.**
- **Nas demais células,** o baseline histórico é a entrega honesta, e o modelo aparece como
  "em evolução".
- **O padrão da V2** (maio–agosto de 2025, salto de corte) derruba todas as tarefas. Isso
  sustenta a proposta de recalibração periódica.

## 3.7 Recalibração periódica simulada (25/09, manhã): reprovada

Regra pré-registrada no commit `b5d38bb`
([`recalibracao-regra.md`](recalibracao-regra.md)).

- **Como foi feito:**
  - post-hoc, sobre os `predictions.parquet` salvos, sem retreinar;
  - reajuste semanal da sigmoide (corte) ou de um fator de viés limitado a [0,5; 2] (volume);
  - janela de 28 dias, só com rótulos já liberados no instante do reajuste.
- **Código:** `src/curtamap/recalibracao.py` (8 testes), `scripts/rapido/recalibrar.py` e
  `scripts/rapido/resumir_recal.py`.
- **Resultados:** em `experimentos/rapido-recal/*.json`.
- **Autoconferência:**
  - com o calibrador congelado, a simulação reproduz a coluna `prediction` com diferença 0,0;
  - o AP e o MAE congelados batem com os `resultado.json`.
- **Fato que sustenta o desenho:** a defasagem de liberação dos rótulos é de 20 h no mínimo e
  36–41 h na mediana, com cerca de 20 liberações por mês.

**Corte** (AP e Brier: congelado / recalibrado / `historico`; IC semanal recalibrado × `historico`):

| Fonte | Rodada | AP | ΔAP | Brier | ΔBrier | IC semanal |
|---|---|---|---|---|---|---|
| Solar | V1 | 0,596 / 0,553 / 0,429 | **−0,044** | 0,077 / 0,077 / 0,087 | −0,000 | [+0,055, +0,205] |
| Solar | V2 | 0,846 / 0,834 / 0,835 | **−0,011** | 0,162 / **0,093** / 0,077 | **−0,069** | [+0,001, +0,038] |
| Solar | V3 | 0,857 / 0,860 / 0,851 | +0,003 | 0,078 / 0,079 / 0,078 | +0,000 | [−0,006, +0,030] |
| Solar | V4 | 0,775 / 0,779 / 0,711 | +0,004 | 0,083 / 0,083 / 0,089 | +0,000 | [+0,042, +0,104] |
| Eólica | V1 | 0,485 / 0,444 / 0,385 | −0,041 | 0,138 / 0,141 / 0,151 | +0,003 | [+0,060, +0,205] |
| Eólica | V2 | 0,780 / 0,774 / 0,782 | −0,007 | 0,213 / 0,158 / 0,144 | −0,055 | [−0,015, +0,036] |
| Eólica | V3 | 0,871 / 0,869 / 0,887 | −0,002 | 0,129 / 0,127 / 0,116 | −0,001 | [−0,033, −0,003] |
| Eólica | V4 | 0,713 / 0,704 / 0,705 | −0,010 | 0,132 / 0,133 / 0,133 | +0,002 | [−0,011, +0,132] |

- **Veredito pela regra: reprova nas duas fontes.**
  - O Brier da V2 cai bem mais que 0,02 (solar −0,069, eólica −0,055).
  - Mas o AP agregado perde mais de 0,005: V1 solar −0,044, V2 solar −0,011 e V1 eólica
    −0,041.
- **Observação (achado, não decisão):**
  - os ICs semanais contra o `historico` ficam praticamente iguais aos do congelado (solar:
    V1 [+0,056, +0,206], V2 [−0,000, +0,035], V3 [−0,006, +0,030], V4 [+0,043, +0,107]);
  - a sigmoide é monótona dentro de cada semana, então o ranking semanal é preservado;
  - a perda de AP vem do ranking **entre** semanas, quando cada semana ganha um nível
    diferente;
  - **o calibrador congelado erra o nível em regime novo, e o recalibrado embaralha a
    comparação entre semanas.** Nenhum dos dois é gratuito.

**Volume** (MAE: congelado / recalibrado / comparador):

| Fonte | V1 | V2 | V3 | V4 | MAE médio recalibrado × comparador | §11 |
|---|---|---|---|---|---|---|
| Solar | 13,04 / 15,13 / 15,44 | 17,27 / 15,35 / 15,13 | 14,79 / 15,19 / 16,09 | 12,16 / 12,41 / 13,59 | −3,60% (o congelado tinha −4,97%) | **Não passa** |
| Eólica | 11,57 / 12,47 / 13,63 | 17,23 / 17,01 / 16,72 | 22,19 / 24,23 / 20,09 | 12,51 / 13,60 / 13,00 | +6,09% | **Não passa** |

- **Efeito no volume:** o fator de viés tira a V2 solar da proteção de piora (+1,5% em vez de
  +14,1%). Mas desfaz o ganho nas rodadas estáveis, e o ganho médio cai.
- **Decisão:** a recalibração periódica **não entra na receita**. Resultado negativo
  registrado, sem variantes de janela, frequência ou limites para salvá-lo, conforme o
  pré-registro.

**Incerteza semanal da causa eólica (005)**, diferença semanal de macro-F1 com bootstrap de
1.000 reamostragens:

| Rodada | Contra o `historico` | Contra o `ultimo_valor` |
|---|---|---|
| V1 | +0,146, IC [+0,045, +0,238], 15/18 | +0,164, IC [+0,052, +0,262] |
| V2 | −0,007, IC [−0,055, +0,041], 8/18 | +0,096, IC [+0,065, +0,128] |
| V3 | +0,000, IC [−0,045, +0,044], 10/18 | +0,094, IC [+0,046, +0,138] |
| V4 | +0,078, IC [+0,039, +0,123], 13/18 | +0,205, IC [+0,126, +0,276] |

- **Contra o `historico`** (o comparador da causa eólica): o benefício é sustentado na V1 e
  na V4, mas o IC contém zero na V2 e na V3.
- **Pelo §11.2,** a célula passa as margens médias, mas fica **`inconclusivo` nas rodadas de
  alta** do corte.
- **Estado diagnóstico:** "passa as margens; ganho concentrado em V1/V4".

**Decisão do responsável (25/09, manhã):** congelar a receita por célula no fim do dia e então
abrir o teste reservado **uma única vez**.

## 3.8 Teste de simplicidade `s01` (25/09, meio-dia): reprovado pela regra, com padrão revelador

Pergunta do responsável: "complicamos demais?". Regra pré-registrada no commit `9c4ee1b`
([`simplicidade-regra.md`](simplicidade-regra.md)).

**Variante:** árvores de 15 folhas e profundidade 4, com 8 features no corte solar e 14 na
causa eólica, contra cerca de 87 features e 63 folhas na referência.

| Célula | Rodada | Referência | `s01` | Diferença | Brier ref. / `s01` | `historico` |
|---|---|---|---|---|---|---|
| Corte solar (AP) | V2 | 0,846 (003) | **0,866** | **+0,020** | 0,162 / **0,074** | 0,835 (Brier 0,077) |
| Corte solar (AP) | V4 | **0,775** (003) | 0,760 | −0,015 | 0,083 / 0,083 | 0,711 |
| Causa eólica (macro-F1) | V2 | 0,564 (005) | **0,614** | **+0,050** | — | 0,577 |
| Causa eólica (macro-F1) | V4 | **0,638** (005) | 0,578 | −0,060 | — | 0,517 |

- **Veredito pela regra: reprova nas duas células**, porque a V4 perde mais de 0,01. Ficam a
  003 e a 005, e as rodadas V1 e V3 da `s01` não foram rodadas.
- **Fato:** o padrão é o mesmo nas duas células. A simples **ganha na rodada de mudança de
  regime** (V2, maio–agosto/2025) e **perde na rodada estável** (V4, janeiro–abril/2026).
- **No corte solar V2,** a simples é a única variante da campanha com Brier melhor que o
  `historico` (0,074 contra 0,077). Isso vale também para a recalibração, o offset, o `q12` e
  o `j6`.
- **Interpretação (hipótese):** as features extras (identidade da usina, volumes e
  frequências longas) ajudam quando o regime se mantém. Quando ele muda, elas carregam o nível
  do período de treino. **A complexidade compra desempenho em regime estável ao custo de
  robustez em mudança de regime.**
- **Resposta à pergunta "complicamos demais?":** em parte.
  - Um modelo com 8 variáveis já captura a maior parte do ganho sobre o `historico` (V4:
    +0,049 da simples contra +0,064 da 003).
  - O que falha na mudança de regime é justamente o que a complexidade adiciona.
  - Pela regra fixada, porém, a complexidade se paga na média das rodadas estáveis.

## 3.9 Estado sistêmico recente `sys` (25/09, início da tarde): reprovado

Regra pré-registrada no commit `3555451` ([`sistemico-regra.md`](sistemico-regra.md)).

- **Features:** fração de usinas do subsistema com `last_positive` e média de
  `positive_frequency_7d`, por fonte + subsistema + `t0`.
- **Por que 7 dias:** a informação mais nova disponível em `t0` tem cerca de 39 h, e as
  colunas de 24 h são 87% nulas.

| Célula | Rodada | AP da 003 | AP da `sys` | Diferença | Brier 003 / `sys` |
|---|---|---|---|---|---|
| Corte solar | V2 | 0,846 | 0,836 | −0,009 | 0,162 / 0,162 |
| Corte solar | V4 | 0,775 | 0,775 | +0,000 | 0,083 / 0,083 |
| Corte eólico | V2 | 0,780 | 0,763 | **−0,017** | 0,213 / 0,227 |
| Corte eólico | V4 | 0,713 | 0,726 | +0,013 | 0,132 / 0,129 |

- **Veredito: reprova nas duas fontes.**
  - Solar: média de −0,005, contra a exigência de +0,005.
  - Eólica: média de −0,002, com uma rodada perdendo mais de 0,01.
- **Execução:** a primeira tentativa eólica (`rapido-eol-v{2,4}-corte-sys`) falhou por memória,
  com o agregado global chegando a 33,5 GB. As runs válidas são as `-sys-b`, com o agregado
  calculado partição a partição (equivalente até 3×10⁻¹⁶).
- **Interpretação:** o estado do subsistema com cerca de 1,5 dia de defasagem não acrescenta
  informação à regra histórica da própria usina. É mais um indício de que o limite é a
  **idade da informação** disponível no noturno, não a engenharia de features.

## 3.10 Sementes 17 e 101 do corte solar 003 (variância da receita congelada)

A semente muda o modelo e a amostra de emissões do treino. Cada célula mostra AP / Brier.

| Rodada | Semente 42 | Semente 17 | Semente 101 | `historico` |
|---|---|---|---|---|
| V1 | 0,596 / 0,077 | 0,597 / 0,076 | 0,586 / 0,078 | 0,429 / 0,087 |
| V2 | 0,846 / 0,162 | 0,844 / 0,159 | 0,844 / 0,163 | 0,835 / 0,077 |
| V3 | 0,857 / 0,078 | 0,855 / 0,078 | 0,856 / 0,079 | 0,851 / 0,078 |
| V4 | 0,775 / 0,083 | 0,776 / 0,083 | 0,773 / 0,083 | 0,711 / 0,089 |

- **AP:** amplitude de no máximo 0,011 (V1) e ≤ 0,004 nas demais rodadas. Nas três sementes,
  o modelo vence o `historico` em todas as rodadas.
- **Brier da V2:** fica entre 0,159 e 0,163 em todas as sementes. É um efeito estrutural da
  mudança de regime, não da semente.
- **Uso:** só descrição da variância. Não serve para reinterpretar a `s01` (a diferença de
  −0,015 dela na V4 é maior que a amplitude entre sementes).

## 3.11 Teste reservado (maio–agosto/2026): aberto uma única vez, receita confirmada

- **Autorização:** o responsável autorizou a abertura única de manhã. A receita foi congelada
  no commit `8271bf1`, antes de gerar as features do período
  ([procedimento](teste-reservado-procedimento.md)).
- **Features:** geradas com `build-features --round reserved`. São 123 partições por fonte,
  com `t0` de 01/05 00h a 31/08 23h30: 22,5 milhões de linhas na solar e 43,4 milhões na
  eólica.
- **Pontuação:** 13h30–14h13, seis células, todas com exit 0. Runs `rapido-*-final-*-reservado`.

| Célula | Receita | Receita no teste | Comparador no teste | Diferença e IC semanal |
|---|---|---|---|---|
| **Corte solar** | modelo 003 | AP **0,875**, Brier **0,071** | `historico` 0,824 / 0,078 | **+0,051**, IC [+0,029, +0,068], 17/18 |
| **Causa eólica** | modelo 005 | macro-F1 **0,739** (REL 0,67) | `historico` 0,678 (REL 0,20) | **+0,061**, IC semanal [+0,008, +0,104], 10/18 |
| Corte eólico | `historico` | AP 0,828, Brier 0,125 | — | diagnóstico do modelo: 0,847 (+0,018, IC [+0,005, +0,030]) |
| Volume solar | `historico` | MAE 16,60 | — | diagnóstico do modelo: 14,56 (−12,3%) |
| Volume eólico | `mesmo_horario_dia_anterior` | MAE 20,10 | — | diagnóstico do modelo: 20,03 (−0,4%) |
| Causa solar | `ultimo_valor` | macro-F1 0,448 | — | diagnóstico do modelo: 0,496 (+0,048) |

**Previsões escritas antes do teste:**

1. **Corte solar, AP ≥ `historico`: confirmada** (+0,051).
   - A ressalva condicional do Brier não se aplicou: a prevalência foi de 25,8%, sem o salto
     de 2025, e o Brier ficou melhor que o do baseline.
2. **Causa eólica, macro-F1 ≥ `historico`: confirmada** (+0,061). O IC semanal exclui zero.
3. **Células de baseline:** reportado o baseline. Os números do modelo são **diagnóstico**. Em
   três delas, o modelo teria vencido fora da amostra (volume solar −12%, causa solar +0,048,
   corte eólico +0,018). Pela §11.3, isso **não** muda a receita: é evidência para uma versão
   futura, a validar com dados novos.

**Determinismo, limitação encontrada:**

- O retreino da pontuação **não é idêntico bit a bit** ao FINAL salvo, apesar da mesma semente
  e das mesmas linhas: o early stopping para em 93→75 árvores (corte solar), 57→44, 60→37 e
  167→221.
- **Causa provável:** a ordem das linhas vinda do motor *streaming* do Polars não é fixa.
- **Magnitude esperada:** a variação entre sementes (§3.10) é de ≤ 0,004 de AP em V2–V4.
- **Consequência:** o artefato do produto é o **`-reservado`**, o modelo efetivamente medido.
- **Correção futura:** ordenar por `KEYS` depois de cada `collect`.

**Observação sobre o comparador:** no volume solar, o `mesmo_horario_dia_anterior` tem MAE
idêntico ao do `historico` (16,603). É coerente com a defasagem de cerca de 39 h: o mesmo
horário de ontem ainda não está liberado e cai no fallback. Não foi investigado a fundo.

## 4. Achados que valem para o produto e para o pitch

1. **"A IA corrige o baseline" funciona.** O modelo recebe a regra histórica como feature, ou
   como offset no volume, e aprende quando ela erra. Na solar, isso deu +0,062 de AP médio e
   10–16% menos erro de volume.
2. **Sazonalidade falsa:** com menos de dois anos de dados solares, "mês" e "dia do ano"
   ensinam tendência como se fosse estação. Removê-los melhorou todas as rodadas.
3. **Mudança de regime:** a taxa de corte solar dobrou em maio–agosto de 2025. O modelo continua
   ordenando bem o risco, mas o calibrador, congelado por quatro meses, subestima o nível.
   - **Proposta de produto:** recalibração semanal com os dados recém-liberados. Isso não foi
     testado.
   - Nem mais dados nem janela recente resolveram.
4. **A quantidade de dados não é o gargalo;** a informação certa é. Isso confirma a leitura da
   2C.
5. **Principais features** (solar corte V4, ganho): as saídas dos baselines, fim de
   semana/feriado, dia da semana, mesmo horário 7 dias antes e hora do dia.

## 5. Estado das filas (atualizar ao retomar)

- **Fila Q** (`experiments/stage2b/execucao/rapido/jobs-q.txt`): quantidade, janela e volume
  total solar V1–V3.
- **Fila R** (`jobs-r.txt`), encadeada depois da Q, com 11 jobs:
  - corte eólico V1–V3 (003);
  - volume total eólico V1–V4 (004);
  - causa solar balanceada V1–V3 (005);
  - causa eólica balanceada V4 (005).
- **Status:** `jobs-q.txt.status` e `jobs-r.txt.status` (terminam em `FILA CONCLUIDA`). Os logs
  ficam em `experiments/stage2b/execucao/rapido/job-*.log`.

## 6. Limitações

- **Fora do protocolo completo:**
  - uma configuração fixa de LightGBM, sem a busca em duas configurações;
  - variantes escolhidas olhando V1–V4 (sazonalidade, offset, balanceamento). Por isso, V1–V4
    não são mais uma avaliação "cega" delas.
- **A única avaliação independente possível é o teste reservado**, ainda fechado. Abri-lo
  exige congelar a receita antes.
- **Amostragem:** 4/48 na solar e 2/48 na eólica no treino; a validação é completa.
- **Memória:** o Claude Code encerrou uma vez os shells em segundo plano por pressão de memória
  durante um treino eólico (pico de 21–24 GiB). O processo sobreviveu.
- **Artefatos:** os joblibs das runs `rapido-fv-v*-corte-001` a `-004` e de
  `rapido-eol-v4-corte-003` foram salvos com o `Encoder` definido em `__main__`. Eles só
  carregam injetando `curtamap.contexto.Encoder` em `__main__`. As runs lançadas depois da
  refatoração (a partir de `rapido-eol-v4-corte-004`) já usam o módulo.
- **Não medidos:** sensibilidade +24h, recortes por entidade/episódio e sementes 17/101.

## 7. Próximos passos sugeridos

1. Consolidar as filas Q e R numa tabela por fonte × tarefa × rodada e aplicar o §11 como
   diagnóstico.
2. **Congelar a receita:**
   - corte: 003;
   - volume: `volume_total` 004;
   - causa: 005 se superar o `ultimo_valor` na média, senão o baseline.
   - Treinar os modelos finais com dados até 30/04/2026, pela mesma receita.
3. **Decidir com o responsável se o teste reservado deve ser aberto uma vez**, com essa receita
   congelada. É a única evidência independente disponível para o pitch.
4. Ligar os modelos ao dashboard (`src/curtamap/app.py`), mostrando baseline, modelo,
   incerteza e limitações lado a lado.

### 7.1 Estado ao fim de 25/09 (tarde) e entrega para a integração

Os itens 1 a 3 acima estão concluídos (§3.6–§3.11). A receita confirmada no teste reservado é
esta:

| Célula | O que o produto exibe | Artefato |
|---|---|---|
| Corte solar | probabilidade do modelo 003, calibrada, com o limiar F2 no `model.joblib` | `experimentos/rapido-fv-final-corte-003-reservado/` |
| Causa eólica | classe prevista pelo modelo 005 (`p_REL`, `p_CNF`, `p_ENE`) | `experimentos/rapido-eol-final-causa-005-reservado/` |
| Corte eólico | `b_historico_prob_positive` | baseline (colunas em `baselines.parquet`) |
| Volume solar | `b_historico_volume_expected` | baseline |
| Volume eólico | `b_mesmo_horario_dia_anterior_volume_expected` | baseline |
| Causa solar | argmax de `b_ultimo_valor_cause_{CNF,ENE,REL}` (empate: CNF, ENE, REL; `_baseline_cause`) | baseline |

- **Carregar os modelos:** `joblib.load(...)` devolve `{"model", "encoder", "calibrator",
  "threshold"}`. O `Encoder` é `curtamap.contexto.Encoder`, e os artefatos `-reservado` não
  precisam do contorno de `__main__`.
- **Caminho exato de inferência** (bloco de validação de `scripts/rapido/treinar_contexto.py`;
  transcreva sem parafrasear):
  - **Entrada:** `features.parquet` + `baseline_wide(baselines)` juntados por `KEYS`, mais a
    coluna `tau_weekend_or_holiday`, que **não existe** no Parquet. Ela é calculada no script
    com `_weekend_or_holiday(calendar)` a partir de
    `configs/experimental/calendar-2023-2026.json`, e o `Encoder` a exige. As colunas
    sazonais (`SEASONAL`) foram removidas na receita.
  - **Corte:**
    - `raw = probability_with_offset(model, encoder.matrix(chunk), None)`;
    - depois `calibrator.predict(raw)`;
    - depois `np.where(eligible_history, prob, b_historico_prob_positive)`.
    - O limiar F2 serve só para o alerta (sim/não).
  - **Causa:** `predict_proba` → argmax em `model.classes_`. Nas linhas sem
    `eligible_history`, vale o argmax do `historico` (`_baseline_cause`).
  - **O fallback `historico` para as linhas sem histórico elegível faz parte da receita** nas
    duas células de modelo.
- **Reprodução histórica para a demonstração:** os `predictions.parquet` das runs
  `-reservado` (maio–agosto/2026) já trazem previsão, baseline e verdade por usina e janela.
  São 90 MB a 770 MB por célula. O dashboard deve ler um recorte, sem carregar tudo em
  memória, e indicar que se trata de reprodução histórica.
- **Limitações a exibir:**
  - treino fora do protocolo completo;
  - calibração sensível a mudança de regime (V2/2025);
  - informação com cerca de 39 h de idade no cenário noturno;
  - não determinismo bit a bit do treino.
- **Pendente técnico:** ordenar as linhas por `KEYS` depois de cada `collect`, para um treino
  determinístico. Isso fica para depois da entrega, porque a ordenação duplica a memória no
  pico eólico.

### 7.2 Preparação da integração (25/09, tarde)

- **Inferência no pacote:**
  - `curtamap.contexto.predict_corte`, `predict_causa`, `baseline_cause` e `replay_frame`;
  - autoconferência em três dias do teste: diferença 0,0 em 548.352 linhas do corte solar e
    nenhuma divergência em 387.149 linhas da causa eólica, contra os `predictions.parquet`.
- **Recorte de demonstração:** `scripts/rapido/recorte_demo.py` gera
  `experimentos/rapido-demo/replay.parquet`, com 158.016 linhas e 2,1 MB:
  - uma emissão por dia às 20h, de 18/08 a 31/08/2026;
  - colunas `prob_corte`, `alerta_corte`, `volume_esperado_mwmed`, `causa_prevista`, `p_*`,
    as colunas `*_fonte` com a origem de cada número e a verdade observada.
  - O horário das 20h é **escolha de demonstração** (logo após a liberação simulada), não
    regra do protocolo.
