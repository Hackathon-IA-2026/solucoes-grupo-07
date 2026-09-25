# Prompt: teste rápido de quantidade de dados e janela de treino

Execute um experimento curto e exploratório no CurtaMap. Responda em português do Brasil.
Trabalhe na branch `etapa-2-experimental`, sem merge e sem push. Não abra, não gere features e
não pontue o teste reservado (maio–agosto/2026).

## Contexto (fatos já estabelecidos; não refaça)

- **Etapa 2C** (`docs/reports/stage2c/decision.md`): os modelos da 2B perderam para o baseline
  `historico` porque usaram só 12 das cerca de 50 features dos datasets. O teste reservado
  segue bloqueado.
- **Treino rápido exploratório** de 25/09/2026, fora do protocolo completo, com o script
  `scripts/rapido/treinar_contexto.py` e o módulo `src/curtamap/contexto.py`:
  - LightGBM com as features do §8 já presentes em `stage2b-datasets`, mais as saídas dos
    quatro baselines e categorias nativas;
  - mesmos segmentos temporais, disponibilidade de rótulos, calibração sigmoide, limiar F2 e
    fallback `historico` da 2B;
  - validação completa da rodada, comparada ao baseline nas mesmas linhas.
- **Resultados de referência** (AP de `corte_positivo`; resumo com
  `uv run python scripts/rapido/resumir.py`):

  | Run | Fonte | Treino | AP V1 / V2 / V3 / V4 (modelo − `historico`) | Brier |
  |---|---|---|---|---|
  | `rapido-fv-v*-corte-003` | solar | 4/48, sem mês e dia do ano | +0,168 / +0,011 / +0,006 / +0,064 (média +0,062) | pior só na V2 (0,162 contra 0,077) |
  | `rapido-fv-v*-corte-004` | solar | idem, com `--offset` | +0,093 / +0,022 / +0,007 / +0,055 | pior só na V2 (0,123 contra 0,077) |
  | `rapido-eol-v4-corte-003` | eólica | 2/48, sem mês e dia do ano | V4: +0,008 | ligeiramente melhor |

- **Diagnóstico do Brier na V2 solar:** o ranking é bom, mas o nível ficou baixo (previsão
  média de cerca de 0,10 contra taxa real de 0,21–0,32). A prevalência saltou entre o treino
  e maio–agosto de 2025.
- **Memória:**
  - solar 4/48: pico de 15 GiB;
  - eólica 2/48: pico de 21–24 GiB;
  - a máquina tem 32 GB, e o Claude Code encerra shells em segundo plano sob pressão de
    memória;
  - o dataset inteiro **não cabe**: a solar teria cerca de 30 GB de matriz, a eólica cerca
    de 98 GB.

## Perguntas

1. **Quantidade:** treinar com mais emissões por dia (12/48, um quarto) melhora a solar em
   relação a 4/48?
2. **Janela:** treinar só com os meses mais recentes antes do corte ataca a mudança de regime
   (especialmente o Brier da V2) sem perder AP?

## Regra de decisão (fixa antes de ver resultados)

Compare cada variante com a referência `-003` da mesma fonte, nas **mesmas rodadas**:
solar V2 e V4 primeiro; V1 e V3 só se a variante passar nessas duas.

- **Adote a variante** somente se:
  - o ganho médio de AP sobre a `-003` for ≥ +0,005;
  - nenhuma rodada piorar mais de 0,01 em AP;
  - o Brier não piorar mais de 0,005 em nenhuma rodada.
- **Janela:** também adote se o Brier da V2 cair pelo menos 0,02 com AP não pior que −0,005 em
  todas as rodadas testadas.
- **Caso contrário,** mantenha a `-003` (4/48, histórico completo). Resultado negativo é
  resultado válido: registre e não procure outra variante para "salvar" a hipótese.

## Tarefas

1. **Leitura:** `scripts/rapido/treinar_contexto.py`, `src/curtamap/contexto.py`,
   `experiments/stage2b/execucao/rapido/fila.sh` e `experiments/stage2b/README.md` (proibido
   `git clean -x`).
2. **Janela de treino (TDD onde couber):**
   - acrescente a `treinar_contexto.py` a opção `--train-months N`, que restringe initial e
     refit a `t0 >= calibration_start − N meses`;
   - tuning, calibração e validação ficam inalterados;
   - registre `train_months` no `resultado.json`;
   - não altere o comportamento padrão.
3. **Jobs** (arquivo `experiments/stage2b/execucao/rapido/jobs-q.txt`, um comando por linha,
   `D=t0_month,t0_day_of_year,tau_month,tau_day_of_year`):
   - `--source fotovoltaica --round V2 --task corte_positivo --slots 12 --drop $D --run-id rapido-fv-v2-corte-q12`
   - idem para a V4 (`rapido-fv-v4-corte-q12`);
   - `--source fotovoltaica --round V2 --task corte_positivo --slots 4 --train-months 6 --drop $D --run-id rapido-fv-v2-corte-j6`
   - idem para a V4 (`-j6`);
   - se a regra aprovar alguma variante nas duas rodadas, repita-a na V1 e na V3.
4. **Execução desacoplada do shell:**
   `nohup bash experiments/stage2b/execucao/rapido/fila.sh experiments/stage2b/execucao/rapido/jobs-q.txt > /dev/null 2>&1 &`
   - Um job por vez; nunca em paralelo.
5. **Monitoramento:**
   - use a ferramenta Monitor sobre `jobs-q.txt.status`, com um laço que emite linhas novas e
     termina em `FILA CONCLUIDA`;
   - se o monitor expirar ou for encerrado por pressão de memória, **rearme-o**: o processo da
     fila continua vivo;
   - antes do `--slots 12`, confira a memória livre; se ela ficar abaixo de 4 GB durante o
     ajuste, registre o fato;
   - não encerre processos sem necessidade.
6. **Análise:**
   - aplique a regra de decisão acima;
   - produza uma tabela run × rodada com AP, Brier, IC semanal, pico de memória e duração.
7. **Entrega:**
   - entrada no diário (`docs/implementation-journal.md`, append-only) com fatos,
     interpretação, decisão, limitações (fora do protocolo completo, rodadas parciais) e
     próximos passos;
   - commits atômicos em Conventional Commits (código, depois diário);
   - informe as verificações feitas e as não feitas.

## Proibições

- Regenerar os `stage2b-datasets` (as colunas já existem).
- Usar o dataset inteiro no treino (não cabe na RAM).
- Mudar a regra de decisão depois de ver resultados.
- Apagar runs anteriores.
- Push ou merge.
