# Entrega focada em alertas — protocolo de 26/09/2026

Decisão solicitada pelo usuário: adiar novas experiências de volume e priorizar algo
entregável. Branch `codex/melhoria-previsao`, iniciada em `fd0a70b`, após fetch de todos
os remotos. A pasta original tem trabalho não commitado e permanece preservada.

Antes dos resultados desta execução:

- Reproduzir apenas o componente de ocorrência HGB vigente: mesmas 14 features,
  parâmetros, semente, janela de 365 dias e calendário. Sem escolha de nova receita.
- Avaliar agosto/2026, já examinado anteriormente: reprodução retrospectiva, nunca novo
  teste cego. Treinar com rótulos publicados na emissão de 31/07 às 20h.
- Usar os limiares `jan_abr` já registrados, sem ajuste em agosto. Comparar HGB servido,
  histórico 28d, mesmo slot do último dia publicado e último valor nas mesmas linhas.
  O HGB original e o componente de ocorrência servido são a mesma receita.
- Reportar AP, Brier, precisão, recall, F1, TP/FP/FN/TN, cobertura e nulos por fonte,
  mês e idade da informação. Baselines binários usam 0,5; histórico usa o limiar
  congelado da fonte como referência operacional comum, sem otimização própria.
- Dados: reaproveitar Parquet reais locais, conferir hashes contra auditoria anterior,
  registrar período e revisão desconhecida. Não baixar outra revisão sem necessidade.
- Ensaio inicial: solar, uma semana de avaliação e 30 dias de treino, somente para custo.
  A execução final usa 365 dias de treino e o mês completo para cada fonte em sequência.
- Limites: duas threads; um processo pesado por vez; interromper se o processo exceder
  3 GiB de RAM ou 20 minutos. Sem GPU, serviços pagos ou deploy.
- Entrega: replay local de alertas, painel específico e exportação CSV. Ranking por
  quantidade de janelas em alerta, seguido de probabilidade máxima; nenhuma ordenação
  por volume, conversão em receita financeira ou promessa de energia recuperável.
- As 48 probabilidades não serão somadas para estimar P(algum corte no dia), nem
  a frequência de alertas será chamada de probabilidade diária. Ausência permanece nula.
- Manter a composição e os modelos existentes intactos. O painel é uma entrada explícita
  para demonstração histórica; não muda automaticamente `product_predictor()`.

Os arquivos complementares do pacote (`LEIA-ME.md`, `CONTEXTO.md`, bundle e
`evidencias-recentes/`) não foram localizados no Desktop/Career e Downloads. O remoto
contém o commit indicado, o relatório v3, os experimentos anteriores e o diário.

## Extensão solicitada: quando + contexto de causa + valor de negócio

Antes de avaliar o contrafactual financeiro, em 26/09, branch própria
`codex/alertas-impacto-negocio`:

- Hipótese: concentrar uma manutenção flexível de 2 horas em janelas de maior
  probabilidade de corte pode reduzir a geração observada sacrificada pela parada.
- Unidade de avaliação: cada usina × dia completo de agosto, de forma independente.
  Não assumir que a usina faria manutenção todos os dias; o total representa a soma de
  oportunidades contrafactuais, não economia mensal realizável.
- Janela de trabalho hipotética fixa: 08h–18h; duração 2h; início em meia-hora.
  Baselines: 08h–10h; maior frequência histórica de corte em 28 dias;
  menor geração histórica por slot nos últimos 28 dias publicados. Comparar nas mesmas linhas.
- Escolha CurtaMap: maior média de P(corte) do bloco; desempate pelo horário mais cedo.
  Nunca usar geração, causa ou preço realizado do dia-alvo para selecionar o bloco.
- Avaliação posterior: geração verificada × 0,5h × fração da instalação parada × preço.
  Cenário principal: 10% da geração da entidade indisponível, escala linear ilustrativa.
  Ganho = custo do baseline − custo CurtaMap; permitir ganhos negativos.
- PLD oficial por submercado/hora da CCEE, se recuperável, apenas para avaliação ex post.
  Sem acesso ao arquivo, usar preço de cenário explicitamente informado (50/100/200 R$/MWh),
  sem chamá-lo de PLD observado. Não inferir faturamento contratado ou ressarcimento.
- Causa: distribuição das ordens observadas nos 28 dias publicados antes de cada emissão,
  com amostra e participação. É contexto histórico determinístico; não previsão do modelo.
- Relatar ganho e perda por fonte, proporção de casos melhores/piores e comparação com
  baseline de baixa geração. Não vender alerta bom como economia demonstrada automaticamente.
- Paradas reais exigem agenda, equipe, disponibilidade técnica e permissões do operador;
  o estudo não prova efeito causal de desligar equipamentos nem efeito na redistribuição do corte.
