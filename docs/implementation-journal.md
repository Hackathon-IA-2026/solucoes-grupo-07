# Diário de implementação do CurtaMap

Registro cronológico das evidências, decisões, aprendizados e limitações produzidos durante o projeto. Este documento complementa o histórico do Git: os commits mostram a mudança; o diário explica o raciocínio e seu significado para o usuário e para a apresentação.

As entradas são append-only. Quando uma conclusão mudar, uma nova entrada deve explicar a evolução em vez de apagar o entendimento anterior.

## 2026-09-19 - Fundação técnica e aquisição das bases

### Contexto e pergunta

Era necessário preparar um repositório reproduzível e obter as bases oficiais sem versionar arquivos grandes ou depender de procedimentos manuais diferentes em cada máquina.

### Fatos e evidências observados

- O Caderno do Hackathon aponta uma pasta pública com cinco Parquet tratados do ONS e dois materiais de apoio do ERA5.
- As bases somam mais de 100 milhões de registros; portanto, não devem ser carregadas integralmente em pandas nem enviadas ao Git.
- O projeto precisa permanecer open source sob licença MIT e ser executável localmente antes de depender da AWS.

### Interpretação e decisão

- Adotar Python 3.12 e `uv` para um ambiente reproduzível.
- Manter os dados em `data/raw/`, ignorados pelo Git.
- Automatizar descoberta e download com um módulo do próprio pacote CurtaMap.
- Preservar arquivos existentes por padrão e exigir `--force` para substituição intencional.

### Alternativas consideradas

- Download manual: descartado como fluxo principal por ser pouco reproduzível.
- Versionar os Parquet: descartado por tamanho, custo e risco de duplicação.
- Baixar automaticamente durante `uv sync`: descartado para não gerar uma transferência grande e inesperada.

### Implementação e validação

- Criado `curtamap.download_data` com modos de listagem, download e inclusão opcional dos tutoriais.
- O desenvolvimento seguiu Red-Green-Refactor; os testes revelaram e corrigiram inicialmente um problema de empacotamento do módulo.
- A listagem remota confirmou os cinco Parquet esperados.

### Limitações e incertezas

- O script não registra checksums dos arquivos baixados ainda.
- O tamanho dos arquivos precisa ser considerado antes de cópias adicionais ou envio ao S3.

### Valor para o usuário e para a apresentação

A aquisição reproduzível demonstra que o CurtaMap pode ser reconstruído a partir de dados públicos e rastreáveis, fortalecendo a credibilidade técnica e a possibilidade de evolução além do protótipo.

### Próximos passos

Auditar schemas, cobertura, duplicidades e domínios; depois formalizar e testar a definição do alvo de curtailment.

## 2026-09-19 - Arquitetura inicial e ambiente AWS

### Contexto e pergunta

Era necessário decidir uma direção técnica sem antecipar algoritmos ou acoplar o produto a serviços que poderiam não estar disponíveis no ambiente do Hackathon.

### Fatos e evidências observados

- O ambiente permite ECS, ECR, CodeBuild, S3, DynamoDB, SageMaker, Bedrock, Cognito e observabilidade.
- O provisionamento deve ocorrer por CloudFormation ou CDK, nas regiões `us-east-1` ou `us-west-2`.
- Toda a solução deve permanecer em um único repositório.
- O problema central é tabular e temporal; modelos generativos não calculam a previsão de curtailment.

### Interpretação e decisão

- Manter frontend, backend, modelagem e infraestrutura em monorepo.
- Tratar React/Vite + FastAPI como candidato para a interface final e Streamlit como protótipo e contingência, aguardando um spike comparativo.
- Definir os três problemas de modelagem - ocorrência, volume e causa - sem escolher antecipadamente os algoritmos.
- Tratar Bedrock e NVIDIA NIM como provedores opcionais e substituíveis para explicação em linguagem natural.

### Alternativas consideradas

- Fixar Streamlit imediatamente: adiado por possível limitação de customização visual.
- Fixar React imediatamente: adiado pelo custo adicional de implementação e testes.
- Usar um LLM como núcleo: descartado porque o valor quantitativo precisa ser calculado por modelos e regras rastreáveis.

### Implementação e validação

- A arquitetura, as restrições AWS e o roadmap foram documentados.
- LightGBM e SHAP foram removidos das dependências para não converter candidatos em decisões prematuras.
- O esqueleto Streamlit permaneceu executável e retornou health check válido.

### Limitações e incertezas

- Permissões e custos efetivos dos serviços AWS ainda precisam de um spike.
- A tecnologia final da interface e os algoritmos serão escolhidos após evidências de esforço e desempenho.

### Valor para o usuário e para a apresentação

O desenho evita tecnologia pela tecnologia: cada componente deverá demonstrar utilidade para antecipação, explicação ou decisão do gerador. Isso sustenta uma defesa clara do papel central da IA e das limitações assumidas.

### Próximos passos

Executar a etapa de fundamentos e dados antes de iniciar spikes de interface, modelos candidatos ou implantação AWS.

## 2026-09-19 - Criação do fluxo contínuo de narrativa

### Contexto e pergunta

Como garantir que decisões tomadas por agentes de IA permaneçam compreensíveis e estudáveis pelo responsável humano, além de úteis para o storytelling final?

### Fatos e evidências observados

- O histórico do Git registra alterações, mas não captura sozinho todas as evidências, interpretações, alternativas e implicações de negócio.
- A EDA e os experimentos futuros produzirão descobertas que podem mudar tratamento, modelagem, produto e narrativa do pitch.

### Interpretação e decisão

Tornar este diário uma etapa obrigatória da conclusão de toda tarefa material. Cada entrada deve separar fatos, interpretações, decisões e hipóteses, conectando o trabalho ao usuário final e à apresentação.

### Alternativas consideradas

- Depender apenas das mensagens das sessões: descartado porque são dispersas e difíceis de consultar depois.
- Depender apenas dos commits: insuficiente para explicar resultados analíticos e raciocínio de negócio.
- Registrar somente ao final: descartado pelo risco de perda de contexto e reconstrução retrospectiva imprecisa.

### Implementação e validação

- O fluxo foi formalizado no `AGENTS.md`.
- Este arquivo foi criado como registro cronológico append-only.
- As principais decisões anteriores foram recuperadas para iniciar a narrativa com contexto.

### Limitações e incertezas

O diário exige disciplina contínua e deve evitar tanto omissões quanto excesso de detalhes sem valor decisório.

### Valor para o usuário e para a apresentação

O responsável passa a ter uma fonte única para estudar o problema, auditar o trabalho delegado e recuperar fatos, decisões e histórias que sustentem uma apresentação de negócio convincente.

### Próximos passos

Na Etapa 1, registrar separadamente a auditoria, a definição do alvo, cada descoberta relevante da EDA e qualquer mudança metodológica decorrente dos dados.

## 2026-09-19 - Etapa 1.1: contrato, auditoria e escolha da base analítica

### Contexto e pergunta

Precisávamos saber se os cinco arquivos representavam a mesma população e se poderiam
ser usados sem multiplicar energia. Antes de implementar, foram lidos AGENTS, roadmap,
arquitetura, diário, notas do pitch e documentação de dados; Git estava limpo.

### Fatos e evidências observados

A auditoria colunar encontrou 102.739.069 linhas físicas. As principais somam
10.806.720 observações sem chaves nulas, duplicatas ou lacunas internas. A integrada
exclui exatamente 1.365.552 linhas eólicas de out/2023–mar/2024; não altera valores.
O detail contém 385/56 duplicatas excedentes eólicas/solares e 358.844/2.064 janelas
internas ausentes. Há 267 entidades principais, majoritariamente conjuntos; não são
267 usinas individuais. A geração das 15 usinas individuais diretamente comparáveis
coincide em 732.384 intervalos. Fontes, consultas, checksums, schemas, nulos gerais e
condicionais mensais, domínios e extremos estão em `docs/reports/stage1/audit.json`.

### Interpretação e decisão

Usar a união das duas principais na EDA, sem concatenar integrada ou detail. Manter
`fonte + id_ons` mesmo sem colisão atual entre fontes. Reter anomalias como achados:
29 gerações negativas, um limite negativo e extremos meteorológicos/disponibilidade
exigem tratamento explícito; nenhum percentil vira regra física automaticamente.

### Alternativas consideradas

Usar somente a integrada perderia seis meses eólicos. Somar detail às principais
contaria usinas dentro de conjuntos novamente. Deduplicar sem inspecionar seria uma
regra sem evidência. Comparar todos os meses de uma só vez gerou spill excessivo;
a comparação exata por mês preservou a semântica e reduziu o custo operacional.

### Implementação e validação

Criados `data_contract.py` e `audit.py`, JSON e Markdown reproduzíveis. TDD começou
com falha de importação do módulo ausente; fixtures cobriram schema, fonte composta,
chaves nulas, duplicatas, lacunas, off-grid, infinitos, negativos, flags, identidade,
nulos condicionais, arquivos vazios/ausentes e diferenças de multiconjunto.
As sete verificações de auditoria passaram antes da execução completa do snapshot.
O Opus 5 (`claude-opus-5`, effort high) fez revisão metodológica somente leitura;
aceitamos investigar identidade, rótulo sem limite e distinguir comando de corte positivo.

### Limitações e incertezas

Fuso e convenção início/fim da janela não foram confirmados. O detail não tem chave
formal de conjunto neste snapshot; o join individual é apenas uma validação parcial.
Achados reais fazem `--strict` falhar deliberadamente, embora os testes passem.

### Valor para o usuário e para a apresentação

A unidade operacional é usina **ou conjunto**. A distinção evita apresentar uma
promessa de precisão por usina física que a base principal não sustenta. A auditoria
fornece evidência de credibilidade e limites, não melhoria de previsão.

### Próximos passos

Formalizar o alvo, medir o impacto das anomalias e confrontar a fórmula com a GNR
publicada diretamente pelo ONS, antes de interpretar tendências no notebook.

## 2026-09-19 - Etapa 1.2: alvo e confronto com GNRa publicada

### Contexto e pergunta

A fórmula proposta mede geração não realizada e corresponde aos campos oficiais?

### Fatos e evidências observados

Os dicionários ONS atuais incluem GNRa com a diferença referência menos geração,
clipping zero e condicionamento à limitação. Foram baixados 64 arquivos oficiais dos
mesmos períodos, separados em `data/interim/official`. A fórmula reproduziu os
3.127.621 valores publicados não nulos, sem divergência acima de 0,001 MW. Há 129.615
GNRa nulas em intervalos solares limitados de 2024: soma parcial não é total comparável.
O snapshot local de 2025 soma 37,21075 TWh; publicação atual difere −0,0160% na eólica
e −0,0212% na solar. Fontes/checksums/comparações estão nos relatórios `official-*`.

### Interpretação, decisão e alternativas

Separar comando de limitação e volume positivo. Usar referência comum, não referência
final REL para todas as causas. Preservar negativos e sinalizar 21 volumes eólicos
indeterminados; manter variante bruta de sensibilidade, 3.732,3295 MWh nesses casos.
Descartamos imputaçao silenciosa e substituição dos originais por dados revisados.
A revisão do Opus foi avaliada criticamente e preservada em `docs/reviews/`.

### Implementação e validação

Função pura Polars e projeção DuckDB têm testes de paridade, nulos, zero, clipping,
negativos, NaN/infinito, causas/origens, fonte e conversão de unidade. O comparador
público tem testes de cobertura, diferenças e integração das cinco dimensões.
TDD confirmou módulo ausente e depois rejeitou comparação de totais incompletos;
a implementação mantém esses deltas nulos. Consulte `docs/target-definition.md`.

### Limitações e incertezas

Comparar totais não reconcilia revisões linha a linha. O JSON detail eólico contém
campos do principal; preservamos a resposta e conferimos o PDF. Fuso/início/fim de
janela e latência de publicação seguem pendentes. Totais são estimativas provisórias.

### Valor para o usuário e apresentação

Podemos explicar de onde vem cada MWh analítico, sem prometer compensação, recuperação
ou equivalência com estatísticas comerciais. Nenhum LLM produziu as métricas.

### Próximos passos

Concluir a interpretação da EDA no notebook, inventário contra vazamento, notas do
pitch, revisão de código pelo Opus e fechamento documental da Etapa 1.

## 2026-09-19 - Etapa 1.3: revisão independente do trabalho anterior e revisões do ONS

### Contexto e pergunta

Um segundo agente recebeu a tarefa de revisar criticamente tudo o que a Etapa 1 já havia
produzido (auditoria, alvo, validação pública) antes de concluí-la. A pergunta era: as
conclusões registradas nas entradas 1.1 e 1.2 resistem a uma leitura adversarial?

### Fatos e evidências observados

- **Correção da entrada 1.2.** A entrada anterior citava só os deltas de 2025 (−0,0160% e
  −0,0212%). Os outros anos têm deltas maiores: eólica −0,238% (2023), **−0,850%
  (2024)**; solar −0,482% (2026). Além disso, `formula_validation` compara a GNRa publicada
  com a fórmula aplicada **ao próprio arquivo oficial**. Ela valida a definição, mas não
  diz se o snapshot é igual à publicação.
- Foi criada uma junção linha a linha snapshot × publicação atual (`revision_check`), pela chave
  `fonte + id_ons + din_instante`. Resultados: 10.806.096 linhas casam; 132.290 têm geração,
  limite ou referência diferentes; 173 têm rótulo diferente; 52.310 intervalos mudam de
  energia (soma −298.040 MWh); **47 de 64 meses** diferem. Os arquivos oficiais foram
  modificados entre 13/02/2025 e 19/09/2026; meses de 2023 foram regravados em 14/09/2026.
