# Handoff da sessão 01 — Etapa 2B no computador dedicado (22/09/2026)

Fonte factual para a próxima sessão e para a entrada do diário. Horários em UTC−3.

## 1. Estado do Git (local, sem push, `main` intocada)

Branch `etapa-2-experimental`, HEAD `ce73b6d`. Commits desta sessão sobre `e389332`:

| Commit | Conteúdo |
|---|---|
| `07116b9` | fix: pico de memória portável (`peak_rss_bytes`, `resources.py`); `import resource` quebrava o CLI no Windows |
| `747d69c` | fix: chaves de `checksums.json` sempre com `/` |
| `9589843` | test: inventário lido em UTF-8 |
| `1605650` | docs: diário — portabilidade + inviabilidade medida do código original |
| `0ad6be4` | perf: features e baselines vetorizados (oráculo `tests/reference_stage2b.py`, paridade em `tests/test_experimental_vectorized_parity.py`) |
| `70a181d` | perf: partições diárias em paralelo (`--workers`, `feature_workers: 6` na config) |
| `a187150` | fix: rejeita `(fonte,id_ons,din_instante)` duplicado; requests vazio; restrição nula documentada |
| `f3cca8b` | perf: codificação categórica e limiar F2 vetorizados (oráculo `tests/reference_models_stage2b.py`) |
| `f039347`, `064a064`, `f33c5b1` | campanha/sensibilidade preguiçosas por partes (oráculo `tests/reference_campaign_stage2b.py`), feitos por executor em worktree |
| `ce73b6d` | merge explícito (--no-ff) dos três commits acima |

Última suíte completa medida: 187 passed, 1 skipped (`test_notebook`, Parquet ausentes em data/raw — a
máquina tem os Parquet em data/raw, então o skip ocorreu só no worktree), ruff check/format limpos.
Pendência Git: worktree travado `.claude/worktrees/agent-a4853e8040807e41f` (branch
`worktree-agent-a4853e8040807e41f`, já integrada). Remover com
`git worktree remove --force --force <caminho>` e `git branch -d worktree-agent-a4853e8040807e41f`.

Divergências intencionais em relação ao código original (todas testadas):
- volume indeterminado / restrição nula na linha direta do baseline vira nulo (original: TypeError, que
  quebraria a geração eólica em 2026);
- schema de features estável (colunas todas nulas mantêm tipo);
- timestamps ns→us na entrada;
- observações duplicadas são rejeitadas (os 4 caches reais têm 0 duplicatas e 0 restrições nulas).

## 2. Ambiente e caminhos

- Windows 11 Pro, 32 GB RAM (31,9 GiB), Ryzen 5 5600X (6 núcleos/12 threads), Python 3.12.12 via uv 0.9.15,
  polars 1.44.2, duckdb 1.5.5, lightgbm 4.7.0, scikit-learn 1.9.1.
- Raiz externa: `Y:\CurtaMap Etapa 2B` (≈ 620 GB livres). Carregar ambiente: `. "Y:\CurtaMap Etapa 2B\env.ps1"`
  (define `CURTAMAP_DATA_DIR/MODEL_DIR/EXPERIMENT_DIR/CACHE_DIR/TEMP_DIR`, `TMP`, `TEMP`,
  `POLARS_TEMP_DIR`, `PYTHONUTF8`). O código lê `CURTAMAP_EXPERIMENT_DIR` (não `_ROOT`).
