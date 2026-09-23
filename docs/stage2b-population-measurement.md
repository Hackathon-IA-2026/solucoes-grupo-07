# Medição das populações da Etapa 2B

O módulo `curtamap.experimental.population_measurement` mede exatamente os filtros
atuais, sem treinar, amostrar, mudar elegibilidade ou abrir o teste reservado. Sua
saída é uma tabela de **4 rodadas × 5 segmentos × 4 tarefas = 80 células**. Fonte e
cenário devem ser informados explicitamente; esta medição aceita somente o cenário
principal `noturno_dia_util`, utilizado por `run_campaign_round`.

## Como interpretar as contagens

Cada linha de entrada representa `(fonte, id_ons, t0, horizonte)`. Não corresponde a
um alvo `tau` distinto: diferentes emissões podem compartilhar a mesma verdade.
As distribuições de dia, mês, entidade e horizonte são marginais do dataset inteiro,
não cruzamentos nem distribuições de cada célula. Por dia há mínimo, máximo e número
de emissões `t0` distintas. `fonte + id_ons` identifica entidades no relatório.

O código de referência é `campaign._range`, `campaign._task_filter`,
`campaign._validation_filter` e `training.internal_boundaries`. O medidor chama essas
funções, preservando limites inclusivos e o tratamento de nulos de Polars.

Defina `F = mínimo t0`, `C = cutoff`, `U = C − 56 dias`, `K = C − 28 dias` e
`V = início da validação`. `C` é a meia-noite após o último dia inteiramente liberado
em `V`, conforme o calendário conservador informado. O JSON registra esses valores
e os limites efetivos por rodada, sem assumir que `C = V`.

| Segmento | Limite inferior de t0 | Limite de t0 + 24h | target_available_at |
|---|---|---|---|
| initial | F inclusivo | ≤ U | ≤ U |
| tuning | U inclusivo | ≤ K | ≤ K |
| refit | F inclusivo | ≤ K | ≤ K |
| calibration | K inclusivo | ≤ C | ≤ V |
| validation | V inclusivo | ≤ fim da rodada | sem filtro |

Todos os quatro segmentos internos exigem `eligible_history`. Os filtros adicionais
de tarefa são:

- `corte_positivo`: `target_observed` e `true_positive` não nulo;
- `restricao_registrada`: `target_observed` e `true_restriction` não nulo;
- `volume_condicional`: `target_observed`, `true_volume_valid`, `true_positive` e
  `true_volume_mwmed > 0`;
- `causa`: `target_observed`, `true_restriction` e causa em REL/CNF/ENE.

Calibração só é consumida pelas duas tarefas de ocorrência. As células de
calibração de volume e causa têm `used=false` e contagens nulas, não zero exemplos.
Refit sobrepõe initial e tuning; não se devem somar segmentos como amostras únicas.
Tampouco se deve presumir que refit é exatamente a união: os limites de disponibilidade
de rótulos são diferentes, e initial/tuning têm expurgo temporal próprio.

Na **validação**, `prediction_rows` conta o painel aberto inteiro, incluindo histórico
inelegível e alvo não observado. `rows` conta o suporte potencial do alvo segundo
`campaign._metrics_for_prediction`: ocorrência com alvo não nulo; causa reconhecida
REL/CNF/ENE; volume com alvo finito. O modelo é chamado para todas as linhas e o
fallback substitui a previsão onde não há histórico elegível.

O regressor de volume é ajustado em cortes positivos elegíveis, mas sua avaliação
externa recebe o painel inteiro. `volume_metrics` seleciona pares alvo/previsão
finitos para MAE completo, WAPE e viés; apenas o MAE condicional restringe também
`alvo > 0`. Portanto `positive_volume_rows` informa o suporte potencial desse MAE;
não se reaplicam `true_positive`, `true_volume_valid` nem `target_observed` na avaliação.
O suporte realizado ainda depende da finitude das previsões produzidas depois.
Ocorrência rejeita probabilidades não finitas; este medidor não antecipa sucesso de
modelos nem cria métricas novas.

## Execução e evidência durável

Execute a partir do checkout aprovado, com os caminhos reais e um nome de saída novo:

```powershell
uv run python -m curtamap.experimental.population_measurement `
  --dataset-root '<diretório das partições date=...>' `
  --start 2023-10-01 --end 2026-05-01 `
  --source eolica --scenario noturno_dia_util `
  --calendar configs/experimental/calendar-2023-2026.json `
  --dataset-commit '<commit registrado na preparação>' `
  --expected-partitions 942 `
  --output '<diretório externo ao dataset>/populacoes.json'
```

O intervalo é `[start,end)` por dias e não pode ultrapassar 2026-05-01. O medidor
abre somente `features.parquet` das datas solicitadas, com projeção de 12 colunas.
Baselines, caches de alvos e partições reservadas não são abertos. Agregações são
preguiçosas; somente uma partição diária projetada pode permanecer no cache do
plano. As coletas devolvem 80 agregados ou distribuições marginais pequenas; nenhuma
matriz completa de treino é produzida. Esta estratégia limita memória por dia,
mas não promete uma única leitura física por arquivo.

JSON e `.progress.jsonl` são exclusivos e ficam fora do dataset. Cada início e
conclusão de partição é sincronizado com `flush`/`fsync`; o progresso registra suas
contagens e tamanho/mtime, detectando alteração desses metadados durante a leitura.
Uma falha escreve um evento final e relatório parcial, sem sobrescrever evidência
anterior. Não há retomada implícita: uma repetição precisa de novos arquivos.
O calendário pequeno é identificado por hash; os dados grandes não são re-hasheados.
Tamanho/mtime, paths e commits são proveniência, não prova criptográfica de integridade.

## Riscos de memória no treinamento atual

O medidor não elimina a necessidade de dimensionamento do treino:

1. `campaign` mantém initial, tuning, refit e calibração de uma tarefa simultaneamente;
   refit duplica parte das observações já presentes. Depois libera os splits da tarefa.
2. `train_family` mantém os dois candidatos internos durante a seleção e o refit.
   Os oito modelos finais ficam acumulados para a previsão compartilhada.
3. O pré-processamento gera arrays numéricos Float64, um empilhamento denso temporário
   e matrizes CSR; LightGBM recebe matrizes de treino e tuning ao mesmo tempo.
4. A validação usa partes, mas as métricas relêem todas as previsões projetadas de um
   modelo por vez. Planejamento de partes coleta um índice global; a verdade de
   episódios mantém todos os pares entidade/tau da rodada, deduplicados.
5. Os objetos de exceção guardados no relatório de execução podem reter traceback e
   referências temporárias. Esta é uma possibilidade de retenção, não um pico medido.

Contagens sustentam uma proposta de execução; não estimam sozinhas bytes de pico,
tempo, sucesso de convergência ou qualidade preditiva. Qualquer redução de população
ou mudança metodológica depende de uma decisão posterior explícita.
