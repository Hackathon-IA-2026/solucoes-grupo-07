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

## 2026-09-22 - Etapa 2A: decisões metodológicas e protocolo experimental aprovado

### Contexto e pergunta

Partimos do commit `ce43c48fe974a5c36fba42ce1bfd3dc486f501f9`, com a Etapa 1 fechada e
o Git limpo. O responsável pediu uma etapa exclusiva de raciocínio e discussão antes
de implementar ou treinar modelos. A pergunta era como comparar previsões de corte
de forma útil para o gerador, sem usar informações que não estariam disponíveis na
emissão e sem escolher antecipadamente um algoritmo.

A discussão foi conduzida em linguagem progressivamente mais acessível. Primeiro,
esclarecemos os horários das janelas, a diferença entre data da ocorrência e data de
publicação, e por que a validação escolhe enquanto o teste final avalia uma escolha
já congelada. Depois, o responsável solicitou todas as decisões restantes em uma
única lista, aprovou o conjunto e refinou o orçamento e a divisão entre máquinas.

### Fatos e evidências observados

Foram lidos os documentos obrigatórios, o notebook e o código/testes relevantes.
A inspeção foi somente leitura: nenhuma feature experimental, baseline ou modelo
foi implementado e nenhum treinamento ou métrica preditiva foi executado nesta etapa.

As bases principais contêm 10.806.720 observações, de outubro/2023 a agosto/2026 para
eólica e abril/2024 a agosto/2026 para solar. A integrada sobrepõe as principais;
o detail não tem associação de conjuntos completamente validada. Há 21 volumes
eólicos indeterminados, 42 restrições solares com rótulo desconhecido e ausência
de PAR. Esses fatos vêm da auditoria e do notebook, não de novos experimentos.

A pesquisa nas fontes públicas foi motivada por duas dúvidas reais do protocolo:

- Os catálogos ONS informavam atualizações às 12h e 19h. A rotina RO-AO.BR.13,
  revisão 09, usa horário de Brasília e descreve apuração do dia anterior, com
  exceções de dias não úteis e flexibilidade às segundas/após feriados. Isso não
  garante que cada arquivo esteja completo às 19h nem prova a regra histórica
  para todos os anos do snapshot.
- A inspeção somente leitura de agosto/2026 dos dados oficiais intra-semihora
  encontrou todos os 215.685 registros eólicos e 74.886 solares com início/fim da
  restrição dentro da meia hora iniciada em `din_instante`. Exemplos: 00h contém
  00h00–00h29; 23h30 contém 23h30–23h59. URLs, contagens, comparação e hashes estão
  na seção 1.2 do [protocolo](experimental-protocol.md). Não foram incorporados
  novos dados ao snapshot nem aos resultados da Etapa 1.

O Mac disponível tem 8 GiB de memória. O responsável informou um computador dedicado
com Ryzen 5 5600X, 32 GB DDR4 a 3.200 MT/s, RTX 2060 de 6 GB e aproximadamente 580 GB
livres em SSD. O local usual do clone tem cerca de 44 GB livres em outra unidade.
As especificações do outro computador são informação do usuário, não uma medição
remota feita nesta sessão. Sistema operacional e caminhos serão verificados no destino.

### Interpretação e decisão

O protocolo aprovado está em [experimental-protocol.md](experimental-protocol.md).
Ele diferencia evidências, hipóteses, decisões, concretizações de implementação e
questões necessariamente dependentes de resultados. As decisões centrais são:

- Renovar previsões a cada 30 minutos, sempre cobrindo 24h. O timestamp passa a ser
  tratado como início: emissão 10h prevê primeiro 10h–10h30 e termina às 10h do dia
  seguinte. Isso evolui o inventário anterior, que começava em `t0 + 30 min`.
- Simular liberação integral às 19h30 do próximo dia útil, com calendário conservador
  explicitamente versionado. O horário é hipótese experimental, não SLA do ONS.
  Executar sensibilidade com mais 24h de atraso. Não reconstruir chegadas parciais
  das 12h a partir de um arquivo revisado que não registra sua disponibilidade.
- Tratar corte positivo como alerta principal e ordem de limitação como segunda
  tarefa. Isso evolui a preferência inicial por comando no documento de alvos.
  Ordens sem perda continuam relevantes, sem serem confundidas com energia perdida.