- A primeira versão da junção indicava cerca de 584 mil “revisões” solares em 2024. A
  investigação mostrou que eram só representação: `NULL` no snapshot e `''` na publicação atual.
  Com a normalização, sobram 173 diferenças reais de rótulo.
- 624 linhas de nov/2024 trocaram de código: `BA4ECLA` virou `CJU_BA4ECLA`.
- Bug de SQL: o alias `matched` sem `AS` é palavra reservada no DuckDB e quebrou a consulta
  nova. Todos os aliases da função passaram a usar `AS`. Também foi corrigida a precedência
  de `AND`/`OR` no contador `changed_energy`.
- Auditoria: `identity_drift` ignorava trocas entre `NULL` e valor, e o join detail × principal
  não media multiplicação por duplicatas. Após a correção e a reexecução (48 s): nenhuma
  mudança de UF, subsistema ou CEG, e `duplicated_join_rows = 0`. As conclusões de 1.1 se
  mantêm.
- O detail eólico começa em 01/01/2023, nove meses antes da principal. Isso não estava
  documentado.

### Interpretação e decisão

- As diferenças entre o snapshot e a publicação vêm de **revisões pós-operação do ONS**, não da
  fórmula. Todos os totais passam a ser tratados como provisórios. O JSON agora carrega
  `status: provisional` e o escopo explícito (não é reconciliação financeira, comercial nem CCEE).
- O snapshot continua sendo a fonte do alvo, porque é a base oficial do desafio. A publicação
  atual serve só como validação. Não substituímos os dados.
- Revisões são um risco de vazamento temporal: um backtest com dados revisados usa
  informação inexistente em `t0`. Isso foi registrado no inventário.
- `rotulo_sem_limite` passou a ignorar texto vazio, e foi criada a flag `origem_desconhecida`,
  simétrica a `razao_desconhecida`.

### Alternativas consideradas

- Comparar só totais: rejeitado, porque não separa revisão de erro de fórmula.
- Tratar `''` como rótulo: rejeitado, porque inflaria contradições artificiais em dados futuros.
- Reconciliar entidades renomeadas por nome: adiado, pois nome não é chave validada.

### Implementação e validação

Ciclo TDD: testes novos falharam primeiro (`ImportError` de `revision_check`, `KeyError` de
`origem_desconhecida`, contagem de `cegs` com `NULL`, ausência de `join_rows`) e depois
passaram. Os casos cobertos são: linha só em um lado, valor revisado, `''` × `NULL`,
referência igual à geração, conversão 100 MWmed → 50 MWh, grade incompleta preservada e
paridade Polars × DuckDB. Os relatórios `audit.json` e `official-comparison.json` foram
regenerados.

### Revisão metodológica externa

A revisão da entrada 1.1 foi feita com o modelo `claude-opus-5`, esforço `high`, somente
leitura, sem edição automática. O metadado local confirma o modelo. Cada uma das 15 sugestões
foi triada em `docs/reviews/opus-stage1-methodology.md`:

- **Aceitas:** 2, 5, 6, 8, 9, 10, 11, 12, 13 e 15.
- **Aceita como limitação:** 4, sobre fuso e convenção de início/fim.
- **Adaptadas:** 1 (dois alvos, sem forçar a troca) e 7 (igualdade exata em vez de tolerância).
- **Parcialmente aceita:** 14 (temp_directory no padrão).
- **Parcialmente rejeitada:** 3. A fórmula não é “só hipótese”, pois reproduz 3.127.621 valores
  publicados; os totais continuam provisórios.

### Limitações e incertezas

Não temos o histórico de versões (vintages) do ONS: não dá para reconstruir o que era
conhecido em cada data. A latência de publicação continua desconhecida.

### Valor para o usuário e para a apresentação

Mostra rigor: sabemos exatamente o que foi validado (a fórmula) e o que não foi (a igualdade com
a publicação atual). Também mostra uma característica real dos dados que o gerador precisa
conhecer: o ONS revisa o passado.

### Próximos passos

Refazer a EDA em notebook e concluir o inventário de vazamento (entrada 1.4).

## 2026-09-19 - Etapa 1.4: EDA em notebook, inventário contra vazamento e fechamento da Etapa 1

### Contexto e pergunta

O usuário pediu a EDA contida em um único notebook executável, com narrativa, consultas,
tabelas e gráficos. A EDA existia só como agregações em `eda.py` e um JSON temporário não
versionado. Pergunta: o problema é grande, crescente, concentrado e recorrente o suficiente para
justificar antecipação por entidade?

### Fatos e evidências observados

Todos os fatos abaixo vêm de `notebooks/01_eda_fundamentos_dados.ipynb` e são conferidos por
`assert` na seção 13.

- **Crescimento.** Na mesma janela abr–ago, a eólica foi de 4,40 para 9,54 e 12,24 TWh
  (2024–2026), e a solar de 1,38 para 4,72 e 6,03 TWh.
- **Painel fixo.** Na eólica, 135 entidades vão de 3,18 para 7,61 e 10,27 TWh. Na solar,
  50 entidades vão de 1,20 para 3,39 e **3,36** TWh. O crescimento solar recente vem de
  entidades novas.
- **Causa.** CNF dominava a eólica em 2024 (61%). ENE domina em 2025 (51% eólica, 61% solar)
  e em 2026 (61% e 84%). ENE eólico, em abr–ago, foi de 0,75 para 7,96 TWh; CNF ficou em cerca
  de 3 TWh. Em fev/2025 houve um pico isolado de REL eólico, com 2,01 TWh.
- **Geografia (2025).** Total de 37,21 TWh, 70% eólico. RN 32%, BA 29%, MG 13%; NE 84%.
- **Concentração.** 36, 85 e 112 de 180 entidades eólicas e 13, 34 e 49 de 87 solares concentram
  50, 80 e 90% da energia.
- **Tempo.** O pico de incidência é às 10 h, como publicado. A eólica tem incidência noturna de
  9–14%.
- **Episódios.** Mediana de 9 e 10 intervalos, ou seja, 4,5–5 h. Só 15–16% duram 30 min, e
  87–89% dos intervalos com corte estão em episódios de 4 h ou mais.
- **Persistência.** P(corte | corte 24 h antes) = 0,70 e 0,71, contra bases de 0,26 e 0,19.
  P(corte | corte 30 min antes) = 0,92 e 0,90.
- **Comando × corte.** 18% das limitações eólicas e 22% das solares têm volume zero.
- **Rótulos.** 0 limitações eólicas e 42 solares sem causa ou origem válida. PAR está ausente.
  A origem é SIS em 75% dos intervalos limitados eólicos e em 90% dos solares.

### Interpretação e decisão

- A narrativa do “por que agora” se sustenta com dados próprios: crescimento em painel fixo
  (eólica) e mudança de regime de CNF/local para ENE/sistêmico. Para o gerador, isso significa
  perdas mais longas e simultâneas em muitas usinas.
- A persistência alta indica que os baselines serão fortes. O valor do modelo precisa ser medido
  contra “mesmo horário do dia anterior”, com latência declarada.
- O critério descritivo de persistência (≥ 500 cortes e P(t+30 min) ≥ 0,8), fixado antes da
  contagem, aprovou 175 de 180 e 80 de 87 entidades. Ele **não discrimina**. A conclusão
  registrada é que a persistência é disseminada, não que exista um subconjunto especial.
- Decisão para a Etapa 2: dois alvos de ocorrência, volume condicionado ao corte positivo e
  avaliação por fonte, causa e painel.

### Alternativas consideradas

- Ler o `tmp/eda-tables.json` antigo: rejeitado, porque não é versionado nem reproduzível. O
  notebook recalcula a partir de `data/raw/` em cerca de 8 s, após conferir o SHA-256.
- Plotly: rejeitado para as saídas versionadas, porque embutir o plotly.js incharia o `.ipynb`.
  Usamos matplotlib com paleta categórica validada para daltonismo.
- Comparar totais anuais brutos: rejeitado, porque os anos das bordas são incompletos. Usamos a
  janela abr–ago e 2025 como ano completo.
- Texto com números digitados à mão sem verificação: rejeitado. A seção 13 falha se algum número
  mudar.

### Implementação e validação

- `eda.py` ganhou `episode_durations` e `daily_persistence`, com testes escritos antes. Os
  testes cobrem quebras por lacuna e por valor desconhecido e a exigência de par observado em
  t−24 h.
- O notebook foi gerado, formatado pelo Ruff e executado com `nbclient`. `tests/test_notebook.py`
  verifica as saídas versionadas e reexecuta o notebook quando os Parquet existem (cerca de 10 s).
- `docs/feature-inventory.md` classifica todos os campos do snapshot, os extras da publicação
  atual e as colunas do alvo. `tests/test_feature_inventory.py` falha se algum campo ficar sem
  classe. O documento registra: horizonte de 48 janelas; valores verificados futuros são
  pós-evento; vento e irradiância do detail são verificados, não previsão; meteorologia futura só
  com timestamp as-of; histórico próprio só como defasagem; latência ONS e revisões como
  incerteza.
- `pitch-notes.md` foi reescrito separando o que foi reproduzido, o que foi validado contra a
  publicação atual, as referências externas e as hipóteses.
- Os 20%, os 4.021 MWmed e os R$ 6,5 bi continuam **externos** e não reproduzidos.

### Limitações e incertezas

- Sem fuso e sem convenção de início/fim.
- Anos incompletos.
- Totais provisórios por causa das revisões.
- 21 volumes eólicos indeterminados.
- Persistência descritiva não é desempenho de modelo.
- O detail não foi usado.
- O notebook (0,95 MB) e o `audit.json` (1 MB) excedem o ideal de artefatos pequenos. É uma
  exceção consciente, documentada no contrato de dados.

### Valor para o usuário e para a apresentação

Sustenta os blocos do pitch:

- **Problema:** 37 TWh em 2025, concentrado e em episódios longos.
- **Por que agora:** ENE mais que dez vezes maior na mesma janela, com crescimento no painel fixo.
- **Solução:** persistência que permite antecipar.
- **Credibilidade:** fórmula validada contra o ONS e limitações assumidas.

O alerta sobre o painel fixo solar evita uma afirmação forte demais no palco.

### Próximos passos

Etapa 2:

1. Congelar cortes temporais e protocolo as-of com cenários de latência.
2. Implementar baselines e métricas por fonte e causa.
3. Buscar sinais sistêmicos ex-ante para ENE.
4. Decidir o tratamento das 21 linhas negativas e das entidades renomeadas.

## 2026-09-19 - Etapa 1.5: verificação adversarial independente

### Contexto e pergunta

Antes de entregar a Etapa 1, um agente verificador com contexto limpo e acesso somente leitura
tentou quebrar o código, os números e as afirmações das entradas 1.1–1.4.

### Fatos e evidências observados

- Cerca de 25 números dos documentos, do notebook e dos relatórios foram recalculados de forma
  independente com DuckDB sobre `data/raw` e `data/interim/official`. Todos conferiram.
- **Defeito confirmado, dormente.** `strip_chars()` do Polars remove tab e quebra de linha;
  `trim()` do DuckDB, sem argumento, não remove. Um rótulo como `"\tREL\n"` seria `REL` em
  Polars e `DESCONHECIDA` em DuckDB. Nenhum arquivo local ou oficial contém esses caracteres,
  então nenhum número publicado foi afetado.
- A aparente divergência entre “29 gerações negativas” (1.1), “21 eólicas” (contrato) e “20
  sob limitação” (alvo) foi resolvida: são recortes diferentes. São 21 eólicas (20 limitadas)
  + 8 solares = 29.

### Interpretação e decisão

Corrigir a paridade com um conjunto explícito de espaços (espaço, tab, LF, CR) nos dois
backends e também na comparação de rótulos de `revision_check`. A colisão teórica do token
`'<NULL>'` em `identity_drift` foi aceita como risco documentado: esse literal não ocorre nos dados.

### Implementação e validação

Casos de tab e quebra de linha foram adicionados ao teste de paridade. Eles falharam (Red) e
passaram após a correção. `official-comparison.json` foi regenerado: as diferenças ficaram
abaixo de 10⁻¹¹ % e vêm da ordem de soma paralela do DuckDB, sem mudança de resultado.

### Limitações, valor e próximos passos

A verificação reforça a credibilidade dos números do pitch, mas não substitui revisão de
especialista do setor elétrico. A Etapa 1 está pronta para aprovação e commit pelo responsável.

## 2026-09-20 - Correção de interpretação no fechamento da Etapa 1

### Contexto e pergunta

Uma revisão final identificou que a entrada 1.4 e a síntese do notebook aproximavam duas
dimensões distintas: causa (`CNF`/`ENE`) e origem (`LOC`/`SIS`). A mesma redação sugeria
simultaneidade entre entidades sem que a EDA tivesse calculado coocorrência temporal.

### Fatos e evidências observados

O notebook mede separadamente a participação de energia por causa, a fração de intervalos por
origem e a duração/persistência dos episódios em cada entidade. Ele não cruza causa com origem
na conclusão citada nem mede quantas entidades sofrem corte simultaneamente em cada janela.

### Interpretação e decisão

