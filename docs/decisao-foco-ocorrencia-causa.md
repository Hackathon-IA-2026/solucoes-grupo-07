# Decisão: o produto passa a se apoiar só em "quando" e "por quê"

Data: 26/09/2026. Branch: `etapa-2-nova-abordagem`. Documento de contexto para a integração
das Etapas 2, 3 e 4 na `main`.

## 1. A decisão em uma frase

O CurtaMap deixa de prever volume e deixa de tentar um modelo de causa. O produto passa a
servir duas informações: **quando** haverá corte, dada pela probabilidade por usina e meia-hora
para o dia seguinte, e **por quê**, dada pela causa provável tirada do histórico da usina. O
esforço seguinte vai para a **experiência de produto e a recomendação** construídas sobre
essas duas saídas, e não para ganhos marginais de modelagem.

## 2. Por que decidimos assim

Fatos medidos, todos já registrados no diário e em `docs/reports/nova-abordagem/`:

| Frente | Resultado | Onde está |
|---|---|---|
| Ocorrência (v1) | Vence o `historico` em 8 de 8 meses nas duas fontes. AP de 0,788 contra 0,740 na eólica e de 0,813 contra 0,747 na solar em jan–ago. Em setembro, fora da amostra, 0,921 contra 0,899 e 0,907 contra 0,867, com recall de alerta de 0,94 e 0,90 | README, seções 2 e 3 |
| Causa, modelo (v1) | Não vence a moda da usina: macro-F1 de 0,631 contra 0,649 na eólica. Na solar vence só 5 de 8 meses. Em setembro, a moda venceu nas duas fontes | README, seções 2 e 3 |
| Causa, frente C (v3) | Não adotada: no máximo 5 de 8 meses. A causa troca em só 16–17% dos casos | README, seção 7; diário 10/n |
| Regime nacional, frente B (v3) | Não adotada: perde na virada de fevereiro (−0,06 de AP na eólica) | diário 9/n |
| Volume eólico (v1 e v2) | Empate técnico com o `historico`. Nenhuma das 6 variantes da v2 passou da regra acima do ruído de semente | diário 7/n |
| Volume solar (v1) | O modelo venceu: WAPE de 0,851 contra 0,950 em jan–ago e de 0,607 contra 0,652 em setembro | README, seções 2 e 3 |
| Faixas de volume, frente A (v3) | Adotada só em recortes: k₀ nas duas fontes, e k₁/k₂ apenas na solar. Na eólica diária, a composição tem RPS pior que o `historico` (0,161 contra 0,155), e o k₀ diário é mal calibrado | README, seção 7; diário 11/n e 12/n |

Leitura da equipe (decisão, não medida):

- A previsão de ocorrência é o ponto forte. Ela é estável, confirmada fora da amostra e fácil
  de explicar.
- A causa histórica é tão boa quanto qualquer modelo que tentamos, e é transparente: "nas
  últimas 4 semanas, 80% das ordens nesta usina e neste horário foram ENE".
- O volume é o ponto fraco. Na eólica não sai do empate. Na solar há ganho, mas a equipe
  avaliou que ele não compensa o custo de explicar uma terceira saída com confiabilidade
  desigual entre as fontes. As faixas acrescentaram complexidade para um ganho pequeno e em
  casos específicos.
- **Registro honesto:** o volume solar do modelo vencia o baseline. Descartá-lo é escolha de
  produto (simplicidade e uma única história confiável), e não falha medida do modelo.

## 3. O que ficou na branch

- **Modelo:** `diario_ocorrencia_v1`, com um classificador HistGradientBoosting de ocorrência
  por fonte, as mesmas 14 features, os mesmos parâmetros e os mesmos limiares da v1 (eólica
  0,3461; solar 0,3212).
  - Manifesto: `docs/reports/nova-abordagem/modelo-congelado-ocorrencia.json`.
  - Artefato: `models/previsao/diario_ocorrencia_v1_2026-08-30.joblib`, fora do Git.
  - Regeneração em cerca de 1 min:
    `uv run python -m curtamap.previsao.treinar --limiares data/interim/previsao/limiares.json --manifesto docs/reports/nova-abordagem/modelo-congelado-ocorrencia.json`.
- **Paridade verificada:** o `p_corte` do novo artefato é idêntico, com diferença máxima de 0
  e alertas iguais, ao do classificador de ocorrência do artefato v3 em dois dias-alvo de
  agosto (25 e 26/08; 22.656 linhas). Por isso as métricas de ocorrência do backtest e de setembro valem
  para ele sem novo processamento.
- **Causa:** servida sempre pela participação nas ordens da usina no slot em 28 dias, com
  recurso ao estado em 7 dias (`tipo_saida_causa`). É a mesma regra servida na v1.
- **Volume:** não é previsto. As colunas do contrato ficam nulas, e `tipo_saida_volume` vale
  `nao_previsto`.
- **Contrato:** a "ausência de previsão" passa a ser só `p_corte` nulo. As colunas de volume
  continuam no esquema, para que as outras etapas não quebrem antes da integração.
