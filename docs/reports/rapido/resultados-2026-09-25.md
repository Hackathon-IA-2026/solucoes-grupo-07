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
| Eólica | causa | 005 | macro-F1 +0,056 | 3/4 | **Passa as margens** (falta a incerteza semanal) |

- **Onde a IA é defensável:**
  - **alerta de corte solar**, com a ressalva de calibração;
  - **causa eólica.**
- **Nas demais células,** o baseline histórico é a entrega honesta, e o modelo aparece como
  "em evolução".
- **O padrão da V2** (maio–agosto de 2025, salto de corte) derruba todas as tarefas. Isso
  sustenta a proposta de recalibração periódica.

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