- Estimar volume condicional positivo e avaliar também o produto de probabilidade
  e volume sobre todos os casos válidos. Manter MWmed/MWh, cauda e os 21 nulos.
  Antecipar causa entre ordens conhecidas, preservando REL/CNF/ENE e sem inventar PAR.
- Comparar baselines temporais/estatísticos com famílias linear regularizada e
  boosting tabular, com LightGBM como candidato. Separar fontes e compartilhar
  aprendizado entre suas entidades, com horizonte como feature.
- Usar quatro validações de quatro meses, de janeiro/2025 a abril/2026, com treino
  crescente. Reservar maio–agosto/2026 para teste após escolha congelada. Ajustes
  internos, calibração e limiares usam exclusivamente segmentos anteriores.
- Manter painel aberto principal, aquecimento de 28 dias/80% e fallback explícito.
  Não selecionar retrospectivamente entidades sobreviventes, preencher ausências
  com zero ou usar atributos posteriores à emissão.
- Exigir probabilidades de ocorrência e avaliação de calibração. Intervalo de volume
  é recomendado, condicionado à execução e validação de cobertura. Probabilidade
  estimada não significa porcentagem de certeza de que uma decisão está correta.
- Fixar antes dos resultados margens práticas: +0,02 de AP, redução de 5% no MAE
  completo sem piorar WAPE e +0,02 de macro-F1; melhorar em três de quatro rodadas,
  com proteções de estabilidade, Brier, suporte, incerteza, entidades e episódios.
  Esses números são critérios aprovados para comparação, não métricas observadas.

O teste final não escolhe o vencedor: consultar sucessivamente seus resultados
também permite sobreajuste humano. Ele pode vetar adoção, mas não deve promover um
segundo colocado e continuar sendo descrito como avaliação independente da escolha.
Da mesma forma, prever períodos históricos é um ensaio para medir utilidade futura;
a simulação precisa respeitar o que poderia ser conhecido em cada emissão.

### Alternativas consideradas

Usar também meio-dia seria tecnicamente possível em uma coleta real. O problema
retrospectivo é desconhecer quais registros chegaram em cada publicação. A integração
foi adiada pelo escopo do hackathon, com proposta de capturas versionadas futuras.
Uma piora com histórico antigo não provará que essa integração resolverá o erro.

Prever só uma vez por noite simplificaria a emissão, mas reduziria a cobertura futura
ao longo do dia. A atualização de meia em meia hora foi mantida, mesmo sem novos
dados em cada emissão. Modelos recursivos, 48 modelos distintos, fontes conjuntas,
rolling de 12 meses, meteorologia e busca extensa ficaram adiados.

O teto inicial sugerido de 500 mil exemplos de treinamento foi revisto quando o
responsável informou a máquina dedicada. Ele significava amostragem, não lote de
leitura. A decisão final é priorizar todos os exemplos elegíveis. Uma execução
pequena serve para verificar funcionamento e medir recursos; não escolhe candidatos.
Amostragem só será considerada diante de inviabilidade demonstrada e registrada.
Processamento em lotes não garante que todo estimador treine fora da memória.

O orçamento de 12h é planejamento inicial da execução inteira, não previsão de
duração ou 12h por modelo. Os 50 GiB discutidos representam referência de armazenamento
de artefatos, não RAM; são revisáveis por medição, sem apagar resultados negativos.

Esperar pela AWS para os primeiros resultados foi rejeitado: concentraria ambiente,
implementação e descoberta de desempenho no evento. Experimentos e ajuste final são
planejados localmente; AWS fica para disponibilizar a solução, sem exigir retreino.

### Implementação e validação

Nesta etapa, foram alterados exclusivamente o protocolo e esta entrada append-only.
Os documentos históricos da Etapa 1 foram preservados; o protocolo registra as
evoluções de semântica e passa a especificar o experimento. Não foram alterados
código, dependências, notebook, dados ou resultados experimentais.

A Etapa 2B será implementada e testada no Mac, com caminhos genéricos/configuráveis.
O responsável transferirá/clonará os commits para o computador dedicado, editará
os caminhos locais e realizará ali o piloto e os treinamentos. Arquivos grandes,
caches e temporários também precisam usar o SSD externo escolhido. Um clone do remoto
não transfere commits que não receberam push: o handoff exige Git bundle ou cópia/clone
local e transferência separada dos dados ignorados, conferindo hashes no destino.

