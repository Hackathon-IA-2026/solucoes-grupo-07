# Etapa 2B — relatório factual de execução (CurtaMap)

Redigido em 24/09/2026, na sessão 05. Máquina dedicada Windows 11 (Ryzen 5 5600X, 32 GB). Raiz
externa `Y:\CurtaMap Etapa 2B`. Este relatório substitui o rascunho
`relatorio-etapa-2b-sessao03.md`, que fica preservado.

**Natureza do documento.** O relatório descreve o que foi executado e medido. Ele **não escolhe
vencedor**, não aplica os critérios do §11 do protocolo e não interpreta desempenho. Os números
das tabelas foram copiados dos JSON de métricas das runs, sem arredondamento além das casas
exibidas. O teste reservado (maio–agosto/2026) não foi executado nem pontuado.

## 1. Estado e escopo

- **Mínimo do §12.4 executado:**
  - fontes: duas (eólica e fotovoltaica);
  - famílias: duas (`linear` e `lightgbm`);
  - tarefas: `restricao_registrada`, `corte_positivo`, `volume_condicional` e `causa`, mais
    quatro pipelines de volume;
  - rodadas: V1–V4;
  - quatro baselines, calibração binária, métricas com recortes, diagnósticos de volume e
    sensibilidade `noturno_mais_24h` com modelos congelados.
- **Runs válidas:** 8 principais e 8 sensibilidades, todas com `status=complete`,
  `failures=[]` e exit 0. A lista está na §8.
- **Tentativas preservadas e não utilizáveis como resultado:** `main-eolica-v1-001`, `-v2-001`,
  `-v2-002` e `-v2-003` (ver §13).
- **Recomendado não executado:** repetição com as sementes 17 e 101 e intervalo de volume.
- **Opcional não executado:** origem e sensibilidade +72h (`optional_*_enabled=false`).
- **Adiado pelo protocolo:** meteorologia, novas famílias, modelos por horizonte e coleta
  das 12h.
- **Desvio aprovado relevante:** amostragem de emissões t0 no treino (§4).

## 2. Proveniência

| Item | Commit / hash |
|---|---|
| Branch | `etapa-2-experimental` (sem push; `main` em `48f9923`, intocada) |
| Dataset `noturno_dia_util` eólico | geração `70a181d`; verificação `a5b4a87` (18/18) |
| Dataset `noturno_dia_util` solar | geração e verificação `2e79475` (18/18) |
| Datasets `noturno_mais_24h` eólico e solar | geração e verificação `88634ed` (18/18 cada) |
| Medição de populações | eólica `ea88fe7`; solar `2e79475` |
| `main-eolica-v1-002` | `560ae70` (amostragem com pushdown; métricas **antes** da otimização `c73302e`) |
| Demais 7 principais e 8 sensibilidades | `88634ed` (métricas otimizadas `c73302e` + marcadores de fase) |
| Configuração resolvida | `configuration_sha256 = 1ed847278be8…` (idêntico nas 16 runs) |
| Dados brutos (`data_hashes`) | eólica `487050da7ed2…`; fotovoltaica `e293594146a2…` (idênticos nas 16 runs) |
| Calendário | `curtamap-conservador-2023-2026-v1`, SHA-256 `8c3f500b7ca9…` |
| Protocolo | `stage2a-fe71446d` |

- **Equivalência numérica entre `560ae70` e `88634ed`:** está sustentada por testes de
  paridade exata contra o oráculo congelado `tests/reference_metrics_stage2b.py` (commit
  `c73302e`). As runs não foram reexecutadas para comparar.
- **`88634ed`:** acrescenta apenas marcadores de fase no stderr.
- **Branch `codex/otimize-metricas-validacao`:** contém só diário e script operacional desde a
  base `c73302e`. Foi integrada na sessão 05 pelo merge `1fba2f6`, e o código Python
  resultante é idêntico ao `88634ed` (`git diff 88634ed HEAD -- src tests configs` vazio).

## 3. Ambiente

- Windows 11 Pro, Python 3.12.12 e uv 0.9.15.
- Bibliotecas: LightGBM 4.7.0, scikit-learn 1.9.1, Polars 1.44.2, DuckDB 1.5.5 e NumPy 2.3.5,
  conforme o `uv.lock`.
- `threads=6`, `duckdb_memory_limit=22GB`, `feature_workers=6`, semente 42.
- LightGBM: `n_jobs=6`, `deterministic=True`, `force_row_wise=True` (commit `f36d5f6`).
- A fila rodou pelo Agendador de Tarefas (`CurtaMap-Fila-2B`, prioridade normal, sem
  gatilho), fora de qualquer app, a partir de 24/09 06h22.
- Suspensão e hibernação ficaram desativadas durante as runs.

## 4. Protocolo e desvios

1. **Amostragem de t0 no treino (desvio do §12.1, "todos os elegíveis")**, aprovada pelo
   responsável em 23/09.
   - Método `t0_sistematico_diario_v1`, semente 42.
   - Aplicada só aos segmentos initial e refit; tuning, calibração e validação completos.
   - Eólica: ocorrências 4/48, volume e causa 14/48.
   - Solar: ocorrências 16/48, volume e causa 48/48 (sem amostragem).
   - Verificação na §7.
2. **LightGBM com 6 threads determinísticas.** É repetível com o mesmo número de threads, mas
   não é numericamente igual ao piloto em `n_jobs=1`.
3. **Piloto solar dispensado:** a primeira campanha solar exercitou o mesmo caminho técnico.
4. **Código e commits criados na máquina dedicada.** O §13.3 previa que ela não criaria
   commits; na prática, as correções operacionais e de desempenho foram feitas e commitadas
   aqui (`40cb438`, `f36d5f6`, `560ae70`, `c73302e` e `88634ed`), com TDD e registro no diário.
   A 2C deve tratar isso como desvio de processo.
5. **Limitações herdadas do handoff original**, mantidas explícitas e não corrigidas:
   - os baselines de ocorrência usam limiar fixo de 0,5, e o código aplica `threshold or 0.5`
     quando não há limiar calibrado;
   - as features são um subconjunto das previstas no protocolo;
   - há recortes vazios ou ausentes na sensibilidade (§11 e §12);
   - a elegibilidade é definida por t0;
   - o volume condicional é avaliado em todas as linhas (`mae_full`), além da métrica
     condicional;
   - há avisos de depreciação no stderr (§13).

## 5. Datasets e contratos

| Dataset | Partições | Primeira partição | Linhas / emissões | Geração (s) | Verificação |
|---|---|---|---|---|---|
| `noturno_dia_util` eólica | 942 (sem 01/10/2023) | 02/10/2023 | 339.738.048 linhas | — (sessão 02) | 18/18, `a5b4a87` |
| `noturno_dia_util` solar | 759 (sem 01/04/2024) | 02/04/2024 | 114.382.944 features; 2.382.978 emissões | 2.424,2 | 18/18, 121,1 s |
| `noturno_mais_24h` eólica | 941 (sem 01 e 02/10/2023) | 03/10/2023 | 7.069.236 emissões; 1.357.293.312 linhas de baseline | 7.407,9 | 18/18, 302,4 s |
| `noturno_mais_24h` solar | 758 (sem 01 e 02/04/2024) | 03/04/2024 | 2.379.042 emissões; 456.776.064 linhas de baseline | 2.190,3 | 18/18, 90,7 s |

- **Checagens dos quatro contratos:** partições completas, schema único, t0 no intervalo,
  nenhum t0 no período reservado, exatamente 48 horizontes, contrato de tau, nenhum histórico
  após t0, rótulos liberados depois de t0, nenhuma PAR, 4 baselines por requisição com valores
  finitos, primeira liberação igual ao calendário e validação sem tau reservado.
- **Relatórios:** `execucao/verificacoes/dataset-*.json`.
- **Contagens do +24h:** nos dois datasets `noturno_mais_24h`, a coluna "Linhas / emissões"
  traz o total de linhas de baseline informado pelo stdout da geração.

## 6. Pilotos

- **`pilot-eolica-001`** (commit `48bc71a`): 8 ajustes, zero falhas, 60,5 s, pico de 1,72 GB e
  auditoria de hashes e recarga aprovada.
  - O recorte `head2M` tinha **zero** linhas elegíveis, então o piloto é apenas técnico e não
    representa treino.
  - O LightGBM efetivo usou `n_jobs=1`.
- **`pilot-fotovoltaica-001`:** dispensado (§4).

## 7. Populações e cortes

- **Fronteiras (iguais para as duas fontes):**
  - V1 valida de 01/01/2025 a 30/04/2025 (cutoff 30/12/2024);
  - V2, de 01/05 a 31/08/2025;
  - V3, de 01/09 a 31/12/2025;
  - V4, de 01/01 a 30/04/2026.
  - Em cada rodada, tuning começa cerca de 8 semanas antes do cutoff e calibração, cerca de
    4 semanas antes. Os valores exatos estão em `reports/*.json → boundaries`.
- **Populações medidas:** `execucao/medicoes/populacoes-noturno_dia_util-{eolica,fotovoltaica}-001.json`.

**Conferência de `training_rows` contra as populações medidas** (auditoria `auditoria-runs-2b-001`):

| Verificação | Resultado nas 8 runs |
|---|---|
| Linhas de tuning e calibração = população medida | idênticas em todas as tarefas |
| `validation_rows` = `prediction_rows` medido | idênticas (eólica 42.851.184 / 43.830.768 / 43.109.184 / 42.194.016; solar 17.781.648 / 18.273.840 / 19.344.336 / 20.417.904) |
| Razão amostrada/medida em initial/refit, ocorrências eólica | 0,0833 (esperado 4/48 = 0,0833) |
| Idem, volume e causa eólica | 0,2911–0,2916 (esperado 14/48 = 0,2917) |
| Idem, ocorrências solar | 0,3333–0,3334 (esperado 16/48) |
| Volume e causa solar | idênticos à população (48/48) |
| Prevalência amostrada vs. completa (ocorrências) | diferença absoluta ≤ 0,0004 |

