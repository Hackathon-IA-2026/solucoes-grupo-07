# Prompt autossuficiente para a Etapa 2C — GPT-6 Astra

Você é o GPT-6 Astra e deve executar exclusivamente a Etapa 2C do CurtaMap: análise crítica
dos resultados experimentais produzidos pela Etapa 2B e decisão metodológica por tarefa e
fonte. Não implemente correções silenciosas, não retreine candidatos e não abra o teste final
antes de congelar uma decisão explícita.

Responda em português do Brasil. Trabalhe na branch `etapa-2-experimental`, sem merge e sem
push.

> Versão consolidada em 24/09/2026, após a execução real da 2B. Ela reúne o prompt original,
> escrito antes da execução, e os fatos da execução (seção "Fatos da execução 2B"). Este é o
> único prompt da 2C.

## Leitura

Leia integralmente:

- `AGENTS.md` e `docs/experimental-protocol.md`, com atenção especial aos §10, §11 e §13.3;
- `docs/stage2b-execution.md` e `docs/reports/stage2b/implementation-status.md`;
- **`docs/reports/stage2b/execution-report.md`**: relatório factual de 15 seções da execução
  real, a fonte principal sobre o que foi executado;
- `docs/implementation-journal.md`, principalmente as entradas de 23 e 24/09/2026;
- os commits de implementação da 2B;
- todos os manifestos, checksums, relatórios, métricas, previsões, diagnósticos, logs e falhas
  da raiz experimental externa (hoje `Y:\CurtaMap Etapa 2B`; os caminhos abaixo são relativos
  a ela), além de `execucao/run-index.json`.

Confira primeiro hashes, commit do código, calendário, configuração, versões, sementes, cortes
e conclusão de cada run.

Separe fatos, interpretações, hipóteses e decisões. Não trate execução incompleta, métrica
ausente, classe sem suporte, não convergência ou fixture sintética como resultado válido.
Confirme que o cenário +24h reutilizou modelos, pré-processadores, calibradores e limiares do
cenário principal sem reajuste. Verifique populações, cobertura, painel aberto/fixo, entidades
novas, histórico insuficiente, idade, fins de semana/feriados, horizontes, episódios e cauda.

## Fatos da execução 2B

### Commits de referência

| O quê | Commit |
|---|---|
| Código das runs eólica V2–V4, das 4 solares, das 8 sensibilidades e dos datasets +24h | `88634ed` |
| V1 eólica | `560ae70`, com métricas anteriores à otimização `c73302e` e equivalentes por teste de paridade |
| Merge dos registros da fila | `1fba2f6` |
| Handoff | commits `docs:` posteriores; ver `git log --oneline -8 etapa-2-experimental` |

### Runs válidas (e apenas estas)

| Fonte | V1 | V2 | V3 | V4 |
|---|---|---|---|---|
| Eólica, principal | `main-eolica-v1-002` | `main-eolica-v2-004` | `main-eolica-v3-001` | `main-eolica-v4-001` |
| Solar, principal | `main-fotovoltaica-v1-001` | `-v2-001` | `-v3-001` | `-v4-001` |
| Eólica, +24h (congelada) | `delay-eolica-v1-001` | `-v2-001` | `-v3-001` | `-v4-001` |
| Solar, +24h (congelada) | `delay-fotovoltaica-v1-001` | `-v2-001` | `-v3-001` | `-v4-001` |

`main-eolica-v1-001`, `-v2-001`, `-v2-002` e `-v2-003` são tentativas falhas ou canceladas.
Estão preservadas, mas nunca devem ser usadas como resultado.

### Integridade

- **Handoff:** confira `handoff/SHA256SUMS-handoff.txt` e o SHA-256 de
  `handoff/inventario-etapa-2b-002.csv` contra `csv_sha256` em
  `handoff/inventario-etapa-2b-002.resumo.json`. O `-001` foi substituído.
- **Runs copiadas de máquina:** recalcule o SHA-256 das 16 runs contra o `checksums.json` de
  cada uma. O script `execucao/verificacoes/auditar_runs_2b.py` faz isso depois de ajustar
  `ROOT`.
- **Congelamento fora do Windows:** a checagem de congelamento desse script dá falso negativo,
  porque os relatórios gravam caminhos absolutos `Y:\…`. O congelamento já foi verificado na
  máquina dedicada (`execucao/verificacoes/auditoria-runs-2b-001.json`).
- **Divergências:** qualquer divergência interrompe a análise e deve ser relatada.

### Lacunas que a 2B não cobriu

- **Agregações do §10.2 e do §10.3 não produzidas:** visão por entidade com peso igual (WAPE
  agregado e média de WAPEs, sem trocar os nomes), energia diária só pela emissão das 00h,
  incerteza semanal e interseção comparável entre o cenário principal e o +24h. Calcule-as a
  partir das previsões Parquet ou registre-as como ausentes.