Verificações de fechamento documental executadas: `git diff --check`,
`uv run --no-sync ruff check .` (sem achados) e
`uv run --no-sync ruff format --check .` (33 arquivos já formatados). Uma checagem
somente leitura confirmou links locais, ausência de whitespace residual, formato dos
hashes de pesquisa, escopo restrito aos dois documentos e que o diário anterior foi
preservado byte a byte como prefixo da nova versão. A revisão de consistência cobriu
horários, cortes internos/externos, regras de fallback e handoff entre máquinas.
Não foram executados testes de treinamento nem a suíte que reexecuta a EDA: não houve
mudança de código e o escopo autorizado era exclusivamente documental.

### Limitações e incertezas

Não existe desempenho preditivo medido nesta etapa, nem garantia de treinamento
completo em determinado tempo. O snapshot contém revisões e não possui vintages;
o calendário de publicação é hipotético. O período reservado para teste já apareceu
na EDA descritiva. As faixas de incerteza, adequação do histórico noturno e modelos
finais dependem de experimentos e têm regras explícitas na seção 11 do protocolo.

A implementação pronta no Mac não significa que a Etapa 2B experimental terminou.
Ela só se completa depois da execução real, com falhas, cobertura, resultados
negativos e limitações preservados. Publicar um modelo retreinado posteriormente
não transfere automaticamente a avaliação independente de uma versão anterior.

### Valor para o usuário e para a apresentação

O gerador poderá distinguir risco de ordem, risco de perda energética, quantidade
esperada e causa condicional. A apresentação terá uma história verificável: o que
era conhecido na previsão, contra quais regras simples a IA foi comparada e onde
ela agrega ou não valor. Não se transforma persistência descritiva em acurácia,
porcentagem de saída em certeza ou simulação de horário em garantia de produção.

### Próximos passos

Implementar o protocolo com TDD no Mac, preparar configuração e handoff entre máquinas,
executar a campanha no computador dedicado e entregar o pacote neutro para análise.
A decisão de modelos virá depois dos resultados, seguida de ajuste/avaliação final
com teste protegido. Não houve push, treinamento ou implantação nesta etapa.

## 2026-09-22 - Correção do handoff entre o Mac e o computador dedicado

### Contexto e pergunta

Após a aprovação do protocolo, o responsável esclareceu que o computador dedicado
será exclusivamente um executor das tarefas pesadas. A implementação, a análise e
qualquer commit devem permanecer no Mac.

### Decisão

O código e a configuração já commitados no Mac serão levados ao computador dedicado
por cópia local, bundle ou meio equivalente, com caminhos editáveis e sem valores
pessoais versionados. Essa máquina não receberá desenvolvimento nem criará commits.
Ao final, serão trazidos de volta somente os artefatos da execução: manifesto,
métricas, previsões, modelos, logs, diagnósticos, falhas, checksums e relatório.
Commits, correções e análise dos resultados serão feitos no Mac após a conferência
dos artefatos.

### Limitações e próximos passos

O remoto não será usado como canal implícito de transferência: sem push, alterações
locais não aparecem em um clone remoto. O procedimento de transferência do código
e dos artefatos deve ser executado pelo responsável, preservando hashes. O prompt da
Etapa 2B deverá repetir essa separação e exigir configuração genérica dos diretórios.

## 2026-09-22 - Branch dedicada para a Etapa 2

### Contexto e decisão

O responsável pediu que o protocolo e a implementação da Etapa 2 não fossem mantidos
na `main`, seguindo o padrão de branch usado na Etapa 1. Foi criada a branch local
`etapa-2-experimental`, que contém o commit documental da Etapa 2. A `main` será
preservada no commit anterior ao protocolo.

Toda implementação da 2B deverá ocorrer nessa branch. O Sol não fará merge durante
a implementação ou a execução. Depois que os artefatos retornarem do computador
dedicado, a análise da 2C decidirá se a integração é apropriada; somente então um
merge poderá ser feito na `main`.

### Limitações e próximos passos

Esta branch é local e não será enviada por push nesta etapa. O computador dedicado
receberá uma cópia do código da branch, executará apenas as tarefas pesadas e devolverá
os artefatos. Commits e análise continuam no Mac. O prompt da 2B deve exigir branch,
proibir merge antecipado e manter a `main` intacta até a decisão posterior.
