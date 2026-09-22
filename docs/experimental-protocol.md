# Protocolo experimental aprovado — Etapa 2A

Data: 22/09/2026. Referência anterior: `ce43c48fe974a5c36fba42ce1bfd3dc486f501f9`.
Estado: decisões metodológicas aprovadas em discussão com o responsável pelo projeto;
nenhum experimento preditivo executado nesta etapa. Não há modelo vencedor.

Este documento define a implementação e a execução da Etapa 2B e os critérios de análise
da Etapa 2C. `AGENTS.md` permanece obrigatório. As concretizações operacionais abaixo
fecham os detalhes necessários para reproduzir as decisões aprovadas; não representam
resultados ou novos fatos sobre o ONS. Inviabilidade demonstrada exige registro antes
de alterar o protocolo, nunca uma mudança silenciosa para melhorar métricas.

## 1. Leitura, evidências e evolução das definições

Fontes locais obrigatórias: [roadmap](roadmap.md), [arquitetura](architecture.md),
[contrato de dados](data-contract.md), [alvos](target-definition.md),
[inventário de features](feature-inventory.md), [diário](implementation-journal.md),
[pitch](pitch-notes.md), [notebook da Etapa 1](../notebooks/01_eda_fundamentos_dados.ipynb),
módulos de `src/curtamap/` e testes de `tests/`.

### 1.1 Fatos do snapshot, não resultados preditivos

- As duas bases principais somam 10.806.720 observações: 7.951.920 eólicas e
  2.854.800 fotovoltaicas. São 267 entidades, muitas delas conjuntos de usinas.
- Eólica: 01/10/2023 a 31/08/2026. Solar: 01/04/2024 a 31/08/2026.
  Os anos das bordas não constituem anos completos.
- A integrada é subconjunto das principais; não concatenar as três. O detail tem
  outra granularidade e não possui associação validada de todos os conjuntos.
- Não foram encontradas lacunas internas ou duplicidades nas principais. Isso não
  autoriza interpretar ausência futura como zero nem conhecer entradas/saídas antes
  de elas se tornarem observáveis.
- Cerca de 18% das ordens eólicas e 22% das solares têm volume calculado zero.
- Há 21 volumes eólicos indeterminados, todos em 2026. Há 42 restrições solares sem
  causa/origem reconhecida. `PAR` não aparece; `REL`, `CNF` e `ENE` aparecem.
- A comparação pública encontrou diferenças em 47 de 64 meses, 132.290 linhas com
  diferenças numéricas e 173 com diferenças de rótulo. Não existem vintages que
  permitam reconstruir a informação publicada em cada data histórica.
- Persistência, concentração e crescimento de ENE são observações da EDA, não
  desempenho preditivo. Não utilizar o painel de sobreviventes da EDA na seleção
  experimental de entidades.

Evidências: [auditoria](reports/stage1/audit.json),
[comparação pública](reports/stage1/official-comparison.json) e notebook.

### 1.2 Pesquisa temporal realizada durante a discussão