- Dados: cópias dos dois Parquet principais em `dados\raw\`, SHA-256 conferidos:
  eólica `487050da…0734d`, solar `e2935941…711ec` (iguais a `docs/reports/stage1/audit.json`).
  Originais em `data/raw` do repositório intactos. Integrada e detail não copiados.
- Executor durável: `execucao\run-step.ps1` (lança `uv run curtamap-experiment ...` destacado, grava
  `command.txt`, `start.json` com commit/env/PID, `stdout.log`, `stderr.log`, `samples.csv` de memória/disco,
  `end.json` com exit code/duração). Uso:
  `Start-Process pwsh -WindowStyle Hidden -PassThru -ArgumentList @("-NoProfile","-File","`"Y:\CurtaMap Etapa 2B\execucao\run-step.ps1`"","-StepId","<id-unico>","-Repo","`"<repo>`"","-SampleSeconds","60","-Arguments","`"<args>`"")`
  Recusa StepId existente. Aceita `-ExperimentDirOverride` para sondas.
- Índice de runs predefinidos: `execucao\run-index.json` (18 runs, todos `nao_iniciada`).

## 3. Passos executados (evidências em `execucao\passos\<step>`)

| Passo | Commit | Resultado |
|---|---|---|
| preflight (Windows nativo, código original) | `e389332` | FALHOU: `ModuleNotFoundError: resource` (evidências em scratchpad da sessão, resumidas no diário `1605650`) |
| preflight | `9589843` | OK, branch/commit/raw presentes |
| `prep-targets-noturno_dia_util-001` | `9589843` | exit 0, 60,5 s, pico ~1,0 GB; 7.951.920 linhas eólicas (35 partições) e 2.854.800 solares (29) |
| `prep-targets-noturno_mais_24h-001` | `1605650`* | exit 0, 50,9 s, mesmas contagens e hashes |
| `sonda-features-eolica-1dia-001` (código original) | `9589843` | INTERROMPIDA pelo operador após 544,7 s, 0 dias concluídos (`INTERRUPCAO.txt`) |
| medição 1 t0 eólico (código original) | `9589843` | > 20 min sem concluir (`medicoes\t0-eolica.RESULTADO.txt`) |
| medição 1 t0 eólico vetorizado | pós-`0ad6be4` | 0,20 s/t0 (features 0,12 + baselines 0,08), 156 entidades, 7.488 linhas/t0 |
| `sonda-features-eolica-7dias-vetorizado-001` | `70a181d` | exit 0, 67 s, 2.515.968 features, 10.063.872 baselines, 6 workers |
| **`features-noturno_dia_util-eolica-development-001`** | **`70a181d`** | **exit 0, 8.105,6 s (2 h 15 min), 943 dias, 339.738.048 features, 1.358.952.192 baselines, 1.884 arquivos, pico ~4,6 GB (árvore de processos)** |

*o cache de alvos não depende dos commits posteriores (targets inalterados).
O dataset eólico foi gerado em `70a181d`; commits posteriores não mudam a saída com dados reais
(0 duplicatas; `f3cca8b` e a campanha não tocam a geração). Registrar o commit por dataset.
Durante essa geração a CPU foi disputada por testes e subagentes; a taxa limpa é desconhecida.

Datasets: `experimentos\stage2b-datasets\scenario=<cen>\source=<fonte>\round=development\date=*/{features,baselines}.parquet`.

## 4. Pendências, na ordem

1. Rodar o verificador de contrato (somente leitura) no dataset eólico principal:
   `uv run python "Y:\CurtaMap Etapa 2B\execucao\verificacoes\check_dataset.py" "<dir round=development>" 2023-10-01T00:00:00 2026-05-01T00:00:00 "Y:\CurtaMap Etapa 2B\execucao\verificacoes\dataset-noturno_dia_util-eolica.json"`
   (foi interrompido antes de gravar resultado). Esperado: 942 partições (o 1º dia pode não ter
   features por não haver nada liberado — confirmar e registrar); schema único; 48 horizontes; sem t0 no
   reservado; linhas com `tau >= 2026-05-01` existem (horizontes das últimas emissões de 30/04) e nunca
   são pontuadas — reportar a contagem.
2. Piloto técnico eólico (`pilot-eolica-001`), comando de `docs/stage2b-execution.md` §4. Usa
   `head(2.000.000)` = primeiros dias de out/2023 (tudo inelegível, histórico curto): válido só para
   recursos/contratos; declarar isso. Métricas do piloto não escolhem nada.
3. Medir, com varredura preguiçosa dos filtros exatos de `_range`/`_task_filter`, o nº de linhas por rodada
   × segmento (initial/tuning/refit/calibration/validação) × tarefa, e projetar memória com os coeficientes
   do executor (trecho coletado ≈ 84 B/linha; CSR ≈ 148 B/linha; pico de `fit_transform` ≈ 556 B/linha).
   Estimativa prévia V1 eólica: initial ≈ 119 mi, refit ≈ 128 mi linhas → ~22 GB só de trechos + ~18 GB de
   matriz + picos de ~66 GB; V4 ≈ 2,2×. **O treino com todos os elegíveis não cabe em 32 GB.**
4. Perguntar ao usuário (uma única pergunta, com números) a contingência de treino — decisão metodológica
   (§12.2), não do executor. Requisitos do protocolo para qualquer amostragem: reproduzível; preserva
   proporções temporais/entidades/horizontes e prevalência natural; mesmo conjunto elegível para todos os
   candidatos da tarefa; fixada antes de qualquer métrica externa; validação continua completa. Uma opção
   (não decisão): subconjunto determinístico com semente de emissões `t0`, mantendo todas as entidades e os
   48 horizontes de cada emissão escolhida. Incluir também, se o piloto mostrar peso: LightGBM com
   `n_jobs=1` fixo (a config diz threads 6); mudar threads pode alterar resultados sem `deterministic=True`
   → mudança registrada. Registrar a decisão como desvio de protocolo (diário, config resolvida, 2C).
5. Gerar os outros três datasets, um processo pesado por vez, com o executor durável e verificador de contrato
   após cada um: solar principal (2024-04-01→2026-05-01), eólica +24h e solar +24h. Considerar testar
   `--workers` maior (ex.: 10) numa sonda curta sem concorrência antes.
6. Piloto solar; campanha V1–V4 (8 runs) e sensibilidade +24h (8 runs, `--frozen-run`), após a decisão.
7. Validação de artefatos, pacote de handoff em `Y:\CurtaMap Etapa 2B\handoff` (inventário com caminho,
   tamanho e SHA-256), relatório factual de 15 seções.
8. Entrada no diário (`docs/implementation-journal.md`, append-only) cobrindo a vetorização, a campanha
   preguiçosa, a geração eólica e os números acima; commit `docs:`.

## 5. Observações de conformidade (não corrigidas; para a 2C)

- Baselines pontuados com limiar fixo 0,5, não o procedimento F2 interno (§7.2); `threshold or 0.5`
  converte limiar 0,0 em 0,5.
- Modelos usam 8 numéricas + 4 categóricas das ~50 features geradas.
- Sensibilidade fixa `entity_new`/`panel_fixed` = False (recortes vazios; `painel_aberto` = global).
- `entity_new`/`panel_fixed` usam só `id_ons` (ok dentro de uma fonte).
- Recortes `idade:*` dos baselines usam a idade do comparador.
- Volume condicional avaliado contra todas as linhas da validação.
- `history_eligibility` usa `t0` como corte, não `c(t0)` do protocolo §4 (preservado por paridade).
- Aviso de depreciação: `eval_set` do LightGBM e `is_in(Series)` do Polars.
- `audit.py:393` e `public_reference.py:130` gravam texto sem `encoding` (Etapa 1; fora do fluxo 2B).

## 6. Tarefas de background interrompidas

As 6 tarefas marcadas como interrompidas (b2mzqzb3f, bvnyebxma, b4ygou81e, brri2r9ca, bteqwkhk9,
b7a2282v2) eram apenas monitores de acompanhamento. O processo real terminou com exit 0 (`end.json`).
A única ação perdida foi a execução do verificador de contrato (pendência 1).

## 7. Proibições mantidas

Não executar `reserved-test`, não gerar features ≥ 2026-05-01 para pontuação, não escolher vencedor, não
usar métricas do piloto para decisão, não apagar resultados/falhas, não amostrar sem decisão do usuário,
não fazer push nem merge em `main`. Commits locais são permitidos (autorização do usuário nesta sessão),
com TDD, Conventional Commits em pt-BR e integração por commit de merge explícito (--no-ff).