A conclusão anterior "CNF/local para ENE/sistêmico" fica substituída por duas afirmações
independentes: ENE passa a dominar a energia estimada em 2025/2026, e SIS predomina entre as
origens registradas. Episódios longos são fato observado; simultaneidade continua hipótese.
Persistência passa a ser descrita como sinal temporal candidato à antecipação, não como prova de
capacidade preditiva.

### Implementação, limitações e próximos passos

A síntese do notebook foi corrigida sem alterar código, dados, gráficos ou resultados numéricos.
A Etapa 2 deve medir desempenho fora da amostra e, se a simultaneidade for relevante para o
produto, incluir uma análise explícita de coocorrência por janela e região.

## 2026-09-22 - Contrato de saída, preditor provisório e plano de trabalho paralelo

### Contexto e pergunta

Terça-feira, com a Etapa 2 ainda em andamento. O presencial vai de 25 a 27/09 e a apresentação
é no domingo, com três desenvolvedores e a maior parte do trabalho concentrada no responsável.
Pergunta: dá para adiantar as etapas 3 a 6 sem esperar a decisão de modelo da Etapa 2C, e sem
retrabalho quando ela sair?

### Fatos e evidências observados

- Recomendação, interface e deploy dependem do formato da previsão, não do algoritmo. O
  protocolo da Etapa 2A (§2.1, §5 e §7) já define unidade, horizontes, tarefas e baselines.
- A 2C pode declarar uma tarefa `inelegivel` (por exemplo, causa) ou preferir um baseline. O
  handoff da 2C também prevê uma Etapa 2D, o que pode atrasar a decisão para depois de sexta.
- Com o cenário noturno do protocolo, a observação de `tau − 24h` quase nunca está liberada no
  instante da previsão: numa terça às 10h, o último dia liberado é domingo.
- Execução real em 14/10/2025 às 10h (corte `nightly_cutoff` = 13/10 00h): leitura de 28 dias
  (299.376 linhas) em 0,2 s e previsão em 0,08 s; 154 entidades eólicas e 69 solares, 10.704
  linhas, nenhuma sem previsão. Alertas: 58,6% das janelas eólicas e 32,2% das solares. Energia
  somada nas 48 janelas: ≈183 GWh eólica e ≈48 GWh solar.

### Interpretação e decisão

- O formato da saída foi fixado antes do modelo em `src/curtamap/contracts.py`
  (`FORECAST_SCHEMA`, `RECOMMENDATION_SCHEMA` e validadores). Causa e previsão podem ser nulas,
  sempre com motivo, para que uma inelegibilidade decidida na 2C não mude o contrato.
- O preditor provisório é o baseline "mesmo horário mais recente disponível, até 28 dias"
  (§7.2), e não o "mesmo horário do dia anterior". Pela latência, este último cairia quase
  sempre no fallback.
- O teste reservado (a partir de 01/05/2026) é recusado por padrão na leitura e na previsão.
- Trabalho dividido em trilhas por branch (`docs/parallel-plan.md`): o responsável segue na
  Etapa 2, o Dev 2 fica com a Etapa 3 e o Dev 3 com a Etapa 4 e a preparação local da Etapa 5.
  Prompts autossuficientes em `docs/handoffs/stage3-prompt.md` e `stage4-prompt.md`.
- Interface em Streamlit, decidida pelo responsável: menos código, um único container e
  contrato só em Python. Para evitar conflitos, a interface será multipágina, com um arquivo
  por tela.

### Alternativas consideradas

- **Esperar a 2C:** adiada. Custaria dias para evitar poucas horas de ajuste; o contrato já
  absorve as decisões possíveis da 2C.
- **Mock sintético em vez de baseline:** descartado. O baseline usa dados reais e é
  explicitamente rotulado.
- **React + FastAPI:** preferência inicial do responsável, trocada por Streamlit pelo prazo.
- **Fallback regional do protocolo no preditor provisório:** adiado. Sem observação no
  horário, a previsão fica nula com motivo, em vez de um número de baixa evidência.

### Implementação e validação

TDD em ambos os módulos: `tests/test_contracts.py` e `tests/test_forecasting.py` falharam na
coleta antes da implementação e passaram depois. Os testes cobrem vazamento após o corte, janela
de 28 dias, volume inválido, causas não aprendíveis, identidade por fonte, grade de 30 minutos e
bloqueio do teste reservado.

Uma verificação adversarial independente não encontrou vazamento temporal. Ela conferiu as
fronteiras do corte noturno (inclusive exatamente às 19h30), a janela de 28 dias até o
microssegundo, o bloqueio do teste reservado e a execução com Parquet real de mar–abr/2026.
Encontrou, porém, lacunas no validador: comparações com nulo escondiam alerta sem `p_corte`,
`tau` nulo, energia nula com volume preenchido e energia ausente em recomendações. Também
apontou que faltavam campos de proveniência exigidos pelo protocolo. Tudo foi corrigido com
testes antes, e o contrato ganhou `cenario_disponibilidade`, `instante_observacao` e
`cobertura_historico`. `causa_base` nula foi mantida de propósito: significa causa
indeterminada. Suíte completa: 149 testes aprovados com `PYTHONUTF8=1`.
`ruff check` e `ruff format --check` limpos. Sem essa variável, `test_feature_inventory` falha no
Windows porque lê o Markdown sem `encoding="utf-8"`. É um defeito anterior e fora deste escopo.
`.gitattributes` passou a usar `merge=union` no diário, para unir entradas de branches paralelas.

### Limitações e incertezas

- O corte de disponibilidade considera só fins de semana; os feriados do calendário da Etapa 2
  ainda não estão no `main`.
- As probabilidades do baseline são 0 ou 1, sem calibração nem intervalo de volume.
- Como o baseline copia o último dia liberado, a energia prevista herda o perfil desse dia.
  Nos ≈231 GWh do exemplo, o último dia liberado era um domingo, e a média diária de 2025 é
  ≈102 GWh. **Interpretação, não medida:** fins de semana com carga baixa podem inflar a
  previsão. Isso não foi quantificado.
- O esquema de recomendação é uma versão inicial. A Etapa 3 pode propor extensões por PR
  separado.

### Valor para o usuário e para a apresentação

Permite demonstrar o fluxo previsão → recomendação → decisão com dados reais antes da escolha do
modelo. O baseline também é o comparador que o modelo final precisa superar, o que sustenta a
narrativa de credibilidade: "comparamos com a regra simples que o gerador já poderia usar".

### Próximos passos

1. Responsável: fazer push do `main` e distribuir os prompts; seguir na 2B/2C.
2. Dev 2 e Dev 3: abrir as branches a partir do `origin/main` e trabalhar pelos prompts.
3. Depois da 2C: implementar o preditor escolhido atrás do `Predictor` e trocar na interface.
4. Corrigir a leitura sem encoding de `test_feature_inventory` num commit próprio.

## 2026-09-26 - Nova Etapa 2 (1/n): recomeço, trava de setembro, calendário e diagnóstico

### Contexto e pergunta

O responsável decidiu refazer a modelagem do zero, sem partir da receita da Etapa 2 anterior
(só 2 das 6 células usavam modelo, com ganho pequeno sobre o baseline). A pergunta de abertura
é: **o problema é tão complexo quanto o pipeline anterior (100+ M de linhas, ~50 features,
picos de 33 GB) sugeria?** O trabalho roda num notebook de 8 GB de RAM e 8 núcleos, sem
LightGBM, com o `HistGradientBoosting` do scikit-learn, que já é dependência.

### Fatos e evidências observados

- A base compacta (uma linha por usina × meia hora, com os alvos de `derive_targets`) tem
  7,95 M de linhas na eólica e 2,85 M na solar. O DuckDB a gera em ~2 s, com 1,2 GB de RSS.
- Com a emissão diária às 20h da véspera, o último dia liberado (L) fica 2 dias antes do
  dia-alvo (T) em 67% dos dias, 3–4 dias em 30% e até 7 dias perto de feriados.
- Diagnóstico em jan–ago/2026, com o alvo sendo o corte positivo por usina × meia hora
  (script exploratório; os números serão refeitos pelo módulo testado):

  | Preditor (mesmas linhas) | AP eólica | AP solar |
  |---|---|---|
  | `historico`: frequência da usina no slot, 28 d até L | 0,780 | 0,783 |
  | mesmo slot do último dia liberado | 0,595 | 0,560 |
  | oráculo: fração **realizada** de usinas do estado cortadas em T × slot | 0,945 | 0,943 |
  | oráculo: `historico` × nível estadual diário **realizado** em T | 0,879 | 0,909 |

  Correlação do nível estadual diário entre L e T: 0,57 na eólica e 0,28 na solar.
- Modelo só do nível diário estadual (HGB com nível em L, médias de 7 e 28 d, fração ENE,
  idade, dia da semana e feriado nacional; dobras mensais jan–ago/2026): o MAE cai de 0,124
  para 0,113 na eólica e de 0,092 para 0,082 na solar, contra a média de 28 d. O ganho é real,
  mas de apenas ~10%.

### Interpretação e decisão

- **Interpretação:** a estrutura do problema é simples. O perfil horário da usina já vem do
  próprio histórico, e o corte é regional e simultâneo. A parte difícil é o **nível** do
  dia-alvo, que depende de vento, sol e carga daqui a 2–4 dias, sinais que o dataset não traz
  como previsão. Sem previsão meteorológica, o teto de ganho sobre o `historico` é limitado.
  Complexidade de pipeline não compra esse sinal.
- **Decisão:** manter o desenho pequeno. Uma linha por usina × slot × dia-alvo, emitida uma
  vez por dia; features indexadas pelo último dia liberado L, nunca por T; poucas features
  com significado físico ou operacional.
- **Regra de decisão, registrada antes dos resultados do modelo:** em cada célula
  (fonte × corte/volume/causa), o modelo só substitui o melhor baseline se vencer nas mesmas
  linhas na média das dobras mensais jan–ago/2026 **e** em pelo menos 6 dos 8 meses. Caso
  contrário, a célula usa o melhor baseline, com `tipo_saida = baseline`. Maio–agosto/2026 já
  foi visto pela receita anterior e aqui é período de desenvolvimento, não teste.

### Alternativas consideradas

- Retomar o pipeline emissão × horizonte: descartado pelo responsável e pelas medições do §2.2
  do prompt, já que as 48 emissões diárias são redundantes.
- LightGBM: adiado. Exige libomp no macOS e teve bug com categóricas no volume. O HGB do
  sklearn basta para começar.

### Implementação e validação

- `RESERVED_TEST_START` passou para 01/09/2026, num commit dedicado. **Atenção na
  integração:** `etapa-3-recomendacao` e `etapa-4-interface` importam a mesma constante.
- `curtamap.previsao.calendario` calcula o corte de publicação com o calendário de feriados
  (todos os tipos, inclusive os do Rio) e oferece a consulta de feriado nacional para a
  feature de carga baixa. `forecasting.nightly_cutoff` passou a delegar a ele, que vira a
  fonte única do corte usada pela interface. Os testes cobrem terça, 19h/19h30, sábado,
  domingo, segunda, o feriado de 07/09/2026 e a falta de cobertura.

### Limitações e incertezas

- Os números acima são exploratórios e usam uma janela de 28 d calculada por `rolling_by` em
  dias com dado. Serão refeitos pelo módulo testado.

### Valor para o usuário e para a apresentação

É a base da narrativa "problema simples na estrutura, difícil no sinal": o corte é regional e
previsível no perfil, e o que falta para acertar o nível do dia é previsão do tempo. Isso
prepara o experimento oráculo (H5), que mede quanto valeria um feed meteorológico.

### Próximos passos

Modelo direto por usina × slot contra os baselines; volume e causa; módulo testado; setembro.

## 2026-09-26 - Nova Etapa 2 (2/n): backtest jan–ago/2026 e decisão por célula

### Contexto e pergunta

O modelo diário por usina × slot supera os baselines nas mesmas linhas? A regra de decisão
foi registrada na entrada anterior e implementada em `curtamap.previsao.relatorio` (commit
`b4aa4a8`) antes de qualquer resultado do backtest oficial.

### Fatos e evidências observados

Backtest de `curtamap.previsao.avaliacao`: 8 dobras mensais, jan–ago/2026, ~3,6 min por dobra
no notebook de 8 GB, com pico de ~1,5 GB. Métricas em
`docs/reports/nova-abordagem/metricas_backtest.csv`; decisão em `decisao_celulas.csv`.

| Célula | Modelo (média) | Melhor baseline (média) | Meses vencidos* | Decisão |
|---|---|---|---|---|
| Corte eólico, AP | 0,788 | `historico` 0,740 | 8/8 | modelo |
| Corte solar, AP | 0,813 | `historico` 0,747 | 8/8 | modelo |
| Volume solar, WAPE meia-hora | 0,851 | `historico` 0,950 | 7/8 | modelo |
| Volume eólico, WAPE meia-hora | 1,083 | `ultimo_valor` 1,097 | 5/8 | baseline |
| Causa eólica, macro-F1 | 0,631 | moda da usina 28 d 0,649 | 2/8 | baseline |
| Causa solar, macro-F1 | 0,504 | moda da usina 28 d 0,462 | 5/8 | baseline |

\* contra o melhor baseline **de cada mês**, que é a leitura operacionalizada no código.

Outros fatos:

- **Brier:** o modelo é melhor que o `historico` na maioria dos meses, mas ligeiramente pior
  na eólica em março (0,105 contra 0,104) e em junho (0,159 contra 0,152).