Exemplos (refit, `corte_positivo`, prevalência amostrada / completa):

| Fonte | V1 | V2 | V3 | V4 |
|---|---|---|---|---|
| Eólica | 0,1463 / 0,1462 | 0,1626 / 0,1623 | 0,1894 / 0,1891 | 0,2396 / 0,2393 |
| Solar | 0,1132 / 0,1131 | 0,1198 / 0,1197 | 0,1446 / 0,1445 | 0,1771 / 0,1770 |

- **Deslocamento de prevalência entre segmentos:** a prevalência de tuning e calibração difere
  bastante da de initial. Exemplo: eólica V3, `corte_positivo` 0,4024 no tuning e 0,4754 na
  calibração, contra 0,1800 no initial. Isso vem da população, não da amostragem, e deve ser
  considerado na leitura da calibração.

## 8. Execução principal

| Run | Fonte/rodada | Commit | Início → fim | Duração (s) | Status |
|---|---|---|---|---|---|
| `main-eolica-v1-002` | eólica V1 | `560ae70` | 23/09 19h03 → 22h53 | 13.835,3 | complete |
| `main-eolica-v2-004` | eólica V2 | `88634ed` | 24/09 06h22 → 07h30 | 4.072,3 | complete |
| `main-eolica-v3-001` | eólica V3 | `88634ed` | 07h30 → 08h55 | 5.066,8 | complete |
| `main-eolica-v4-001` | eólica V4 | `88634ed` | 08h55 → 10h19 | 5.066,7 | complete |
| `main-fotovoltaica-v1-001` | solar V1 | `88634ed` | 10h19 → 10h50 | 1.840,0 | complete |
| `main-fotovoltaica-v2-001` | solar V2 | `88634ed` | 10h50 → 11h24 | 1.991,1 | complete |
| `main-fotovoltaica-v3-001` | solar V3 | `88634ed` | 11h24 → 12h14 | 3.014,9 | complete |
| `main-fotovoltaica-v4-001` | solar V4 | `88634ed` | 12h14 → 13h26 | 4.339,8 | complete |

- **Conteúdo de cada run** (54 arquivos com checksum):
  - 8 modelos (`.joblib`);
  - previsões Parquet;
  - 28 arquivos de métricas: 8 de modelos, 4 pipelines de volume e 16 de baselines;
  - 4 diagnósticos de volume;
  - relatório e manifest.
- **Durações por fase** (marcadores `[curtamap-fase]`; a V1 não tem marcadores):

