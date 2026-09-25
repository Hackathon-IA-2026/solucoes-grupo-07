# Direção técnica inicial do CurtaMap

## Decisao de produto

O usuario principal do MVP e o **gerador eolico ou solar**. O produto tem dois ritmos:

- **Operacional:** previsao atualizada a cada 30 minutos, cobrindo as proximas 24 horas (48 janelas). O usuario consulta no inicio do dia e recebe destaque quando risco, volume ou causa mudam materialmente.
- **Tatico:** resumo semanal/mensal de perdas, causas e oportunidades para manutencao, contratos e cenarios de armazenamento.

O dashboard deve abrir com a decisao que o usuario precisa tomar, nao com a acuracia do modelo: usinas em risco, janela, MWh, causa, confianca e acao sugerida.

## Fluxo do sistema

1. **Ingestao:** Parquet do ONS e, quando existir, previsao meteorologica realmente disponivel no instante da inferencia.
2. **Validacao:** schema, chave `fonte + id_ons`, cobertura de nulos, duplicidade, frequencia de 30 minutos e unidades.
3. **Features:** calendario, defasagens por usina, historico no mesmo horario, agregados regionais/sistemicos e sinais meteorologicos validos.
4. **Problemas de modelagem:**
   - classificador binario para ocorrencia de corte;
   - regressor para volume, condicionado a corte;
   - classificador de causa/origem, se a cobertura dos rotulos permitir.
5. **Recomendacao:** regras explicitas por causa + simulacao simples de despacho. Clustering serve para segmentar assinaturas, nao para substituir regras de negocio.
6. **Entrega:** dashboard local e uma implantação reproduzível na AWS. A tecnologia da interface final ainda será decidida.

Os três problemas estão definidos, mas os algoritmos não. A seleção ocorrerá depois da auditoria dos dados, por meio de baselines e experimentos temporais reproduzíveis. LightGBM, regressões regularizadas e outros modelos tabulares são candidatos, não compromissos arquiteturais.

## Inferência em produção: cálculo incremental de features

Decisão registrada em 24/09/2026, ao fim da Etapa 2B. Ela vale para a fase de produto,
depois do treino final e do teste reservado, e não altera a Etapa 2C.

**Princípio.** Os datasets de features da 2B (≈ 8,2 GB) existem para treinar e avaliar: cobrem
todas as usinas, a cada meia hora de ≈ 2,5 anos, com 48 horizontes. Em operação, a pergunta é
sempre "e as próximas 24 h a partir de agora?". Por isso a aplicação calcula as features de
**um t0 por vez**, a partir de uma janela móvel de dados brutos. Ela não carrega nem distribui
o dataset de treino.

**O que a inferência precisa (estado mínimo):**

- os modelos finais congelados, em `models/`, com versão, receita e hashes (dezenas de MB);
- uma janela móvel de dados brutos de **35 dias** por fonte, cerca de 5 MB. As features usam
  janelas de até 28 dias (`features.py`, `baselines.py`), e a preparação lê 35 dias
  (`preparation.py`);
- uma tabela pequena por usina com a data do primeiro registro, usada pelas flags de histórico
  insuficiente e de usina nova;
- o calendário de liberação (hoje simulado às 19h30 do dia útil seguinte).

**Fluxo:**

1. **Job agendado de previsão:**
   1. quando o ONS libera dados novos, ingere o incremento e descarta o que passar de 35 dias;
   2. calcula as features do t0 atual com **a mesma função usada no treino**;
   3. aplica os modelos (ocorrência, volume e causa);
   4. grava as previsões com t0, horizonte, versão do modelo, fonte e horário da última
      atualização (Parquet/DuckDB).
2. **Dashboard:** apenas lê as previsões gravadas e as exibe com fonte, janela temporal, última
   atualização, incerteza e limitações. Não calcula features nem treina.

**Custo estimado** (hipótese extrapolada dos tempos medidos na geração dos datasets da 2B,
≈ 8 s por dia de 48 t0 na eólica e ≈ 3 s na solar):

- features de um t0 para todas as usinas: frações de segundo de cálculo, mais a leitura da
  janela de histórico;
- previsão: milissegundos;
- ciclo completo: poucos segundos por fonte.

Cabe num container modesto, sem GPU e sem serviço externo obrigatório. A implantação na AWS
continua atrás de interfaces e configuração.

**Modo de reprodução (demonstração).** Como os dados disponíveis terminam em 2026, o MVP roda
o mesmo job com um relógio histórico: recebe um t0 passado e usa só os dados que estariam
liberados naquele instante. O código é idêntico ao da operação; muda apenas a fonte do "agora".
O dashboard deve indicar explicitamente que se trata de reprodução histórica.

**Requisito de qualidade: paridade treino/produção.** O principal risco desse desenho é o
cálculo incremental divergir do dataset de treino. Antes de integrar o job, é obrigatório um
teste de paridade:

