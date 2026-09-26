# Protocolo do experimento: histórico × HGB ajustado × rede temporal

Registrado em 26/09/2026, **antes** de qualquer resultado dos candidatos novos. Mudanças
posteriores devem ser acrescentadas ao fim deste arquivo, com data e motivo, sem reescrever
o que está acima.

## Base

- **Branch:** `codex/experimento-rede-temporal`, criada de `origin/main` no commit `7ee94f4`.
  É o mesmo commit de `origin/etapa-2-nova-abordagem`; `etapa-4-interface-nova-abordagem`
  não altera `src/curtamap/previsao/`.
- **Dados:** snapshot do hackathon em `data/raw` (até 31/08/2026) e a publicação atual de
  setembro do ONS, baixada às 17:49 UTC de 26/09/2026, com `Last-Modified` 26/09 15:06 GMT e
  cobertura de 01 a 25/09. O manifesto e os SHA-256 ficam em `manifesto.json`.
- **Unidade e informação** (do código de `curtamap.previsao`):
  - a emissão é às 20h da véspera do dia-alvo T;
  - as 48 saídas são as meias-horas 00:00–23:30 de T (`t0` = 00h de T, horizonte 1..48);
    "48" são meias-horas, não horas;
  - só entram dados até o fim do último dia liberado L. O dado de um dia é liberado às 19h30
    do dia útil seguinte, com fins de semana, feriados e pontos facultativos
    (`configs/calendario-2023-2026.json`);
  - `T − L` fica entre 2 e 7 dias.

## Períodos

| Período | Papel | Observação |
|---|---|---|
| jan–abr/2026 (4 dobras mensais) | **Seleção**: variantes, hiperparâmetros, arquitetura, épocas e limiares | Já usado como desenvolvimento pela Etapa 2 |
| mai–ago/2026 (4 dobras mensais) | **Avaliação dos candidatos congelados** | Já visto pela receita anterior: não é cego |
| 01–24/09/2026 | Avaliação secundária | Resultados já examinados pela Etapa 2: **não é teste cego** |
| 25/09/2026 | Reservado, olhado uma única vez depois do congelamento | Um dia só: nenhuma conclusão depende dele |

Em cada dobra mensal M, o treino usa só rótulos até o último dia liberado na emissão da
véspera do dia 1º de M, com origem expandindo. Todas as usinas de uma data ficam do mesmo
lado da divisão. Validações internas (por exemplo, a parada antecipada da rede) usam só dias
anteriores a esse corte.

## Linhas avaliadas

- Todos os concorrentes são avaliados nas mesmas linhas: meias-horas de T com rótulo válido
  (`y_corte` não nulo), geradas por `build_features` com o `release_map` da emissão das 20h.
- Se algum concorrente não tiver previsão numa linha, isso é contado e reportado como
  cobertura. As métricas principais usam a interseção.

## Concorrentes

- **A. Histórico:**
  - ocorrência = `hist_28d`; volume = `vol_hist_28d`;
  - a variante "servida" reproduz o produto: volume eólico = `vol_hist_28d`, com o HGB
    original quando o histórico é nulo; volume solar = HGB original.
- **B0. HGB original:** `curtamap.previsao.modelo` sem mudança (controle).
- **B1. HGB com ajustes:** variáveis de mudança recente, janela de treino e pesos por
  recência, e busca pequena de hiperparâmetros, escolhidos em jan–abr.
- **C. Rede temporal pequena:** GRU compartilhada entre fontes; justificativa no relatório.

## Métricas de seleção (fixadas antes)

- **Volume:** WAPE diário (soma por usina × dia) médio das dobras de seleção. É a métrica
  de planejamento do gerador. Desempate: WAPE por meia-hora. Viés e MAE são reportados, mas
  não decidem.
- **Ocorrência:** AP média das dobras de seleção. Brier é reportado.
- **Causa:** fora deste experimento.
- **Limiar de alerta:** escolhido pelo F1 nas previsões fora da amostra de jan–abr, com a
  função corrigida, e aplicado a mai–ago.
- Nenhum ajuste mira um mês específico. Fevereiro é investigado depois, como diagnóstico.

## Regra de recomendação

Um candidato só é recomendado para substituir o componente servido se, em mai–ago:

- vencer na média;
- vencer em pelo menos 3 das 4 dobras;
- não piorar setembro de forma material.

Magnitude, estabilidade entre sementes e custo entram na recomendação escrita.