| run | duração total (s) | preparação+treino | previsão | métricas modelos | pipelines | baselines | relatório | soma fit_seconds | pico processo (GiB) | pico árvore amostrado (GiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| main-eolica-v1-002 | 13835.3 | — | — | — | — | — | — | 1308.9 | 12.61 | 10.61 |
| main-eolica-v2-004 | 4072.3 | 2343 | 749 | 305 | 152 | 504 | 0 | 2329.3 | 15.75 | 13.60 |
| main-eolica-v3-001 | 5066.8 | 3374 | 685 | 332 | 153 | 499 | 0 | 3358.0 | 18.77 | 14.56 |
| main-eolica-v4-001 | 5066.7 | 3613 | 598 | 251 | 144 | 446 | 0 | 3592.5 | 22.02 | 17.01 |
| main-fotovoltaica-v1-001 | 1840.0 | 1187 | 282 | 128 | 58 | 167 | 0 | 1181.8 | 9.80 | 7.09 |
| main-fotovoltaica-v2-001 | 1991.1 | 1344 | 250 | 135 | 61 | 184 | 0 | 1338.5 | 14.77 | 10.21 |
| main-fotovoltaica-v3-001 | 3014.9 | 2230 | 332 | 153 | 69 | 198 | 0 | 2223.3 | 19.75 | 17.41 |
| main-fotovoltaica-v4-001 | 4339.8 | 3553 | 358 | 154 | 69 | 197 | 0 | 3541.3 | 24.06 | 18.49 |

- **Peso de cada fase:** nas 7 runs com marcadores, preparação e treino somam de 58% a 82% da
  duração. A V1 levou 13.835 s, com 1.309 s de `fit`. Ela é anterior à otimização de métricas
  e à troca de lançador, então sua duração não é comparável às demais.

## 9. Baselines e resultados factuais

- **O que as tabelas mostram:** o recorte `global` de cada run principal (cenário
  `noturno_dia_util`) e, nas colunas "+24h", o mesmo modelo congelado no cenário
  `noturno_mais_24h`.
- **Limitações de leitura:**
  - não há ordenação nem julgamento;
  - baselines de ocorrência usam limiar fixo de 0,5 (§4);
  - AP é a integral em degraus (`average_precision`), não a trapezoidal;
  - "MAE total" (`mae_full`) cobre todos os volumes válidos, e "MAE condicional" só as
    linhas com alvo > 0;
  - `volume-A-B` é o pipeline com ocorrência da família A e volume da família B;
  - `volume_condicional-F` é o regressor condicional avaliado sozinho em todas as linhas.
- **Causa:** nos baselines `ultimo_valor` e `mesmo_horario_recente`, os valores de causa são, nas 8 runs,
  idênticos. Isso é um fato dos arquivos; a razão não foi investigada.
- **Linhas completas:** os recortes por horizonte, faixa, painel, idade, episódio e cauda
  estão em `experimentos/<run>/metrics/*.json`, com 63 ou 64 recortes por arquivo.
- **Resumo por rodada:** o protocolo pede média de V1–V4, desvio, mínimo/máximo e diferenças
  pareadas. Isso **não foi calculado aqui**; fica para a 2C.


#### eolica V1 — `main-eolica-v1-002` (sensibilidade: `delay-eolica-v1-001`)


restricao_registrada (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.4215 | 0.1692 | 0.2112 | 0.3003 | 0.8157 | 0.6073 | 0.2391 | 42.687.648 | 0.4003 | 0.1780 | 0.8717 |
| modelo lightgbm | 0.3954 | 0.1749 | 0.2405 | 0.2755 | 0.8648 | 0.6057 | 0.2391 | 42.687.648 | 0.3851 | 0.1796 | 0.9076 |
| baseline ultimo_valor | 0.3279 | 0.2364 | 0.5000 | 0.5086 | 0.3295 | 0.3545 | 0.2391 | 42.687.648 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.4182 | 0.1743 | 0.5000 | 0.4315 | 0.3607 | 0.3729 | 0.2391 | 42.687.648 | — | — | — |
| baseline mesmo_horario_recente | 0.3624 | 0.2402 | 0.5000 | 0.4976 | 0.4771 | 0.4811 | 0.2391 | 42.687.648 | — | — | — |
| baseline historico | 0.4197 | 0.1739 | 0.5000 | 0.4315 | 0.3588 | 0.3713 | 0.2391 | 42.687.648 | — | — | — |

corte_positivo (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.3882 | 0.1462 | 0.1568 | 0.2767 | 0.7469 | 0.5575 | 0.1993 | 42.687.648 | 0.3660 | 0.1528 | 0.8166 |
| modelo lightgbm | 0.3343 | 0.1648 | 0.1702 | 0.2297 | 0.9009 | 0.5686 | 0.1993 | 42.687.648 | 0.3208 | 0.1719 | 0.9131 |
| baseline ultimo_valor | 0.2771 | 0.2067 | 0.5000 | 0.4696 | 0.2879 | 0.3121 | 0.1993 | 42.687.648 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.3828 | 0.1512 | 0.5000 | 0.4137 | 0.2935 | 0.3116 | 0.1993 | 42.687.648 | — | — | — |
| baseline mesmo_horario_recente | 0.3158 | 0.2136 | 0.5000 | 0.4626 | 0.4426 | 0.4465 | 0.1993 | 42.687.648 | — | — | — |
| baseline historico | 0.3848 | 0.1508 | 0.5000 | 0.4136 | 0.2916 | 0.3099 | 0.1993 | 42.687.648 | — | — | — |

volume (recorte global; MAE em MWmed)

| origem | MAE total | MAE condicional | WAPE | viés | cobertura | suporte | MAE total +24h | WAPE +24h |
|---|---|---|---|---|---|---|---|---|
| volume-linear-linear | 16.19 | 44.78 | 1.5859 | 1.58 | 0.9962 | 42.687.648 | 17.90 | 1.7538 |
| volume-linear-lightgbm | 13.47 | 42.35 | 1.3191 | -2.67 | 0.9962 | 42.687.648 | 14.13 | 1.3842 |
| volume-lightgbm-linear | 19.11 | 45.37 | 1.8725 | 5.33 | 0.9962 | 42.687.648 | 20.47 | 2.0052 |
| volume-lightgbm-lightgbm | 15.41 | 41.41 | 1.5100 | 0.04 | 0.9962 | 42.687.648 | 15.69 | 1.5376 |
| volume_condicional-linear | 39.23 | 46.51 | 3.8428 | 30.59 | 0.9962 | 42.687.648 | 41.02 | 4.0190 |
| volume_condicional-lightgbm | 30.96 | 37.35 | 3.0331 | 20.50 | 0.9962 | 42.687.648 | 30.68 | 3.0057 |
| baseline ultimo_valor | 12.93 | 45.81 | 1.2668 | -1.56 | 0.9962 | 42.687.648 | — | — |
| baseline mesmo_horario_dia_anterior | 13.63 | 41.32 | 1.3351 | -0.91 | 0.9962 | 42.687.648 | — | — |
| baseline mesmo_horario_recente | 12.84 | 41.68 | 1.2583 | 0.08 | 0.9962 | 42.687.648 | — | — |
| baseline historico | 13.65 | 41.41 | 1.3369 | -0.95 | 0.9962 | 42.687.648 | — | — |

causa (recorte global)

| origem | macro-F1 | recall REL | recall CNF | recall ENE | suporte | macro-F1 +24h |
|---|---|---|---|---|---|---|
| modelo linear | 0.3319 | 0.0011 | 0.8796 | 0.4077 | 10.205.443 | 0.3714 |
| modelo lightgbm | 0.3603 | 0.0032 | 0.8639 | 0.4957 | 10.205.443 | 0.3675 |
| baseline ultimo_valor | 0.6081 | 0.6711 | 0.6364 | 0.5330 | 10.205.443 | — |
| baseline mesmo_horario_dia_anterior | 0.5263 | 0.4627 | 0.5813 | 0.5478 | 10.205.443 | — |
| baseline mesmo_horario_recente | 0.6081 | 0.6711 | 0.6364 | 0.5330 | 10.205.443 | — |
| baseline historico | 0.5247 | 0.4576 | 0.5817 | 0.5478 | 10.205.443 | — |

#### eolica V2 — `main-eolica-v2-004` (sensibilidade: `delay-eolica-v2-001`)


restricao_registrada (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.6420 | 0.2386 | 0.1403 | 0.5037 | 0.9812 | 0.8248 | 0.4664 | 43.503.696 | 0.6339 | 0.2314 | 0.9842 |
| modelo lightgbm | 0.7133 | 0.2044 | 0.1283 | 0.5021 | 0.9860 | 0.8267 | 0.4664 | 43.503.696 | 0.6821 | 0.2118 | 0.9866 |
| baseline ultimo_valor | 0.5533 | 0.3677 | 0.5000 | 0.7049 | 0.3642 | 0.4032 | 0.4664 | 43.503.696 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.8309 | 0.1438 | 0.5000 | 0.8029 | 0.7575 | 0.7661 | 0.4664 | 43.503.696 | — | — | — |
| baseline mesmo_horario_recente | 0.6632 | 0.2500 | 0.5000 | 0.7463 | 0.7030 | 0.7113 | 0.4664 | 43.503.696 | — | — | — |
| baseline historico | 0.8347 | 0.1435 | 0.5000 | 0.8028 | 0.7569 | 0.7657 | 0.4664 | 43.503.696 | — | — | — |

corte_positivo (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.5676 | 0.2212 | 0.1217 | 0.4242 | 0.9721 | 0.7726 | 0.3852 | 43.503.696 | 0.5613 | 0.2206 | 0.9791 |
| modelo lightgbm | 0.5748 | 0.2167 | 0.1095 | 0.4127 | 0.9889 | 0.7730 | 0.3852 | 43.503.696 | 0.5594 | 0.2181 | 0.9867 |
| baseline ultimo_valor | 0.4497 | 0.3453 | 0.5000 | 0.6099 | 0.2871 | 0.3211 | 0.3852 | 43.503.696 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.7759 | 0.1445 | 0.5000 | 0.7577 | 0.6741 | 0.6893 | 0.3852 | 43.503.696 | — | — | — |
| baseline mesmo_horario_recente | 0.5766 | 0.2525 | 0.5000 | 0.6832 | 0.6422 | 0.6500 | 0.3852 | 43.503.696 | — | — | — |
| baseline historico | 0.7816 | 0.1441 | 0.5000 | 0.7577 | 0.6732 | 0.6886 | 0.3852 | 43.503.696 | — | — | — |

volume (recorte global; MAE em MWmed)

| origem | MAE total | MAE condicional | WAPE | viés | cobertura | suporte | MAE total +24h | WAPE +24h |
|---|---|---|---|---|---|---|---|---|
| volume-linear-linear | 22.74 | 38.13 | 1.1690 | -3.38 | 0.9925 | 43.503.696 | 24.16 | 1.2427 |
| volume-linear-lightgbm | 21.89 | 39.13 | 1.1253 | -5.98 | 0.9925 | 43.503.696 | 22.74 | 1.1696 |
| volume-lightgbm-linear | 22.42 | 38.28 | 1.1527 | -4.46 | 0.9925 | 43.503.696 | 22.98 | 1.1819 |
| volume-lightgbm-lightgbm | 21.73 | 39.43 | 1.1171 | -6.81 | 0.9925 | 43.503.696 | 21.98 | 1.1302 |
| volume_condicional-linear | 39.42 | 34.95 | 2.0261 | 24.74 | 0.9925 | 43.503.696 | 40.10 | 2.0622 |
| volume_condicional-lightgbm | 36.22 | 34.49 | 1.8621 | 18.98 | 0.9925 | 43.503.696 | 35.88 | 1.8451 |
| baseline ultimo_valor | 21.98 | 47.18 | 1.1301 | -9.58 | 0.9925 | 43.503.696 | — | — |
| baseline mesmo_horario_dia_anterior | 16.72 | 33.51 | 0.8597 | -4.28 | 0.9925 | 43.503.696 | — | — |
| baseline mesmo_horario_recente | 20.72 | 41.41 | 1.0651 | -1.44 | 0.9925 | 43.503.696 | — | — |
| baseline historico | 16.72 | 33.50 | 0.8597 | -4.32 | 0.9925 | 43.503.696 | — | — |

causa (recorte global)

| origem | macro-F1 | recall REL | recall CNF | recall ENE | suporte | macro-F1 +24h |
|---|---|---|---|---|---|---|
| modelo linear | 0.4161 | 0.0793 | 0.9154 | 0.3696 | 20.290.779 | 0.4315 |
| modelo lightgbm | 0.4069 | 0.0861 | 0.9536 | 0.3323 | 20.290.779 | 0.4190 |
| baseline ultimo_valor | 0.5030 | 0.2554 | 0.7053 | 0.5910 | 20.290.779 | — |
| baseline mesmo_horario_dia_anterior | 0.5783 | 0.1406 | 0.7083 | 0.8362 | 20.290.779 | — |
| baseline mesmo_horario_recente | 0.5030 | 0.2554 | 0.7053 | 0.5910 | 20.290.779 | — |
| baseline historico | 0.5766 | 0.1357 | 0.7107 | 0.8361 | 20.290.779 | — |

#### eolica V3 — `main-eolica-v3-001` (sensibilidade: `delay-eolica-v3-001`)


restricao_registrada (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.7340 | 0.2237 | 0.2491 | 0.5519 | 0.9889 | 0.8537 | 0.5325 | 42.945.648 | 0.7314 | 0.2337 | 0.9942 |
| modelo lightgbm | 0.7937 | 0.2068 | 0.1511 | 0.6154 | 0.9304 | 0.8440 | 0.5325 | 42.945.648 | 0.7760 | 0.2136 | 0.9268 |
| baseline ultimo_valor | 0.6285 | 0.3904 | 0.5000 | 0.8051 | 0.3521 | 0.3967 | 0.5325 | 42.945.648 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.9206 | 0.1027 | 0.5000 | 0.8485 | 0.9001 | 0.8893 | 0.5325 | 42.945.648 | — | — | — |
| baseline mesmo_horario_recente | 0.7909 | 0.1686 | 0.5000 | 0.8371 | 0.8484 | 0.8461 | 0.5325 | 42.945.648 | — | — | — |
| baseline historico | 0.9232 | 0.1022 | 0.5000 | 0.8486 | 0.9003 | 0.8895 | 0.5325 | 42.945.648 | — | — | — |

corte_positivo (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.6716 | 0.2221 | 0.2321 | 0.4982 | 0.9841 | 0.8235 | 0.4746 | 42.945.648 | 0.6682 | 0.2305 | 0.9894 |
| modelo lightgbm | 0.8075 | 0.1811 | 0.2339 | 0.6853 | 0.8213 | 0.7899 | 0.4746 | 42.945.648 | 0.7794 | 0.1908 | 0.8215 |
| baseline ultimo_valor | 0.5559 | 0.3811 | 0.5000 | 0.7490 | 0.2962 | 0.3369 | 0.4746 | 42.945.648 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.8833 | 0.1168 | 0.5000 | 0.8063 | 0.8635 | 0.8515 | 0.4746 | 42.945.648 | — | — | — |
| baseline mesmo_horario_recente | 0.7317 | 0.1915 | 0.5000 | 0.7933 | 0.8066 | 0.8039 | 0.4746 | 42.945.648 | — | — | — |
| baseline historico | 0.8865 | 0.1163 | 0.5000 | 0.8061 | 0.8637 | 0.8515 | 0.4746 | 42.945.648 | — | — | — |

volume (recorte global; MAE em MWmed)

| origem | MAE total | MAE condicional | WAPE | viés | cobertura | suporte | MAE total +24h | WAPE +24h |
|---|---|---|---|---|---|---|---|---|
| volume-linear-linear | 32.06 | 40.19 | 1.1348 | 1.11 | 0.9962 | 42.945.648 | 33.66 | 1.1914 |
| volume-linear-lightgbm | 30.63 | 41.01 | 1.0842 | -3.54 | 0.9962 | 42.945.648 | 31.50 | 1.1150 |
| volume-lightgbm-linear | 25.58 | 40.09 | 0.9054 | -6.25 | 0.9962 | 42.945.648 | 26.73 | 0.9461 |
| volume-lightgbm-lightgbm | 25.07 | 41.03 | 0.8873 | -9.76 | 0.9962 | 42.945.648 | 25.94 | 0.9183 |
| volume_condicional-linear | 44.71 | 39.48 | 1.5826 | 24.48 | 0.9962 | 42.945.648 | 45.75 | 1.6196 |
| volume_condicional-lightgbm | 40.86 | 38.02 | 1.4466 | 17.08 | 0.9962 | 42.945.648 | 40.97 | 1.4502 |
| baseline ultimo_valor | 26.40 | 51.63 | 0.9345 | -18.47 | 0.9962 | 42.945.648 | — | — |
| baseline mesmo_horario_dia_anterior | 20.09 | 32.49 | 0.7113 | 0.95 | 0.9962 | 42.945.648 | — | — |
| baseline mesmo_horario_recente | 22.43 | 39.05 | 0.7940 | 0.46 | 0.9962 | 42.945.648 | — | — |
| baseline historico | 20.11 | 32.48 | 0.7119 | 0.95 | 0.9962 | 42.945.648 | — | — |

causa (recorte global)

| origem | macro-F1 | recall REL | recall CNF | recall ENE | suporte | macro-F1 +24h |
|---|---|---|---|---|---|---|
| modelo linear | 0.4134 | 0.0000 | 0.8927 | 0.4031 | 22.867.317 | 0.4363 |
| modelo lightgbm | 0.3976 | 0.0000 | 0.8285 | 0.4094 | 22.867.317 | 0.3910 |
| baseline ultimo_valor | 0.4323 | 0.0485 | 0.6916 | 0.5582 | 22.867.317 | — |
| baseline mesmo_horario_dia_anterior | 0.5024 | 0.0262 | 0.6691 | 0.8076 | 22.867.317 | — |
| baseline mesmo_horario_recente | 0.4323 | 0.0485 | 0.6916 | 0.5582 | 22.867.317 | — |
| baseline historico | 0.5012 | 0.0232 | 0.6705 | 0.8076 | 22.867.317 | — |

#### eolica V4 — `main-eolica-v4-001` (sensibilidade: `delay-eolica-v4-001`)


restricao_registrada (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.4307 | 0.2099 | 0.2059 | 0.3689 | 0.9601 | 0.7271 | 0.3270 | 42.030.480 | 0.4283 | 0.2102 | 0.9716 |
| modelo lightgbm | 0.4246 | 0.2168 | 0.1783 | 0.3866 | 0.8302 | 0.6753 | 0.3270 | 42.030.480 | 0.4210 | 0.2198 | 0.8159 |
| baseline ultimo_valor | 0.3652 | 0.3149 | 0.5000 | 0.5655 | 0.1603 | 0.1871 | 0.3270 | 42.030.480 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.7414 | 0.1346 | 0.5000 | 0.7005 | 0.7331 | 0.7263 | 0.3270 | 42.030.480 | — | — | — |
| baseline mesmo_horario_recente | 0.5735 | 0.2037 | 0.5000 | 0.6987 | 0.6631 | 0.6699 | 0.3270 | 42.030.480 | — | — | — |
| baseline historico | 0.7444 | 0.1344 | 0.5000 | 0.7003 | 0.7321 | 0.7255 | 0.3270 | 42.030.480 | — | — | — |

corte_positivo (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.3951 | 0.1990 | 0.2065 | 0.3378 | 0.9566 | 0.7002 | 0.2947 | 42.030.480 | 0.3917 | 0.1998 | 0.9709 |
| modelo lightgbm | 0.3834 | 0.1995 | 0.2042 | 0.3451 | 0.9165 | 0.6885 | 0.2947 | 42.030.480 | 0.3816 | 0.2006 | 0.9112 |
| baseline ultimo_valor | 0.3266 | 0.2913 | 0.5000 | 0.5212 | 0.1410 | 0.1651 | 0.2947 | 42.030.480 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.7020 | 0.1333 | 0.5000 | 0.6757 | 0.6767 | 0.6765 | 0.2947 | 42.030.480 | — | — | — |
| baseline mesmo_horario_recente | 0.5228 | 0.2055 | 0.5000 | 0.6597 | 0.6249 | 0.6316 | 0.2947 | 42.030.480 | — | — | — |
| baseline historico | 0.7054 | 0.1331 | 0.5000 | 0.6758 | 0.6753 | 0.6754 | 0.2947 | 42.030.480 | — | — | — |

volume (recorte global; MAE em MWmed)

| origem | MAE total | MAE condicional | WAPE | viés | cobertura | suporte | MAE total +24h | WAPE +24h |
|---|---|---|---|---|---|---|---|---|
| volume-linear-linear | 18.10 | 31.05 | 1.5397 | 1.69 | 0.9961 | 42.030.480 | 18.83 | 1.6023 |
| volume-linear-lightgbm | 16.35 | 32.39 | 1.3913 | -1.77 | 0.9961 | 42.030.480 | 16.67 | 1.4182 |
| volume-lightgbm-linear | 18.08 | 31.04 | 1.5382 | 1.69 | 0.9961 | 42.030.480 | 18.29 | 1.5559 |
| volume-lightgbm-lightgbm | 16.28 | 32.38 | 1.3852 | -1.84 | 0.9961 | 42.030.480 | 16.26 | 1.3833 |
| volume_condicional-linear | 40.77 | 34.32 | 3.4685 | 32.57 | 0.9961 | 42.030.480 | 40.99 | 3.4871 |
| volume_condicional-lightgbm | 32.98 | 30.88 | 2.8056 | 21.90 | 0.9961 | 42.030.480 | 32.32 | 2.7495 |
| baseline ultimo_valor | 13.64 | 38.77 | 1.1604 | -6.91 | 0.9961 | 42.030.480 | — | — |
| baseline mesmo_horario_dia_anterior | 13.00 | 29.96 | 1.1065 | -0.94 | 0.9961 | 42.030.480 | — | — |
| baseline mesmo_horario_recente | 13.73 | 34.39 | 1.1680 | -1.21 | 0.9961 | 42.030.480 | — | — |
| baseline historico | 13.01 | 29.98 | 1.1068 | -0.96 | 0.9961 | 42.030.480 | — | — |

causa (recorte global)

| origem | macro-F1 | recall REL | recall CNF | recall ENE | suporte | macro-F1 +24h |
|---|---|---|---|---|---|---|
| modelo linear | 0.4825 | 0.3003 | 0.5759 | 0.6261 | 13.743.836 | 0.4691 |
| modelo lightgbm | 0.4515 | 0.2048 | 0.3869 | 0.7487 | 13.743.836 | 0.3453 |
| baseline ultimo_valor | 0.5113 | 0.3256 | 0.4479 | 0.7741 | 13.743.836 | — |
| baseline mesmo_horario_dia_anterior | 0.5165 | 0.1293 | 0.4785 | 0.8988 | 13.743.836 | — |
| baseline mesmo_horario_recente | 0.5113 | 0.3256 | 0.4479 | 0.7741 | 13.743.836 | — |
| baseline historico | 0.5165 | 0.1270 | 0.4825 | 0.8988 | 13.743.836 | — |

#### fotovoltaica V1 — `main-fotovoltaica-v1-001` (sensibilidade: `delay-fotovoltaica-v1-001`)


restricao_registrada (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.2379 | 0.1291 | 0.1333 | 0.1645 | 0.9779 | 0.4916 | 0.1546 | 17.781.648 | 0.2361 | 0.1329 | 0.9863 |
| modelo lightgbm | 0.5328 | 0.0999 | 0.1160 | 0.3141 | 0.8217 | 0.6209 | 0.1546 | 17.781.648 | 0.4878 | 0.1044 | 0.8234 |
| baseline ultimo_valor | 0.1546 | 0.1546 | 0.5000 | — | 0.0000 | 0.0000 | 0.1546 | 17.781.648 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.4688 | 0.1032 | 0.5000 | 0.4692 | 0.3879 | 0.4019 | 0.1546 | 17.781.648 | — | — | — |
| baseline mesmo_horario_recente | 0.2853 | 0.1652 | 0.5000 | 0.4625 | 0.4246 | 0.4317 | 0.1546 | 17.781.648 | — | — | — |
| baseline historico | 0.4688 | 0.1032 | 0.5000 | 0.4692 | 0.3879 | 0.4019 | 0.1546 | 17.781.648 | — | — | — |

corte_positivo (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.2071 | 0.1086 | 0.1040 | 0.1469 | 0.8559 | 0.4355 | 0.1233 | 17.781.648 | 0.1977 | 0.1170 | 0.9034 |
| modelo lightgbm | 0.4423 | 0.0891 | 0.0901 | 0.2577 | 0.8143 | 0.5686 | 0.1233 | 17.781.648 | 0.3859 | 0.0943 | 0.8239 |
| baseline ultimo_valor | 0.1233 | 0.1233 | 0.5000 | — | 0.0000 | 0.0000 | 0.1233 | 17.781.648 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.4289 | 0.0869 | 0.5000 | 0.4507 | 0.3177 | 0.3377 | 0.1233 | 17.781.648 | — | — | — |
| baseline mesmo_horario_recente | 0.2467 | 0.1385 | 0.5000 | 0.4332 | 0.3982 | 0.4048 | 0.1233 | 17.781.648 | — | — | — |
| baseline historico | 0.4289 | 0.0869 | 0.5000 | 0.4507 | 0.3177 | 0.3377 | 0.1233 | 17.781.648 | — | — | — |

volume (recorte global; MAE em MWmed)

| origem | MAE total | MAE condicional | WAPE | viés | cobertura | suporte | MAE total +24h | WAPE +24h |
|---|---|---|---|---|---|---|---|---|
| volume-linear-linear | 857.83 | 2143.64 | 66.0426 | 840.95 | 1.0000 | 17.781.648 | 1133.78 | 87.2643 |
| volume-linear-lightgbm | 21.30 | 91.19 | 1.6400 | -0.77 | 1.0000 | 17.781.648 | 23.26 | 1.7902 |
| volume-lightgbm-linear | 1152.26 | 4943.95 | 88.7101 | 1137.04 | 1.0000 | 17.781.648 | 1394.54 | 107.3349 |
| volume-lightgbm-lightgbm | 18.20 | 86.37 | 1.4014 | -1.97 | 1.0000 | 17.781.648 | 19.20 | 1.4779 |
| volume_condicional-linear | 4693.87 | 11527.48 | 361.3709 | 4687.18 | 1.0000 | 17.781.648 | 5121.12 | 394.1616 |
| volume_condicional-lightgbm | 68.77 | 68.73 | 5.2947 | 57.08 | 1.0000 | 17.781.648 | 67.81 | 5.2189 |
| baseline ultimo_valor | 12.99 | 105.33 | 1.0000 | -12.99 | 1.0000 | 17.781.648 | — | — |
| baseline mesmo_horario_dia_anterior | 15.44 | 75.10 | 1.1888 | -0.94 | 1.0000 | 17.781.648 | — | — |
| baseline mesmo_horario_recente | 15.96 | 83.93 | 1.2289 | -0.15 | 1.0000 | 17.781.648 | — | — |
| baseline historico | 15.44 | 75.10 | 1.1888 | -0.94 | 1.0000 | 17.781.648 | — | — |

causa (recorte global)

| origem | macro-F1 | recall REL | recall CNF | recall ENE | suporte | macro-F1 +24h |
|---|---|---|---|---|---|---|
| modelo linear | 0.4108 | 0.1166 | 0.6957 | 0.5801 | 2.749.101 | 0.4376 |
| modelo lightgbm | 0.3482 | 0.0009 | 0.6013 | 0.6831 | 2.749.101 | 0.3454 |
| baseline ultimo_valor | 0.5199 | 0.5237 | 0.5339 | 0.5434 | 2.749.101 | — |
| baseline mesmo_horario_dia_anterior | 0.4368 | 0.4097 | 0.4952 | 0.4600 | 2.749.101 | — |
| baseline mesmo_horario_recente | 0.5199 | 0.5237 | 0.5339 | 0.5434 | 2.749.101 | — |
| baseline historico | 0.4367 | 0.4097 | 0.4952 | 0.4600 | 2.749.101 | — |

#### fotovoltaica V2 — `main-fotovoltaica-v2-001` (sensibilidade: `delay-fotovoltaica-v2-001`)


restricao_registrada (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.3648 | 0.2251 | 0.1116 | 0.3248 | 0.9535 | 0.6874 | 0.3158 | 18.273.840 | 0.3654 | 0.2208 | 0.9818 |
| modelo lightgbm | 0.7967 | 0.1254 | 0.0890 | 0.4611 | 0.9284 | 0.7719 | 0.3158 | 18.273.840 | 0.6887 | 0.1602 | 0.9548 |
| baseline ultimo_valor | 0.3159 | 0.3157 | 0.5000 | 0.5110 | 0.0006 | 0.0008 | 0.3158 | 18.273.840 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.8942 | 0.0698 | 0.5000 | 0.8492 | 0.8414 | 0.8429 | 0.3158 | 18.273.840 | — | — | — |
| baseline mesmo_horario_recente | 0.6859 | 0.1347 | 0.5000 | 0.8074 | 0.7529 | 0.7632 | 0.3158 | 18.273.840 | — | — | — |
| baseline historico | 0.8943 | 0.0698 | 0.5000 | 0.8492 | 0.8414 | 0.8429 | 0.3158 | 18.273.840 | — | — | — |

corte_positivo (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.3316 | 0.1903 | 0.0961 | 0.2783 | 0.9354 | 0.6353 | 0.2545 | 18.273.840 | 0.3298 | 0.1912 | 0.9580 |
| modelo lightgbm | 0.6757 | 0.1291 | 0.0975 | 0.3677 | 0.9312 | 0.7127 | 0.2545 | 18.273.840 | 0.5101 | 0.1611 | 0.9337 |
| baseline ultimo_valor | 0.2545 | 0.2545 | 0.5000 | — | 0.0000 | 0.0000 | 0.2545 | 18.273.840 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.8348 | 0.0773 | 0.5000 | 0.7936 | 0.7558 | 0.7631 | 0.2545 | 18.273.840 | — | — | — |
| baseline mesmo_horario_recente | 0.5763 | 0.1459 | 0.5000 | 0.7310 | 0.6754 | 0.6858 | 0.2545 | 18.273.840 | — | — | — |
| baseline historico | 0.8348 | 0.0773 | 0.5000 | 0.7936 | 0.7558 | 0.7631 | 0.2545 | 18.273.840 | — | — | — |

volume (recorte global; MAE em MWmed)

| origem | MAE total | MAE condicional | WAPE | viés | cobertura | suporte | MAE total +24h | WAPE +24h |
|---|---|---|---|---|---|---|---|---|
| volume-linear-linear | 31.36 | 64.86 | 1.4357 | -0.26 | 1.0000 | 18.273.840 | 34.74 | 1.5904 |
| volume-linear-lightgbm | 30.33 | 65.88 | 1.3885 | -1.98 | 1.0000 | 18.273.840 | 32.93 | 1.5077 |
| volume-lightgbm-linear | 26.33 | 51.94 | 1.2052 | 4.69 | 1.0000 | 18.273.840 | 31.12 | 1.4248 |
| volume-lightgbm-lightgbm | 25.55 | 53.26 | 1.1698 | 2.81 | 1.0000 | 18.273.840 | 29.69 | 1.3590 |
| volume_condicional-linear | 79.28 | 53.07 | 3.6294 | 69.42 | 1.0000 | 18.273.840 | 79.66 | 3.6467 |
| volume_condicional-lightgbm | 72.63 | 52.60 | 3.3246 | 61.04 | 1.0000 | 18.273.840 | 71.00 | 3.2502 |
| baseline ultimo_valor | 21.84 | 85.82 | 1.0000 | -21.84 | 1.0000 | 18.273.840 | — | — |
| baseline mesmo_horario_dia_anterior | 15.13 | 46.18 | 0.6927 | -3.05 | 1.0000 | 18.273.840 | — | — |
| baseline mesmo_horario_recente | 19.33 | 61.00 | 0.8848 | -2.03 | 1.0000 | 18.273.840 | — | — |
| baseline historico | 15.13 | 46.18 | 0.6927 | -3.05 | 1.0000 | 18.273.840 | — | — |

causa (recorte global)

| origem | macro-F1 | recall REL | recall CNF | recall ENE | suporte | macro-F1 +24h |
|---|---|---|---|---|---|---|
| modelo linear | 0.4014 | 0.0288 | 0.8723 | 0.5106 | 5.768.291 | 0.4117 |
| modelo lightgbm | 0.3351 | 0.0000 | 0.9769 | 0.3619 | 5.768.291 | 0.3551 |
| baseline ultimo_valor | 0.4011 | 0.1717 | 0.2450 | 0.7751 | 5.768.291 | — |
| baseline mesmo_horario_dia_anterior | 0.5109 | 0.1505 | 0.4128 | 0.8869 | 5.768.291 | — |
| baseline mesmo_horario_recente | 0.4011 | 0.1717 | 0.2450 | 0.7751 | 5.768.291 | — |
| baseline historico | 0.5108 | 0.1503 | 0.4128 | 0.8869 | 5.768.291 | — |

#### fotovoltaica V3 — `main-fotovoltaica-v3-001` (sensibilidade: `delay-fotovoltaica-v3-001`)


restricao_registrada (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.4007 | 0.2158 | 0.2711 | 0.3283 | 0.9980 | 0.7088 | 0.3248 | 19.180.800 | 0.3985 | 0.2183 | 0.9980 |
| modelo lightgbm | 0.8568 | 0.1085 | 0.1615 | 0.7165 | 0.8680 | 0.8328 | 0.3248 | 19.180.800 | 0.7537 | 0.1465 | 0.8082 |
| baseline ultimo_valor | 0.3248 | 0.3248 | 0.5000 | — | 0.0000 | 0.0000 | 0.3248 | 19.180.800 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.9120 | 0.0703 | 0.5000 | 0.8163 | 0.8884 | 0.8730 | 0.3248 | 19.180.800 | — | — | — |
| baseline mesmo_horario_recente | 0.7280 | 0.1183 | 0.5000 | 0.8178 | 0.8180 | 0.8179 | 0.3248 | 19.180.800 | — | — | — |
| baseline historico | 0.9120 | 0.0703 | 0.5000 | 0.8163 | 0.8884 | 0.8730 | 0.3248 | 19.180.800 | — | — | — |

corte_positivo (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.3513 | 0.1847 | 0.2007 | 0.2815 | 0.9618 | 0.6484 | 0.2570 | 19.180.800 | 0.3498 | 0.1890 | 0.9817 |
| modelo lightgbm | 0.7792 | 0.1076 | 0.1561 | 0.6423 | 0.8318 | 0.7855 | 0.2570 | 19.180.800 | 0.6700 | 0.1358 | 0.7591 |
| baseline ultimo_valor | 0.2570 | 0.2570 | 0.5000 | — | 0.0000 | 0.0000 | 0.2570 | 19.180.800 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.8506 | 0.0778 | 0.5000 | 0.7601 | 0.8049 | 0.7955 | 0.2570 | 19.180.800 | — | — | — |
| baseline mesmo_horario_recente | 0.6248 | 0.1293 | 0.5000 | 0.7489 | 0.7477 | 0.7479 | 0.2570 | 19.180.800 | — | — | — |
| baseline historico | 0.8506 | 0.0778 | 0.5000 | 0.7601 | 0.8049 | 0.7955 | 0.2570 | 19.180.800 | — | — | — |

volume (recorte global; MAE em MWmed)

| origem | MAE total | MAE condicional | WAPE | viés | cobertura | suporte | MAE total +24h | WAPE +24h |
|---|---|---|---|---|---|---|---|---|
| volume-linear-linear | 32.90 | 60.72 | 1.5212 | 3.31 | 0.9915 | 19.180.800 | 35.16 | 1.6247 |
| volume-linear-lightgbm | 34.12 | 65.95 | 1.5779 | 2.50 | 0.9915 | 19.180.800 | 35.78 | 1.6534 |
| volume-lightgbm-linear | 18.80 | 49.43 | 0.8692 | -1.92 | 0.9915 | 19.180.800 | 21.85 | 1.0100 |
| volume-lightgbm-lightgbm | 22.73 | 63.99 | 1.0509 | -3.02 | 0.9915 | 19.180.800 | 24.63 | 1.1385 |
| volume_condicional-linear | 66.91 | 47.23 | 3.0940 | 55.17 | 0.9915 | 19.180.800 | 69.78 | 3.2246 |
| volume_condicional-lightgbm | 75.68 | 70.17 | 3.4997 | 56.65 | 0.9915 | 19.180.800 | 75.67 | 3.4968 |
| baseline ultimo_valor | 21.63 | 84.13 | 1.0000 | -21.63 | 0.9915 | 19.180.800 | — | — |
| baseline mesmo_horario_dia_anterior | 16.09 | 43.97 | 0.7442 | 1.19 | 0.9915 | 19.180.800 | — | — |
| baseline mesmo_horario_recente | 18.88 | 58.20 | 0.8729 | -0.49 | 0.9915 | 19.180.800 | — | — |
| baseline historico | 16.09 | 43.97 | 0.7442 | 1.19 | 0.9915 | 19.180.800 | — | — |

causa (recorte global)

| origem | macro-F1 | recall REL | recall CNF | recall ENE | suporte | macro-F1 +24h |
|---|---|---|---|---|---|---|
| modelo linear | 0.4191 | 0.0000 | 0.6619 | 0.6580 | 6.229.259 | 0.4082 |
| modelo lightgbm | 0.2706 | 0.0000 | 0.0146 | 0.9902 | 6.229.259 | 0.2723 |
| baseline ultimo_valor | 0.4918 | 0.3977 | 0.4184 | 0.7018 | 6.229.259 | — |
| baseline mesmo_horario_dia_anterior | 0.5216 | 0.2310 | 0.4487 | 0.7904 | 6.229.259 | — |
| baseline mesmo_horario_recente | 0.4918 | 0.3977 | 0.4184 | 0.7018 | 6.229.259 | — |
| baseline historico | 0.5216 | 0.2310 | 0.4487 | 0.7904 | 6.229.259 | — |

#### fotovoltaica V4 — `main-fotovoltaica-v4-001` (sensibilidade: `delay-fotovoltaica-v4-001`)


restricao_registrada (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.3260 | 0.1921 | 0.1832 | 0.2845 | 0.9130 | 0.6332 | 0.2638 | 20.417.904 | 0.3368 | 0.1900 | 0.9482 |
| modelo lightgbm | 0.7473 | 0.1466 | 0.1296 | 0.6843 | 0.6690 | 0.6720 | 0.2638 | 20.417.904 | 0.6641 | 0.1665 | 0.6036 |
| baseline ultimo_valor | 0.2638 | 0.2638 | 0.5000 | — | 0.0000 | 0.0000 | 0.2638 | 20.417.904 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.8043 | 0.0875 | 0.5000 | 0.7325 | 0.7905 | 0.7782 | 0.2638 | 20.417.904 | — | — | — |
| baseline mesmo_horario_recente | 0.5962 | 0.1448 | 0.5000 | 0.7347 | 0.7059 | 0.7115 | 0.2638 | 20.417.904 | — | — | — |
| baseline historico | 0.8043 | 0.0875 | 0.5000 | 0.7325 | 0.7905 | 0.7782 | 0.2638 | 20.417.904 | — | — | — |

corte_positivo (recorte global)

| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modelo linear | 0.2774 | 0.1595 | 0.1396 | 0.2331 | 0.9339 | 0.5832 | 0.2063 | 20.417.904 | 0.2874 | 0.1586 | 0.9591 |
| modelo lightgbm | 0.6760 | 0.1263 | 0.1089 | 0.6036 | 0.6823 | 0.6649 | 0.2063 | 20.417.904 | 0.6068 | 0.1390 | 0.6383 |
| baseline ultimo_valor | 0.2063 | 0.2063 | 0.5000 | — | 0.0000 | 0.0000 | 0.2063 | 20.417.904 | — | — | — |
| baseline mesmo_horario_dia_anterior | 0.7109 | 0.0886 | 0.5000 | 0.6755 | 0.6581 | 0.6615 | 0.2063 | 20.417.904 | — | — | — |
| baseline mesmo_horario_recente | 0.4801 | 0.1474 | 0.5000 | 0.6512 | 0.6154 | 0.6222 | 0.2063 | 20.417.904 | — | — | — |
| baseline historico | 0.7109 | 0.0886 | 0.5000 | 0.6755 | 0.6581 | 0.6615 | 0.2063 | 20.417.904 | — | — | — |

volume (recorte global; MAE em MWmed)

| origem | MAE total | MAE condicional | WAPE | viés | cobertura | suporte | MAE total +24h | WAPE +24h |
|---|---|---|---|---|---|---|---|---|
| volume-linear-linear | 23.06 | 53.24 | 1.6646 | 2.00 | 1.0000 | 20.417.904 | 24.52 | 1.7687 |
| volume-linear-lightgbm | 23.30 | 55.44 | 1.6817 | 1.58 | 1.0000 | 20.417.904 | 24.16 | 1.7430 |
| volume-lightgbm-linear | 14.26 | 49.77 | 1.0298 | -4.48 | 1.0000 | 20.417.904 | 15.11 | 1.0897 |
| volume-lightgbm-lightgbm | 15.14 | 54.46 | 1.0929 | -5.05 | 1.0000 | 20.417.904 | 15.64 | 1.1279 |
| volume_condicional-linear | 70.40 | 49.25 | 5.0824 | 63.58 | 1.0000 | 20.417.904 | 72.70 | 5.2441 |
| volume_condicional-lightgbm | 75.30 | 65.29 | 5.4363 | 64.78 | 1.0000 | 20.417.904 | 74.17 | 5.3500 |
| baseline ultimo_valor | 13.85 | 67.13 | 1.0000 | -13.85 | 1.0000 | 20.417.904 | — | — |
| baseline mesmo_horario_dia_anterior | 13.59 | 44.23 | 0.9809 | -1.01 | 1.0000 | 20.417.904 | — | — |
| baseline mesmo_horario_recente | 15.78 | 57.48 | 1.1394 | -1.25 | 1.0000 | 20.417.904 | — | — |
| baseline historico | 13.59 | 44.23 | 0.9809 | -1.01 | 1.0000 | 20.417.904 | — | — |

causa (recorte global)

| origem | macro-F1 | recall REL | recall CNF | recall ENE | suporte | macro-F1 +24h |
|---|---|---|---|---|---|---|
| modelo linear | 0.4189 | 0.1963 | 0.2685 | 0.8132 | 5.385.344 | 0.3687 |
| modelo lightgbm | 0.3310 | 0.1297 | 0.0094 | 0.9468 | 5.385.344 | 0.3315 |
| baseline ultimo_valor | 0.5018 | 0.1524 | 0.5407 | 0.8271 | 5.385.344 | — |
| baseline mesmo_horario_dia_anterior | 0.4342 | 0.0272 | 0.3970 | 0.8822 | 5.385.344 | — |
| baseline mesmo_horario_recente | 0.5018 | 0.1524 | 0.5407 | 0.8271 | 5.385.344 | — |
| baseline historico | 0.4342 | 0.0272 | 0.3970 | 0.8822 | 5.385.344 | — |

## 10. Calibração e limiares

- **Ocorrência:** os modelos usam calibração sigmoide ajustada no segmento de calibração
  (completo, sem amostragem). O limiar foi escolhido pelo pipeline e está registrado em
  `reports/*.json → models.*.threshold`.
- **Volume e causa:** `calibration_status = nao_aplicavel`.
- **Baselines de ocorrência:** limiar fixo de 0,5, sem calibração (limitação herdada).
- **Confiabilidade:** as dez faixas fixas de 0,1 estão em `metrics/*.json →
  calibration_bins`, por recorte.
- **Observação factual:** o regressor `volume_condicional-lightgbm` solar selecionou
  `n_estimators = 1` em V3 e V4. A 2C deve examinar isso antes de qualquer leitura de
  desempenho dessa combinação.

| Run | Modelo | Calibração | Limiar | Parâmetros selecionados | fit_seconds |
|---|---|---|---|---|---|
| main-eolica-v1-002 | causa-lightgbm | nao_aplicavel | — | {"max_depth": 5, "n_estimators": 29, "num_leaves": 31} | 131.6 |
| main-eolica-v1-002 | causa-linear | nao_aplicavel | — | {"C": 0.1} | 479.5 |
| main-eolica-v1-002 | corte_positivo-lightgbm | sigmoide | 0.1702 | {"max_depth": 5, "n_estimators": 51, "num_leaves": 31} | 153.1 |
| main-eolica-v1-002 | corte_positivo-linear | sigmoide | 0.1568 | {"C": 1.0} | 158.1 |
| main-eolica-v1-002 | restricao_registrada-lightgbm | sigmoide | 0.2405 | {"max_depth": 5, "n_estimators": 65, "num_leaves": 31} | 150.9 |
| main-eolica-v1-002 | restricao_registrada-linear | sigmoide | 0.2112 | {"C": 1.0} | 133.0 |
| main-eolica-v1-002 | volume_condicional-lightgbm | nao_aplicavel | — | {"max_depth": 5, "n_estimators": 65, "num_leaves": 31} | 40.5 |
| main-eolica-v1-002 | volume_condicional-linear | nao_aplicavel | — | {"alpha": 0.01} | 62.3 |
| main-eolica-v2-004 | causa-lightgbm | nao_aplicavel | — | {"max_depth": 5, "n_estimators": 246, "num_leaves": 31} | 400.7 |
| main-eolica-v2-004 | causa-linear | nao_aplicavel | — | {"C": 1.0} | 683.0 |
| main-eolica-v2-004 | corte_positivo-lightgbm | sigmoide | 0.1095 | {"max_depth": 5, "n_estimators": 14, "num_leaves": 31} | 131.6 |
| main-eolica-v2-004 | corte_positivo-linear | sigmoide | 0.1217 | {"C": 0.1} | 176.3 |
| main-eolica-v2-004 | restricao_registrada-lightgbm | sigmoide | 0.1283 | {"max_depth": 5, "n_estimators": 294, "num_leaves": 31} | 601.1 |
| main-eolica-v2-004 | restricao_registrada-linear | sigmoide | 0.1403 | {"C": 1.0} | 186.1 |
| main-eolica-v2-004 | volume_condicional-lightgbm | nao_aplicavel | — | {"max_depth": 5, "n_estimators": 27, "num_leaves": 31} | 40.8 |
| main-eolica-v2-004 | volume_condicional-linear | nao_aplicavel | — | {"alpha": 0.0001} | 109.5 |
| main-eolica-v3-001 | causa-lightgbm | nao_aplicavel | — | {"max_depth": 4, "n_estimators": 5, "num_leaves": 15} | 196.7 |
| main-eolica-v3-001 | causa-linear | nao_aplicavel | — | {"C": 1.0} | 1112.0 |
| main-eolica-v3-001 | corte_positivo-lightgbm | sigmoide | 0.2339 | {"max_depth": 5, "n_estimators": 498, "num_leaves": 31} | 900.1 |
| main-eolica-v3-001 | corte_positivo-linear | sigmoide | 0.2321 | {"C": 1.0} | 217.8 |
| main-eolica-v3-001 | restricao_registrada-lightgbm | sigmoide | 0.1511 | {"max_depth": 5, "n_estimators": 307, "num_leaves": 31} | 494.5 |
| main-eolica-v3-001 | restricao_registrada-linear | sigmoide | 0.2491 | {"C": 1.0} | 195.0 |
| main-eolica-v3-001 | volume_condicional-lightgbm | nao_aplicavel | — | {"max_depth": 5, "n_estimators": 169, "num_leaves": 31} | 117.8 |
| main-eolica-v3-001 | volume_condicional-linear | nao_aplicavel | — | {"alpha": 0.0001} | 124.0 |
| main-eolica-v4-001 | causa-lightgbm | nao_aplicavel | — | {"max_depth": 4, "n_estimators": 186, "num_leaves": 15} | 681.2 |
| main-eolica-v4-001 | causa-linear | nao_aplicavel | — | {"C": 1.0} | 1701.0 |
| main-eolica-v4-001 | corte_positivo-lightgbm | sigmoide | 0.2042 | {"max_depth": 4, "n_estimators": 13, "num_leaves": 15} | 160.1 |
| main-eolica-v4-001 | corte_positivo-linear | sigmoide | 0.2065 | {"C": 1.0} | 195.3 |
| main-eolica-v4-001 | restricao_registrada-lightgbm | sigmoide | 0.1783 | {"max_depth": 5, "n_estimators": 7, "num_leaves": 31} | 162.4 |
| main-eolica-v4-001 | restricao_registrada-linear | sigmoide | 0.2059 | {"C": 0.1} | 230.9 |
| main-eolica-v4-001 | volume_condicional-lightgbm | nao_aplicavel | — | {"max_depth": 5, "n_estimators": 302, "num_leaves": 31} | 252.6 |
| main-eolica-v4-001 | volume_condicional-linear | nao_aplicavel | — | {"alpha": 0.0001} | 209.0 |
| main-fotovoltaica-v1-001 | causa-lightgbm | nao_aplicavel | — | {"max_depth": 4, "n_estimators": 27, "num_leaves": 15} | 58.1 |
| main-fotovoltaica-v1-001 | causa-linear | nao_aplicavel | — | {"C": 0.1} | 163.6 |
| main-fotovoltaica-v1-001 | corte_positivo-lightgbm | sigmoide | 0.0901 | {"max_depth": 5, "n_estimators": 420, "num_leaves": 31} | 359.7 |
| main-fotovoltaica-v1-001 | corte_positivo-linear | sigmoide | 0.1040 | {"C": 0.1} | 96.3 |
| main-fotovoltaica-v1-001 | restricao_registrada-lightgbm | sigmoide | 0.1160 | {"max_depth": 4, "n_estimators": 492, "num_leaves": 15} | 391.8 |
| main-fotovoltaica-v1-001 | restricao_registrada-linear | sigmoide | 0.1333 | {"C": 0.1} | 57.7 |
| main-fotovoltaica-v1-001 | volume_condicional-lightgbm | nao_aplicavel | — | {"max_depth": 4, "n_estimators": 64, "num_leaves": 15} | 18.1 |
| main-fotovoltaica-v1-001 | volume_condicional-linear | nao_aplicavel | — | {"alpha": 0.01} | 36.5 |
| main-fotovoltaica-v2-001 | causa-lightgbm | nao_aplicavel | — | {"max_depth": 5, "n_estimators": 7, "num_leaves": 31} | 82.1 |
| main-fotovoltaica-v2-001 | causa-linear | nao_aplicavel | — | {"C": 1.0} | 314.6 |
| main-fotovoltaica-v2-001 | corte_positivo-lightgbm | sigmoide | 0.0975 | {"max_depth": 5, "n_estimators": 227, "num_leaves": 31} | 268.9 |
| main-fotovoltaica-v2-001 | corte_positivo-linear | sigmoide | 0.0961 | {"C": 0.1} | 122.0 |
| main-fotovoltaica-v2-001 | restricao_registrada-lightgbm | sigmoide | 0.0890 | {"max_depth": 5, "n_estimators": 332, "num_leaves": 31} | 349.7 |
| main-fotovoltaica-v2-001 | restricao_registrada-linear | sigmoide | 0.1116 | {"C": 0.1} | 89.3 |
| main-fotovoltaica-v2-001 | volume_condicional-lightgbm | nao_aplicavel | — | {"max_depth": 5, "n_estimators": 172, "num_leaves": 31} | 52.8 |
| main-fotovoltaica-v2-001 | volume_condicional-linear | nao_aplicavel | — | {"alpha": 0.0001} | 59.0 |
| main-fotovoltaica-v3-001 | causa-lightgbm | nao_aplicavel | — | {"max_depth": 4, "n_estimators": 3, "num_leaves": 15} | 138.5 |
| main-fotovoltaica-v3-001 | causa-linear | nao_aplicavel | — | {"C": 1.0} | 548.8 |
| main-fotovoltaica-v3-001 | corte_positivo-lightgbm | sigmoide | 0.1561 | {"max_depth": 5, "n_estimators": 497, "num_leaves": 31} | 575.0 |
| main-fotovoltaica-v3-001 | corte_positivo-linear | sigmoide | 0.2007 | {"C": 0.1} | 131.8 |
| main-fotovoltaica-v3-001 | restricao_registrada-lightgbm | sigmoide | 0.1615 | {"max_depth": 5, "n_estimators": 485, "num_leaves": 31} | 586.9 |
| main-fotovoltaica-v3-001 | restricao_registrada-linear | sigmoide | 0.2711 | {"C": 0.1} | 130.9 |
| main-fotovoltaica-v3-001 | volume_condicional-lightgbm | nao_aplicavel | — | {"max_depth": 5, "n_estimators": 1, "num_leaves": 31} | 31.7 |
| main-fotovoltaica-v3-001 | volume_condicional-linear | nao_aplicavel | — | {"alpha": 0.0001} | 79.7 |
| main-fotovoltaica-v4-001 | causa-lightgbm | nao_aplicavel | — | {"max_depth": 4, "n_estimators": 18, "num_leaves": 15} | 225.2 |
| main-fotovoltaica-v4-001 | causa-linear | nao_aplicavel | — | {"C": 1.0} | 1040.6 |
| main-fotovoltaica-v4-001 | corte_positivo-lightgbm | sigmoide | 0.1089 | {"max_depth": 5, "n_estimators": 500, "num_leaves": 31} | 861.9 |
| main-fotovoltaica-v4-001 | corte_positivo-linear | sigmoide | 0.1396 | {"C": 0.1} | 205.7 |
| main-fotovoltaica-v4-001 | restricao_registrada-lightgbm | sigmoide | 0.1296 | {"max_depth": 5, "n_estimators": 500, "num_leaves": 31} | 822.9 |
| main-fotovoltaica-v4-001 | restricao_registrada-linear | sigmoide | 0.1832 | {"C": 1.0} | 219.8 |
| main-fotovoltaica-v4-001 | volume_condicional-lightgbm | nao_aplicavel | — | {"max_depth": 5, "n_estimators": 1, "num_leaves": 31} | 42.7 |

**Cauda de volume (p99 do treino, MWmed; define o recorte `cauda_volume_p99_treino`):**

| Fonte | V1 | V2 | V3 | V4 |
|---|---|---|---|---|
| Eólica | 259,51 | 289,87 | 300,70 | 326,88 |
| Solar | 387,96 | 561,20 | 589,69 | 594,52 |

## 11. Diagnósticos e cobertura

- **Cobertura do volume:** a fração de pares alvo/previsão finitos no recorte global é
  0,9925 na eólica V2, por exemplo. O valor de cada run está na coluna "cobertura" da §9.
- **Diagnósticos de volume:** `diagnostics/*-volume-*.json`, um por pipeline, com as 10
  entidades e os 10 episódios de maior erro absoluto acumulado.
- **Recortes ausentes nas runs principais:** `entidade_nova` falta em 28 dos 224 arquivos de
  métricas (63 recortes em vez de 64). Isso é coerente com a ausência de entidades novas nessas rodadas, mas não foi verificado.
- **Recortes com métrica principal nula nas runs principais:**
  - ocorrência: `inicio_episodio`, `primeiro_zero_pos_episodio` e `cauda_volume_p99_treino`
    (48 arquivos por tarefa de ocorrência; provavelmente porque esses recortes contêm uma só classe, hipótese não verificada);
  - causa: `historico_insuficiente` (6) e `idade:acima_96h` (3).
  - Em todos os casos o suporte é preservado. Pelo §10.1, AP de recorte com classe única não
    permite comparação. O motivo do nulo não está gravado no JSON: é uma lacuna do §13.2.
- **Ainda não produzidos:** a visão por entidade com peso igual, a energia diária pela emissão
  das 00h e a incerteza semanal (§10.2 e §10.3) não saem da execução 2B. A 2C deve
  calculá-los a partir das previsões Parquet ou registrá-los como ausentes.

## 12. Sensibilidade (`noturno_mais_24h`)

| Run | Congela | Commit | Duração (s) | Pico processo (GiB) | `validation_rows` |
|---|---|---|---|---|---|
| `delay-eolica-v1-001` | `main-eolica-v1-002` | `88634ed` | 1.178,5 | 5,71 | 42.846.576 |
| `delay-eolica-v2-001` | `main-eolica-v2-004` | `88634ed` | 1.536,9 | 6,33 | 43.823.856 |
| `delay-eolica-v3-001` | `main-eolica-v3-001` | `88634ed` | 1.506,5 | 6,89 | 43.104.576 |
| `delay-eolica-v4-001` | `main-eolica-v4-001` | `88634ed` | 1.356,0 | 5,70 | 42.191.712 |
| `delay-fotovoltaica-v1-001` | `main-fotovoltaica-v1-001` | `88634ed` | 633,3 | 2,87 | 17.777.040 |
| `delay-fotovoltaica-v2-001` | `main-fotovoltaica-v2-001` | `88634ed` | 603,3 | 3,12 | 18.273.840 |
| `delay-fotovoltaica-v3-001` | `main-fotovoltaica-v3-001` | `88634ed` | 692,9 | 3,42 | 19.325.904 |
| `delay-fotovoltaica-v4-001` | `main-fotovoltaica-v4-001` | `88634ed` | 753,7 | 3,29 | 20.401.776 |

- **Congelamento verificado nas 8 runs:**
  - `models_retrained=false`;
  - nenhuma pasta `models/`;
  - os 8 `frozen_model` de cada run apontam para a run principal correta;
  - o SHA-256 de cada modelo é igual ao registrado no `checksums.json` da principal;
  - limiares e `calibration_status` idênticos;
  - nenhum `fit_seconds`.
- **Linhas de validação:** o +24h tem um pouco menos linhas na maioria das rodadas, porque as
  emissões dos dias iniciais sem partição ficam de fora. Na solar V2 as contagens são iguais.
  A interseção comparável entre os cenários (§10.2.4) **não** foi calculada.
- **Recortes ausentes em todos os 96 arquivos de métricas de sensibilidade:**
  `cauda_volume_p99_treino`, `entidade_nova`, `fora_cauda_volume`, `inicio_episodio`,
  `painel_fixo` e `primeiro_zero_pos_episodio` (58 recortes em vez de 64). Limitação herdada:
  esses recortes não estão disponíveis para a comparação principal vs. atraso.
- **Outros:** a sensibilidade não calcula baselines nem diagnósticos de volume. Também há
  macro-F1 nulo em `historico_insuficiente` em 2 arquivos.

## 13. Recursos, falhas e retomada

**Recursos:** o maior pico de working set de processo foi de 24,06 GiB
(`main-fotovoltaica-v4-001`). O maior pico da árvore, amostrado a cada 30 s, foi de 18,49 GiB.
Os picos reais de processo **superaram a meta de 20 GiB** usada para projetar a taxa de
amostragem: 24,06 GiB na solar V4 e 22,02 GiB na eólica V4. A projeção subestimou o consumo,
mas não houve falha nem thrashing. A vigia de memória (commit livre < 2 GB por 2 min) não
disparou. Os tempos da fila completa estão em `execucao/fila/fila.log`.

**stderr:** nas 8 principais há 8 avisos `LGBMDeprecationWarning` (`eval_set`) e os marcadores
de fase. Nas sensibilidades, o stderr está vazio.

**Falhas e tentativas (preservadas, não usar como resultado):**

| Tentativa | Commit | O que aconteceu | Evidência |
|---|---|---|---|
| `main-eolica-v1-001` | `f36d5f6` | Interrompida pelo agente aos 458 s: máscara de amostragem sem pushdown, 41–46 GB comprometidos, thrashing. Corrigido em `560ae70`. | `passos/main-eolica-v1-001/INTERRUPCAO.txt`, CSV de memória |
| `main-eolica-v2-001` | `560ae70` | Exit 1 em 30,4 s: preflight exige a branch `etapa-2-experimental`, e o worktree estava em `execucao/fila-2b`. | `passos/main-eolica-v2-001` |
| `main-eolica-v2-002` | `560ae70` | Cancelada pelo responsável às 02h22 de 24/09 para reiniciar com `c73302e`. | `end.json` com `interrupted_by_user`, `INTERRUPCAO.txt` |
| `main-eolica-v2-003` | `c73302e` | A árvore desapareceu por volta de 02h27, junto com a atualização forçada do app Codex (hipótese fortemente sustentada). Sem `end.json`; o manifest segue `running` e não foi reescrito. | `INTERRUPCAO.txt`, eventos AppX no diário |
| Fila, 23/09 22h53 | — | O lançador perdia limites de argumento: 9 passos falharam em cerca de 20 s sem criar diretório. | entrada do diário de 24/09 (os `*.runner.stderr.log` foram sobrescritos, vazios, pelas retomadas) |
| `check-noturno_mais_24h-eolica-001` (1ª tentativa) | — | `pwsh -File` leu `-m` como parâmetro; a fila parou das 15h30 às 17h08. Corrigido com `-Arguments:<valor>`. | entrada do diário de 24/09 (log do runner sobrescrito na retomada) |

**Retomada:**

- A fila terminou (`fila concluída com sucesso`, 24/09 20h11).
- O worktree executor `worktrees/execucao-fila` foi **removido** na sessão 05, junto com a
  branch `execucao/fila-2b` (sem commits próprios), porque nenhuma run dependia mais dele.
- Para relançar algo pela fila:
  1. Recrie o worktree:
     `git worktree add --force "Y:/CurtaMap Etapa 2B/worktrees/execucao-fila" etapa-2-experimental`
     (`--force`, porque a branch fica em checkout no repositório principal). Em seguida,
     rode `uv sync` nele.
  2. Use StepIds novos (`-00N`).
  3. Dispare `Start-ScheduledTask CurtaMap-Fila-2B`.
  4. Para parar a fila, crie `execucao/fila/PARAR`. Não use `Stop-ScheduledTask`, que encerra
     só a raiz.

## 14. Integridade e inventário

- **Auditoria `auditoria-runs-2b-001`** (passo em `execucao/passos/`, script
  `execucao/verificacoes/auditar_runs_2b.py`, saída `execucao/verificacoes/auditoria-runs-2b-001.json`):
  - SHA-256 recalculado de **todos** os arquivos listados nos `checksums.json` das 16 runs:
    54 por principal e 26 por sensibilidade, **zero divergências, zero ausentes, zero
    arquivos fora da lista** além do próprio `checksums.json`;
  - congelamento das 8 sensibilidades confirmado (§12).
- **Inventário `inventario-2b-002`** (vale este; script `execucao/verificacoes/inventariar_2b_v2.py`):
  - arquivos: `handoff/inventario-etapa-2b-002.csv` (caminho relativo, bytes, SHA-256, origem
    do hash) e `handoff/inventario-etapa-2b-002.resumo.json`;
  - 8.133 arquivos, 67.348.497.296 bytes: 640 hashes reaproveitados dos checksums verificados
    e 7.493 calculados, incluindo os 6.800 arquivos de `stage2b-datasets`;
  - excluídos: `temporarios/`, `worktrees/`, `handoff/`, `execucao/CHECKPOINT-*.md` (log vivo)
    e o diretório do próprio passo;
  - SHA-256 do CSV: `99920bab92ba9a96f873497cabffbb4402d912c45373f9e6f2c03b561ea87fd5`.
- **Inventário `inventario-2b-001`, substituído:** foi preservado como
  `handoff/inventario-etapa-2b-001.*`. Ele incluía arquivos que continuaram sendo gravados
  depois do cálculo (o checkpoint e os logs do próprio passo) e não deve ser usado para
  conferência.
- **Hashes de `handoff/`** (relatório, prompt e CSVs): `handoff/SHA256SUMS-handoff.txt`.
- **Índice de runs:** `execucao/run-index.json`, atualizado na sessão 05. A versão anterior
  está em `execucao/verificacoes/run-index.pre-sessao05.json`.

## 15. Pendências e handoff 2C

**Para a 2C decidir ou calcular (não feito na 2B):**

1. Aplicar o §11:
   - escolher o baseline comparador único por tarefa e fonte;
   - calcular médias V1–V4 com desvio, mínimo/máximo e diferenças pareadas;
   - aplicar margens e proteções;
   - atribuir os estados `inelegivel`, `inconclusivo` ou `requer_analise`.
2. Visão por entidade com peso igual, energia diária pela emissão das 00h, incerteza semanal e
   interseção comparável principal vs. +24h (§10.2 e §10.3).
3. Examinar `volume_condicional-lightgbm` solar com `n_estimators=1` (V3 e V4) e o recall de
   REL muito baixo dos modelos de causa, antes de qualquer conclusão.
4. Decidir se as extensões recomendadas (sementes 17 e 101, intervalo de volume) ainda cabem
   no prazo.

**Limitações que toda leitura deve citar:**

- amostragem de t0 em initial/refit (§4 e §7);
- limiar 0,5 dos baselines e `threshold or 0.5`;
- subconjunto de features;
- recortes vazios ou ausentes na sensibilidade;
- elegibilidade por t0;
- volume condicional avaliado em todas as linhas;
- avisos de depreciação do LightGBM;
- V1 eólica em código de métricas anterior, equivalente por paridade;
- LightGBM com 6 threads, diferente do piloto;
- commits criados na máquina dedicada.

**Proibições que continuam valendo:** não abrir nem pontuar o teste reservado
(maio–agosto/2026); não mudar grades, candidatos ou metodologia para resgatar médias; não fazer
merge em `main` sem aprovação da 2C.

**Prompt de análise:** `handoff/PROMPT-analise-etapa-2c.md`.
