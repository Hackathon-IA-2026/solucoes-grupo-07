
## 2026-09-23 - Etapa 2B: dataset solar, decisão de contingência e início do treino

### Contexto e pergunta

Com as populações eólicas medidas, a pergunta consolidada
(`execucao/PERGUNTA-contingencia-treino-sessao04.md`) pediu decisão sobre amostragem,
aplicação à solar, threads, orçamento de 12 h e uso da V1 eólica como porta medida.
O responsável respondeu: "Siga com o que você faria (ações recomendadas)", e acrescentou
que as últimas sessões gastaram tempo demais com verificações redundantes enquanto só um
modelo havia sido treinado. A partir daqui, a prioridade explícita é o treino.

### Fatos: dataset e populações solares

Geração `features-noturno_dia_util-fotovoltaica-development-001`, commit `2e79475`:
exit 0, **2.424,2 s**, stderr vazio, 759 partições, 1.518 arquivos, 457.531.776 baselines.
Verificação `check-noturno_dia_util-fotovoltaica-001` (mesmo commit): **18/18 checagens**,
exit 0, 121,1 s, pico 1,07 GB. 114.382.944 features, 82 entidades, 2.382.978 emissões de
48 horizontes; só 01/04/2024 sem partição (primeira liberação 02/04/2024 19h30, igual ao
calendário); 87.984 linhas com tau ≥ 01/05/2026 e zero após os filtros V1–V4. Causas CNF,
ENE, REL e DESCONHECIDA (coerente com as 42 restrições solares sem causa do §1.1), sem PAR.

Medição `populacoes-noturno_dia_util-fotovoltaica-001`: exit 0, 106,4 s, 59/59 checagens
cruzadas. Refit das ocorrências: V1 29.088.288, V2 46.912.152, V3 64.939.512,
V4 83.666.856 linhas; volume V4 14.808.004; causa V4 19.523.621. Validação prevista:
17.781.648, 18.273.840, 19.344.336 e 20.417.904 linhas. Pico projetado do treino completo
das ocorrências: 19,9 (V1) a 56,7 GiB (V4); volume ≤ 10,0 GiB e causa ≤ 13,2 GiB.

### Decisão aplicada (desvio registrado do §12.1 “todos os elegíveis”)

- Amostragem `t0_sistematico_diario_v1`, semente 42: em cada dia, `k` das 48 meias-horas
  igualmente espaçadas, deslocadas por SHA-256(`42|data`). Emissões inteiras (todas as
  entidades, 48 horizontes). Só initial e refit; tuning, calibração e validação completos.
  Mesma seleção entre famílias, candidatos e rodadas; initial ⊂ refit.
- Regra de taxa: única por fonte/tarefa em todas as rodadas, a maior fração de 48 cujo pico
  projetado fique ≤ 20 GiB na rodada mais pesada. Eólica: ocorrências 4/48, volume e causa
  14/48. Solar: ocorrências 16/48 (máximo 0,345 em V4), volume e causa 48/48 (completo).
- LightGBM: `n_jobs=6`, `deterministic=True`, `force_row_wise=True`. Repetível com o mesmo
  número de threads; não é numericamente igual ao piloto em `n_jobs=1`.
- Orçamento de 12 h revisado implicitamente pela decisão; duração real será medida pela V1.
- `main-eolica-v1-001` é a porta medida: pico e duração antes das demais runs.
- Piloto solar: dispensado como run separada, porque a primeira campanha solar exerce o
  mesmo caminho técnico com a população real (decisão de prioridade; registrar se falhar).

Alternativas: hash puro por t0 (descartado: ±12% por meia-hora a 8%); taxa por rodada
(descartada: muda a fração entre rodadas); treino completo (inviável, até 184 GiB projetados).

### Implementação e validação

Commits `40cb438` (amostragem, campanha, CLI, configuração) e `f36d5f6` (threads).
TDD: testes de espaçamento, SHA-256 estável, emissões inteiras, aninhamento, semente,
leitura por fonte no CLI, segmentos (só initial/refit reduzidos, fração ≈ 4/48) e
parâmetros do LightGBM. Suíte `contingencia-pytest-001`: 241 aprovados e 2 falhas de
paridade causadas apenas pelas chaves novas `training_sampling`/`training_rows` do relatório,
ausentes no oráculo; a normalização passou a removê-las e a exigir `training_sampling=None`
sem amostragem; paridade 3/3 aprovada depois. Ruff check/format e `git diff --check` aprovados.
O relatório de cada rodada registra linhas e prevalência de cada split, permitindo conferir
a prevalência amostrada contra as populações medidas.

### Limitações

A amostragem reduz exemplos de ajuste e pode reduzir desempenho; toda comparação da 2C deve
citá-la. As proporções por mês/hora são garantidas pela construção; prevalência e entidades
serão conferidas pelos `training_rows` das runs. A fase de validação completa não foi medida
antes da V1.