- **Histórico exigido:** voltou a 92 dias (`HISTORY_DAYS`), porque os 130 dias só eram
  necessários para as faixas.
- **Removido do código**, mas recuperável:
  - faixas (`faixas.py`, `faixas_servico.py`);
  - sinais de restrição (`restricoes.py`);
  - runners `scripts/experimentos/` da v2 e da v3;
  - componentes de volume e de causa do modelo.
- **Mantido como evidência:** relatórios em `docs/reports/nova-abordagem/` (incluindo `v2/`
  e `v3/`), manifestos antigos e as entradas 1/n a 12/n do diário.

### Como recuperar o que foi removido

| O quê | Onde |
|---|---|
| Estado completo da v3 (faixas, frentes A/B/C, runners) | tag `arquivo/etapa-2-v3-faixas` (commit `fd0a70b`) |
| v1 com volume p10–p90 e causa HGB | commit `7ee94f4`, que é também o `origin/main` atual |

## 4. Situação da `main` (investigada em 26/09)

- `origin/main` aponta para `7ee94f4` ("docs: corrija a faixa de ganho de AP e precise o
  handoff"). Esse commit é **ancestral** desta branch. Portanto, a `main` recebeu a nova
  Etapa 2 **até a v1**: ocorrência, volume exato com p10–p90 e causa pela moda da usina. Ela
  **não** tem nada da v2 nem da v3 (faixas).
- A causa provável é que esta branch já teve a `main` como upstream, e os pushes daquele
  período foram para lá. Hoje o upstream está correto (`origin/etapa-2-nova-abordagem`).
- A `etapa-4-interface-nova-abordagem` também parte da `main` atual e, portanto, da v1.
- A `main` local está 28 commits atrás de `origin/main`.
- **Consequência:** limpar a `main` não exige cirurgia separada. Basta levar esta branch à
  `main` (fast-forward ou merge), e a `main` herda a decisão. Nada foi alterado na `main`
  nesta sessão.

## 5. O que muda para as Etapas 3 e 4 na integração

A recomendação e o painel hoje assumem volume. Pontos concretos:

- **Etapa 3** (`origin/etapa-3-recomendacao`, `recommendation.py`):
  - `recommendation.py` levanta erro se um alerta tiver `energia_esperada_mwh` nulo (linhas
    108–109);
  - a mesma função soma energia em risco (linhas 125–126).
  - Com o novo preditor, todo alerta terá energia nula. É preciso redesenhar a recomendação
    para partir de janela, probabilidade e causa, sem MWh.
- **Etapa 4** (`origin/etapa-4-interface-nova-abordagem`):
  - `painel/proveniencia.py:61` trata volume nulo como "sem previsão";
  - `painel/ranking.py` ordena por energia esperada;
  - `ui/graficos.py` e `ui/operacao.py` desenham energia e banda p10–p90.
  - Tudo isso precisa passar a usar `p_corte`, o alerta, as horas em alerta e a causa.
- **Contrato:** depois de adaptar as duas etapas, remover de `FORECAST_SCHEMA` as colunas de
  volume. Hoje elas continuam por compatibilidade.
- **Impacto financeiro e de CO₂:** sem volume previsto, não há MWh recuperáveis por janela.
  Se a apresentação quiser um número de valor, ele deve vir de um **cenário declarado**, por
  exemplo "horas em alerta × potência de referência histórica da usina", com premissas
  visíveis e análise de sensibilidade. Nunca deve ser apresentado como previsão.

## 6. Direção de produto a partir daqui

A mensagem muda de "nosso modelo é muito preciso" para "com duas informações simples e
confiáveis, entregamos ao gerador uma decisão pronta para o dia seguinte". Hipóteses de
produto a validar, nenhuma delas implementada:

- **Agenda do dia seguinte:** por usina, as janelas de 30 min em alerta, com a probabilidade
  e o limiar visíveis, emitidas às 20h do dia anterior.
- **Causa como contexto de ação:** a causa provável, com a frase de proveniência ("moda das
  ordens da usina neste horário nas últimas 4 semanas"), orienta o tipo de ação. O
  significado operacional de cada código (`REL`, `CNF`, `ENE`) e a ação compatível precisam
  ser confirmados no Caderno de Desafios antes de irem para a tela.
- **Ações que não dependem de volume:**
  - programar manutenção nas janelas em que o corte é provável;
  - avisar a operação e o comercial;
  - registrar a ordem esperada para conferência posterior com o ONS.
- **Confiança explícita:** o painel mostra o desempenho histórico medido, com AP, recall e
  precisão do alerta em setembro, e deixa claro o que é modelo (ocorrência) e o que é regra
  histórica (causa).

## 7. Limitações que continuam valendo

- Não há previsão meteorológica. O nível do dia-alvo é a parte difícil (README, seção 4).
- Setembro teve só 24 dias e não testou uma mudança de regime.
- O modelo não tem recalibração periódica.
- A causa histórica erra quando o regime muda. Ela é o melhor que medimos, não um diagnóstico
  causal.
