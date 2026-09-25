# Retomada do CurtaMap — Etapa 2B após a fila de treinamento (sessão 05)

Responda sempre em português do Brasil. Repositório:
`M:\Bibliotecas\Development\workspaces\hackathon-ia-coppe-2026`, branch `etapa-2-experimental`.
Computador dedicado: Windows 11, Ryzen 5 5600X, 32 GB. Raiz externa: `Y:\CurtaMap Etapa 2B`.

## Orientação do responsável (obrigatória)

Foco em concluir a 2B e avançar; **evitar verificações redundantes**. Rode cada verificação
obrigatória uma única vez por mudança; não repita checagens já aprovadas sem evidência de
alteração. Decisões técnicas recomendadas podem ser executadas e registradas sem pedir
confirmação; perguntar só o que for metodológico e ainda não decidido.

## Leitura inicial (só isto, nesta ordem)

1. `Y:\CurtaMap Etapa 2B\execucao\CHECKPOINT-sessao-03.md` — seções "sessão 04" no fim.
2. `Y:\CurtaMap Etapa 2B\execucao\run-index.json`.
3. `Y:\CurtaMap Etapa 2B\execucao\fila\fila.log` e a saída de
   `pwsh -File "Y:\CurtaMap Etapa 2B\execucao\status-fila.ps1"`.
4. `AGENTS.md` e as duas últimas entradas de `docs/implementation-journal.md`.
5. Consulte `docs/experimental-protocol.md` apenas nas seções necessárias (§10–§13).

## Estado conhecido ao fim da sessão 04 (23/09/2026 ~21h30)

- Commits em `etapa-2-experimental`: `ea88fe7` (merge do medidor de populações), `2e79475`
  (diário: populações eólicas), `40cb438` (amostragem t0), `f36d5f6` (LightGBM 6 threads
  determinísticas), `560ae70` (correção de pushdown da máscara). Sem push; `main` em `48f9923`.
- Datasets principais eólico e solar gerados e verificados (18/18 cada). Populações medidas:
  `execucao/medicoes/populacoes-noturno_dia_util-{eolica,fotovoltaica}-001.json`.
- **Decisão do responsável (23/09):** "siga com as ações recomendadas" — pergunta em
  `execucao/PERGUNTA-contingencia-treino-sessao04.md`. Aplicado: amostragem sistemática diária
  de t0, semente 42, só em initial/refit (eólica 4/48 ocorrências e 14/48 volume/causa; solar
  16/48 ocorrências, volume/causa completos); tuning, calibração e validação completos;
  LightGBM n_jobs=6, deterministic=True, force_row_wise=True; piloto solar dispensado; V1
  eólica como porta medida. É desvio registrado do "todos os elegíveis" (§12.1) e deve ir à 2C.
- `main-eolica-v1-001` foi **interrompida** (máscara sem pushdown, 46 GB comprometidos,
  thrashing); evidência preservada em `execucao/passos/main-eolica-v1-001*`. Corrigido em `560ae70`.
- `main-eolica-v1-002` (commit `560ae70`) rodava: treino ≈30 min, previsões+métricas ≈2 h+.
- **Fila automática** autorizada pelo responsável: `execucao/fila/fila-2b.ps1`, código congelado
  em `Y:\CurtaMap Etapa 2B\worktrees\execucao-fila` (branch `execucao/fila-2b`, `560ae70`).
  Ordem: main eólica V2–V4 → main solar V1–V4 → gerar/verificar +24h eólica → delay eólica
  V1–V4 → gerar/verificar +24h solar → delay solar V1–V4. `delay-eolica-v1-001` congela a
  partir de `main-eolica-v1-002`. Parar: criar `execucao/fila/PARAR`.
- **Diário pendente:** a decisão de contingência, a solar, a V1-001 interrompida, a correção e
  a fila ainda não foram registradas. Rascunho em
  `execucao/rascunhos/diario-sessao04-contingencia.md` — completar com os fatos das runs e
  acrescentar ao diário (append-only) num commit `docs:`.

## Tarefas desta sessão

1. Conferir somente leitura: branch, HEAD, status, worktrees, processos, fila.log, status-fila.
   Se a fila ainda estiver rodando, não interfira; trabalhe só no repositório principal.
2. Para cada run concluída: exit code, `manifest.json` status, `reports/`, `failures/`,
   stderr, duração, pico de memória (samples.csv), `training_sampling`/`training_rows` do
   relatório (conferir prevalência amostrada vs. populações medidas). Falha ou run bloqueada:
   diagnosticar, preservar evidência, relançar com **novo** StepId/run_id (`-002`) e registrar.
3. Atualizar `run-index.json` com status, commits e evidências de cada run.
4. Validar artefatos: checksums de cada run e congelamento das sensibilidades (sem retreino).
5. Inventário (caminho relativo, tamanho, SHA-256), relatório factual de 15 seções
   (estado/escopo; proveniência; ambiente; protocolo/desvios; datasets/contratos; pilotos;
   populações/cortes; execução principal; baselines/resultados factuais; calibração/limiares;
   diagnósticos/cobertura; sensibilidade; recursos/falhas/retomada; integridade/inventário;
   pendências e handoff 2C) e prompt de análise da 2C em `Y:\CurtaMap Etapa 2B\handoff`.
6. Diário append-only e commits atômicos em português (Conventional Commits), sem push.
7. Integrar `execucao/fila-2b` só se houver commits nela (normalmente não há) e remover o
   worktree de execução depois que nenhuma run depender dele.

## Regras permanentes

Não executar o teste reservado nem pontuar maio–agosto/2026; não escolher vencedor; não mudar
grades, candidatos ou metodologia; não apagar falhas ou resultados negativos; não fazer push
nem merge em `main`; um processo pesado por vez pelo `run-step.ps1`; manter explícitas as
limitações do handoff original (limiar 0,5 dos baselines e `threshold or 0.5`, subset de
features, recortes vazios na sensibilidade, elegibilidade por t0, volume condicional avaliado
em todas as linhas, warnings) e a amostragem aprovada. Ao terminar, informar o que foi concluído,
o que falhou e o comando exato de retomada.
