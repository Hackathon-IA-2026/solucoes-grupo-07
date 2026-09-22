# Prompt autossuficiente para a Etapa 2C — GPT-6 Astra

Você é o GPT-6 Astra e deve executar exclusivamente a Etapa 2C do CurtaMap: análise crítica
dos resultados experimentais produzidos pela Etapa 2B e decisão metodológica por tarefa e
fonte. Não implemente correções silenciosas, não retreine candidatos e não abra o teste final
antes de congelar uma decisão explícita.

Trabalhe na branch `etapa-2-experimental`, sem merge e sem push. Leia integralmente `AGENTS.md`,
`docs/experimental-protocol.md`, `docs/stage2b-execution.md`,
`docs/reports/stage2b/implementation-status.md`, `docs/implementation-journal.md`, os commits
de implementação da 2B e todos os manifestos, checksums, relatórios, métricas, previsões,
diagnósticos, logs e falhas retornados do computador dedicado. Confira primeiro hashes,
commit do código, calendário, configuração, versões, sementes, cortes e conclusão de cada run.

Separe fatos, interpretações, hipóteses e decisões. Não trate execução incompleta, métrica
ausente, classe sem suporte, não convergência ou fixture sintética como resultado válido.
Confirme que o cenário +24h reutilizou modelos, pré-processadores, calibradores e limiares do
cenário principal sem reajuste. Verifique populações, cobertura, painel aberto/fixo, entidades
novas, histórico insuficiente, idade, fins de semana/feriados, horizontes, episódios e cauda.

Para cada fonte (`eolica`, `fotovoltaica`) e tarefa (`corte_positivo`,
`restricao_registrada`, volume completo do pipeline e causa REL/CNF/ENE), compare todos os
baselines e as famílias linear/LightGBM. Para volume, examine as quatro combinações entre o
classificador de corte positivo e o regressor condicional. Não escolha pela média agregada.

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

Somente depois dessa análise, congele por escrito a receita completa: features, família,
configuração, fonte, tarefa, treinamento final permitido, calibrador, limiar, pipeline de
volume e versão dos artefatos. Então decida explicitamente se o teste reservado de
maio–agosto de 2026 deve ser liberado. O teste serve para confirmar ou vetar a receita; não
serve para promover um segundo colocado ou continuar escolhendo modelos. Se houver lacuna de
implementação ou experimento adicional necessário, escreva um prompt preciso para a Etapa 2D
e mantenha o teste bloqueado.

Atualize o diário append-only em português com fatos, interpretações, alternativas, decisão,
limitações e próximos passos. A decisão final da Etapa 2C pertence a você, não à Etapa 2B.

