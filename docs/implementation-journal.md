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

## 2026-09-23 - Etapa 3: recomendação rastreável e cenários de impacto

### 1. Contexto e pergunta

Com o contrato de previsão estabilizado e a escolha do modelo ainda independente, a pergunta foi:
como transformar 48 janelas de previsão em uma decisão útil ao gerador sem prometer recuperação,
receita, ressarcimento ou benefício climático? A implementação também precisava alimentar a visão
tática com histórico observado e preservar integralmente o teste reservado a partir de 01/05/2026.

### 2. Fatos e evidências observados

- A taxonomia oficial distingue REL (indisponibilidade externa), CNF (confiabilidade), ENE
  (impossibilidade de alocar geração na carga) e PAR (limite indicado no parecer de acesso). A
  NT-ONS DOP 0022/2025 informa que os comandos chegam pelo SINapse, podem mudar ao longo do dia e
  que a referência final para eventual ESS é apurada em eventos REL.
- O MME publicou para o LRCAP Armazenamento 2026 requisitos mínimos de 30 MW, quatro horas e 85%
  de eficiência total. O PDE 2030 da EPE usa 90% como premissa de eficiência de ciclo de bateria.
- Para sensibilidade financeira, a CCEE publicou em 2025 piso de R$ 58,60/MWh, teto de
  R$ 751,73/MWh e expectativa média de R$ 310,29/MWh em junho para SE/CO, NE e N. Esses números
  não são o contrato do gerador.
- A planilha 2025 do MCTI para a margem de operação do SIN tem mínimo mensal de 0,2146,
  média aritmética de 0,4124667 e máximo de 0,5780 tCO₂/MWh. São fatores de cenário de emissão
  deslocada, não créditos certificados.
- Uma emissão reconstituída somente com dados anteriores a maio, `t0 = 29/04/2026 10h` e corte de
  dados em 28/04 00h, leu 310.464 linhas dos 28 dias anteriores, produziu 11.088 janelas e 500
  episódios. Para `fotovoltaica + CJU_MGARN`, o baseline indicou ENE de 12h a 14h e 148,14 MWh
  em risco. Sob a bateria de referência, os cenários deram 51/54/54 MWh, R$ 2.988,60 /
  R$ 16.755,66 / R$ 40.593,42 e 10,9446 / 22,2732 / 31,2120 tCO₂.

### 3. Interpretação e decisão

Alertas consecutivos são agrupados somente dentro de `fonte + id_ons + t0`; assim, não se somam
emissões sobrepostas nem entidades homônimas de fontes diferentes. Se a causa variar ou faltar em
qualquer janela, o episódio fica com causa indeterminada em vez de escolher uma causa dominante.

As ações são determinísticas: preservar evidências para REL, coordenar operação para CNF, avaliar
armazenamento para ENE, revisar o parecer para PAR e validar a causa quando ela for nula. Somente
ENE recebe energia recuperável nesta versão, limitada por energia em risco, potência × duração,
capacidade e eficiência. As demais ficam em zero porque não existe premissa defensável que converta
coordenação ou estudo em MWh. Preço ou carbono ausente produz nulo.

### 4. Alternativas consideradas

- Dividir episódios quando a causa muda: rejeitado, pois o requisito temporal define o episódio
  pela continuidade do alerta; a causa do episódio fica nula de modo conservador.
- Eleger a causa com maior energia prevista: rejeitado, porque criaria uma causa que o contrato não
  observou de forma uniforme e poderia direcionar a ação errada.
- Aplicar uma fração genérica de recuperação a todas as causas: rejeitado por falta de fonte.
- Usar PLD como receita ou REL como ressarcimento automático: rejeitado; ambos dependem de contrato,
  apuração e regulação.
- Preencher premissas faltantes com valores típicos: rejeitado. A ausência permanece nula e a
  recuperação não quantificada fica em zero.

### 5. Implementação e validação

O ciclo TDD começou com falha de importação de `curtamap.recommendation`. Os testes foram escritos
antes para episódio único, continuidade, janela sem alerta, fontes iguais com o mesmo `id_ons`,
causa nula, energia nula, todas as causas inclusive PAR, premissas ausentes, limite da recuperação,
proveniência e resumo tático semanal/mensal. Depois foram implementados:

- `group_risk_windows`, `recommendation_rule`, `build_recommendations` e `impact_sensitivity`;
- premissas versionadas em `configs/premissas/v1.json`;
- `summarize_history`, que chama `derive_targets` e agrega entidade, período, causa, UF e subsistema;
- documentação completa em `docs/recommendation-rules.md` e atualização do pitch.

Todas as recomendações produzidas passam por `validate_recommendations`. A validação final executou
`uv run pytest` (**167 testes aprovados**), `uv run ruff check .` e
`uv run ruff format --check .`, ambos limpos. Nenhuma chamada usou `allow_reserved_test=True`; a
função tática recusa explicitamente qualquer linha a partir de 01/05/2026.

### 6. Limitações e incertezas

- A bateria de 30 MW/120 MWh é referência setorial, não um ativo conhecido da entidade.
- O preço base é uma expectativa mensal publicada para junho/2025; não é preço por submercado e
  hora do episódio nem condição contratual do gerador.
- O fator MCTI representa margem de operação; o resultado não é inventário nem redução certificada.
- O baseline copia o horário recente, tem probabilidades 0/1 e ainda será substituído ou confirmado
  pela Etapa 2C. A emissão reconstituída não é evidência de uma decisão real tomada em 29/04.
- `id_ons` pode representar conjunto, não usina física. Estado de carga, topologia, habilitação e
  espaço para descarga futura não estão no contrato.
- PAR não é uma causa produzida pelo preditor atual, mas sua regra pública existe para histórico e
  futuras entradas compatíveis, sem alterar `FORECAST_SCHEMA`.

### 7. Valor para o usuário e para a apresentação

O gerador recebe uma janela, uma ação compatível com a causa, a antecedência e os limites que
precisa conferir. O pitch ganha um exemplo auditável em que 148,14 MWh em risco não viram uma
promessa: o cenário limita a 51–54 MWh e mostra a origem de cada número. Isso materializa a tese
do CurtaMap: IA prevê; regras e premissas visíveis transformam previsão em decisão responsável.

### 8. Próximos passos

1. Validar as cinco ações e o texto de antecedência com operadores de geradores e especialistas em
   comercialização/regulação.
2. Substituir potência, capacidade, eficiência, estado de carga e preço de referência por dados do
   ativo/contrato, mantendo nulo quando não houver integração confiável.
3. Decidir com o responsável se preço horário por submercado entra numa futura versão de premissas.
4. Integrar a saída contratual na interface da Etapa 4 sem importar o módulo experimental.
5. Após a Etapa 2C, repetir a história com o preditor escolhido e liberar o teste reservado somente
   pelo processo metodológico aprovado.

## 2026-09-23 — Auditoria Etapa 3: isole os testes legados do período reservado

### Contexto, fatos e decisão

Antes de executar a suíte da auditoria, a leitura do código encontrou dois caminhos incompatíveis
com a proteção da Etapa 2C: `tests/test_forecasting.py` passava explicitamente a opção de liberação
do teste; `tests/test_notebook.py` podia abrir os outputs históricos ou executar integralmente a
EDA da Etapa 1. Esses caminhos **não foram executados nesta auditoria**.

O teste de previsão passou a verificar a fronteira permitida (horizonte terminando exatamente em
01/05/2026, limite exclusivo), sem liberação. Os dois testes do notebook ficam explicitamente
ignorados até decisão da 2C. Isso protege a execução padrão dos testes; não cria uma barreira
universal contra scripts antigos de EDA ou acesso direto aos arquivos.

### Alternativa, validação e limitação

Usar uma variável de ambiente para contornar a proteção foi descartado. A revisão relevante usa
`uv run pytest tests/test_forecasting.py tests/test_notebook.py`, Ruff e formatação desses arquivos.
As verificações dos outputs antigos e da execução integral do notebook ficam deliberadamente
pendentes. O notebook não foi aberto nem reexecutado. Próximo passo: concluir a auditoria do
backend com fixtures sintéticas e um recorte real estritamente anterior a maio/2026.

## 2026-09-23 — Auditoria Etapa 3: corrija limites físicos, nulos e entradas inválidas

### 1. Contexto e pergunta

A auditoria adversarial da entrega `ff8461b` perguntou se os cenários respeitam potência em cada
meia hora, se desconhecido continua desconhecido e se as fontes sustentam as afirmações.

### 2. Fatos e evidências observados

