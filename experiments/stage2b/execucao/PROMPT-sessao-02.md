Você continuará a Etapa 2B do CurtaMap no computador dedicado (Windows 11, PowerShell), no repositório M:\Bibliotecas\Development\workspaces\hackathon-ia-coppe-2026, branch `etapa-2-experimental`, HEAD esperado `ce73b6d`. Responda em português do Brasil.

Antes de qualquer ação, leia integralmente:
1. `Y:\CurtaMap Etapa 2B\execucao\HANDOFF-sessao-01.md` (estado factual, números, pendências, proibições);
2. AGENTS.md, docs/experimental-protocol.md, docs/stage2b-execution.md, docs/reports/stage2b/implementation-status.md e as duas últimas entradas de docs/implementation-journal.md.

Regras desta continuação (valem sobre o prompt original da 2B):
- Desenvolvimento e commits locais são permitidos nesta máquina, com TDD (Red–Green–Refactor), Conventional Commits em pt-BR, commits atômicos, `uv run pytest`, `uv run ruff check .` e `uv run ruff format --check .` antes de cada commit. Nada de push. Nada de merge em `main`. Trabalho paralelo feito em outro worktree/branch entra em `etapa-2-experimental` só por commit de merge explícito (`git merge --no-ff`), nunca fast-forward.
- Continua proibido: executar `reserved-test` ou pontuar maio–agosto/2026; escolher vencedor ou usar métricas do piloto para decidir; alterar grades, candidatos, metodologia; introduzir amostragem sem decisão explícita do usuário; apagar resultados, falhas ou runs incompletos.
- Um processo pesado por vez, sempre pelo executor durável `Y:\CurtaMap Etapa 2B\execucao\run-step.ps1` (StepId novo e único), com `. "Y:\CurtaMap Etapa 2B\env.ps1"` carregado. Não rode suítes de teste completas nem subagentes pesados enquanto uma geração/treino estiver rodando; se precisar, use testes direcionados.
- Não altere o worktree principal enquanto uma run estiver ativa (os processos importam o código dele).
- Todo item material termina com entrada append-only no diário.

Comece por aqui, nesta ordem:
0. Verificação inicial somente leitura: `git branch --show-current`, `git rev-parse HEAD`, `git status --short`, `git worktree list`. Remova o worktree travado já integrado (`git worktree remove --force --force .claude/worktrees/agent-a4853e8040807e41f` e `git branch -d worktree-agent-a4853e8040807e41f`), depois de confirmar que `f33c5b1` é ancestral de HEAD.
1. Rode o verificador de contrato somente leitura no dataset eólico principal (comando exato na seção 4 do handoff). Analise cada checagem; explique a partição do primeiro dia e a contagem de linhas com `tau >= 2026-05-01` (esperadas e nunca pontuadas — confirme pelos limites dos segmentos). Se alguma checagem falhar, pare e reporte antes de prosseguir.
2. Execute o piloto técnico eólico `pilot-eolica-001` (docs/stage2b-execution.md §4) pelo executor durável; produza parecer estritamente técnico (completou, contratos, tempo, pico de memória, armazenamento, artefatos, warnings, possibilidade de prosseguir), declarando que `head(2M)` cobre só os primeiros dias de out/2023.
3. Meça por varredura preguiçosa, com os filtros exatos de `_range`/`_task_filter` de `campaign.py`, as linhas por rodada V1–V4 × segmento × tarefa na eólica, e projete memória de treino com os coeficientes do handoff. Em seguida faça ao usuário UMA pergunta consolidada sobre a contingência de treino (requisitos do §12.2 e opção de amostragem determinística de emissões t0 descritos no handoff; inclua a questão do LightGBM `n_jobs=1` se o piloto indicar peso). Não implemente amostragem antes da resposta.
4. Enquanto aguarda a resposta, e depois dela, gere os demais datasets (solar principal; eólica +24h; solar +24h), cada um seguido do verificador de contrato. Opcional antes: sonda curta sem concorrência comparando `--workers 6` e `--workers 10`.
5. Registre no diário uma entrada didática cobrindo a sessão 01 (portabilidade, vetorização com oráculos e divergências intencionais, campanha preguiçosa, geração eólica, números, limitações) e os resultados da sessão atual; commit `docs:`.
6. Siga a partir daí o plano original da 2B: piloto solar, campanha V1–V4, sensibilidade +24h com `--frozen-run`, validação de artefatos, pacote de handoff com inventário (caminho relativo, tamanho, SHA-256) e relatório factual de 15 seções — sem vencedor e sem liberar o teste final.

Mantenha atualizado `Y:\CurtaMap Etapa 2B\execucao\run-index.json` (situação factual de cada um dos 18 runs) e registre o commit usado por cada dataset e run. Ao atingir marcos, informe o usuário em poucas frases; não use polling agressivo.
