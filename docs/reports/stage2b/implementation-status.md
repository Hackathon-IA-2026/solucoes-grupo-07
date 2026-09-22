# Relatório factual da Etapa 2B — implementação no Mac

Data: 22/09/2026. Estado: `execucao_pendente`.

Commits de código da 2B: `32a1ac6`, `1bf8e0e`, `8129e6d` e `1cbfcb2`.

## Implementação realizada

- Contrato de emissão com 48 horizontes diretos, primeira janela iniciando em `t0` e término
  em `t0 + 24h`.
- Cenários `noturno_dia_util` e `noturno_mais_24h`, calendário conservador 2023–2026 e corte
  as-of por liberação às 19h30 do próximo dia útil.
- V1–V4 com treino crescente, segmentos internos de ajuste/calibração e bloqueio separado do
  teste reservado.
- Preparação colunar mensal dos dois Parquet principais, features históricas as-of, painel
  aberto/fixo, elegibilidade de 28 dias/80%, novos IDs, idade, agregados, episódios e cauda.
- Baselines de último valor, ontem no mesmo horário, mesmo horário recente e estatísticas
  históricas, com frequência, média positiva, majoritária, última causa, fallback, idade e
  disponibilidade nativa.
- Regressões logísticas, Gamma GLM, logística multinomial e LightGBM, com duas configurações
  congeladas, pré-processamento esparso ajustado no treino, calibração sigmoide e limiar F2.
- Métricas estruturadas das três tarefas, quatro combinações do pipeline de volume, recortes
  de horizonte, histórico, painel, idade, fim de semana/feriado, episódio e cauda.
- Runs imutáveis com manifesto, configuração, modelos, previsões, métricas, falhas, retomada e
  checksums; caminhos externos com espaços foram exercitados.

## Testes e verificações realizados no Mac

- Testes sintéticos cobrem os contratos temporais, disponibilidade, nulos/zero/indeterminado,
  os 21 volumes indeterminados, classes ausentes, ausência de PAR sintético, baselines,
  agregados as-of, treino-only, persistência, reprodutibilidade e bloqueio do teste.
- LightGBM foi importado e ajustado em fixtures sintéticas após instalação local de `libomp`.
- O `preflight` foi executado com caminhos contendo espaços e reconheceu branch, commit, dois
  Parquet principais e espaço livre.
- `uv run pytest`: **141 testes passaram** em 13,40 s.
- `uv run ruff check .`, `uv run ruff format --check .` e `git diff --check` foram executados
  no fechamento; o resultado final é registrado também no diário.

## Execução técnica pequena

Não executada com dados reais no Mac. A separação aprovada reserva o piloto de recursos ao
computador dedicado. Existe comando específico que não emite métricas de seleção.

## Experimentos completos executados

Nenhum. Não há métricas preditivas reais, modelo vencedor, tempo de campanha ou consumo real
do computador dedicado neste relatório.

## Resultados positivos e negativos

Não aplicável antes da campanha. Resultados sintéticos validam comportamento de software, não
desempenho do CurtaMap. Nenhum baseline ou candidato pode ser promovido com essas fixtures.

## Falhas observadas

- O primeiro carregamento do LightGBM no macOS falhou por ausência de `libomp.dylib`. O runtime
  foi instalado no Mac e a exigência foi documentada; o destino deve verificar sua própria
  dependência OpenMP.
- Nenhuma falha experimental real foi observada porque a execução pesada está pendente.

## Limitações e hipóteses

- O calendário é uma simulação conservadora e não reproduz a escala operacional real do ONS.
- O snapshot revisado não contém vintages; o backtest continuará retrospectivo sob
  disponibilidade hipotética.
- O runner materializa a matriz de ajuste de cada estimador em memória. O piloto deve medir se
  todos os exemplos elegíveis cabem em 32 GB; qualquer contingência de amostragem exige retorno
  ao Mac e nova decisão registrada.
- Origem LOC/SIS, atraso +72h, intervalos de volume e sementes 17/101 são extensões posteriores
  ao mínimo; estão desativadas na configuração inicial e não devem atrasar a campanha mínima.

## Decisões deixadas para a Etapa 2C

Astra deve aplicar os critérios aprovados por tarefa e fonte, considerar todas as rodadas,
baselines, incerteza, falhas e custos, e então decidir se algum candidato é defensável. A 2B não
escolhe vencedor e não libera o teste final.