A primeira execução de 66 casos novos produziu **42 falhas e 24 aprovações**, antes das correções.
Entradas negativas/não finitas, cenários incompletos, origem inválida, proveniência inconsistente,
grade irregular e previsão no período reservado não eram integralmente recusados. O resumo tático
convertia grupo todo nulo em zero e apresentava somas parciais como totais. A ausência de parâmetros
de bateria também produzia zero. A fórmula agregada superestimava carga quando a energia se
concentrava em poucas janelas.

Recorte real `[26/04/2026, 28/04/2026)`: 22.176 linhas → 11.088 previsões → 500 recomendações.
Nenhum dado reservado foi consultado. Para `fotovoltaica + CJU_MGARN`, emissão 29/04 às 10h,
as quatro janelas de 12h–14h contêm 2,9865 / 83,5655 / 61,4625 / 0,1255 MWh. A 30 MW, a entrada
máxima é **33,112 MWh**, não 60. Portanto, os **51/54/54 MWh anteriores ficam corrigidos para
28,1452/29,8008/29,8008 MWh**. São cenários isolados, não despacho garantido.

As fontes primárias confirmam os números de preço e fatores de emissão; R$ 310,29 foi recalculado
como média ponderada de 720 horas (310,29297222 antes do arredondamento). Os fatores mensais MCTI
somam 4,9496; a média simples é 0,4124666667. A Portaria MME 136/2026 define energia entregável
no PMI, tornando necessária a distinção entre capacidade de entrada e de saída. O PDE 2030,
p. 294, usa 90% em estudo de geração distribuída, não como garantia para BESS centralizado.

A Lei 15.269/2025 e o art. 1º-B da Lei 10.848/2004 tornam incorreta a frase universal
“somente REL pode ensejar ESS”. As descrições REL/CNF foram corrigidas sem calcular direitos.
A análise regulatória detalhada e os links ficam no relatório da auditoria.

### 3. Interpretação e decisão

Premissas v2 passam a ser o padrão: capacidade útil de saída; RTE aplicada uma vez à entrada;
potência de carga de 30 MW explicitamente hipotética. V1 fica preservada para reprodução da
convenção anterior. A função de cenário recebe opcionalmente o perfil semi-horário; a construção
de recomendações sempre o fornece. Sem perfil, a função isolada entrega somente um teto agregado.

Premissas estruturais ausentes dão erro; valor explicitamente nulo com justificativa permanece
nulo. Como o contrato exige energia recuperável preenchida, `build_recommendations` recusa
recuperação indeterminada em vez de usar zero. Não se alteraram contratos, preditor ou interface.
O resumo tático ganhou contagens de volumes nulos/válidos, cortes indeterminados e energia
conhecida separada; seu total fica nulo se qualquer volume do grupo for desconhecido.

### 4. Alternativas consideradas

Clampear entradas inválidas, escolher outro cenário quando falta base e imputar zero foram
rejeitados. Simular SOC, topologia, descarga futura, lucro líquido ou certificação climática sem
dados do ativo também foi rejeitado. Uma proposta separada de evolução do contrato é necessária.

### 5. Implementação e validação

`assumptions.py`, `recommendation.py`, premissas v2 e regressões adversariais. TDD Red–Green,
seguido de testes de fronteira, perfil, overflow, conservação, ordenação de cenários e integração
sintética e real `load_history → SameSlotRecentBaseline → build_recommendations`.
`uv run pytest`: **241 aprovados, 2 ignorados** (notebook protegido); Ruff, formatação de 44
arquivos e `git diff --check` passaram. Execução real: leitura 0,584 s, previsão 0,053 s,
recomendação 0,116 s, resumo 0,006 s. RSS máximo do processo: 722.534.400 bytes; não equivale ao
tamanho do frame (histórico: 2.261.328 bytes). Não houve pandas nem benchmark da base integral.

### 6–8. Limitações, valor e próximos passos

A correção reduz uma superestimação concreta do pitch. Mesmo a energia corrigida depende de
ativo, SOC, conexão e descarga viável; não somar cenários de episódios como plano de operação.
Carbono continua sensibilidade histórica, não efeito causal; valor é bruto, não receita líquida
ou compensação. Próximos passos: relatório e handoff da Etapa 4, proposta de contrato para
indeterminação, decisão da 2C e entrevistas com operadores/comercialização/regulação/BESS.