- **Alerta:**
  - limiar F1-ótimo escolhido fora da amostra em jan–abr: 0,30 na eólica e 0,32 na solar;
  - com ele, em mai–ago (fora da amostra), o recall vai de 0,73 a 0,95 na eólica e de 0,85 a
    0,94 na solar, com precisão de 0,58 a 0,82;
  - em jan–abr, recall e precisão estão dentro da amostra usada na escolha;
  - limiar final, escolhido com jan–ago: 0,346 na eólica e 0,321 na solar.
- **Volume:**
  - o WAPE diário por usina (a métrica de planejamento) também favorece o modelo na solar
    (0,49–0,78 contra 0,59–0,91 do `historico`, fora fevereiro);
  - o preditor "zero" tem WAPE 1,0 por construção e vence **todos** os preditores da eólica em
    fevereiro, março, abril e junho;
  - WAPE e MAE premiam a mediana, que é zero num alvo inflado de zeros, enquanto a
    recomendação consome a média (energia esperada);
  - o viés total do modelo fica entre −26% e +86%. Fevereiro, com pouco corte, é o pior mês
    para todos os preditores baseados em média.
- **Intervalo p10–p90:** a cobertura geral de 0,87 a 0,97 é inflada pelas linhas sem corte.
  Nas meias-horas com corte, ela cai para 0,63–0,79 na eólica e 0,69–0,81 na solar, perto
  dos 80% nominais.

### Interpretação e decisão

- **Ocorrência (a saída principal):** o ganho é claro e estável. O modelo vence nos 16
  meses-fonte, com +0,05 a +0,17 de AP sobre o `historico`, e o maior ganho aparece em
  fevereiro, na mudança de regime.
- **Composição servida** (`SERVING` em `curtamap/previsao/modelo.py`), com proveniência por
  linha em `tipo_saida_volume` e `tipo_saida_causa`:
  - ocorrência: modelo nas duas fontes;
  - volume solar: modelo;
  - volume eólico: `historico`;
  - causa: moda da usina no slot em 28 d, com recurso ao estado em 7 d, nas duas fontes.
- **Desvio registrado antes de setembro:** ao pé da letra, a regra escolheria `ultimo_valor`
  para o volume eólico, porque tem a melhor média. Servimos `historico` porque:
  - a média do `ultimo_valor` só é melhor por causa de fevereiro;
  - o `historico` o vence em 7/8 meses no WAPE de meia-hora e no diário;
  - o `ultimo_valor` subestima a energia em 30–98% em todos os meses, o que quebraria a energia
    em risco da Etapa 3.

  Esse desvio é entre baselines e não infla nenhuma alegação sobre o modelo.
- **Sensibilidade da regra, só para divulgação:** com um baseline fixo (`historico`) em vez do
  melhor de cada mês, o volume eólico venceria em 6/8 meses, com margens de 0,002 a 0,07 fora
  de fevereiro. É um empate técnico. A decisão continua a do código. As outras cinco células
  não mudam entre as duas leituras.
- **Não otimizar o volume eólico para WAPE:** ganhar WAPE ali significaria encolher E[v] na
  direção de zero, o que piora a energia esperada que a recomendação consome.

### Alternativas consideradas

- Reinterpretar a regra depois dos resultados: descartado.
- Iterar livremente sobre volume e causa: limitado a uma ou duas tentativas **na causa**,
  todas listadas e feitas antes de abrir setembro.

**Hipótese da tentativa 1, escrita antes de rodar:** o modelo de causa perde para a moda da
usina porque o `class_weight='balanced'` e as features estaduais diluem o sinal dominante da
usina. Diagnóstico: um HGB só com as três participações da usina no slot em 28 d e **sem**
peso balanceado. Se nem ele empatar com a moda, o limite está no aprendiz ou no alvo, e a
iteração para.

### Implementação e validação

- `apply_serving` com testes: o volume eólico servido é igual a `vol_hist_28d`, a causa
  servida é o argmax das participações e a proveniência sai por linha.
- Cobertura p10–p90 em y > 0 acrescentada às métricas.
- Rótulo semanal de setembro corrigido: o `weekday` do Polars vai de 1 a 7.
- Suíte completa verde, com ruff limpo.

### Limitações e incertezas

- Maio–agosto/2026 já tinha sido visto pela receita anterior. Aqui é desenvolvimento.
- O limiar de alerta e a composição foram escolhidos com jan–ago. Só setembro é teste.
- Os hiperparâmetros foram fixados a priori, sem busca. Pode haver ganho não explorado, e
  também não há sobreajuste de busca.

### Valor para o usuário e para a apresentação

- **Frase do pitch, sustentada por evidência nas mesmas linhas:** "prevemos na véspera, às
  20h, em quais meias-horas de amanhã cada usina será cortada, melhor que a frequência
  histórica da própria usina em 16 de 16 meses-fonte".
- O volume e a causa ganham honestidade, não número. O painel mostra de onde vem cada
  componente.

### Próximos passos

Tentativa 1 de causa; congelar o modelo com manifesto; validar em setembro; H5 (oráculo
meteorológico); relatório e handoff.

## 2026-09-26 - Nova Etapa 2 (3/n): tentativa de causa e congelamento antes de setembro

### Contexto e pergunta

Uma tentativa de melhorar a causa, com hipótese registrada antes, e depois o congelamento da
receita para a validação única em setembro.

### Fatos e evidências observados

Diagnóstico de causa: macro-F1 médio de jan–ago/2026, nas mesmas linhas (cache em
`data/interim/cache_causa.parquet`, script exploratório).

| Variante | Eólica | Solar | Meses > moda (eól./sol.) |
|---|---|---|---|
| Moda da usina 28 d (baseline) | 0,649 | 0,462 | — |
| Atual (13 features, balanceado) | 0,625 | 0,498 | 2 / 5 |
| Só participações da usina, sem peso | 0,638 | 0,422 | 3 / 0 |
| Só participações da usina, balanceado | 0,567 | 0,426 | 1 / 3 |
| 13 features, sem peso | 0,630 | 0,483 | 4 / 6 |

### Interpretação e decisão

- **Eólica:** nem o aprendiz restrito às participações da usina empata com a moda. Pelo
  critério registrado, o limite está no aprendiz ou no alvo, não nas features, e a iteração
  para. **Interpretação:** a causa da ordem é quase uma propriedade da usina e do slot, e a
  moda recente já captura isso.
- **Solar:** a variante sem peso venceria em 6/8 meses, mas foi a melhor de 4 variantes nas
  mesmas dobras. Adotá-la seria viés de seleção, com margem de 0,02. **Decisão:** manter a moda
  da usina, como a regra já decidia, e registrar a variante como candidata para uma futura
  validação independente.
- **Congelamento:**
  - modelo `diario_hgb_v1_2026-08-30`, treinado com rótulos até 30/08/2026, o último dia
    liberado na emissão que prevê 01/09;
  - 2,71 M linhas eólicas e 1,31 M solares;
  - limiar de alerta de 0,346 na eólica e 0,321 na solar;
  - SHA-256 `6340240d…` e commit da receita `e89be0f`;
  - manifesto em `docs/reports/nova-abordagem/modelo-congelado.json`.

### Alternativas consideradas

Mais tentativas de causa ou de volume eólico: descartadas. A primeira tentativa respondeu à
pergunta, e novas rodadas só aumentariam o risco de sobreajuste às dobras.

### Implementação e validação

- `treinar.py` grava o manifesto.
- O calendário aceita `CURTAMAP_CALENDAR_PATH`, para o container.
- Suíte verde.

### Limitações e incertezas

- A causa servida é um baseline. O pitch não deve atribuir a causa ao modelo.
- A reprodução histórica e a validação de setembro ainda não foram rodadas.

### Valor para o usuário e para a apresentação

- Mostra disciplina: a regra decide, a tentativa é declarada e o congelamento é verificável
  por hash.
- Sustenta a narrativa: "o modelo onde ele ganha e o baseline honesto onde não ganha".

### Próximos passos

1. Baixar setembro.
2. Prever sem rótulo.
3. Avaliar por semana.

## 2026-09-26 - Nova Etapa 2 (4/n): setembro, reprodução para o dashboard e oráculo meteorológico

### Contexto e pergunta

- As escolhas congeladas se sustentam fora da amostra?
- Quanto valeria uma previsão meteorológica?
- Além disso, entregar o recorte histórico para o dashboard.

### Fatos e evidências observados

- **Setembro de 2026**, a validação independente, aberta uma única vez depois do commit
  `7b64b46`:
  - dados baixados às 06:35 UTC de 26/09, com `Last-Modified` de 25/09 às 22h UTC, cobrindo
    01 a 24/09 (manifesto em `docs/reports/nova-abordagem/setembro/`);
  - previsões sem rótulo gravadas antes da avaliação (SHA-256 `b1c8ed21…`);
  - corte: AP de 0,921 contra 0,899 do `historico` na eólica (vence 3/4 semanas) e de 0,907
    contra 0,867 na solar (4/4);
  - volume solar: WAPE 0,607 contra 0,652 e WAPE diário 0,517 contra 0,565;
  - causa: a moda da usina (servida) teve 0,839 contra 0,765 do modelo na eólica e 0,501
    contra 0,447 na solar;
  - alerta com o limiar congelado: recall de 0,94 e 0,90, precisão de 0,82 e 0,81.
- **Reprodução**, em `data/interim/previsao/reproducao_2026-08-03_2026-08-30.parquet`:
  - 28 emissões às 20h e 315.072 linhas no contrato, com `observado_*` ao lado;
  - modelo treinado com rótulos até 30/07;
  - AP de 0,920 contra 0,904 na eólica e de 0,904 contra 0,865 na solar.
- **H5, oráculo em mai–ago:**
  - clima verificado do estado no dia-alvo: AP eólica de 0,826 para 0,872, WAPE diário eólico
    de 0,711 para 0,540, AP solar de 0,860 para 0,869;
  - clima de L, que é legítimo: sem ganho.

### Interpretação e decisão

- **Fato:** setembro confirmou as decisões congeladas. **Interpretação:** o ganho da
  ocorrência é robusto, mas setembro teve prevalência parecida com agosto e não testou uma
  mudança de regime.
- **Interpretação:** o gargalo do volume eólico é meteorológico. O H5 quantifica o valor de um
  feed de previsão de vento como teto, não como garantia.
- **Decisão:** o clima de L não entra no produto, porque não teve ganho.

### Alternativas consideradas

Usar setembro para ajustar a receita: proibido pelo protocolo e não feito.

### Implementação e validação

- Módulos `setembro`, `reproducao` e `produto`, todos com testes.
- Script do H5 versionado em `scripts/experimentos/oraculo_h5.py`.
- Relatório completo em `docs/reports/nova-abordagem/README.md`.
- Handoff em `docs/handoffs/etapa-2-nova-abordagem-handoff.md`.

### Limitações e incertezas

- Setembro tem só 24 dias.
- O H5 usa clima verificado e médio por estado. Uma previsão real teria erro, e a
  granularidade por usina poderia mudar o número.

### Valor para o usuário e para a apresentação

- **Demonstração:** 4 semanas de emissões diárias com a verdade ao lado.
- **Validação independente:** setembro, publicado depois do snapshot.
- **"Por que agora" e evolução do produto:** o próximo ganho vem de previsão meteorológica,
  não de mais complexidade.

### Próximos passos (domingo)

1. Integrar com as Etapas 3 e 4 seguindo o handoff: trava de setembro, 92 dias de histórico
   e proveniência por componente.
2. Containerizar com `configs/`, `models/` e `data/raw/`.

## 2026-09-26 - Nova Etapa 2 (5/n): correções da revisão final

### Contexto e pergunta

A revisão final encontrou um número errado no diário e um defeito de serviço.

### Fatos e evidências observados

- **Correção da entrada 2/n:** ela diz "+0,05 a +0,17 de AP sobre o `historico`". O
  `metricas_backtest.csv` mostra ganhos mensais de **+0,009 a +0,173**:
  - na eólica: +0,074, +0,173, +0,031, +0,027, +0,035, +0,020, +0,009 e +0,018;
  - na solar: de +0,035 a +0,147.

  O ganho médio é de +0,048 na eólica e de +0,066 na solar. A frase "vence em 16 de 16
  meses-fonte" continua correta. Na eólica, porém, a margem fica entre +0,01 e +0,035 em 6 dos
  8 meses. **No pitch, use o ganho médio, não a faixa.**
- Na reprodução de agosto, o volume eólico servido (média de 28 d) ficava acima do p90 do
  modelo em 0,69% das linhas e abaixo do p10 em 0,15%.

### Interpretação e decisão

- **Decisão:** alargar a banda para conter a média servida. É um ajuste de serviço
  pós-congelamento. O artefato congelado e as métricas de setembro não mudam, porque
  `setembro.predict` usa o modelo sem o serviço.
- **Handoff:** a frase sobre `t0` de manhã foi corrigida. Com `nightly_cutoff`, a idade 1 só
  aparece se `t0` for o próprio instante da emissão.
- **Relatório:**
  - a divulgação de que o `SERVING` foi escolhido com dados que incluem agosto foi
    acrescentada;
  - a afirmação "capturam o que há de previsível" foi marcada como interpretação;
  - o texto agora diferencia o commit do código (`e89be0f`) do commit do congelamento
    documental (`7b64b46`).

### Implementação e validação

- Commit `04113b8`, com teste de que a média servida fica dentro da banda.
- Suíte verde, com ruff limpo.
- A reprodução de agosto será regenerada com o serviço corrigido.

