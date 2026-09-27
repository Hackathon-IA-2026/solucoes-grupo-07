# Ambiente AWS do Hackathon

Este documento registra apenas capacidades e restrições úteis ao desenvolvimento. Credenciais, emails de acesso, URLs temporárias e instruções pessoais de login não devem ser versionados.

## Janelas informadas

- Testes: 18 a 20 de setembro de 2026.
- Desenvolvimento presencial: 25 a 27 de setembro de 2026.

## Restrições gerais

- Regiões disponíveis: `us-east-1` e `us-west-2`.
- Recursos devem ser provisionados com CloudFormation ou CDK.
- O projeto inteiro deve permanecer em um único repositório.
- ECR permite criar e consultar repositórios de imagens.
- API Gateway está limitado à invocação de APIs existentes via `execute-api`.
- Há restrições específicas para passagem e assunção de papéis IAM.

## Serviços confirmados

| Área | Serviços relevantes |
|---|---|
| Computação | Lambda, ECS, Auto Scaling |
| Dados | S3, DynamoDB, OpenSearch, EFS |
| IA | SageMaker, Bedrock, Bedrock AgentCore e Agent Registry |
| Integração | EventBridge, SNS e API Gateway |
| Identidade | Cognito Identity e Cognito User Pools |
| Build | CloudFormation, CodeBuild e ECR |
| Observabilidade | CloudWatch, CloudWatch Logs, CloudTrail, X-Ray e Application Signals limitado |
| Segurança | IAM, KMS, SSM e STS com restrições |
| EC2 | Consulta de rede e gerenciamento de launch templates |

## Restrições de IAM relevantes

- Papéis criados pela equipe só podem ser passados a Bedrock, Bedrock AgentCore, ECS, EC2 e EFS.
- Lambda e CodeBuild devem receber o papel `WSParticipantRole` fornecido pelo ambiente.
- `sts:AssumeRole` está limitado aos papéis explicitamente disponibilizados pelo workshop.
- O Code Editor usa uma identidade mais restrita que as credenciais gerais do participante.

## Bedrock

O catálogo informado inclui famílias Anthropic Claude, Amazon Nova, OpenAI GPT, xAI Grok, Moonshot Kimi, DeepSeek, Writer, TwelveLabs e Amazon Titan Embeddings. A disponibilidade real depende do identificador de inferência e de seu prefixo `us.` ou `global.`; a aplicação deve tratar indisponibilidade como uma condição normal e possuir fallback.

Nenhum modelo generativo será acoplado ao domínio. O Zelo deve escolher um provedor por configuração e continuar funcional sem essa camada.

## Hipótese inicial de implantação

1. S3 guarda dados brutos, processados e artefatos de modelos.
2. SageMaker ou uma tarefa ECS executa treino e processamento pesado após um teste comparativo de permissões, custo e tempo.
3. CodeBuild produz uma imagem no ECR.
4. ECS executa a aplicação web. Se React for escolhido, um build multi-stage pode servir frontend e FastAPI em um único serviço.
5. DynamoDB guarda previsões e metadados somente se a persistência for necessária ao fluxo da demo.
6. CloudWatch concentra logs, métricas e alarmes.
7. CDK descreve a infraestrutura completa, sem criação manual oculta.

Essa topologia é uma hipótese de trabalho. Cada serviço entra apenas depois de um spike mínimo comprovar permissões e necessidade.