1. escolher t0 presentes em `experiments/stage2b/experimentos/stage2b-datasets`;
2. recalculá-los pelo caminho incremental, só com a janela de 35 dias;
3. exigir igualdade linha a linha das features.

Os datasets da 2B servem de gabarito para esse teste, e só nesse papel precisam existir fora
do container.

## Interface: decisão pendente

O Streamlit é adequado para exploração e possui `st.chat_input` e `st.chat_message`. Também aceita componentes customizados e CSS, mas um botão flutuante, navegação sofisticada e identidade visual muito específica tendem a exigir componentes próprios e soluções mais frágeis.

React/Vite + FastAPI oferece controle total sobre mapa, storytelling, responsividade e um assistente flutuante. Em contrapartida, aumenta o escopo, a quantidade de contratos frontend/backend e o custo de testes e deploy.

Com ECS, ECR e CodeBuild confirmados, a alternativa React é tecnicamente viável dentro de um único repositório. Um Dockerfile multi-stage pode compilar o frontend e servir os arquivos estáticos junto da API FastAPI em um único serviço ECS. A decisão deve ser tomada após um spike curto comparando esforço, qualidade visual e risco de entrega; não haverá migração tardia sem essa validação.

## Por que nao usar um LLM como modelo principal

O problema central é uma série temporal tabular, grande, desbalanceada e com necessidade de explicação quantitativa. O LLM recebe apenas um JSON validado com previsão, principais fatores, premissas e recomendação; ele não recalcula nem altera os números.

## IA generativa: Bedrock e NVIDIA NIM

O uso recomendado é limitado a uma explicação curta para o cartão de cada usina, um assistente contextual e perguntas sobre resultados já calculados. O provedor deve ser intercambiável e desativável; o valor central do CurtaMap não pode depender de um LLM.

O ambiente oferece um catálogo amplo no Bedrock, enquanto o NVIDIA Build/NIM continua interessante pelo patrocínio e pela API compatível com OpenAI. A escolha entre ambos será feita por um teste pequeno de qualidade em português, latência, estabilidade e facilidade de integração. Não há motivo para integrar dois provedores ao MVP apenas por disponibilidade.

## AWS

O documento de ambiente confirma `us-east-1` e `us-west-2`, com provisionamento obrigatório por CloudFormation ou CDK. Estão disponíveis, entre outros:

- ECS, Lambda e Auto Scaling para computação;
- S3, DynamoDB, OpenSearch e EFS para dados;
- SageMaker, Bedrock e Bedrock AgentCore para IA;
- ECR e CodeBuild para build e deploy;
- API Gateway, EventBridge e SNS para integração;
- Cognito para identidade;
- CloudWatch, CloudTrail e X-Ray para observabilidade.

A arquitetura inicial considera:

- S3 para dados e artefatos versionados;
- SageMaker ou uma tarefa ECS para treino, conforme custo e limites observados;
- ECS/ECR para a aplicação web conteinerizada;
- DynamoDB para previsões e metadados de execução quando necessário;
- Bedrock ou NIM como camada generativa opcional;
- CloudWatch para logs e métricas;
- CDK como primeira opção de infraestrutura como código, sujeito a um spike de permissões.

As restrições de IAM e passagem de papéis precisam ser codificadas explicitamente. Segredos e instruções de login nunca entram no Git.

O inventário confirmado, as restrições e as hipóteses de implantação estão detalhados em [aws-environment.md](aws-environment.md).

## Avaliacao minima

- Backtest temporal com janelas que imitam previsao real D+1.
- Baselines: ultimo valor e mesmo horario do dia anterior.
- Evento: PR-AUC, recall e precisao no limiar operacional.
- Volume: MAE e WAPE em MW/MWh, incluindo erro total por dia.
- Causa: macro-F1 e matriz de confusao apenas sobre rotulos validos.
- Avaliar separadamente eolica/fotovoltaica, usinas vistas/nao vistas e causas.

## Riscos que precisam ficar visiveis

1. Vento e irradiancia verificados causam vazamento se forem usados como se estivessem disponiveis D+1.
2. A formula de volume cortado ainda precisa ser validada contra o dicionario do ONS e especialistas.
3. `razao` e `origem` podem ter cobertura insuficiente para classificacao supervisionada.
4. Recomendacao de bateria e estimativa de CO2 sao cenarios, nao causalidade nem garantia financeira.
5. Um modelo por usina pode nao generalizar; um modelo global com identidade e historico da usina deve ser o primeiro teste.

## Perguntas abertas para a equipe/organizacao

- Quais arquivos e credenciais de dados ja estao disponiveis para o grupo?
- Qual definicao oficial ou aceita de volume de curtailment sera usada?
- Existe limite de custo/credito e politica de desligamento da conta?
- O endpoint NVIDIA Build tera chave fornecida ou cada participante cria a sua?
- O pitch final tem duracao e formato de entrega definidos alem do repositorio MIT?