### Limitações e próximos passos

Nenhuma decisão de modelo mudou. Próximo passo: a integração de domingo.

## 2026-09-26 - Nova Etapa 2 (6/n): limiar com empates e protocolo das melhorias v2

### Contexto e pergunta

A equipe pediu três frentes de melhoria das métricas:

1. corrigir a escolha do limiar de alerta;
2. selecionar as features por evidência (correlação e importância por permutação em grupos),
   sem ignorar nenhuma feature disponível;
3. atacar o volume eólico, cujo sinal de problema mais claro é fevereiro (WAPE diário de
   1,655 no modelo contra 2,605 no `historico`).

Esta entrada registra a correção do limiar e, **antes de qualquer resultado**, o protocolo
das frentes 2 e 3.

### Fatos e evidências observados: limiar

- **Defeito:** `choose_threshold` pontuava o F1 em cada posição do ranking, inclusive no
  meio de um grupo de probabilidades iguais. Mas o alerta é `p >= limiar`, então um limiar
  inclui o grupo empatado inteiro.
  - Exemplo sintético (agora em teste): a função escolhia 0,5, cujo F1 real é 0,40,
    enquanto o limiar 0,9 dá F1 de 0,67.
- **Correção:** o F1 só é avaliado no fim de cada grupo empatado (commit `020b5ef`).
- **Efeito nos dados reais: nenhum.** Nas previsões fora da amostra do backtest, o HGB
  produz probabilidades quase contínuas:
  - eólica: 440.926 valores distintos em 882.864 linhas de jan–abr;
  - solar: 214.450 em 428.976.

  Uma única linha estava empatada no limiar escolhido. Os limiares não mudam, nem o de
  jan–abr nem o final de jan–ago (0,3461 na eólica e 0,3212 na solar).
- **Validação da escolha:** o limiar escolhido em jan–abr, aplicado a mai–ago, dá F1 de
  0,792 na eólica e 0,812 na solar. O melhor limiar possível dentro de mai–ago (um teto,
  inutilizável na prática) daria 0,793 e 0,812. A escolha já estava praticamente no ótimo.

### Interpretação e decisão: limiar

- A correção fica, porque evita que um modelo futuro, com probabilidades mais discretas,
  sofra o defeito.
- Não há ganho a relatar nos dados reais, e o modelo congelado v1 não muda.

### Protocolo pré-registrado das frentes 2 e 3

**Período.** Setembro de 1 a 24 já foi aberto para validar a v1 e está **gasto**. Qualquer
v2 é escolhida apenas nas 8 dobras mensais de jan–ago/2026, com o mesmo protocolo do
backtest (origem expandindo, emissão das 20h, feriados). Setembro só pode reaparecer como
checagem de sanidade, marcada como contaminada. A confirmação independente de uma v2 exige
dias ainda não vistos: o arquivo de setembro do ONS foi atualizado em 26/09, com dias após
24/09, e depois vem outubro.

**Cache de features.** As features de um dia-alvo T dependem só dos dados até o último dia
liberado L(T), não da dobra. Por isso, elas são calculadas uma vez para os dias-alvo de
01/01/2025 a 31/08/2026 e cada dobra é um filtro de linhas. Isso é equivalente ao backtest,
porque o treino de cada dobra continua limitado a dias-alvo ≤ último dia liberado antes do
mês.

**Frente 2: correlação e importância por permutação em grupos.**

- **Pool:** todas as colunas que `build_features` produz, e não só as 21 usadas hoje. Isso
  inclui:
  - `restricao_hist_28d`, `origem_sis_28d`, `cobertura_28d`;
  - `causa_*_28d` e `estado_rel_7d`/`estado_cnf_7d`;
  - `ultimo_valor_corte`/`ultimo_valor_volume`.

  Também entram quatro tendências novas:
  - `tend_hist` = `hist_7d − hist_28d`;
  - `tend_estado` = `estado_nivel_7d − estado_nivel_28d`;
  - `tend_usina` = `usina_nivel_ultimo − usina_nivel_7d`;
  - `tend_vol` = `vol_hist_7d − vol_hist_28d`.
- **Correlação:** Spearman entre pares, numa amostra de 300 mil linhas de treino por fonte.
  Os grupos saem de uma clusterização hierárquica (ligação média) sobre `1 − |ρ|`, com corte
  em |ρ| > 0,7, decidido agora.
- **Importância:** um modelo **superconjunto** por fonte, só ocorrência e volume esperado,
  com os mesmos hiperparâmetros da v1, é treinado em cada uma das 8 dobras. No mês
  fora da amostra, cada grupo é permutado em conjunto (a mesma permutação de linhas para
  todas as colunas do grupo), com 3 repetições.
  - Métricas: queda de AP na ocorrência e aumento da deviance de Poisson no volume, que é o
    que o modelo otimiza.
  - O resultado é reportado como média ± desvio entre dobras e número de dobras com
    importância positiva.
- **Leitura:** importância é associação no modelo, não causalidade. Ela só **indica**
  candidatos:
  - para remoção: grupos com importância ≤ 0 em pelo menos 5 de 8 dobras;
  - para inclusão: grupos novos com importância > 0 em pelo menos 6 de 8 dobras.
- **Confirmação:** no máximo 2 conjuntos candidatos por fonte × componente (reduzido e/ou
  aumentado). Eles são retreinados nas 8 dobras e substituem a v1 só se vencerem na média
  **e** em pelo menos 6 de 8 meses:
  - AP na ocorrência;
  - na eólica, o volume segue a métrica da frente 3.

**Frente 3: volume eólico.** São até 7 variantes do regressor de volume esperado da eólica,
todas declaradas agora:

| Variante | Mudança |
|---|---|
| B0 | v1 (referência) |
| B1 | + as 4 tendências |
| B2 | janela de treino de 180 dias |
| B3 | janela de 90 dias |
| B4 | peso de recência com meia-vida de 90 dias (janela de 365) |
| B5 | peso de recência com meia-vida de 30 dias |
| B6 | B1 combinada com a melhor de B2–B5 pela métrica principal |

- **Métrica principal, escolhida agora:** o **WAPE diário por usina × dia**, que é a unidade
  de planejamento e a métrica em que fevereiro foi apontado. Secundárias: WAPE da
  meia-hora, RMSE da meia-hora (métrica adequada para a média) e viés.
- **Mudança de regra declarada:** a regra da v1 comparava com o melhor baseline **de cada
  mês**, incluindo o `ultimo_valor`, que vence subestimando a energia (viés de −89% em
  fevereiro). Para o volume eólico, a comparação passa a ser com o `historico`, que é o
  componente servido.
  - O modelo (B0 ou variante) passa a ser servido se vencer o `historico` no WAPE diário na
    média e em pelo menos 6 de 8 meses, sem viés médio pior.
  - **Contaminação reconhecida:** já vimos que o B0 vence o `historico` no WAPE diário na
    média (0,853 contra 0,981). A regra nova foi escolhida sabendo disso, e esse fato será
    dito junto de qualquer conclusão.
- **Seleção entre variantes:** a vencedora é a melhor de 7 nas mesmas dobras, o mesmo caso
  "melhor de N" que fez a tentativa de causa ser rejeitada. Por isso, ela só é adotada se a
  margem sobre o B0 aparecer em pelo menos 6 de 8 meses. A adoção final continua dependendo
  de dias novos.

**Versão.** Nada substitui o `diario_hgb_v1` nem o `modelo-congelado.json`. O que for adotado
vira `diario_hgb_v2`, com manifesto, limiares e reprodução novos, e o handoff é atualizado.

### Adendo ao protocolo (antes dos resultados das variantes)

- **Fato observado:** a B0 lida do cache em outra ordem de linhas **não** reproduziu a v1.
  Em fevereiro, o WAPE diário foi 1,727, contra 1,655 da v1. Com as linhas ordenadas por
  `fonte, id_ons, dia, slot`, como em `modelo.fit`, ela reproduz a v1 exatamente
  (1,655084).
- **Causa:** acima de 200 mil linhas, o HGB calcula os limites dos bins numa subamostra, que
  depende da ordem das linhas e da semente.
- **Consequência:** a ordem das linhas sozinha move o WAPE diário de fevereiro em 0,07.
  Esse é o ruído do próprio modelo, e diferenças entre variantes menores que ele não
  significam nada.
- **Decisão, tomada antes de ver B1–B6:**
  - o cache passa a ser ordenado como na v1;
  - duas réplicas da B0 com sementes 1 e 2 medem o ruído;
  - uma variante só conta como vitória num mês se a margem sobre a B0 superar a maior
    diferença entre as três réplicas da B0 naquele mês.

## 2026-09-26 - Nova Etapa 2 (7/n): resultados da v2 (correlação e volume eólico) e interrupção

### Contexto e pergunta

Esta entrada executa o protocolo da entrada 6/n. A importância por permutação foi
interrompida a pedido do responsável: a bateria do notebook estava acabando e a equipe
decidiu pivotar a recomendação para não depender do volume.

### Fatos e evidências observados

**Correlação de Spearman.** Foram usadas 300 mil linhas de treino por fonte (dobra de
agosto) e grupos com |ρ| > 0,7. Arquivos: `docs/reports/nova-abordagem/v2/spearman_*.csv`.

- **Perfil do slot:** `hist_7d/28d/91d`, `vol_hist_7d/28d` e `restricao_hist_28d`, com ρ de
  0,82 a 0,97. Na solar, o grupo absorve ainda `ref_hist_28d`, `origem_sis_28d` e
  `causa_*_28d`.
- **Pares quase redundantes:**
  - `restricao_hist_28d` ~ `hist_28d`: 0,97 na eólica e 0,95 na solar;
  - `ultimo_slot` ~ `vol_ultimo_slot`: 0,96 e 0,99;
  - `estado_ene_7d` ~ `estado_cnf_7d`: −0,89 e −0,91;
  - usina ~ estado no último dia: 0,85 e 0,79.
- **Pares que não são redundantes:** perfil do slot × nível do estado tem ρ = 0,44 na eólica e
  0,11 na solar. As quatro tendências novas ficaram isoladas, sem entrar em nenhum grupo.
- **Feature morta:** `ultimo_valor_*` é constante na solar, porque a última meia-hora de L é
  noturna.
- **Nulos:** as features de causa e origem da usina estão nulas em 18% das linhas eólicas e
  53% das solares. Na correlação, o nulo foi marcado como −1, o que infla parte das ligações.

**Volume eólico, WAPE diário médio de jan–ago.** Arquivos:
`v2/volume_eolico.csv` e `v2/volume_eolico_resumo.csv`.

| Variante | Média | Fevereiro | Viés | Meses vencendo a B0 acima do ruído |
|---|---|---|---|---|
| B0 (v1, semente 0) | 0,853 | 1,655 | −0,5% | — |
| B0, sementes 1 e 2 | 0,856 e 0,866 | 1,620 e 1,710 | +0,9% e +0,3% | réplicas |
| B1, tendências | 0,848 | 1,532 | −2,4% | 2 de 8 |
| B2, janela de 180 d | 0,866 | 1,583 | −15% | 2 de 8 |
| B3, janela de 90 d | 0,889 | 1,509 | −26% | 3 de 8 |
| B4, meia-vida de 90 d | 0,871 | 1,740 | −0,3% | 1 de 8 |
| B5, meia-vida de 30 d | divergiu (previsões da ordem de 10³⁶ em jan) | — | — | 0 de 8 |
| B6, B1 + B2 | 0,855 | 1,544 | −15% | 3 de 8 |
| `historico` | 0,981 | 2,605 | +13,8% | — |

- A B0 reproduz a v1 exatamente nos 8 meses.
- O ruído por mês é a diferença máxima entre as três réplicas da B0. Vai de 0,007 (janeiro) a
  0,090 (fevereiro).
- **B0 contra `historico`:** a semente 0 vence em 6 de 8 meses, com média melhor, viés
  menor e RMSE de 38,9 contra 39,9. As sementes 1 e 2 vencem em só 3 de 8 meses.

**Importância por permutação: parcial, interrompida.** Só o AP base do modelo superconjunto
(34 colunas) nas dobras eólicas de jan a jun foi registrado: 0,805, 0,570, 0,803, 0,822,
0,808 e 0,680. Na v1, com 14 features, os valores são 0,817, 0,569, 0,786, 0,828, 0,811 e
0,683. Nenhuma importância por grupo foi gravada.

### Interpretação e decisão

- **Pela regra pré-registrada, nenhuma variante substitui a B0.** A B1 tem a melhor média,
  mas dentro do ruído de semente.
- As tendências e as janelas curtas melhoram fevereiro acima do ruído, o que confirma o
  sintoma de mudança de regime. Porém, as janelas curtas pioram jun–ago e subestimam a
  energia em 15% a 26%. Recência agressiva deixa a Poisson do HGB instável (B5).
- **B0 contra `historico`:** a regra passa na semente 0, mas não é robusta às réplicas. Na
  eólica, o modelo é claramente melhor em jan, fev e ago e empata nos demais meses. Nenhuma
  mudança de serviço foi feita: a equipe decidiu pivotar a recomendação para não depender do
  volume.
- **Interpretação, não medida:** o superconjunto não melhora o AP de forma consistente sobre
  a v1 (3 de 6 dobras parciais acima, 3 abaixo). Mais colunas não compram sinal. A v1 continua
  congelada.