Os catálogos oficiais de [eólica](https://dados.ons.org.br/dataset/restricao_coff_eolica_usi)
e [solar](https://dados.ons.org.br/dataset/restricao_coff_fotovoltaica) informavam
atualizações diárias às 12h e 19h na consulta de 21/09/2026. Isso não informa a
disponibilidade individual de cada linha nem garante completude em cada atualização.

A [rotina RO-AO.BR.13, revisão 09](https://www.ons.org.br/MPO/Documento%20Normativo/4.%20Rotinas%20Operacionais%20-%20SM%205.13/4.3.%20Rotinas%20P%C3%B3s-Opera%C3%A7%C3%A3o/4.3.2.%20Apura%C3%A7%C3%A3o%20de%20Dados/RO-AO.BR.13_Rev.09.pdf),
vigente desde 18/06/2026, usa horário de Brasília (UTC−3) nos registros (§4.1).
Na apuração diária (§6.1.1), exclui fins de semana/feriados, prevê disponibilização
do dia anterior até 15h e flexibiliza horários às segundas e após feriados, dentro
do dia. Há consistência pelos agentes e revisões posteriores. Essa regra de apuração
não é uma garantia de entrega do arquivo público às 19h, nem prova de aplicação
inalterada desde 2023.

A convenção de início do patamar tem evidência adicional nos dados atuais
[intra-semihora eólicos](https://dados.ons.org.br/dataset/coff_eolica_usi_intrasemihora)
e [solares](https://dados.ons.org.br/dataset/coff_fotovoltaica_intrasemihora).
Uma inspeção somente leitura dos arquivos de agosto/2026 encontrou:

| Fonte | Linhas examinadas | SHA-256 do arquivo consultado |
|---|---:|---|
| Eólica | 215.685 | `c7570ea8ed91a365e77df846ee7cdded7079abe943e98fbac82b735109d76721` |
| Solar | 74.886 | `ee07700dd6a0ca4d4144255f7acf73c0d37b054cb1623270f9a3c1a6d908ebd8` |

Endereços:

- [Parquet eólico](https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_eolica_intrasemihora/COFF_USI_EOLICAS_INTRASEMIHORA_2026_08.parquet).
- [Parquet solar](https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_fotovoltaica_intrasemihora/COFF_USI_FOTOVOLTAICA_INTRASEMIHORA_2026_08.parquet).

Em todas as linhas, convertendo horas/minutos para inteiros antes da aritmética:
`minuto(din_instante) <= minuto(hor_inicial) <= minuto(hor_final) < minuto(din_instante) + 30`.
Aqui `minuto` é o número de minutos desde 00h. Exemplos eólicos: patamar 00h contém
00h00–00h29; patamar 23h30 contém 23h30–23h59. A consulta usou arquivos em memória,
não alterou o snapshot e não acrescentou esses campos às features.

**Interpretação e decisão:** tratar o timestamp como início da janela e usar
`America/Sao_Paulo` (UTC−3 nos períodos analisados). A evidência vem da publicação
atual; a aplicação ao snapshot histórico é uma convenção documentada, não uma
verificação de todas as versões históricas.

### 1.3 Evoluções que prevalecem para este experimento

Este protocolo especifica a Etapa 2 sem reescrever os registros da Etapa 1:

1. A primeira janela passa a iniciar em `t0`, em vez de `t0 + 30 min` no inventário.
2. `corte_positivo` torna-se o alerta principal; `restricao_registrada` continua
   como tarefa secundária explícita. A definição inicial priorizava o comando.
3. O cenário de publicação usa calendário e lote noturno; não presume latência zero
   para os baselines nem uma latência oficial fixa de 24h.
4. Treinamento local no computador dedicado é o caminho principal. AWS é uma etapa
   posterior de disponibilização, sem dependência para obter resultados preditivos.
5. Não existe teto metodológico de 500 mil exemplos: esse número foi discutido para
   o Mac de 8 GiB e substituído pela prioridade de treinamento completo elegível.

## 2. Contrato operacional

### 2.1 Emissão e alvos futuros

- `t0` está na grade de 30 minutos, em horário de Brasília. Armazenar fuso e offsets
  explicitamente; não reinterpretar os timestamps ingênuos como UTC.
- Para `h` inteiro entre 1 e 48: início `tau = t0 + (h - 1) × 30 min`; alvo referente
  ao intervalo semiaberto `[tau, tau + 30 min)`. O horizonte termina em `t0 + 24h`.
- Exemplo: emissão 10h, primeira janela 10h–10h30, última 9h30–10h do dia seguinte.
- Unidade única: `fonte + id_ons + t0 + h`. Preservar também `tau`, versão do modelo,
  cenário, corte de dados, cobertura, idade do histórico e caminho de fallback.
- Emissões a cada 30 minutos não implicam novas observações ou novo treinamento
  a cada emissão. A janela futura avança; features de calendário e idade mudam.
- Não conhecer dados do próprio intervalo iniciado em `t0`. O limite de leitura é
  a disponibilidade simulada até `t0`, além de o intervalo observado já ter terminado.
- A implementação deve informar o instante real em que a previsão ficou pronta.
  A inferência real precisa ser medida; processamento que entrega depois do início
  do intervalo não pode ser narrado como antecipação integral desse intervalo.

### 2.2 Modelos globais por fonte

Um modelo por tarefa e fonte, compartilhado entre entidades, com horizonte como
feature. Não são 267 modelos individuais nem 48 modelos por horizonte. Eólica e
solar são separadas inicialmente. As 48 saídas são diretas: nenhuma previsão vira
entrada de outro horizonte. Modelos conjuntos, por horizonte e recursivos ficam
adiados, evitando uma multiplicação de experimentos sem hipótese prioritária.

## 3. Disponibilidade simulada, calendário e revisões

### 3.1 Cenário principal `noturno_dia_util`

Para uma observação cujo intervalo começa no dia civil `d`, definir `B(d)` como
o primeiro dia útil estritamente posterior a `d` e a liberação simulada como
`A(d) = B(d) às 19h30`. Toda a informação da linha herda essa liberação.
Ela só pode alimentar uma previsão ou treinamento quando `A(d) <= instante de corte`.
Nunca derivar disponibilidade pelo `mtime` do arquivo atual.

Calendário conservador: sábado/domingo, feriados nacionais, estaduais do Rio de
Janeiro, municipais da cidade do Rio de Janeiro e pontos facultativos federais.
Para esta simulação, dias parcialmente facultativos contam como dias inteiros
sem liberação. A implementação deve compilar a lista de datas de 2023–2026 a partir
de calendários/atos oficiais de cada ano, com URL, data da consulta, motivo e hash
do manifesto. Deduplicar coincidências. Congelar o calendário antes de qualquer
métrica; ele não afirma reproduzir a escala de trabalho real do ONS.

Exemplo sem feriado: sexta após 19h30 contém até quinta; sábado/domingo conservam
quinta; segunda antes de 19h30 ainda conserva quinta; segunda às 19h30 libera sexta,
sábado e domingo. Não supor publicação parcial intermediária.

As 19h30 incluem uma margem convencional após o horário anunciado. São hipótese,
inclusive na segunda e após feriados, não prazo oficial garantido. No produto real,
a coleta deverá confirmar recebimento, conteúdo, cobertura e versão; não basta o
relógio passar das 19h30. A integração das 12h fica fora do experimento inicial.

### 3.2 Sensibilidade obrigatória `noturno_mais_24h`

Definir `A_atrasado(d) = A(d) + 24h corridas`, sem novo arredondamento para dia útil.
Recalcular features, baselines, cadastro conhecido, elegibilidade e idade do histórico.
Manter congelados os modelos, pré-processadores, calibradores e limiares aprendidos
no cenário principal; não retreinar ou reajustar ao ver o cenário atrasado.

Reportar cada cenário em sua população conhecida e, adicionalmente, a comparação
pareada na interseção das emissões elegíveis, com a cobertura perdida fora dela.
Esse teste mede degradação com informação mais antiga, não ganho com dados das 12h.
Uma sensibilidade adicional de `A(d) + 72h` é opcional.

### 3.3 Snapshot revisado e limites de alegação

Congelar os dois arquivos principais originais por SHA-256. As publicações atuais
da validação da Etapa 1 não substituem o snapshot nem se misturam a ele no treino.
Revisões posteriores podem afetar features históricas, cadastro e alvos. A máscara
de disponibilidade controla o cenário, mas não remove informação retrospectiva
embutida nas revisões. Portanto: **backtest retrospectivo de snapshot revisado sob
disponibilidade hipotética**, e não reprodução comprovada da operação histórica.

Dados parciais das 12h poderiam ser úteis em produção. Para avaliá-los historicamente,
seriam necessárias capturas com recebimento, versão e cobertura conhecidos. O problema
é a ausência dessa evidência, não uma impossibilidade técnica de ingerir linhas parciais.
Desempenho insuficiente à noite não prova que incluir meio-dia resolverá a limitação.

## 4. População, histórico e observações ausentes

- Universo operacional: IDs cujo primeiro registro já foi liberado no cenário.
  Ler atributos pela última informação conhecida, nunca pelo cadastro final completo.
- `id_ons` novo é nova entidade até existir uma associação independente e temporalmente
  verificável. Não unir por nome, nem aplicar retrospectivamente a renomeação observada
  na comparação oficial. Preservar sempre a fonte na identidade.
- Definir `c(t0)` como o término do último dia integralmente liberado pelo calendário
  do cenário, limitado ao intervalo histórico existente. É corte comum de referência,
  não o timestamp de um registro futuro usado para preencher faltas.
- Elegibilidade para a previsão aprendida: ao menos 28 dias de extensão histórica
  observável até `c(t0)`, com pelo menos 80% das 1.344 posições de meia hora em
  `[c(t0) - 28 dias, c(t0))` presentes. Resultados indeterminados mantêm suas máscaras
  específicas por tarefa. Cobertura de linhas não significa validade de todos os campos.
- Entidades conhecidas sem essa cobertura usam o fallback histórico regional/fonte.
  Esse comportamento também integra as métricas do pipeline no painel aberto.
- Não criar previsões anteriores ao primeiro conhecimento da entidade. Não usar sua
  última ocorrência no arquivo completo como data de saída previamente conhecida.
- Uma entidade antes conhecida continua no universo mesmo sem novas linhas; mostrar
  histórico envelhecido e fallback. Não declarar encerramento de operação por silêncio.
- Falta de linha, alvo indeterminado e observação válida com valor zero são três estados
  diferentes. Não interpolar alvos, preencher janelas com zero ou avançar valores através
  de lacunas sem identificar explicitamente a regra de baseline.
- Sem verdade observada, preservar a previsão mas não pontuar a tarefa. Reportar por
  período/fonte/horizonte a população prevista, avaliável, não observada e inválida.

Painel aberto é principal. Painel fixo é diagnóstico: congelar IDs elegíveis em
01/01/2025 00h segundo o cenário principal, usando só o passado então conhecido.
Não exigir presença futura. Novos IDs e histórico insuficiente têm recortes próprios.
O painel fixo da EDA, condicionado a cobertura futura, não é reutilizado.

## 5. Tarefas e saídas

### 5.1 Ocorrência principal e secundária

- Principal: `corte_positivo`, probabilidade de volume analítico maior que zero.
- Secundária obrigatória: `restricao_registrada`, probabilidade de ordem de limitação.
- Manter as fórmulas de `curtamap.targets`: não redefinir ocorrência por um limiar
  mínimo de MW para facilitar o aprendizado. Volume indeterminado implica ocorrência
  positiva indeterminada, mas não invalida automaticamente o alvo de comando ou causa.
- Ordens com zero são positivas para comando e negativas para corte positivo.
- Treinar e avaliar classificadores separados. Reportar eventual incoerência
  `P(corte_positivo) > P(restricao_registrada)`. Não apresentar suas probabilidades
  como partição conjunta nem corrigir silenciosamente com truncamento posterior.
  Uma camada probabilística conjunta é evolução, caso essa incoerência seja material.

### 5.2 Volume

Regressor aprende `E[volume_mwmed | corte_positivo]` nos cortes positivos válidos.
Saída deve ser finita e não negativa. Pipeline probabilístico:
`volume_esperado = P(corte_positivo) × volume_condicional`.
Essa saída não depende do limiar de alerta; evitar zerar a energia só porque a
probabilidade ficou abaixo do limiar escolhido para a classificação.

Converter a energia de cada janela por `MWh = MWmed × 0,5`. Somar as 48 energias
previstas de uma emissão produz sua estimativa de 24h. Não somar todas as emissões
sobrepostas como se fossem perdas físicas distintas.

Avaliar separadamente regressor sobre cortes positivos, pipeline sobre todos os alvos
de volume válidos e volumes diários. Não avaliar só os cortes corretamente detectados.
Os 21 casos indeterminados ficam fora da perda de volume e do alvo positivo, com
contagem e cobertura explícitas; comando/causa continuam quando válidos. Não usar a
variante bruta que admite negativos como alvo alternativo de seleção.

Preservar a cauda válida; sem winsorização, corte de percentil ou exclusão de episódios
grandes por conveniência. Gamma com ligação logarítmica trabalha diretamente com o
volume positivo e estima média condicional. Não substituir por regressão de `log1p`
e exponenciação ingênua, que muda a quantidade estimada. Média esperada e mediana que
minimiza erro absoluto não são a mesma coisa; a avaliação mede esse trade-off.

### 5.3 Causa

Previsão emitida em `t0`, sem acesso à ocorrência ou causa real futura. Treinar apenas
com restrições de causa reconhecida (`REL`, `CNF`, `ENE`), incluindo volume zero.
O filtro de população usa o resultado para definir a tarefa condicional, nunca como
feature. Gerar probabilidades condicionais: "se houver ordem, qual causa é provável?".
Não confundir isso com a probabilidade de a ordem ocorrer.

Sem causa conhecida: excluir da perda de causa, preservar cobertura e os outros alvos.
Não aprender `DESCONHECIDA` como causa física; não criar exemplos sintéticos de `PAR`.
Não fundir `REL` com outras classes. Se faltar classe no treino, manter o conjunto de
saídas documentado, marcar classe não aprendida e reportar a falha de cobertura.

Avaliação principal sobre todas as restrições de causa conhecida; diagnóstico sobre
o subconjunto com corte positivo e sobre restrições corretamente alertadas. Este último
nunca substitui a avaliação principal. Para uma visão completa do alerta de comando,
reportar também acerto conjunto de detectar a ordem e acertar a causa, contando ordens
perdidas e falsos alertas. O classificador de causa não recebe a verdade futura da ordem.
As probabilidades de causa não são automaticamente consideradas calibradas.

Origem `LOC`/`SIS` é extensão opcional com população e disponibilidade análogas. Não
misturar causa com origem nem atribuir causalidade às associações aprendidas.

## 6. Cortes temporais e ajustes internos

### 6.1 Rodadas externas

| Rodada | Início inclusivo da validação | Fim exclusivo | Histórico inicial permitido |
|---|---|---|---|
| V1 | 01/01/2025 00h | 01/05/2025 00h | Início de cada fonte, sujeito ao as-of |
| V2 | 01/05/2025 00h | 01/09/2025 00h | Idem, expanding |
| V3 | 01/09/2025 00h | 01/01/2026 00h | Idem, expanding |
| V4 | 01/01/2026 00h | 01/05/2026 00h | Idem, expanding |
| Teste reservado | 01/05/2026 00h | 01/09/2026 00h | Somente após decisão congelada |

Em cada bloco, emitir em todos os `t0` de meia hora cuja faixa completa de 24h esteja
contida nele: `inicio <= t0` e `t0 + 24h <= fim`. Isso remove as últimas 47 emissões
de cada bloco, preservando 48 horizontes comparáveis por emissão. Não imputar as bordas.
Nunca usar split aleatório. Previsões repetidas do mesmo alvo em horizontes diferentes
são válidas unidades operacionais, mas são estatisticamente dependentes.

### 6.2 Treino, escolha limitada de parâmetros e calibração

Para um bloco que começa em `S`, calcular `C` como o término do último dia cuja
liberação principal ocorreu até `S`. Definir fronteiras internas em dias civis:
`U = C - 56 dias`, `K = C - 28 dias`.

1. Ajuste inicial: exemplos históricos com todas as janelas anteriores a `U` e cujos
   alvos já estavam liberados em `U`. Features sempre reconstruídas no respectivo `t0`.
2. Ajuste de hiperparâmetros: emissões com 48 janelas inteiramente em `[U, K)` e alvos
   liberados até `K`. Avaliar as no máximo duas configurações de cada família/tarefa.
   A família não é eliminada nessa etapa; escolher uma configuração dentro de cada uma.
3. Reajuste daquela configuração: histórico anterior a `K`, com alvos liberados em `K`.
   Não incluir exemplos de calibração ou alvos cujo intervalo cruza a fronteira.
4. Calibração/limiar: emissões inteiramente em `[K, C)` com alvos liberados até `S`.
   O modelo usado para produzi-las é o do passo 3. Não reajustar depois com esses
   rótulos e reaproveitar como se o calibrador ainda fosse independente desse ajuste.
5. Validação externa: congelar modelo, configuração, codificações, calibrador e limiar
   durante os quatro meses. Atualizar somente as features históricas permitidas e
   as estatísticas online dos baselines conforme o cenário.

Para todo conjunto de ajuste, aplicar disponibilidade do rótulo no instante de ajuste,
não apenas `tau < S`. Isso deixa uma margem variável ao redor dos cortes; um embargo
fixo de 24h não substitui a regra de publicação. Registrar limites efetivos, exemplos
excluídos por fronteira/latência, aquecimento e cobertura dos segmentos internos.

O início do histórico de cada fonte é preservado; exemplos sem aquecimento de 28 dias
não alimentam os modelos aprendidos. São possíveis dados de histórico para features
e baselines. Pré-processamento aprende somente no conjunto de ajuste correspondente.

### 6.3 Proteção do teste e treino posterior

A Etapa 2B implementa o caminho do teste e seus contratos com dados sintéticos, mas
não executa previsões pontuadas, seleção, calibração ou relatórios preditivos no teste
real. Uma opção explícita, separada do comando padrão, deve exigir a referência à
decisão congelada para liberar sua execução posterior.

A Etapa 2C escolhe usando V1–V4 e congela a receita de ajuste, tarefa, fonte, features,
configurações, calibração, limiares e combinações de modelos antes de abrir o teste.
O ajuste final local pode reaproveitar os períodos antigos de validação no treino,
mantendo a separação interna e a disponibilidade anteriores a 01/05/2026.

O teste confirma ou veta adoção; não é uma nova rodada para escolher um concorrente.
Se houver alteração orientada pelos resultados do teste, esse período passa a integrar
o desenvolvimento e deixa de sustentar uma alegação independente para a nova versão.
Um ajuste posterior para operação pode incorporar dados mais recentes, mas é outra
versão, cuja avaliação independente exige observações posteriores apropriadas.

O período reservado já foi explorado descritivamente na Etapa 1. Descrever como
reservado para desempenho preditivo, não como nunca examinado.

## 7. Baselines implementáveis

Todos usam exclusivamente dados liberados no cenário até `t0`. Nunca usar o resultado
real futuro para decidir qual regra ou fallback aplicar. Conservar `baseline_id`,
timestamp efetivamente usado, idade, motivo do fallback e taxa de aplicação nativa.

### 7.1 Estatísticas históricas e fallback comum

Histórico recente: `[c(t0) - 28 dias, c(t0))`, com observações válidas por tarefa.
Estimar separadamente probabilidade de comando, probabilidade de corte positivo,
média de volume positivo, média de volume incluindo zeros e distribuição de causas
entre ordens reconhecidas. Para volume esperado estatístico, usar
`frequência de corte × média positiva`; sem positivos em histórico de volume válido,
a expectativa é zero, mas a média condicional deve ser marcada não estimável.

Hierarquia para cada estatística: entidade no mesmo horário da janela prevista,
entidade em todos os horários, mesma fonte/UF no mesmo horário, mesma fonte no mesmo
horário e mesma fonte em todos os horários. Exigir sete observações válidas no grupo
para usar a estimativa; média positiva exige sete positivos, distribuição de causas
exige sete ordens conhecidas. Isso é convenção operacional, não garantia de precisão.

Para entidades com menos de 28 dias/80% de cobertura, iniciar diretamente em fonte/UF.
Se não houver nenhum grupo utilizável, marcar ausência de evidência: probabilidade
binária 0,5, distribuição de causa uniforme nas três classes e volume esperado zero
como saída técnica de fallback, explicitamente sem informação. Não ocultar esses casos
da cobertura ou apresentá-los como previsão energética confiável. Não acessar o futuro
para melhorar um fallback; na população avaliada de 2025 em diante, registrar se isso
de fato acontecer, sem presumir antecipadamente contagem zero.

### 7.2 Regras por tarefa e horizonte

| Baseline | Ocorrência | Volume completo | Causa condicional |
|---|---|---|---|
| Último valor | Último alvo válido disponível (0/1), repetido nos 48 horizontes | Último volume válido, repetido nos 48 horizontes | Última causa reconhecida em ordem dos últimos 28 dias; senão majoritária |
| Mesmo horário do dia anterior | Alvo em `tau - 24h`, se disponível | Volume nesse timestamp, se disponível | Causa nesse timestamp se houver ordem reconhecida disponível |
| Mesmo horário mais recente disponível | Alvo no horário de `tau` no dia anterior disponível mais recente, até 28 dias | Volume na mesma regra | Última ordem reconhecida nesse horário, até 28 dias |
| Frequência/média histórica | Frequência recente com fallback comum | Frequência positiva × média positiva do grupo | Distribuição histórica; classe majoritária para decisão |

Nos dois baselines de mesmo horário, consultar cada horizonte separadamente.
Se a posição requerida faltar, for inválida ou ainda não estiver liberada, usar o
fallback estatístico, identificando a substituição. Não deslocar silenciosamente o
baseline de ontem para anteontem: essa é outra regra, com outro nome.

Para a avaliação de volume condicional, incluir a média histórica positiva e a última
perda positiva disponível nos últimos 28 dias, com fallback de média positiva. Os
baselines diretos de volume completo permanecem separados desses diagnósticos.
Não substituir um baseline de volume por seu acerto apenas entre eventos detectados.

A classe majoritária desempata por ordem fixa `CNF`, `ENE`, `REL`. Frequências empíricas
podem fornecer probabilidades; último valor binário produz 0/1 e não é calibrado por
construção. Aplicar o mesmo procedimento interno de limiar aos baselines probabilísticos.
As comparações devem mostrar tanto o baseline com fallback quanto seu subconjunto
de disponibilidade nativa, sem escolher retrospectivamente apenas o subconjunto fácil.

## 8. Features iniciais e transformações

Lista permitida inicial, igual entre famílias antes da codificação específica:

| Família | Concretização | Controle temporal |
|---|---|---|
| Calendário | Hora/posição de meia hora, dia da semana, mês, dia do ano; representações cíclicas; horizonte e calendário de `t0`/`tau` | Conhecidos na emissão; calendário versionado |
| Cadastro | Fonte, ID, UF, subsistema e indicação cadastral conjunto/individual quando conhecida | Última informação liberada, categorias novas explícitas |
| Histórico próprio | Última ocorrência de cada alvo, volume e causa; valores em 30 min, 1h, 24h, 48h e 7 dias antes do último registro conhecido | Lookup exato; ausências mantidas, não interpoladas |
| Mesmo horário | Alvos históricos de `tau - 1, 2, 3, 7 dias`, somente quando disponíveis | Máscara por timestamp e liberação; não é meteorologia futura |
| Estatísticas móveis | Frequências, médias, desvio e máximo de volume; composição de causa em 24h, 7d e 28d | Janelas terminam em `c(t0)`; contagens/denominadores explícitos |
| Agregados | Frequências de ocorrência e média de volume por fonte/UF e fonte/subsistema | Só observações liberadas; registrar entidades e observações contribuintes |
| Episódio observado | Comprimento da sequência positiva conhecida até o último registro; tempo desde última causa/corte conhecido | Quebrar em zero, lacuna ou alvo desconhecido; não prolongar até `t0` |
| Cobertura/idade | Fração de posições presentes/válidas, idade do último registro e da última ordem | Apenas ausências detectáveis até a emissão |

Agregados incluem todas as entidades conhecidas da região, inclusive a própria entidade;
isso não usa futuro, mas deve ser uniforme entre modelos. Nenhum agregado depende do
conjunto de entidades que sobreviverá ao final do período. Para médias, usar contagens
válidas; sem denominador, retornar ausente. Não chamar média de subconjunto de total
regional completo. Mudança de regime será tratada pelo histórico recente e diagnósticos,
sem criar flags de mudanças descobertas ao observar validação ou teste.

Campos verificados brutos de geração, referência, limite e disponibilidade ficam fora
da lista inicial: os históricos dos alvos já representam o primeiro teste informativo.
Disponibilidade extrema exige investigação própria antes de inclusão. Nome, descrição
livre, arquivo de origem e flags pós-evento da janela futura não são features.
Detail, referências finais de liquidação, novos campos públicos e meteorologia futura
ficam adiados. Uma integração meteorológica exigiria emissão/recebimento verificável;
vento/irradiância verificados e reanálises não são substitutos operacionais D+1.

Valores faltantes de feature: manter indicador. Para modelos lineares, mediana aprendida
no treino numérico e categoria ausente/desconhecida; padronização numérica ajustada só
no treino. Para árvores, usar o tratamento nativo de ausências/categorias quando
compatível, preservando códigos e dicionários treinados. Não imputar alvos. Sem target
encoding no experimento inicial. Nunca ajustar transformações sobre a base completa.

## 9. Famílias, busca limitada e calibração

### 9.1 Candidatos mínimos

| Família | Ocorrência principal/secundária | Volume positivo | Causa | Hipótese/custo |
|---|---|---|---|---|
| Linear regularizada | Regressão logística L2 | GLM Gamma, ligação log | Logística multinomial L2 | Relações simples e efeitos de entidade; menor complexidade, possível subajuste |
| Boosting tabular | LightGBM binário | LightGBM Gamma | LightGBM multiclasse | Não linearidade/interações; maior risco de sobreajuste e custo de ajuste |

Categorias lineares: one-hot esparso com categorias do treino e tratamento de novos IDs.
Não materializar uma matriz densa gigante. Árvores: categorias nativas e profundidade
limitada. Sem reamostragem de classes ou pesos inversos de frequência inicialmente;
o desbalanceamento é reportado, as probabilidades usam prevalência natural e a causa
é julgada por macro-F1. Não inferir confiabilidade por existirem saídas probabilísticas.

Concretização da busca máxima, congelada antes de medir validação externa:

- Logísticas: `C` em `{0.1, 1.0}`, L2; tolerância `1e-4`, até 1.000 iterações.
- Gamma linear: penalidade L2 `alpha` em `{0.0001, 0.01}`, tolerância `1e-4`,
  até 1.000 iterações. Registrar convenção da biblioteca e convergência.
- LightGBM: duas configurações, `num_leaves` 15 ou 31 e `max_depth` 4 ou 5,
  respectivamente; `learning_rate=0.05`, `min_child_samples=100`, `reg_lambda=1`,
  `max_bin=63`, sem subamostragem de linhas/colunas; até 500 árvores.
  Early stopping de 50 iterações apenas no trecho interno de ajustes. Reajuste posterior
  usa o número de árvores escolhido ali, sem consultar calibração ou validação externa.
- Não tratar não convergência como resultado válido sem diagnóstico. Correções de
  solver/tolerância exigem registro técnico e reexecução comparável, sem nova busca
  orientada pelos resultados externos. Parâmetros efetivos e versões sempre salvos.

Escolha interna: AP para cada ocorrência, MAE condicional para volume e macro-F1 para
causa. Empate: menor complexidade/regularização mais forte. Avaliação externa de volume
continua sendo do pipeline completo. Preservar as duas famílias mesmo que uma pareça
melhor no trecho interno; esse trecho não escolhe a família vencedora.

Para cada fonte/rodada, são duas famílias × quatro tarefas aprendidas (duas ocorrências,
volume e causa), com até duas configurações por ajuste interno. O reajuste e a calibração
são passos adicionais, não novas famílias. Não prometer duração por contagem de modelos.

### 9.2 Probabilidades e limiares

Calibração binária por fonte, alvo e família, compartilhada entre horizontes: ajuste
sigmoide sobre scores fora do ajuste do modelo, no trecho interno de calibração.
Preservar probabilidades brutas e calibradas. Se esse trecho não contiver as duas
classes, não fabricar um calibrador: usar saída bruta, marcar falha e impedir alegação
de calibração demonstrada. Reportar suporte e estabilidade mesmo quando ambas existem.

Limiar: maximizar `F2 = 5 × precisão × recall / (4 × precisão + recall)` nas probabilidades
do trecho interno de calibração, por fonte e alvo; empate prefere o maior limiar para
reduzir alertas redundantes. Não criar limiares por entidade ou por horizonte.
Sem positivos/sem suporte para escolher: limiar técnico 0,5, identificado como fallback.
Calibrador e limiar são ajustes internos; sua qualidade será medida em V1–V4.

A causa usa argmax e desempate fixo. Não exigir probabilidades calibradas de causa para
concluir a comparação mínima, nem apresentá-las como certeza demonstrada.

### 9.3 Combinações para o volume e extensões

Além das duas combinações de ocorrência positiva e regressor da mesma família,
reportar as duas combinações cruzadas. São quatro produtos de previsões já geradas,
sem novos treinamentos. Cada combinação tem identidade e passa pelos mesmos critérios;
nenhuma é escolhida automaticamente pela média. Baselines diretos de volume são
comparadores obrigatórios. A classificação secundária de comando não substitui a
probabilidade positiva nesse produto.

Extensão recomendada de intervalo de volume completo: faixa central nominal de 80%,
usando quantis 10%/90% do residual `volume_real - volume_esperado` no trecho interno de
calibração, por fonte e faixa de horizonte. Somar os quantis à estimativa e limitar
extremos inferiores a zero. Com menos de 100 exemplos válidos na faixa, usar os quantis
da fonte; sem suporte, não emitir intervalo. Reportar cobertura e largura externas,
inclusive em cortes positivos e altos volumes. Não atribuir garantia de cobertura
sob dependência temporal ou mudança de regime, nem alterar o intervalo após ver V1–V4.

## 10. Métricas, agregações e diagnósticos

### 10.1 Definições

- Ocorrência: AP (`average precision`, integral em degraus da precisão por incremento
  de recall), chamada de PR-AUC no relatório com essa definição explícita; não misturar
  com integração trapezoidal. Secundárias: recall, precisão, F2, matriz de confusão,
  Brier médio e confiabilidade em dez faixas fixas de probabilidade de largura 0,1.
  Reportar prevalência, suporte, probabilidades brutas/calibradas e limiar utilizado.
- Volume: MAE em MWmed sobre todos os volumes válidos é principal; WAPE é
  `sum(abs(y - yhat)) / sum(y)`. Reportar também MAE/WAPE condicional, viés médio e
  cobertura. Denominador de WAPE zero implica não aplicável, nunca zero artificial.
- Causa: macro-F1 de `REL`, `CNF`, `ENE`, recall/F1 por classe, confusão e suporte.
  Classe sem verdade positiva no recorte tem F1 não estimável; reportar eventual macro
  entre classes presentes apenas como diagnóstico. Macro principal de três classes
  fica não aplicável nesse recorte. Classe presente mas nunca prevista tem F1 zero.
- Recorte binário sem ambas as classes: marcar AP sem capacidade de comparação nesse
  recorte, preservando suporte, Brier e contagens cabíveis. Não converter ausência de
  suporte em excelência. Precisão sem alertas é não aplicável; recall com positivos
  e nenhum alerta é zero. Para otimização F2, nenhum acerto recebe F2 zero.

### 10.2 Agregações obrigatórias

1. Cada fonte separada; cada rodada separada; cada um dos 48 horizontes e faixas
   `h=1..12` (0–6h), `13..24` (6–12h), `25..48` (12–24h).
2. Métrica global de cada rodada usa todas as unidades avaliáveis daquele recorte.
   Resumo principal é a média aritmética das quatro métricas por rodada, com desvio,
   mínimo/máximo e diferenças pareadas. Métrica calculada após juntar rodadas é secundária.
3. Cada entidade com peso igual em uma visão adicional, com suporte/exclusões definidos
   para métricas não aplicáveis. WAPE agregado e média de WAPEs por entidade são coisas
   diferentes: informar ambos sem trocar seus nomes. Sem ponderação por capacidade
   instalada não disponível historicamente.
4. Painel aberto, painel fixo, histórico insuficiente e IDs novos em relação ao treino;
   cenário principal, atrasado e sua interseção comparável.
5. Dias úteis, fins de semana/feriados, idade do histórico e períodos após liberação.
   Faixas de idade: até 48h, acima de 48 até 96h e acima de 96h.
6. Energia diária: usar somente a emissão canônica às 00h, somando suas 48 janelas,
   e pontuar dias com verdade completa. Não somar emissões sobrepostas. Demais emissões
   podem ter erros de energia de 24h, identificados por `t0`.

### 10.3 Episódios, cauda e incerteza

Episódio observado é sequência de cortes positivos consecutivos da mesma entidade.
Zero encerra; ausência/indeterminação quebra e censura a fronteira. Início observável
exige zero conhecido imediatamente antes; término exige zero imediatamente depois.
Não usar comprimento final, causa final ou volume total de episódio como feature.

Medir recall nas primeiras janelas positivas dos episódios por horizonte, e persistência
indevida de alerta na primeira janela zero após seu fim. Não inferir duração de uma
sequência de forecasts feita com informações posteriores como se fosse previsão única.
Reportar métricas por duração/volume observado apenas como diagnóstico pós-evento.

Para cauda, definir o percentil 99 de volume positivo no treino de cada rodada e medir
separadamente acima/abaixo, sem excluir nenhum do principal. Reportar contribuição das
dez entidades e dos dez episódios de maior erro para o erro total, com identificação
descritiva posterior, nunca seleção de população para melhorar a pontuação.

Para evitar falsa precisão por horizontes sobrepostos, formar blocos de sete dias
consecutivos dentro de cada rodada; manter juntas entidades e horizontes. Calcular
diferenças semanais pareadas entre candidato e baseline e bootstrap desses blocos
(1.000 reamostragens, semente 42), estratificado por rodada, com igual peso entre rodadas.
O intervalo de 95% refere-se à diferença média semanal: é diagnóstico distinto da
média de AP/MAE/macro-F1 por rodada. Preservar suporte e semanas sem métrica estimável.
Dependência superior a sete dias limita essa incerteza; não alegar independência dos
milhões de linhas. Semanas parciais e número de blocos devem ficar explícitos.

## 11. Critérios de comparação e decisão posterior

### 11.1 Comparador e melhoria material

Por tarefa e fonte, escolher o baseline de melhor média primária em V1–V4, mantendo
uma única regra de baseline nas quatro rodadas. Para volume, a métrica é do pipeline
completo. Não escolher um baseline diferente para cada rodada depois de ver o resultado.
Reportar todos; o melhor é o piso de comparação, não um resultado ignorável.

| Tarefa | Melhoria média mínima sobre o melhor baseline |
|---|---|
| Ocorrência, principal e secundária separadamente | Ganho absoluto de AP de pelo menos 0,02 |
| Volume completo | Redução relativa de MAE de pelo menos 5%, sem aumento do WAPE médio estimável |
| Causa | Ganho absoluto de macro-F1 de pelo menos 0,02 |

Exigir melhoria estrita em pelo menos três das quatro rodadas. Se MAE do baseline for
zero, não existe redução relativa possível; o candidato não prova melhoria material
nesse critério. Métrica principal ausente em alguma rodada implica evidência insuficiente
para aprovação automática, sem reduzir retrospectivamente o número de rodadas.

### 11.2 Proteções contra médias enganosas

Mesmo passando a margem média, impedir adoção automática quando:

- AP ou macro-F1 piora mais de 0,02 em qualquer rodada contra o comparador;
- MAE de volume piora mais de 10% relativamente em qualquer rodada;
- Brier médio de ocorrência piora mais de 0,01 absolutamente;
- há vazamento, divergência de população, falha de convergência não resolvida, métricas
  omitidas, previsões inválidas ou falha de reprodução;
- a incerteza da diferença semanal não sustenta benefício (intervalo contendo zero),
  classes sem suporte ou prejuízos concentrados impedem conclusão segura.

Essas condições produzem os estados `inelegivel`, `inconclusivo` ou `requer_analise`,
com o motivo. A Etapa 2B não transforma isso em escolha definitiva de produto.
Ganhos dentro da incerteza não justificam complexidade adicional: preferir a solução
mais simples e barata quando não houver diferença material demonstrada.

Os recortes de fonte/entidade/horizonte/episódio são obrigatórios para a Etapa 2C.
Se um prejuízo importante aparecer neles sem limiar numérico pré-fixado, a decisão
conservadora é não aprovar automaticamente o candidato e registrar a evidência;
não inventar um novo limiar para fazê-lo passar. Esses limites são critérios práticos
do hackathon, não um SLA operacional ou uma demonstração de benefício financeiro.

### 11.3 O que pode ser decidido após os experimentos

| Decisão dependente | Evidência necessária | Regra da análise posterior |
|---|---|---|
| Família/configuração por tarefa e fonte | Métricas V1–V4, incerteza, custo e diagnósticos | Aplicar margens e proteções; baseline é opção válida; não decidir pela média isolada |
| Combinação de ocorrência e volume | Quatro pipelines e baselines com previsões pareadas | Escolher pipeline completo; um bom regressor condicional não basta |
| Suficiência do histórico noturno para a demonstração | Comparação principal e atraso, inícios/fins de episódios, calibração e cobertura | Só alegar utilidade retrospectiva no domínio sustentado; produção exige acompanhamento prospectivo |
| Prioridade de coleta às 12h | Degradação por idade e falhas em transições | Recomendar coleta versionada futura; não concluir que a atualização parcial resolverá o erro |
| Faixa de volume confiável para exposição | Cobertura/largura externas e suporte por faixa | Expor somente com qualificação empírica; sem resultado, mostrar estimativa pontual e limitação |
| Causa rara ou não aprendida | Suporte temporal, recall/F1 e erros conjuntos | Abster-se de recomendação específica onde falta evidência; não inventar PAR |
| Adoção após teste | Receita congelada e teste reservado | Confirmar/vetar; não promover segundo colocado usando o mesmo teste como seleção |

Nada autoriza abrir meteorologia, novos algoritmos ou o teste final para resgatar uma
média insatisfatória. Mudança metodológica necessária cria nova versão do protocolo.

## 12. Orçamento, máquina e armazenamento

### 12.1 Ambiente principal aprovado

Computador dedicado informado pelo responsável: Ryzen 5 5600X, 32 GB DDR4 a
3.200 MT/s, RTX 2060 de 6 GB e SSD com aproximadamente 580 GB livres. O diretório
habitual do repositório está em outra unidade com cerca de 44 GB livres. Essas
especificações foram informadas pelo usuário; sistema operacional, caminhos e espaço
efetivo devem ser verificados no host de execução, não inventados nesta documentação.

**Desenvolvimento no Mac; execução experimental no computador dedicado.** Implementar
os scripts, testes, configuração e documentação no Mac. Executar nele testes sintéticos
e verificações pequenas de integração, sem a campanha de treinamento real. Depois, o
usuário levará para o computador dedicado a versão do código já commitada no Mac,
por cópia local, bundle ou outro meio equivalente, e editará ali apenas os caminhos
locais. O computador dedicado servirá exclusivamente para o piloto de recursos, os
treinamentos e a geração dos artefatos pesados; não haverá desenvolvimento, commit ou
análise metodológica naquela máquina. Não tentar iniciar treinamento real no Mac para
declarar a 2B concluída.

CPU é o caminho mínimo obrigatório; GPU é opcional e não condiciona a entrega.
Referência inicial: seis threads e orçamento aproximado de 22 GiB para o processo
experimental, com ajuste técnico após medir recursos. Limite interno do DuckDB não
é limite de RSS do processo; deixar margem para Polars, arrays, biblioteca de ML e SO.
Não executar vários treinos pesados simultaneamente. Mac de 8 GiB permanece útil para
desenvolvimento e verificações pequenas, sem presumir nele a capacidade do computador.

**Priorizar todos os exemplos elegíveis em cada ajuste**, depois dos filtros temporais,
de tarefa e qualidade. Não há teto fixo de 500 mil exemplos. A preparação, leitura,
predição e métricas devem ser colunares/particionadas; isso não garante que todo
estimador consiga fazer seu ajuste fora da memória. Medir também a matriz expandida
por horizonte, categorias, gradientes, cópias e temporários, não só o tamanho do Parquet.

### 12.2 Execução técnica pequena antes da comparação

Usar apenas passado de treinamento, por exemplo até 500 mil exemplos elegíveis por
tarefa/fonte, para testar contratos, medir tempo/memória e verificar ida e volta de
artefatos. Não usar suas métricas para eliminar famílias, escolher features ou declarar
um vencedor. Depois, executar as quatro rodadas completas conforme o protocolo.

Se a projeção de recursos impedir ajuste completo, tentar antes reduzir cópias,
materialização redundante, categorias densas e concorrência, mantendo a metodologia.
Se continuar inviável, registrar medição, alternativas e proposta explícita de redução.
Não amostrar silenciosamente. Uma contingência de amostragem deve ser reproduzível,
preservar proporções temporais/entidades/horizontes e prevalência natural, usar o mesmo
conjunto elegível entre candidatos da tarefa e ser fixada antes da comparação externa.
Continuar com validação completa. Não mudar para split aleatório nem selecionar só
exemplos fáceis ou só períodos recentes para caber na máquina.

Orçamento inicial de execução experimental: 12 horas de parede para preparação,
treinos, inferência, métricas, sensibilidades e persistência; não são 12 horas por modelo,
nem previsão de duração. Implementação/testes/debug são separados. A execução técnica
deve projetar esse custo; qualquer revisão do orçamento fica registrada antes da
comparação. Não sacrificar rodadas para declarar conclusão dentro do prazo.

Ao atingir recursos/prazo sem completar o mínimo, parar a expansão opcional, salvar
checkpoints, falhas e um relatório de execução incompleta com comando de retomada.
Não chamar resultado parcial de comparação concluída. Não usar tempo poupado para
abrir uma busca adicional de parâmetros fora do protocolo.

### 12.3 Diretórios configuráveis e retenção

A Etapa 2B deve aceitar caminhos absolutos externos, sem depender de onde o repositório
foi clonado. Reaproveitar `CURTAMAP_DATA_DIR` e `CURTAMAP_MODEL_DIR` e estender a configuração
para raiz experimental, cache e temporários. Não fixar letra de unidade, nome do SSD,
caminho pessoal ou credencial no código. Espaços no caminho devem funcionar.

Entregar um exemplo de configuração com caminhos genéricos e instruções para o usuário
editar no computador dedicado. Separar configuração versionada do experimento dos
caminhos locais ignorados pelo Git. Nenhum teste deve depender do SSD pessoal do usuário.

Todos os dados derivados grandes, tabelas de previsões, matrizes, caches, spill do
DuckDB, temporários de bibliotecas e modelos devem ir para a unidade escolhida, não
apenas o resultado final. Verificar espaço livre antes de cada etapa pesada. Um
alerta inicial de 50 GiB de artefatos é referência revisável após a medição, não
consumo previsto, memória RAM ou permissão para apagar evidências. Preservar os
originais, configurações, resultados negativos e artefatos necessários à reprodução.

### 12.4 Prioridades e sementes

- Mínimo: duas famílias, duas fontes, duas ocorrências, volume e causa; V1–V4;
  todos os baselines; calibração binária; métricas e diagnósticos; sensibilidade +24h;
  pacote reproduzível. Semente principal 42.
- Recomendado, após mínimo completo: intervalo de volume e repetição dos modelos
  estocásticos com sementes 17 e 101, sem nova busca ou mudança das configurações.
- Opcional: origem e sensibilidade +72h, nessa ordem. Identificar ausência/limitação
  dessas extensões sem prejudicar a honestidade do resultado mínimo.
- Adiado: outras janelas de treino, modelos conjuntos/recursivos/por horizonte,
  meteorologia, novas famílias e coleta das 12h.

Treino final após escolha também é planejado localmente. AWS é destino futuro para
disponibilizar a aplicação/artefato, não requisito para terminar a comparação. Não
presumir permissões, créditos ou disponibilidade no evento. Hospedar não exige retreinar;
uma versão retreinada com mais dados é nova versão e não herda avaliação independente.

## 13. Implementação, contratos e pacote de resultados

### 13.1 Trabalho autorizado na Etapa 2B

Implementar e executar ponta a ponta, com TDD Red–Green–Refactor. Preservar módulos
de domínio existentes. Novas dependências mínimas só quando necessárias aos candidatos,
com versão/lock registrados; não adicionar um catálogo de ML. Nenhuma integração AWS,
GPU ou LLM é obrigatória. Não alterar os Parquet originais nem regenerar resultados da
Etapa 1 para disfarçar diferenças de snapshot.

Testes devem expressar o contrato antes da implementação: limite de 19h30 e de meia
hora, sexta/fim de semana/segunda e feriados, cenários +24h, fronteiras internas/externas,
primeiro/último horizonte, nenhum label de treino ainda indisponível, cadastro novo,
lacunas/nulos/zero distintos, 21 volumes inválidos, classes ausentes, fallback de ontem
indisponível, agregação regional as-of, unidade de energia e ausência de dupla contagem
de emissões, pré-processamento só de treino e bloqueio do teste real.

Testar também leitura/gravação em diretórios externos com espaços, caminhos de
temporários, reprodução por configuração e paridade das métricas em dados sintéticos.
Não usar o teste final real como fixture para desenvolver o pipeline.

### 13.2 Artefatos estruturados mínimos

Dentro da raiz experimental externa, um `run_id` imutável deve conter:

- Manifesto: commit, hashes dos dois datasets, schema, calendário, versões, host,
  parâmetros efetivos, seeds, diretórios, timestamps, duração e estado de conclusão.
- Configuração resolvida e planos de cortes: fronteiras, população, contagens por
  motivo de inclusão/exclusão, colunas e regras de disponibilidade.
- Datasets ou receitas determinísticas de reconstrução; modelos, pré-processadores,
  calibradores, limiares e dicionários de categorias.
- Previsões particionadas por cenário/fonte/rodada/modelo, com chave completa, alvos
  avaliáveis, probabilidades, volumes, causas, flags e proveniência do fallback.
  Armazenamento pode compartilhar chaves/features para evitar cópias redundantes.
- Métricas em JSON/Parquet, sem `NaN` ambíguo: valor nulo acompanhado do motivo,
  suporte, denominador, tarefa, cenário, painel, fonte, rodada e horizonte/recorte.
- Diagnósticos de calibração, episódios, cauda, entidades, incerteza e disponibilidade;
  matriz de comparações e estados dos critérios; custos e falhas de cada ajuste.
- Logs técnicos, erros, comandos de retomada e índice de arquivos com checksums.

No Git, apenas código, testes, configurações pequenas sem caminhos pessoais e um
relatório factual reproduzível, com links/caminhos lógicos para artefatos locais grandes.
Não versionar Parquet, modelos ou credenciais. Relatórios devem distinguir resultados
executados, opcionais não executados, inviabilidade e hipóteses.

### 13.3 Branch de trabalho e handoff entre máquinas

Toda a implementação da Etapa 2 deve ocorrer na branch dedicada
`etapa-2-experimental`, criada a partir do estado aprovado da Etapa 1. A `main` fica
preservada no estado anterior ao protocolo da Etapa 2. O Sol deve criar seus commits
de implementação exclusivamente nessa branch e não deve fazer merge durante a 2B.
O merge para `main` só será considerado depois de a execução experimental terminar,
os artefatos retornarem ao Mac e a análise da Etapa 2C aprovar a integração. Resultados
experimentais, por si só, não autorizam merge automático.

A entrega no Mac é a **implementação pronta para execução**, não a 2B experimental
concluída. Entregar instruções exatas para configuração de caminhos, instalação,
verificação dos hashes, piloto, execução completa e retomada no computador dedicado.
O SO e os caminhos locais devem ser obtidos no destino. Não exigir o mesmo caminho
absoluto do Mac e não registrar valores pessoais na configuração versionada.

Sem push, o computador dedicado recebe uma cópia do código e dos arquivos de
configuração da versão commitada no Mac; ele não cria commits. Ao terminar, o usuário
traz de volta apenas os artefatos resultantes da execução — manifesto, métricas,
previsões, modelos, logs, diagnósticos, falhas, checksums e relatório — para o Mac.
Esses artefatos devem ter um `run_id` e hashes para permitir conferência. Não trazer
alterações de código feitas durante o treinamento, porque não haverá desenvolvimento
ali. Não criar infraestrutura remota, fazer upload ou sincronizar um clone por
iniciativa própria. A análise, qualquer correção e todos os commits posteriores são
feitos no Mac, depois que os resultados forem recebidos.

Antes da execução real, registrar `execucao_pendente`, listar o que foi testado no Mac
e entregar instruções de retomada. Não substituir experimentos reais por saídas
sintéticas nem apresentar a máquina de desenvolvimento como host dos resultados.

Entregar protocolo aprovado, commits de implementação, configurações, métricas por
rodada/fonte/horizonte, comparação integral com baselines, populações, tempos, memória,
falhas, diagnósticos e acesso aos artefatos. Recomendações da execução são preliminares.
Não escolher um vencedor definitivo, não omitir resultados negativos, não abrir o teste
real e não declarar suficiência operacional só porque uma média melhorou.

O relatório deve permitir à Etapa 2C selecionar por tarefa/fonte ou concluir que faltam
evidências. Um baseline pode ser a melhor entrega disponível. A execução termina com
um prompt de análise e decisão que referencia os commits, o manifesto e as limitações.

Commits atômicos em Conventional Commits e português do Brasil, diário append-only,
testes, `ruff check` e `ruff format --check`. Sem push. Ao final, informar verificações
executadas/não executadas e estado do Git.

## 14. Registro conciso das decisões

| Decisão | Estado | Justificativa e consequência | Origem |
|---|---|---|---|
| `t0` inicia a primeira das 48 janelas; atualização a cada 30 min | Aprovada | Cobertura móvel de 24h, sem atraso artificial de um patamar | Discussão; arquitetura; pesquisa temporal §1.2 |
| Publicação simulada às 19h30 do próximo dia útil | Aprovada como hipótese | Reprodutibilidade de disponibilidade sem inventar SLA | Discussão; fontes ONS §1.2 |
| Sensibilidade com mais 24h | Aprovada | Medir resistência ao envelhecimento do histórico | Discussão; inventário |
| Meio-dia e vintages prospectivos | Adiada | Snapshot não permite reconstruir chegada parcial | Discussão; revisão pública |
| Corte positivo principal; comando secundário | Aprovada | Distinguir perda energética de ordem sem perda | Discussão; alvos; notebook |
| Volume positivo condicional e pipeline probabilístico | Aprovada | Medir quantidade e erro total, preservando cauda | Discussão; alvos |
| 21 volumes indeterminados preservados como nulos | Aprovada | Não inventar energia; filtros específicos por tarefa | Auditoria; alvos; discussão |
| Causa antecipada condicional à ordem; sem PAR sintético | Aprovada | Preservar significado e suporte de classes | Discussão; auditoria |
| Aquecimento de 28 dias/80%, painel aberto e fixo definido no passado | Aprovada | Tratar novos IDs sem selecionar sobreviventes futuros | Discussão; EDA; inventário |
| Quatro validações expanding e teste final separado | Aprovada | Medir estabilidade antes de selecionar | Discussão; cobertura real |
| Features de passado e calendário; duas famílias por fonte | Aprovada | Comparar hipóteses com custo limitado e controle temporal | Discussão; AGENTS; inventário |
| Probabilidades/calibração obrigatórias; intervalo de volume recomendado | Aprovada | Não confundir score com certeza | Discussão |
| Margens, estabilidade, suporte e custos antes dos resultados | Aprovada | Impedir escolha pela melhor média isolada | Discussão; §11 |
| Computador dedicado, treino completo elegível e SSD externo | Aprovada | Recursos informados; prioridade de uso dos dados válidos | Discussão de 22/09/2026; §12 |
| Scripts/testes no Mac, configuração genérica e transferência pelo usuário | Aprovada | Separar desenvolvimento da execução; não preencher caminhos do outro host | Orientação final de 22/09/2026; §13.3 |
| Implementação da 2B em `etapa-2-experimental`; merge somente após 2C | Aprovada | Preservar `main` e revisar o resultado antes da integração | Orientação final de 22/09/2026; §13.3 |
| Execução menor apenas técnica; amostragem só por inviabilidade demonstrada | Aprovada | Corrigir sem pagar todo o custo; não reduzir treino por conveniência | Discussão de 22/09/2026 |
| Algoritmos finais, suficiência noturna e adoção | Dependente de experimento | Evidências e regras de decisão em §11.3 | Discussão; este protocolo |
| AWS para disponibilização posterior | Aprovada | Não concentrar descoberta de falhas no evento | Discussão; evolução da arquitetura |

As decisões dependentes têm critérios registrados. Nenhuma exige escolher um vencedor
agora. Não há métricas preditivas nesta documentação nem autorização para tratar a
Etapa 2B como já executada.
