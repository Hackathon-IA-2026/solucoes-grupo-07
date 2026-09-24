# Etapa 2C — análise e decisão sobre os resultados da 2B (CurtaMap)

Responda em português do Brasil. Repositório `hackathon-ia-coppe-2026`, branch
`etapa-2-experimental`. O último commit da 2B está no fim da seção "Pendências" do diário
`docs/implementation-journal.md`. Os artefatos ficam na raiz externa `Y:\CurtaMap Etapa 2B`, ou
na cópia trazida ao Mac com os mesmos caminhos relativos.

## Leia primeiro (nesta ordem)

1. `handoff/relatorio-etapa-2b.md`: relatório factual de 15 seções. É a fonte principal; há
   cópia versionada em `docs/reports/stage2b/execution-report.md`.
2. `docs/handoffs/stage2c-prompt.md`: prompt original da 2C, redigido antes da execução. Este
   documento **complementa** aquele com os fatos da execução real; em caso de conflito sobre
   o que foi executado, valem os fatos deste e do relatório.
3. `docs/experimental-protocol.md` §10 (métricas e agregações), §11 (critérios de comparação e
   proteções) e §13.3 (handoff).
4. `execucao/run-index.json`: status, commits e evidências das 22 entradas.
5. `AGENTS.md` e as três últimas entradas do diário.

## Antes de analisar: confira a integridade

- Confira o SHA-256 de `handoff/inventario-etapa-2b.csv` contra
  `handoff/inventario-etapa-2b.resumo.json` (`csv_sha256`).
- Se os artefatos foram copiados de máquina, recalcule o SHA-256 das 16 runs contra o
  `checksums.json` de cada uma. O script `execucao/verificacoes/auditar_runs_2b.py` faz isso,
  desde que `ROOT` seja ajustado.
- Qualquer divergência interrompe a análise e deve ser relatada.

## Runs válidas (e apenas estas)

| Fonte | V1 | V2 | V3 | V4 |
|---|---|---|---|---|
| Eólica, principal | `main-eolica-v1-002` | `main-eolica-v2-004` | `main-eolica-v3-001` | `main-eolica-v4-001` |
| Solar, principal | `main-fotovoltaica-v1-001` | `-v2-001` | `-v3-001` | `-v4-001` |
| Eólica, +24h (congelada) | `delay-eolica-v1-001` | `-v2-001` | `-v3-001` | `-v4-001` |
| Solar, +24h (congelada) | `delay-fotovoltaica-v1-001` | `-v2-001` | `-v3-001` | `-v4-001` |

`main-eolica-v1-001`, `-v2-001`, `-v2-002` e `-v2-003` são tentativas falhas ou canceladas.
Nunca as use como resultado.

## Tarefa

1. **Comparação conforme o §11.1:**
   - por tarefa e fonte, escolha **um único** baseline comparador pela melhor média primária
     em V1–V4: AP para as duas ocorrências, MAE do pipeline completo para volume e macro-F1
     para causa;
   - calcule a média, o desvio, o mínimo/máximo e as diferenças pareadas por rodada para cada
     candidato: 2 famílias por tarefa e 4 pipelines de volume;
   - aplique as margens (AP +0,02; MAE −5% sem piora do WAPE; macro-F1 +0,02) e a exigência
     de 3 das 4 rodadas.
2. **Proteções do §11.2**, com o estado `aprovado_preliminar`, `inelegivel`, `inconclusivo` ou
   `requer_analise` e o motivo:
   - piora de mais de 0,02 em AP ou macro-F1 em qualquer rodada;
   - piora de mais de 10% no MAE;
   - piora de mais de 0,01 no Brier;
   - incerteza semanal;
   - classes sem suporte.
3. **Agregações do §10.2 que a 2B não produziu**, calculadas a partir das previsões Parquet:
   - visão por entidade com peso igual (WAPE agregado e média de WAPEs, sem trocar os nomes);
   - energia diária usando só a emissão das 00h;
   - incerteza semanal;
   - interseção comparável entre o cenário principal e o +24h.
   - Se alguma não for viável, registre-a como ausente.
4. **Investigue antes de concluir:**
   - `volume_condicional-lightgbm` solar com `n_estimators=1` em V3 e V4;
   - recall de REL próximo de zero nos modelos de causa, contra cerca de 0,67 no baseline
     `ultimo_valor` eólico V1;
   - valores de causa idênticos entre os baselines `ultimo_valor` e `mesmo_horario_recente`;
   - deslocamento de prevalência entre initial e tuning/calibração.
5. **Sensibilidade +24h:** descreva a degradação por tarefa e fonte nos recortes disponíveis.
   Seis recortes não existem na sensibilidade e não há baselines nela.
6. **Recomende por tarefa e fonte:** modelo, baseline ou "evidência insuficiente". Um baseline
   pode ser a melhor entrega. Não declare suficiência operacional por uma média.

## Limitações que toda conclusão deve citar

- Amostragem sistemática diária de t0 (semente 42) só em initial/refit: eólica 4/48 nas
  ocorrências e 14/48 em volume/causa; solar 16/48 nas ocorrências e completa em
  volume/causa. É desvio aprovado do §12.1. Prevalência amostrada ≈ completa (≤ 0,0004).
- Baselines de ocorrência com limiar fixo de 0,5 e `threshold or 0.5` no código.
- Subconjunto de features; elegibilidade por t0; volume condicional avaliado em todas as
  linhas.
- Recortes vazios ou ausentes na sensibilidade; métricas nulas sem motivo gravado em recortes
  de classe única.
- Avisos `LGBMDeprecationWarning`. LightGBM com 6 threads determinísticas, diferente do
  piloto em 1 thread.
- V1 eólica rodou no commit `560ae70`, antes da otimização de métricas (equivalência por teste
  de paridade); as demais, no `88634ed`.
- Commits de código foram criados na máquina dedicada, contrariando o §13.3.
- As extensões recomendadas não foram executadas: sementes 17 e 101 e intervalo de volume.

## Proibido

- Abrir, carregar ou pontuar o teste reservado (maio–agosto/2026).
- Mudar grades, candidatos, limiares de decisão ou metodologia para resgatar médias; mudança
  necessária cria nova versão do protocolo.
- Promover um segundo colocado usando o teste como seleção.
- Fazer merge em `main` sem aprovação explícita após esta análise.
- Push, salvo pedido do responsável.
- Apagar tentativas falhas ou resultados negativos.

## Entrega

- Tabelas de comparação e estados por tarefa/fonte, com as premissas, em `docs/`.
- Entrada no diário, com fatos, interpretação e decisão separados.
- Commits atômicos em português (Conventional Commits).
- Lista das verificações executadas e das não executadas.