- **Para o pitch:** o marco que pode ser citado é o volume do modelo contra o `historico`,
  com WAPE diário de −13% nas duas fontes em jan–ago. Na solar, isso foi confirmado em
  setembro (0,517 contra 0,565). Na eólica, o ganho se concentra na mudança de regime
  (fevereiro, −36%), e os demais meses empatam.

### Limitações e próximos passos

- A importância por grupos não foi concluída. O script `importancia_grupos.py` está pronto
  e roda em cerca de 55 min, se for retomado.
- O ruído de semente na solar não foi medido.
- Os limiares e o modelo v1 não mudaram, e o handoff continua válido.

## 2026-09-26 - Nova Etapa 2 (8/n): protocolo da v3

### Contexto e pergunta

A equipe pediu três frentes novas sobre a v1 congelada:

- **A:** volume em faixas relativas, com probabilidade calibrada por faixa;
- **B:** sinal de restrição mais fino que o estado, para o AP de ocorrência;
- **C:** causa, tentando vencer a moda da usina nas trocas de regime.

Esta entrada é o **pré-registro**. Ela fixa faixas, features, variantes, métricas e regras
de decisão antes de treinar qualquer variante. Nenhum resultado de variante aparece aqui.

### Fatos e evidências observados (antes de qualquer variante)

- **Snapshot:** os SHA-256 dos 5 Parquet conferem com os do prompt (`a95a1741…`,
  `c1572983…`, `487050da…`, `b268809c…`, `e2935941…`).
- **Âncora reproduzida exatamente** a partir do cache v2 regenerado nesta máquina (Windows,
  12 threads):
  - B0 do volume eólico: WAPE diário de fevereiro = 1,655084 (esperado 1,655084);
  - ocorrência v1 (`OCCURRENCE`, `PARAMS`) nas 8 dobras: diferença de AP de **0,0** nos 16
    meses-fonte contra `ap_modelo` de `metricas_backtest.csv`.
- **Contradição 1: não existe conjunto acima da entidade do modelo.**
  - No `*_tm`, que é a base do modelo, o `id_ons` já é o conjunto: 166 dos 180 ids eólicos
    começam com `CJU` ("CONJ. TERRA SANTA"). Na solar são 83 de 87.
  - O `*_detail` tem 1.060 usinas eólicas em 180 conjuntos (560 solares em 97), mas só 11
    ids eólicos do tm (4 solares) aparecem no detail.
  - 184 dos 198 pares (id, nome) eólicos do tm casam com um `nom_conjuntousina` do detail.
    Cada entidade do modelo, portanto, já é o seu conjunto.
  - `conjunto_nivel_*` repetiria `usina_nivel_*`. **Decisão conservadora:** as features de
    conjunto saem da B1 e da C1. O casamento de nomes não foi tentado, porque só associaria
    cada entidade a ela mesma.
- **Contradição 2: `dsc_restricao` só existe a partir de 01/09/2025** nas duas fontes.
  - Antes disso, o campo é nulo em todas as ordens: 1,39 M de 2,56 M de ordens eólicas com
    causa têm texto nulo.
  - As contagens do prompt se confirmam: 5 textos ENE, 58 CNF e 272 REL na eólica. Na solar
    são 3, 68 e 272.
  - O regime nacional usa `cod_razaorestricao`, que existe no período todo, então a B1 não
    é afetada.
  - Na B2 e no grupo da C1, a janela de 365 dias mistura dois significados de nulo: "antes
    de 09/2025" e "sem corte local". A dobra de janeiro treina com cerca de 4 meses de grupo
    preenchido. Isso não é vazamento, mas é uma mudança de regime entre treino e teste, e fica
    registrado como ressalva da B2.
- **Normalização de `dsc_restricao`** (`normalizar_restricao`, commit `0b3bf2a`):
  - cardinalidade dos textos locais (CNF + REL): de 327 para 135 na eólica e de 337 para 169
    na solar; CNF de 58 para 48 e REL de 272 para 101 na eólica;
  - os 30 textos mais frequentes de cada fonte foram conferidos à mão. "FLUXO FNESE" reúne 64
    variantes eólicas de SGI. Nenhum par de restrições fisicamente distintas foi fundido.
- **Limiares** (`scripts/experimentos/limiares_v3.py`, gravados em
  `docs/reports/nova-abordagem/v3/faixas.json`). São tercis da fração positiva nos dias-alvo
  de 2025, com 2 casas. Nenhum colapsou.

  | Nível | Fonte | k₁ | k₂ | Positivos em 2025 |
  |---|---|---|---|---|
  | meia-hora | eólica | 0,12 | 0,38 | 959.118 meias-horas |
  | meia-hora | solar | 0,20 | 0,48 | 247.784 |
  | diário | eólica | 0,05 | 0,16 | 44.234 dias |
  | diário | solar | 0,05 | 0,14 | 18.194 |

  - Dias de 2025 excluídos do rótulo diário: 171 na eólica e 134 na solar. Todos têm
    `cap_91d = 0`, ou seja, referência nula nos 91 dias. Nenhum dia de 2025 no cache tem
    menos de 48 slots.
  - Frações de meia-hora acima de 1: 4.855 na eólica e 1.220 na solar (0,2% e 0,1%). Elas
    ficam na faixa severa, sem truncamento.

### Interpretação e decisão: regras comuns

- **Período:** só as 8 dobras de jan–ago/2026 (`v2_comum.folds`, janela de 365 dias).
  Setembro de 01 a 24 está gasto e não entra.
- **Cache v3** (`data/interim/previsao/v3/`): tem exatamente as linhas e a ordem do v2, com
  colunas a mais. Nenhuma linha é filtrada por `cap_91d` nulo; o nulo fica no rótulo.
- **Regra de adoção:** a variante vence a referência se ganhar na média das 8 dobras **e** em
  pelo menos 6 de 8 meses. Uma vitória mensal só conta se a margem superar o ruído daquele
  mês.
- **Ruído:** é a maior diferença da métrica entre as sementes 0, 1 e 2.
  - Quando a referência tem semente (B0, A0 contra A1), o ruído vem das réplicas da
    referência.
  - **Quando a referência é determinística** (o `historico` na frente A, a moda na frente C),
    o ruído é a amplitude entre as sementes 0, 1 e 2 **do próprio candidato**. Sem isso, o
    ruído valeria zero e a regra ficaria mais frouxa do que a seção 1 pretende.
  - A comparação usa sempre a semente 0.
- **Múltiplas comparações:** no máximo 2 variantes por frente e célula. A melhor de 2 nas
  mesmas dobras é otimista, e isso será dito junto de qualquer conclusão.
- **Modelos:** `HistGradientBoosting` com os `PARAMS` da v1 (`CAUSE_PARAMS` na causa), sem
  busca de hiperparâmetros. Linhas ordenadas por `fonte, id_ons, dia, slot`.

### Frente A: faixas de volume

- **Rótulos:**
  - fração da meia-hora = `y_volume / cap_91d`;
  - fração diária = energia do dia / (`cap_91d` × 24 h), nula sem os 48 slots;
  - `cap_91d` = p99 de `val_geracaoreferencia` em (L − 91, L], janela exata mesmo sem dado
    em L;
  - faixas: sem corte (0), leve (0, k₁], moderado (k₁, k₂] e severo (> k₂).
- **Modelos:** um classificador binário por limiar, fonte e nível para P(fração > k).
  - Na meia-hora, k₀ **reusa** as previsões da B0 com semente 0, sem retreinar.
  - No diário, k₀ é um classificador diário novo ("algum corte no dia").
  - Treino e avaliação usam as linhas com fração não nula.
  - Monotonização por mínimo acumulado: P(>k₂) ≤ P(>k₁) ≤ P(>k₀). As faixas saem por
    diferença.
- **Features:**
  - A0 na meia-hora = `OCCURRENCE` da v1 (14);
  - A0 no diário = média e máximo nos 48 slots de `hist_7d`, `hist_28d`, `hist_91d`,
    `ultimo_slot`, `vol_hist_7d` e `vol_hist_28d` (12), mais `usina_nivel_ultimo`,
    `usina_nivel_7d`, `estado_nivel_ultimo`, `estado_nivel_7d`, `estado_nivel_28d`,
    `estado_ene_7d`, `idade`, `dia_semana` e `feriado` (9);
  - A1 = A0 mais as features adotadas na frente B. Só é executada se a B adotar algo.
- **Baselines nas mesmas linhas:**
  - `historico`: frequência de fração > k do próprio rótulo nos dias de (L − 28, L], no mesmo
    slot na meia-hora. Cada dia passado d usa a sua própria definição de rótulo (`cap_91d` de
    L(d)), então não há vazamento;
  - `ultimo_dia`: o indicador em L;
  - para o RPS, as faixas do `historico` obtidas das frequências monotonizadas.
- **Métricas:**
  - principal: AP de P(>k) por limiar, fonte e nível;
  - secundárias: Brier, confiabilidade em 10 bins, RPS das 4 faixas e skill do RPS sobre o
    `historico`;
  - operacional: limiar de alerta de "severo" F1-ótimo nas previsões fora da amostra de
    jan–abr (`choose_threshold`), com recall e precisão em mai–ago.
  - Não há acurácia de faixa como métrica principal.
- **Adoção:** cada combinação limiar × fonte × nível é servida pelo modelo se o A0 vencer o
  `historico` em AP pela regra. A A1 substitui a A0 se vencê-la pela regra, com ruído das
  sementes da A0.

### Frente B: regime nacional e grupo de restrição

- **Features** (todas até L, janelas exatas):
  - `sin_ene_ultimo` e `sin_ene_7d`: participação de ENE nas ordens com causa conhecida da
    mesma fonte no SIN, em L e média diária em (L − 7, L];
  - `sin_ene_ultimo_total` e `sin_ene_7d_total`: o mesmo, com as duas fontes juntas;
  - `grupo_restricao`: a restrição normalizada mais frequente da usina nas meias-horas com
    corte positivo e causa CNF/REL em (L − 91, L]. Empate pela ordem alfabética. Sem corte
    local, é nulo;
  - `grupo_nivel_ultimo`, `grupo_nivel_7d` e `grupo_tamanho`: fração das meias-horas cortadas
    das usinas da mesma fonte e do mesmo grupo (membros definidos em L), em L e média diária
    em (L − 7, L], e o número de membros.
- **Variantes:** B0 = v1 de ocorrência (sementes 0, 1 e 2); B1 = B0 + as 4 `sin_*`;
  B2 = B1 + as 3 `grupo_*`.
- **Métrica:** AP de ocorrência por fonte, na célula de cada fonte. Também será reportado o AP
  por idade (2, 3 e 4 a 7 dias).
- **Adoção:** pela regra, contra a B0. Se as duas vencerem, a B2 só é adotada se também vencer
  a B1 pela regra; caso contrário, fica a B1.
- **Diagnósticos obrigatórios:**
  - taxa de nulos por feature e por mês, inclusive nos meses de treino;
  - distribuição do tamanho dos grupos. Se a maioria tiver uma só entidade, o nível do grupo
    repete o da usina e a B2 não tem como ganhar;
  - verificação de que usinas novas não ficam com nulo por engano.

### Frente C: causa

- **Referências:**
  - a moda servida: argmax das participações da usina no slot em 28 d, com recurso ao estado
    em 7 d (`apply_serving`);
  - o HGB v1 de causa, só reportado.
- **C1:** HGB multiclasse **sem** peso, com `CAUSE_PARAMS`. Features:
  - `CAUSE` da v1 (13, já com slot, dia da semana, feriado e idade);
  - a moda de 28 d em one-hot (3);
  - `causa_rel_91d`, `causa_cnf_91d` e `causa_ene_91d` (3);
  - as 4 `sin_*`;
  - as 3 `grupo_*`;
  - sem conjunto (contradição 1).
- **C2:** HGB binário ENE × local, com as mesmas features e sem peso.
  - P(ENE) ≥ 0,5 → ENE.
  - Caso contrário, a causa local vem da moda da usina no slot em 91 d entre CNF e REL. Em
    empate, ou sem histórico, usa-se CNF.
- **Treino:** as ordens com causa conhecida, como na v1.
- **Avaliação:**
  - subconjunto principal: `y_causa` conhecida **e** `y_corte = 1`, como pede o prompt;
  - o subconjunto da v1 (toda ordem com causa conhecida) é reportado ao lado, para manter a
    continuidade.
- **Métricas:**
  - macro-F1 (REL, CNF, ENE);
  - F1 por classe;
  - acurácia;
  - taxa de troca e acurácia no subconjunto de troca (causa real ≠ moda de 28 d da usina).
- **Adoção:** vencer a moda servida em macro-F1 pela regra, com ruído das sementes do
  candidato, **sem piorar** a acurácia média. Se nenhuma vencer, a moda continua servida.

### Alternativas consideradas

- **Conjunto por casamento de nomes:** descartado, porque é degenerado (contradição 1).
- **Limiares com mais casas:** não foi preciso, porque nenhum colapsou com 2 casas.
- **Ruído zero para referência determinística:** descartado, porque seria mais frouxo que a
  regra.
- **Filtrar do cache as linhas com `cap_91d` nulo:** descartado, porque mudaria a ordem e a
  amostra de bins do HGB, e a âncora deixaria de valer.

### Limitações e incertezas

- Maio–agosto já foi visto por receitas anteriores. A melhor de 2 é otimista. A adoção
  final depende de dias ainda não vistos (após 24/09/2026 ou outubro).
