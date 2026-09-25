# Recalibração periódica: regra fixada antes dos resultados (25/09/2026)

Estado: **pré-registro**, escrito e commitado antes de rodar qualquer simulação. Exploratório,
fora do protocolo completo. O teste reservado (maio–agosto/2026) continua fechado.

## Pergunta

O modelo solar ordena bem o risco, mas o calibrador fica congelado por quatro meses e subestima
o nível de corte quando a prevalência salta (V2, maio–agosto/2025). Reajustar o calibrador, ou
um fator de viés no volume, com os rótulos que o ONS vai liberando corrige isso sem perder
ranking?

## Fato que fundamenta o desenho

A defasagem `target_available_at − tau` nos datasets solares é de 20 h no mínimo, 36–41 h na
mediana e 91–163 h no máximo em todos os meses de 2024–2026, com cerca de 20 liberações por
mês. Os rótulos saem praticamente todo dia útil. Por isso, um reajuste semanal usa informação
realmente disponível.

## Simulação (post-hoc, sobre `predictions.parquet` já salvos; nada é retreinado)

- **Agenda:** reajuste nas datas `R = início da validação + 7k dias` (k ≥ 1), à meia-noite. As
  linhas com `t0 ∈ [R, R + 7 dias)` usam o ajuste feito em `R`. A semana 0 usa o calibrador
  congelado original.
- **Janela de ajuste em `R`:** linhas de validação com `eligible_history`, rótulo com
  `target_available_at ≤ R`, `t0 + 24 h ≤ R` e `t0 ≥ R − 28 dias`. Se a janela cobrir menos de
  7 dias distintos de `t0`, mantém o ajuste anterior.
- **Corte:** `fit_sigmoid_calibrator(raw, y, seed=42)`, o mesmo usado no treino, aplicado a
  `raw`. O limiar F2 é reajustado na mesma janela e só é reportado.
- **Volume (`volume_total`):** fator `f = Σ real / Σ previsto` na janela, limitado a
  [0,5; 2,0], multiplicando a previsão do modelo.
- **Linhas sem histórico elegível** mantêm o fallback `historico`, sem alteração.
- **Autoconferência:** com o reajuste desligado, a simulação precisa reproduzir exatamente a
  coluna `prediction` salva. Se não reproduzir, o resultado é descartado.

## Runs avaliadas

- **Corte:** `rapido-fv-v{1..4}-corte-003` (alvo principal) e `rapido-eol-v{1..4}-corte-003`
  (diagnóstico).
- **Volume:** `rapido-fv-v{1..4}-voltot-004` e `rapido-eol-v{1..4}-voltot-004`.

## Regra de decisão

**Corte, recalibrado contra congelado (003), nas mesmas linhas, V1–V4:** adota a recalibração
somente se:

1. o Brier da V2 cair pelo menos 0,02;
2. nenhuma rodada piorar o Brier mais de 0,005;
3. nenhuma rodada perder mais de 0,005 de AP.

Depois, reaplica-se o §11 contra o `historico`, incluindo a proteção de Brier médio (+0,01).

**Volume, recalibrado contra o comparador da fonte** (`historico` na solar,
`mesmo_horario_dia_anterior` na eólica), pelo §11 completo:

- redução média de MAE ≥ 5%;
- WAPE médio não pior;
- melhoria estrita em pelo menos 3 de 4 rodadas;
- nenhuma rodada com MAE pior que +10%.

**Resultado negativo é válido.** Não se testam janelas, frequências ou limites alternativos
para salvar a hipótese. Se a regra reprovar, a receita fica como está e a limitação é
registrada.

## Incluído no mesmo passo

Incerteza semanal da causa eólica (`rapido-eol-v{1..4}-causa-005`): diferença semanal de
macro-F1 contra o `historico`, com bootstrap de 1.000 reamostragens (semente 42), pela mesma
receita do AP semanal. Pelo §11.2, um IC 95% contendo zero torna a célula `inconclusivo`.