- **Sensibilidade incompleta:** faltam seis recortes (`cauda_volume_p99_treino`,
  `entidade_nova`, `fora_cauda_volume`, `inicio_episodio`, `painel_fixo` e
  `primeiro_zero_pos_episodio`), e não há baselines nem diagnósticos de volume na sensibilidade.
- **Métricas nulas:** em recortes de classe única, as métricas vêm nulas sem motivo gravado.

### Achados factuais que exigem exame antes de concluir

- `volume_condicional-lightgbm` solar selecionou `n_estimators=1` em V3 e V4.
- Os modelos de causa têm recall de REL próximo de zero; no baseline `ultimo_valor` eólico V1
  ele é de cerca de 0,67.
- Os baselines de causa `ultimo_valor` e `mesmo_horario_recente` são idênticos nas 8 runs.
- A prevalência muda bastante entre initial e tuning/calibração. Exemplo: eólica V3,
  `corte_positivo` 0,18 no initial contra 0,40 no tuning e 0,48 na calibração.
- Os picos de memória reais (24,06 GiB) superaram a meta de 20 GiB da projeção.

### Limitações que toda conclusão deve citar

- **Amostragem sistemática diária de t0** (semente 42), só em initial/refit. É desvio aprovado
  do §12.1.
  - Eólica: 4/48 nas ocorrências e 14/48 em volume e causa.
  - Solar: 16/48 nas ocorrências; volume e causa completos.
  - A prevalência amostrada difere no máximo 0,0004 da completa.
- **Baselines de ocorrência** com limiar fixo de 0,5 e `threshold or 0.5` no código.
- **Dados e alvos:** subconjunto de features, elegibilidade por t0 e volume condicional
  avaliado em todas as linhas.
- **LightGBM:** avisos `LGBMDeprecationWarning`; 6 threads determinísticas, diferente do
  piloto em 1 thread.
- **Processo:** commits de código criados na máquina dedicada, contrariando o §13.3.
- **Extensões não executadas:** sementes 17 e 101 e intervalo de volume.

## Comparação e critérios

Para cada fonte (`eolica`, `fotovoltaica`) e tarefa (`corte_positivo`,
`restricao_registrada`, volume completo do pipeline e causa REL/CNF/ENE), compare todos os
baselines e as famílias linear/LightGBM. Para volume, examine as quatro combinações entre o
classificador de corte positivo e o regressor condicional. Não escolha pela média agregada.
Calcule, por candidato, a média, o desvio, o mínimo/máximo e as diferenças pareadas por rodada.

Use os critérios pré-definidos antes de qualquer teste final:

- ocorrência: ganho médio absoluto de AP de pelo menos 0,02 contra um único melhor baseline
  escolhido em V1–V4;
- volume: redução relativa média de pelo menos 5% no MAE completo, sem piora do WAPE médio;
- causa: ganho médio absoluto de macro-F1 de pelo menos 0,02;
- melhoria estrita em pelo menos três das quatro rodadas.

Impeça adoção automática diante de piora superior a 0,02 em AP/macro-F1 em qualquer rodada,
piora superior a 10% no MAE em qualquer rodada, piora superior a 0,01 no Brier, intervalo
semanal contendo zero, vazamento, falha de reprodução, suporte insuficiente, métrica ausente,
não convergência, previsão inválida ou prejuízo relevante concentrado. Um baseline é uma
decisão válida. Se nenhum candidato o superar, preserve esse resultado.

Produza uma matriz por tarefa e fonte com estado `aprovado_para_teste`, `baseline_preferido`,
`inconclusivo`, `inelegivel` ou `requer_2d`, sempre com evidências e limitações. Recomendações
preliminares da 2B não têm autoridade decisória. Avalie custo, memória, duração, armazenamento,
reprodução e degradação +24h junto do desempenho.

## Receita, teste reservado e Etapa 2D

Somente depois dessa análise, congele por escrito a receita completa: features, família,
configuração, fonte, tarefa, treinamento final permitido, calibrador, limiar, pipeline de
volume e versão dos artefatos. Então decida explicitamente se o teste reservado de
maio–agosto de 2026 deve ser liberado. O teste serve para confirmar ou vetar a receita; não
serve para promover um segundo colocado ou continuar escolhendo modelos. Se houver lacuna de
implementação ou experimento adicional necessário, escreva um prompt preciso para a Etapa 2D
e mantenha o teste bloqueado.

Continua proibido:

- mudar grades, candidatos, limiares de decisão ou metodologia para resgatar médias (uma
  mudança necessária cria nova versão do protocolo);
- apagar tentativas falhas ou resultados negativos;
- fazer merge em `main` sem aprovação explícita;
- fazer push, salvo pedido do responsável.

## Entrega

Atualize o diário append-only em português com fatos, interpretações, alternativas, decisão,
limitações e próximos passos. Faça commits atômicos em Conventional Commits e informe as
verificações executadas e as não executadas. A decisão final da Etapa 2C pertence a você, não
à Etapa 2B.