- Nas features diárias, `vol_hist_*` está em MWmed, sem normalização por `cap_91d`, como
  pede o prompt.

### Valor para o usuário e para a apresentação

- **Disciplina metodológica:** regras escritas antes, contradições registradas e âncora
  exata.
- **Explicação do produto:** a entidade publicada pelo ONS já é o conjunto, e isso explica
  por que "conjunto" não é um agrupamento novo.

### Próximos passos

1. Gerar o cache v3.
2. Executar as frentes B, A e C, com uma entrada de resultados por frente.

## 2026-09-26 - Nova Etapa 2 (9/n): resultados da v3, frente B (regime nacional e grupo de restrição)

### Contexto e pergunta

O AP de ocorrência melhora com sinais mais finos que o estado e legítimos no instante da
previsão? A execução segue o protocolo da entrada 8/n:

- B0 = v1 de ocorrência, com as sementes 0, 1 e 2;
- B1 = B0 + regime nacional de ENE;
- B2 = B1 + grupo de restrição.

Runner: `scripts/experimentos/frente_b.py`. Arquivos: `docs/reports/nova-abordagem/v3/frente_b.csv`
e `frente_b_resumo.csv`. Cache: `scripts/experimentos/cache_features_v3.py`.

### Fatos e evidências observados

- **Âncora:** a B0 com semente 0, lida do cache v3, reproduz o `ap_modelo` da v1 com
  diferença de 0,0 nos 16 meses-fonte. As colunas novas não alteraram linhas nem ordem.
- **Diagnóstico das features** (`nulos_features_*.csv`, `grupos_*.csv`):
  - **grupos grandes:** de 6 a 25 grupos por mês. A mediana do grupo de cada usina vai de 23
    a 90 usinas na eólica e de 6 a 53 na solar. Só 1–4% das usinas eólicas e 0–9% das solares
    estão em grupo unitário, então o nível do grupo **não** repete o da usina;
  - **grupo nulo:** 100% antes de 09/2025, como previsto (contradição 2), e cerca de 9% das
    linhas de 2026 nas duas fontes (usinas sem corte local em 91 dias). Há 2.540 linhas eólicas
    e 3.891 solares desde 12/2025 com ordem local no slot em 91 d, mas sem grupo. Elas vêm de
    ordens sem corte positivo ou com texto nulo, e são menos de 0,3% das linhas;
  - **`sin_ene_ultimo` nulo:** em 4% das linhas eólicas de 2026 (29% em fevereiro), porque
    houve dias L sem nenhuma ordem eólica com causa. As médias de 7 dias nunca são nulas.
- **AP por mês** (semente 0; o ruído é a amplitude das três sementes da B0):

  | Mês | Eól. B0 | Eól. B1 | Eól. B2 | Ruído eól. | Sol. B0 | Sol. B1 | Sol. B2 | Ruído sol. |
  |---|---|---|---|---|---|---|---|---|
  | jan | 0,817 | 0,828 | **0,836** | 0,008 | **0,779** | 0,768 | 0,773 | 0,006 |
  | fev | **0,569** | 0,503 | 0,508 | 0,020 | **0,611** | 0,574 | 0,577 | 0,006 |
  | mar | 0,786 | 0,786 | 0,786 | 0,005 | **0,795** | 0,782 | 0,779 | 0,005 |
  | abr | 0,828 | 0,823 | 0,826 | 0,001 | 0,875 | 0,885 | **0,887** | 0,002 |
  | mai | 0,811 | 0,827 | **0,841** | 0,004 | 0,870 | **0,881** | 0,877 | 0,005 |
  | jun | 0,683 | 0,697 | **0,701** | 0,005 | 0,759 | **0,777** | 0,775 | 0,004 |
  | jul | 0,888 | 0,886 | 0,887 | 0,002 | 0,904 | 0,907 | 0,905 | 0,002 |
  | ago | 0,921 | 0,923 | 0,922 | 0,000 | **0,908** | 0,902 | 0,905 | 0,002 |
  | **média** | 0,788 | 0,784 | **0,788** | | **0,813** | 0,810 | 0,810 | |

- **Decisão pela regra** (meses vencidos acima do ruído, de 8):

  | Comparação | Eólica | Solar |
  |---|---|---|
  | B1 contra B0 | 4 (média pior) | 4 (média pior) |
  | B2 contra B0 | 4 (média +0,0004) | 3 (média pior) |
  | B2 contra B1 | 3 | 1 |
  | B0 contra `historico` | 8 (0,788 contra 0,740) | 8 (0,813 contra 0,747) |

- **AP médio por idade:** eólica B0 com 0,727 (idade 2), 0,910 (3) e 0,756 (4–7); B2 com
  0,733, 0,909 e 0,757. Na solar, B0 com 0,737, 0,938 e 0,768; B2 com 0,738, 0,932 e 0,752.
  Nenhuma variante muda o perfil por idade.

### Interpretação e decisão

- **Decisão:** nada é adotado. A B0 (v1) continua a ocorrência servida, e a A1 não será
  executada, como pré-registrado.
- **Fato:** o sinal nacional e o de grupo ajudam em jan, mai e jun na eólica e em abr–jun na
  solar, com margens de +0,01 a +0,03, acima do ruído. Mas pioram fevereiro nas duas fontes:
  −0,06 na eólica, três vezes o ruído, e −0,04 na solar.
- **Interpretação (não medida):** fevereiro é a mudança de regime do ano, com prevalência de
  15% contra 40% em janeiro. Um sinal de regime do último dia liberado reforça a persistência:
  quando o regime muda entre L e T, ele empurra o modelo na direção errada. O ganho em meses
  estáveis e a perda na transição se anulam na média. É o mesmo padrão já medido para o clima
  de L no H5: persistência que ajuda quando nada muda e atrapalha quando algo muda.
- **Múltiplas comparações:** a melhor de 2 (B2 na eólica) empata com a B0 na média. Mesmo
  sem correção, não haveria o que adotar.

### Alternativas consideradas

- Adotar só para mai–ago, onde a B2 vence: descartado. Seria escolher o período depois de
  ver o resultado.
- Retreinar com features de tendência do regime: fora do pré-registro e já testado na v2
  (tendências no volume, dentro do ruído).

### Implementação e validação

- Funções puras em `faixas.py` e `restricoes.py`, com testes de janela exata, nulos, futuro
  excluído e empates (commit `0b3bf2a`).
- Cache v3 e runners no commit `22414f4`. Suíte verde e ruff limpo.
- As previsões das 5 variantes ficam em `data/interim/previsao/v3/pred_b_<fonte>.parquet`,
  fora do Git. A B0 é o k₀ da frente A.

### Limitações e incertezas

- Na B2, o nulo antes de 09/2025 mistura dois significados (contradição 2). Com mais
  histórico de `dsc_restricao`, o resultado da B2 pode mudar.
- A regra conta meses vencidos. Uma variante que ganha pouco em muitos meses e perde muito em
  um é rejeitada, e isso é intencional: o produto precisa ser robusto na virada de regime.

### Valor para o usuário e para a apresentação

- Reforça a tese do projeto: o gargalo é saber o **nível do dia-alvo**, não descrever melhor
  o passado. Sinais mais finos do passado ajudam em regime estável e atrapalham na virada.
- É um resultado negativo honesto, que pode ser citado como "testamos restrição física e
  regime nacional; não melhoram de forma robusta".

### Próximos passos

Frente A (A0 nos dois níveis) e frente C.

## 2026-09-26 - Nova Etapa 2 (10/n): resultados da v3, frente C (causa)

### Contexto e pergunta

Um modelo vence a moda da usina ao prever as **trocas** de causa (ENE ↔ local) a partir do
estado do sistema em L? A execução segue o protocolo da entrada 8/n:

- C1: HGB multiclasse sem peso, com as features da v1, a moda em one-hot, `causa_*_91d`, o
  regime nacional e o grupo de restrição;
- C2: HGB binário ENE × local; quando o resultado é local, a moda de 91 d entre CNF e REL.

Runner: `scripts/experimentos/frente_c.py`. Arquivos: `v3/frente_c.csv` e
`v3/frente_c_resumo.csv`.

### Fatos e evidências observados

- **Taxa de troca** (causa real ≠ moda de 28 d da usina, nas linhas com corte): 16,4% na
  eólica e 17,5% na solar. A persistência de 83% citada no prompt se confirma.
- **Médias de jan–ago no subconjunto principal** (causa conhecida e corte real; semente 0):

  | Fonte | Preditor | macro-F1 | F1 REL | F1 CNF | F1 ENE | Acurácia | Acurácia na troca |
  |---|---|---|---|---|---|---|---|
  | eólica | moda servida | 0,650 | 0,452 | 0,616 | 0,882 | **0,825** | 0 (por construção) |
  | eólica | HGB v1 | 0,635 | 0,419 | 0,621 | 0,865 | 0,795 | 0,338 |
  | eólica | C1 | 0,657 | 0,384 | 0,696 | 0,891 | 0,825 | 0,327 |
  | eólica | C2 | **0,677** | 0,457 | 0,692 | 0,882 | 0,824 | 0,320 |
  | solar | moda servida | 0,461 | 0,184 | 0,310 | 0,888 | **0,824** | 0 |
  | solar | HGB v1 | **0,508** | 0,254 | 0,417 | 0,851 | 0,771 | 0,382 |
  | solar | C1 | 0,483 | 0,172 | 0,396 | 0,882 | 0,813 | 0,310 |
  | solar | C2 | 0,493 | 0,208 | 0,394 | 0,876 | 0,806 | 0,319 |

  No subconjunto da v1 (toda ordem com causa), os números mudam menos de 0,01. A moda
  eólica dá 0,648, contra 0,649 no relatório v1.
- **Decisão pela regra** (meses vencidos acima do ruído das sementes do candidato):

  | Fonte | Candidato | Média | Moda | Meses | Ruído médio | Acurácia não pior? |
  |---|---|---|---|---|---|---|
  | eólica | C1 | 0,657 | 0,650 | 3/8 | 0,019 | sim (0,8248 contra 0,8251, empate) |
  | eólica | C2 | 0,677 | 0,650 | 5/8 | 0,012 | não (0,8235) |
  | solar | C1 | 0,483 | 0,461 | 5/8 | 0,015 | não (0,813) |
  | solar | C2 | 0,493 | 0,461 | 5/8 | 0,006 | não (0,806) |

- **Por mês, eólica C2 contra moda:**
  - ganha em jan (+0,04), fev (+0,04), mar (+0,08), abr (+0,08) e jun (+0,02);
  - perde em mai (−0,02), jul (−0,01) e ago (−0,02).

### Interpretação e decisão

- **Decisão:** nada é adotado. A moda da usina continua servida nas duas fontes. É o
  resultado "válido e honesto" previsto no protocolo: a causa é quase determinada pela
  localização.
- **Fato:** o ganho de macro-F1 vem das classes minoritárias. Na eólica, o CNF sobe de 0,62
  para 0,69; o REL e o ENE ficam no nível da moda. O ganho não vem de acertar mais: a
  acurácia não melhora. O modelo troca erros da classe dominante por acertos nas raras.
- **Fato:** nas trocas de regime, os modelos acertam de 32% a 38% das vezes, contra 0% da moda
  por construção. Nas linhas sem troca (83%), porém, erram mais que a moda, e o saldo em
  acurácia é zero ou negativo.
- **Interpretação:** existe algum sinal de troca no estado do sistema em L, mas ele é fraco
  demais para compensar o custo nas linhas estáveis. É coerente com a frente B: o regime do
  último dia liberado não antecipa bem o regime do dia-alvo.
- **Múltiplas comparações:** a C2 eólica, melhor de 2, tem +0,027 de macro-F1 e 5/8 meses. É
  otimista e, ainda assim, não passa.
- **Observação não pré-registrada:** na solar, o HGB v1 **balanceado** tem macro-F1 de 0,508,
  contra 0,461 da moda, com acurácia de 0,771 contra 0,824. É a mesma troca de acurácia por
  classes raras, e o HGB v1 não é candidato nesta frente. Fica registrado como candidato
  para uma validação futura.

### Alternativas consideradas

- **Limiar de P(ENE) diferente de 0,5 na C2:** não pré-registrado. Escolhê-lo agora nas
  mesmas dobras seria ajuste pós-resultado.
- **Adotar a C2 eólica por ter a melhor média:** descartado. Ela falha no critério de meses e
  piora a acurácia.

### Limitações e incertezas

- O grupo de restrição tem nulo estrutural antes de 09/2025 (contradição 2).
- O macro-F1 é dominado pelo REL raro, com F1 entre 0,17 e 0,46. Diferenças de 0,02 são da
  ordem do ruído de semente, que vai de 0,006 a 0,019.

### Valor para o usuário e para a apresentação

- **Para o pitch:** "a causa do corte muda de um dia para o outro em só 16–17% dos casos; a
  moda recente da usina acerta 82% das causas; nas trocas, nosso melhor modelo acerta cerca de
  um terço, sem compensar o custo". Isso justifica servir a causa por regra, com proveniência
  explícita.
- O resultado reforça o diagnóstico: a causa é propriedade da localização da usina na rede.

### Próximos passos

Concluir a frente A e decidir o que, se algo, vira `diario_hgb_v3`.

## 2026-09-26 - Nova Etapa 2 (11/n): resultados da v3, frente A (faixas relativas de volume)

### Contexto e pergunta

