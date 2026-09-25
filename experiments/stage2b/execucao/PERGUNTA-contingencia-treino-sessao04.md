# Pergunta consolidada — contingência de treino da Etapa 2B (23/09/2026)

Evidência: `execucao/medicoes/populacoes-noturno_dia_util-eolica-001.json` (passo
`populacoes-noturno_dia_util-eolica-001`, commit `ea88fe7`, exit 0, 96/96 checagens cruzadas
com a verificação aprovada). Diário: commit `2e79475`. Nenhuma amostragem implementada.

## 1. Contagens exatas eólicas (linhas fonte+id_ons+t0+horizonte)

Ocorrência principal e secundária têm contagens idênticas.

| Rodada | Segmento | Ocorrências (cada) | Volume condicional | Causa |
|---|---|---:|---:|---:|
| V1 | initial | 132.692.040 | 18.803.053 | 27.728.833 |
| V1 | tuning | 8.480.256 | 1.537.899 | 2.154.617 |
| V1 | refit | 142.386.336 | 20.818.621 | 30.533.665 |
| V1 | calibration | 9.518.400 | não usada | não usada |
| V2 | initial | 174.755.520 | 28.257.206 | 40.046.603 |
| V2 | tuning | 9.066.528 | 1.077.117 | 1.310.236 |
| V2 | refit | 185.795.136 | 30.160.873 | 42.312.202 |
| V2 | calibration | 9.527.424 | não usada | não usada |
| V3 | initial | 218.732.808 | 39.295.138 | 53.696.964 |
| V3 | tuning | 9.348.816 | 3.762.084 | 4.454.373 |
| V3 | refit | 228.613.584 | 43.239.394 | 58.360.175 |
| V3 | calibration | 9.532.224 | não usada | não usada |
| V4 | initial | 262.143.984 | 60.746.233 | 78.160.184 |
| V4 | tuning | 9.406.320 | 4.256.360 | 4.725.090 |
| V4 | refit | 272.078.832 | 65.106.121 | 83.010.440 |
| V4 | calibration | 9.587.424 | não usada | não usada |

Validação externa (painel aberto, completa, sem filtro de elegibilidade): linhas previstas
V1 42.851.184 · V2 43.830.768 · V3 43.109.184 · V4 42.194.016. Suporte potencial de
ocorrência/volume: 42.687.648 · 43.503.696 · 42.945.648 · 42.030.480. Causa: 10.205.443 ·
20.290.779 · 22.867.317 · 13.743.836.

## 2. Projeção de memória (estimativa com coeficientes históricos, não medição)

84 B/linha de trecho materializado, 148 B/linha de CSR, 556 B/linha no pico de `fit_transform`.
Por tarefa, `_split` mantém initial+tuning+refit+calibração simultaneamente (cópia: refit
repete as linhas de initial). Soma-se o maior pico de ajuste: inicial (556×initial + 148×tuning,
pois o LightGBM recebe o eval) ou refit (556×refit). Picos de ajustes diferentes não se somam;
os splits são liberados entre tarefas. Modelos acumulados são pequenos (8 modelos do piloto ≈3,7 MB).
Exceções guardadas no relatório podem reter tracebacks/referências (risco, não medido).

| Rodada | Ocorrência (cada) | Volume | Causa |
|---|---:|---:|---:|
| V1 | 96,7 GiB (residente 22,9) | 14,0 GiB | 20,5 GiB |
| V2 | 125,9 GiB (29,7) | 20,3 GiB | 28,5 GiB |
| V3 | 154,9 GiB (36,5) | 29,1 GiB | 39,3 GiB |
| V4 | 184,2 GiB (43,3) | 43,9 GiB | 56,0 GiB |

Máquina: 32 GB (31,9 GiB) com SO; referência do protocolo §12.1 ≈22 GiB por processo.
Reduzir cópias (liberar initial antes do refit) não basta: só o refit de V4 projeta ≈141 GiB.
O treino completo é inviável; a fase de métricas da validação não foi medida.

Taxa máxima de emissões t0 (initial e refit) para pico ≤20 GiB, mantendo tuning/calibração
completos: ocorrências V1 0,193 · V2 0,146 · V3 0,116 · V4 0,097; volume V1–V2 ≈1,0 ·
V3 0,683 · V4 0,452; causa V1 0,974 · V2 0,702 · V3 0,504 · V4 0,353.