Um classificador por limiar dá uma probabilidade por faixa de corte ("qual a chance de o
corte ser severo?") melhor que a frequência histórica da própria usina? A execução segue o
protocolo da entrada 8/n:

- A0 nos dois níveis (usina × dia, que é o principal, e meia-hora), sementes 0, 1 e 2;
- a A1 não foi executada, porque a frente B não adotou nada.

Runner: `scripts/experimentos/frente_a.py`. Arquivos em `v3/`:

- `frente_a_A0.csv` (AP e Brier por mês, limiar e preditor; RPS por mês);
- `frente_a_A0_resumo.csv` (decisão);
- `frente_a_A0_alerta_severo.csv`;
- `frente_a_A0_confiabilidade.csv` (10 bins, jan–ago juntos).

### Fatos e evidências observados

- **Ruído de semente:**
  - no nível diário é **exatamente zero**. Com menos de 200 mil linhas de treino, o HGB não
    subamostra os bins e, sem early stopping, a semente não muda nada;
  - na meia-hora, o ruído médio de AP vai de 0,004 a 0,015, conforme o limiar.
- **AP médio de jan–ago** (semente 0, contra o `historico`; meses vencidos acima do ruído):

  | Nível | Fonte | k₀ = 0 | k₁ (leve → moderado) | k₂ (→ severo) |
  |---|---|---|---|---|
  | diário | eólica | **0,919** vs 0,880 (7/8) | 0,596 vs **0,610** (3/8) | 0,361 vs **0,378** (2/8) |
  | diário | solar | **0,928** vs 0,887 (8/8) | **0,740** vs 0,645 (8/8) | **0,426** vs 0,336 (8/8) |
  | meia-hora | eólica | **0,788** vs 0,740 (8/8) | 0,514 vs **0,520** (2/8) | 0,283 vs **0,306** (2/8) |
  | meia-hora | solar | **0,813** vs 0,747 (8/8) | **0,648** vs 0,559 (8/8) | **0,416** vs 0,335 (7/8) |

  O baseline `ultimo_dia` fica abaixo dos dois em todas as células (por exemplo, 0,279 no
  k₂ diário eólico). A prevalência média de "severo" é de 10,4% das meias-horas na eólica e
  6,4% na solar, e de 21% dos dias eólicos.
- **AP de k₂ por mês, nível diário:**
  - solar: modelo acima do `historico` nos 8 meses, com margens de +0,005 (fev) a +0,21 (jul);
  - eólica: modelo abaixo em fev–jul (−0,01 a −0,09) e acima em jan (+0,09) e ago (+0,01).
- **Brier:**
  - meia-hora solar: o modelo vence nos três limiares, em 6 a 8 meses;
  - eólica: o modelo perde em k₁ e k₂;
  - k₀ diário, nas duas fontes: o modelo tem AP melhor, mas Brier **pior** (0,135 contra
    0,118 na eólica). Ele ordena melhor, mas é menos calibrado que a frequência.
- **RPS das 4 faixas** (skill sobre o `historico` categórico, média de jan–ago):
  - meia-hora solar: +7,2%, positivo em 7/8 meses;
  - diário solar: +3,8%, em 6/8;
  - meia-hora eólica: −0,2%, em 2/8;
  - diário eólico: −7,9%, em 1/8.
- **Alerta de "severo"** (limiar F1-ótimo em jan–abr, avaliado em mai–ago):

  | Nível | Fonte | Modelo: recall / precisão | `historico`: recall / precisão |
  |---|---|---|---|
  | diário | eólica | 0,56 / 0,56 | 0,78 / 0,48 |
  | diário | solar | 0,59 / 0,53 | 0,72 / 0,36 |
  | meia-hora | eólica | 0,50 / 0,44 | 0,75 / 0,38 |
  | meia-hora | solar | 0,53 / 0,52 | 0,78 / 0,35 |

  O F1 derivado favorece o modelo na solar (0,56 contra 0,48 no diário) e o `historico` na
  eólica.
- **Exemplo concreto de saída** (solar, modelo da dobra de agosto, treinado só até julho):
  - usina `CJU_MGDRC`, dia-alvo 30/08/2026, idade 3 dias, nível diário:
    - sem corte 0,1%, leve 7,0%, **moderado 55,3%**, severo 37,5%;
    - `historico` P(>k₀)/P(>k₁)/P(>k₂) = 0,89/0,68/0,29;
    - **verdade:** fração diária de 0,203, ou seja, **severo** (k₂ = 0,14). O modelo deu 93%
      para "moderado ou pior", mas a faixa mais provável (moderado) ficou uma abaixo da real;
  - a mesma usina e o mesmo dia na meia-hora, entre 9h e 16h:
    - de 9h às 14h, severo é a faixa mais provável (34%–46%) e a verdade é severo (fração de
      0,52 a 0,74);
    - às 15h, leve fica com 61% e a verdade é moderado (0,40);
    - às 15h30, leve fica com 56% e a verdade é leve (0,09);
  - na eólica, `CJU_CEJAN` em 08/08: severo com 55%, verdade severa (fração de 0,33).

### Interpretação e decisão

- **Pela regra pré-registrada, o modelo é servido nestas células:**
  - k₀ em todas as células de fonte e nível;
  - k₁ e k₂ da **solar**, nos dois níveis.

  Na **eólica**, k₁ e k₂ ficam com o `historico`, nos dois níveis. A composição é por limiar,
  com proveniência por componente.
- **Interpretação:** é o mesmo quadro do volume da v1.
  - Na solar, o modelo sabe quanto do dia será cortado: horas de sol, carga e calendário
    são previsíveis.
  - Na eólica, a intensidade depende do vento do dia-alvo, e o oráculo H5 já mostrou que o
    gargalo é meteorológico.
  - Saber **se** haverá corte (k₀) é regional e persistente, e o modelo vence nas duas fontes.
- **Faixa mais provável:** é informativa, mas não é a métrica. No exemplo, o modelo põe
  93% em "moderado ou pior" e a verdade é severo, com a faixa mais provável uma abaixo. O
  produto deve mostrar as probabilidades, não só a faixa mais provável.
- **Calibração do k₀ diário:** o Brier pior indica que a probabilidade diária de "algum corte"
  precisa de recalibração antes de ser mostrada como número. Isso fica como limitação, porque
  não havia recalibração pré-registrada.

### Alternativas consideradas

- **Servir o modelo também na eólica por ter AP próximo:** descartado. Perde em 6 de 8 meses.
- **Recalibrar o k₀ diário (isotônica em jan–abr):** não pré-registrado. Fica para a próxima
  versão, com dias novos.
- **Faixas em MWh:** descartadas no desenho, porque codificam o tamanho da usina.

### Limitações e incertezas

- Maio–agosto já foi visto por receitas anteriores. Os limiares vêm de 2025 e estão fora das
  dobras.
- Vitórias com ruído zero (nível diário) contam qualquer margem positiva. Em fevereiro, o k₂
  solar diário vence por +0,005, o que é um empate prático.
- `cap_91d` usa o p99 da referência. Usinas com expansão recente podem ter fração acima de 1
  por alguns dias (0,1–0,2% das meias-horas de 2025).

### Valor para o usuário e para a apresentação

- **Pitch (solar):** "para cada usina solar, dizemos na véspera a chance de o corte de amanhã
  ser leve, moderado ou severo, com precisão média 27% maior que a frequência histórica da
  própria usina no limiar de severo (AP de 0,43 contra 0,34)".
- **Pitch (eólica):** "sabemos se haverá corte; quanto será cortado depende do vento de
  amanhã, e sem previsão meteorológica a regra histórica é tão boa quanto o modelo". É o
  mesmo argumento do H5.
- O exemplo concreto mostra a saída da recomendação para uma usina, com a verdade ao lado.

### Próximos passos

Congelar a composição adotada como `diario_hgb_v3` (treino até 30/08), com manifesto e
colunas `p_faixa_*` no produto e fallback preservado.

## 2026-09-26 - Nova Etapa 2 (12/n): congelamento da v3 e integração das faixas no produto

### Contexto e pergunta

A frente A adotou componentes pela regra (11/n):

- k₀ nas duas fontes;
- k₁ e k₂ da solar, nos dois níveis.

As frentes B e C não adotaram nada. O protocolo pede congelar o que foi adotado como
`diario_hgb_v3`, com treino até 30/08, manifesto e produto apontando para a v3 sem perder o
fallback.

### Fatos e evidências observados

- **Artefato** `diario_hgb_v3_2026-08-30`:
  - SHA-256 `1b64de92d6420eb56ce872032e4d23580e1228dd9bb509d127c779ff15fc8afd`;
  - commit da receita `17cf718`;
  - manifesto em `docs/reports/nova-abordagem/modelo-congelado-v3.json`;
  - linhas de treino das faixas: meia-hora com 2.675.547 eólicas (sem classificador de k₁ e
    k₂ servido) e 1.289.184 solares; diário com 55.735 eólicas e 26.858 solares.
- **Os componentes da v1 dentro da v3 são idênticos aos da v1.** Numa emissão de agosto pelo
  caminho do produto (t0 = 21/08, corte de `nightly_cutoff` às 20h de 20/08), a diferença
  máxima de `p_corte` entre a v3 e uma v1 retreinada com a mesma receita foi de 0,0 em 11.232
  linhas.
  - O SHA-256 da v1 regenerada nesta máquina (`d4522378…`) difere do artefato de 26/09
    (`6340240d…`), porque o joblib depende de plataforma e versão. As previsões são o
    critério.
- **Paridade entre treino e serviço:** para os dias-alvo 03/08 e 20/08, `features_faixas`
  (serviço) reproduz o cache v3 (backtest) **exatamente**. Foram 0 divergências em
  `cap_91d`, `exc_hist_k0..2`, `exc_ult_k0..2` e nos agregados diários, em 7.344 meias-horas
  eólicas e 3.888 solares por dia.
- **Composição mista eólica**, medida sem treino novo a partir das previsões fora da amostra:
  k₀ do modelo, k₁ e k₂ do `historico`, monotonizados.
  - Meia-hora: RPS de 0,1056, contra 0,1080 do `historico` puro e 0,1086 do modelo puro. AP
    de k₂ de 0,310, contra 0,306.
  - Diário: RPS de 0,1614, contra 0,1550 do `historico` puro. É **pior**, porque o k₀ diário
    do modelo é mal calibrado (Brier de 0,135 contra 0,118). A composição foi medida depois
    da decisão e não foi pré-registrada, então fica como limitação e não altera a regra.
- **Correção da entrada 10/n:** a tabela diz que a acurácia da C1 eólica "não é pior
  (empate)". Na verdade, 0,8248 < 0,8251, e o código a marcou como pior. A decisão não muda,
  porque a C1 venceu só 3 de 8 meses.

### Interpretação e decisão

- **O que é a v3:** v1 + faixas. Ocorrência, volume, causa, limiares de alerta e `SERVING`
  continuam os da v1.
- **Serviço** (`curtamap.previsao.faixas_servico`):
  - colunas `p_faixa_*`, `faixa_provavel`, `p_faixa_dia_*`, `faixa_provavel_dia`,
    `tipo_saida_faixas` e `tipo_saida_faixas_dia`;
  - a proveniência sai por limiar, por exemplo `k0:modelo,k1:historico,k2:historico` na
    eólica.
- **`product_predictor()`:** tem preferência explícita por v3, depois v1, depois o baseline.
  O `model_id` agora vem da versão no metadado, para que um artefato v1 continue se
  apresentando como v1.
- **Histórico exigido:** sobe para 130 dias antes do corte, porque o `historico` de faixa
  usa o `cap_91d` de cada L(d).

### Alternativas consideradas

- **Usar o `cap_91d` de L para todos os dias passados no `historico` de serviço:**
  descartado. Mudaria a definição avaliada, e a paridade deixaria de ser exata.
- **Servir só o nível da meia-hora:** descartado. O protocolo trata o nível diário como
  principal, e ele foi adotado na solar.
- **Recalibrar o k₀ diário antes de congelar:** não foi pré-registrado. Fica como próximo
  passo, com dias novos.

### Implementação e validação

- Commits:
  - `10d66fa`: serviço, testes de fallback, v1 sem faixas, proveniência, soma 1 e vazamento
    das features de faixa;
  - `17cf718`: `treinar --faixas`.
- A suíte completa passa com `PYTHONUTF8=1`. Sem essa variável, o teste já existente
  `test_feature_inventory` falha no Windows, porque lê um arquivo sem `encoding` (cp1252).
  Isso não tem relação com a v3.
- Ruff limpo.

### Limitações e incertezas

- A v3 não foi avaliada em setembro, que está gasto. A confirmação exige dias após
  24/09/2026.
- O k₀ diário é mal calibrado: a UI não deve lê-lo como frequência. Na eólica diária, a
  composição mista tem RPS pior que o `historico` puro.
- O artefato da v1 de 26/09 não está nesta máquina. A igualdade foi verificada contra uma v1
  retreinada com a mesma receita.

### Valor para o usuário e para a apresentação

- **Na demonstração:** para cada usina e dia, o painel pode mostrar "chance de corte leve,
  moderado ou severo", com a origem de cada número.
- **Na solar:** o número vem do modelo, que vence a regra histórica.
- **Na eólica:** vem da própria história da usina, com a explicação de que a intensidade
  depende do vento de amanhã.

### Próximos passos

1. Integrar as colunas novas na interface, carregando 130 dias de histórico.
2. Confirmar a v3 com dias novos (após 24/09 ou outubro).
3. Recalibrar o k₀ diário.