## 3. Proposta (não implementada)

Regra comum (qualquer variante): emissões t0 inteiras — todas as entidades e os 48 horizontes;
aplicada só a initial e refit; tuning, calibração e validação externa completos; mesmo conjunto
para as duas famílias e todos os candidatos da tarefa; aninhada (t0 escolhido continua escolhido
em V1→V4 e initial ⊂ refit); lista/hash dos t0 fixados antes de qualquer métrica externa;
proporções por mês, hora de t0, dia da semana, entidade, horizonte e prevalência natural
verificadas e reportadas após a seleção — nunca presumidas. Semente explícita: **42**.

Variante recomendada — **sistemática estratificada por dia**: taxa 1/12 (≈0,083) = 4 das 48
meias-horas de cada dia, com deslocamento rotativo derivado de SHA-256(`42|data ISO`) contado
a partir de origem fixa. Fração diária exata, hora do dia balanceada ao longo dos ciclos.
Variante alternativa — hash puro: t0 escolhido se SHA-256(`42|t0 ISO`) < taxa (nunca `hash()`
do Python/Polars). A 8%, o refit de V4 (~36,7 mil t0) ficaria com ~2,9 mil t0: ~61 por
meia-hora do dia (±12%) e ~117 por mês (±9%), com muitos dias com 0–1 emissão.

Taxas: ocorrências 1/12 em todas as rodadas (V4 ≈17,5 GiB, V1 ≈10 GiB projetados; refit
V4 ≈22,7 mi linhas); volume e causa 0,30 → estratificado 14/48 (V4: causa ≈16,6 GiB,
volume ≈13 GiB). Alternativa A: 1/12 para as quatro tarefas. Alternativa B: taxa por rodada
no máximo que cabe (usa mais dados em V1, mas muda a fração entre rodadas).

## 4. Threads

`threads=6` da configuração só chega ao DuckDB da preparação; o LightGBM usa `n_jobs=1` fixo
(`models.py:150`), confirmado no piloto. A logística/Gamma do scikit-learn não usa essas threads.
Opção 1: manter n_jobs=1 (reprodutível, mais lento, igual ao piloto auditado).
Opção 2: LightGBM com n_jobs=6 e `deterministic=True` + `force_row_wise=True` (sem esses,
threads podem alterar resultados); é desvio registrado de parâmetro e exige novo piloto técnico.
Tempo por ajuste completo é desconhecido: o piloto (500 mil linhas, 1,6–10 s) não é estimativa.

Com threads fixas, `deterministic=True` + `force_row_wise=True` garante repetibilidade com o
**mesmo** número de threads; não garante igualdade numérica com os resultados em `n_jobs=1`.

## 5. Riscos não resolvidos pela amostragem

A validação continua completa (~43 mi linhas por rodada): as métricas relêem as previsões de
cada modelo e `_post_event_truth` mantém todos os pares entidade/tau. Essa fase não foi medida;
se exceder o orçamento, nenhuma taxa de treino resolve. Proposta: `main-eolica-v1-001` como
porta medida (pico por fase e duração real) antes de lançar as outras 15 runs.

## 6. Orçamento de 12 h de parede (§12.2)

Consumido até agora em execução real: geração eólica 8.105,6 s, verificação 272,2 s, piloto
60,5 s, medição 150,9 s (≈2,4 h), além da geração solar em curso e das duas +24h pendentes.
16 runs com duração por ajuste desconhecida (n_jobs=1) podem estourar as 12 h. A revisão do
orçamento precisa ser registrada antes da comparação.

## 7. Aplicação à solar

As contagens acima são só eólicas. Proposta: aprovar a **regra** (mesma semente, mesma seleção,
critério pico ≤20 GiB por tarefa, taxa 1,0 onde couber), aplicada à solar depois de medir suas
populações com o mesmo medidor — ou usar as mesmas taxas numéricas nas duas fontes.

## Responder numa única mensagem

a) variante e taxas de amostragem (ou outra contingência);
b) aplicação à solar (regra × mesmas taxas);
c) threads do LightGBM (opção 1 ou 2);
d) orçamento de 12 h (manter × revisar para quanto);
e) V1 eólica como porta medida antes das demais runs (sim/não).
