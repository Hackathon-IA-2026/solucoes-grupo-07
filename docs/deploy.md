# Deploy do CurtaMap na AWS e contingência offline

Passo a passo para a janela de acesso à AWS (25 a 27/09/2026), sem etapas manuais ocultas.
Todo comando roda a partir da raiz do repositório, salvo quando indicado.
Credenciais, URLs de login e IDs da conta **não entram no Git**.

## O que foi verificado antes do acesso

| Item | Estado | Como |
|---|---|---|
| Interface em Streamlit com dados reais (modelo e baseline) | Verificado | `uv run streamlit run src/curtamap/app.py`, capturas no diário |
| `cdk synth` sem credenciais, com e sem ALB | Verificado | `pnpm dlx aws-cdk@2 synth` (Node 24, pnpm 10) |
| Restrições de IAM (papéis só para ECS; sem Lambda nem recurso customizado; sem bootstrap) | Verificado no template | `tests/test_infra.py` |
| Inicialização do contêiner baixando do S3 | Testado com cliente S3 falso | `tests/test_s3_sync.py` |
| `docker build` e `docker run` | **Não verificado** | A máquina de desenvolvimento não tinha Docker. Rodar a seção 2 antes de qualquer outro passo |
| `cdk deploy` sem bootstrap, criação de VPC e de ALB na conta do evento | **Hipótese** | Só verificável com a conta; a seção 6 traz os planos B |

## Arquitetura

- **CurtaMapBase:** repositório ECR `curtamap` e bucket S3 privado (dados em `raw/`, modelo
  em `models/previsao/`). O bucket é `RETAIN`: esvaziá-lo e apagá-lo faz parte da seção 7.
- **CurtaMapApp:** VPC pública (nova ou existente), cluster ECS, tarefa Fargate
  (2 vCPU / 8 GB), ALB público na porta 80 → contêiner na 8501, health check em
  `/_stcore/health`, aderência de sessão (WebSocket do Streamlit) e CloudWatch Logs com
  retenção de 7 dias.
- A tarefa baixa `raw/` e `models/previsao/` do S3 ao iniciar (`python -m curtamap.s3_sync`)
  e depois sobe o Streamlit. Nenhum dado entra na imagem.
- Memória medida localmente: pico de ~2,1 GB com o modelo, 92 dias de histórico e a visão
  tática de 6 meses. Os 8 GB dão folga para a janela de 12 meses; `-c memoryMiB=4096` é
  possível, mas não foi medido.

Restrições codificadas (ver `docs/aws-environment.md`):

- os únicos papéis criados são os da tarefa ECS, assumidos por `ecs-tasks.amazonaws.com`;
- não há Lambda nem recurso customizado. Por isso não há `autoDeleteObjects`,
  `emptyOnDelete` nem restrição do security group padrão por Lambda;
- `BootstraplessSynthesizer`: sem `cdk bootstrap`, que criaria papéis passados ao
  CloudFormation. Em troca, as pilhas não podem ter assets, e a imagem vai ao ECR pelo
  Docker.

## 1. Pré-requisitos (sexta, antes do presencial)

- `uv`, Node ≥ 20 com `pnpm`, Docker e AWS CLI v2.
- Na raiz:

  ```bash
  uv sync --extra data --extra infra --dev
  uv run python -m curtamap.download_data
  # Modelo congelado do produto (~6 min, ~1,5 GB de RAM). Sem ele, a interface usa o baseline.
  mkdir -p data/interim/previsao
  printf '{"eolica": 0.3461, "fotovoltaica": 0.3212}\n' > data/interim/previsao/limiares.json
  uv run python -m curtamap.previsao.treinar --limiares data/interim/previsao/limiares.json
  ```

  Os limiares são os `final_jan_ago` de `docs/reports/nova-abordagem/limiares.json`.

- Credenciais do workshop no terminal (`aws configure` ou variáveis de ambiente) e
  conferência:

  ```bash
  aws sts get-caller-identity
  export AWS_REGION=us-east-1   # ou us-west-2; as pilhas recusam outras regiões
  ```

## 2. Imagem local (primeiro passo do sábado)

```bash
docker build --platform linux/amd64 -t curtamap .
docker run --rm -p 8501:8501 -v "$PWD/data:/app/data" -v "$PWD/models:/app/models" curtamap
# Em outro terminal:
curl -fsS http://localhost:8501/_stcore/health   # deve responder "ok"
```

Abra `http://localhost:8501`: o selo azul indica "Modelo treinado"; o amarelo, "Preditor
provisório (baseline)". Em Mac com Apple Silicon, `--platform linux/amd64` é obrigatório,
porque o Fargate roda em x86_64.

## 3. Pilha base: ECR e S3

```bash
cd infra
pnpm dlx aws-cdk@2 synth                       # sem credenciais já funciona
pnpm dlx aws-cdk@2 deploy CurtaMapBase --require-approval never
cd ..
BUCKET=$(aws cloudformation describe-stacks --stack-name CurtaMapBase \
  --query "Stacks[0].Outputs[?OutputKey=='BucketDados'].OutputValue" --output text)
REPO=$(aws cloudformation describe-stacks --stack-name CurtaMapBase \
  --query "Stacks[0].Outputs[?OutputKey=='RepositorioUri'].OutputValue" --output text)
```

## 4. Dados, modelo e imagem

```bash
# Só as duas bases usadas pela interface (~145 MB); os *_detail não são necessários.
aws s3 cp data/raw/constrained_off_eolica_tm.parquet "s3://$BUCKET/raw/"
aws s3 cp data/raw/constrained_off_fotovoltaica_tm.parquet "s3://$BUCKET/raw/"
aws s3 cp models/previsao/ "s3://$BUCKET/models/previsao/" --recursive

TAG=$(git rev-parse --short HEAD)
aws ecr get-login-password | docker login --username AWS --password-stdin "${REPO%%/*}"
docker tag curtamap "$REPO:$TAG"
docker push "$REPO:$TAG"
```

O snapshot termina em 31/08/2026. Nada de setembro (teste reservado) deve ir para o bucket.

## 5. Pilha da aplicação

Com uma VPC nova (padrão):

```bash
cd infra
pnpm dlx aws-cdk@2 deploy CurtaMapApp -c imageTag=$TAG --require-approval never
```

Com a VPC padrão da conta, se criar VPC não for permitido:

```bash
VPC=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true \
  --query "Vpcs[0].VpcId" --output text)
aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC \
  --query "Subnets[].[SubnetId,AvailabilityZone]" --output text
pnpm dlx aws-cdk@2 deploy CurtaMapApp -c imageTag=$TAG -c vpcId=$VPC \
  -c availabilityZones=us-east-1a,us-east-1b -c publicSubnetIds=subnet-aaa,subnet-bbb
```

Verificação:

```bash
URL=$(aws cloudformation describe-stacks --stack-name CurtaMapApp \
  --query "Stacks[0].Outputs[?OutputKey=='Url'].OutputValue" --output text)
curl -fsS "$URL/_stcore/health"
LOGS=$(aws cloudformation describe-stacks --stack-name CurtaMapApp \
  --query "Stacks[0].Outputs[?OutputKey=='LogGroup'].OutputValue" --output text)
aws logs tail "$LOGS" --follow     # deve mostrar "baixando s3://..." e depois o Streamlit
```

A primeira tarefa leva alguns minutos: ela baixa os Parquet antes de responder. O
`health_check_grace_period` é de 5 minutos.

**Atualizar a aplicação:** novo `docker build`, `docker push` com outra tag e
`deploy CurtaMapApp -c imageTag=<nova>`. Para trocar só dados ou modelo, basta enviá-los ao
bucket e forçar uma tarefa nova:
`aws ecs update-service --cluster <cluster> --service <serviço> --force-new-deployment`.

## 6. Se algo for bloqueado

| Sintoma | Plano B |
|---|---|
| `cdk deploy` pede bootstrap ou falha antes de criar a pilha | `pnpm dlx aws-cdk@2 synth` e `aws cloudformation deploy --template-file cdk.out/CurtaMapBase.template.json --stack-name CurtaMapBase --capabilities CAPABILITY_IAM`; idem para `CurtaMapApp` (com os mesmos `-c` no synth). Os templates não têm assets nem parâmetros de bootstrap |
| Criação de VPC negada | Usar a VPC padrão (seção 5) |
| Criação de ALB negada (ELB não consta da lista confirmada) | `deploy CurtaMapApp -c semAlb=true ...`: tarefa com IP público na porta 8501. O IP muda a cada tarefa: `aws ecs list-tasks`, `aws ecs describe-tasks` (anexo ENI) e `aws ec2 describe-network-interfaces` (`Association.PublicIp`); abrir `http://<ip>:8501` |
| `iam:PassRole` negado para o papel da tarefa | Registrar o erro exato; a política só permite passar papéis a ECS, que é o caso. Se persistir, pedir orientação à organização; a demo segue local |
| Push no ECR negado | Conferir se o login usa a mesma região da pilha; o ambiente permite criar e consultar repositórios |
| Tarefa reinicia em laço | `aws logs tail`: bucket vazio ou sem permissão aparece como erro do `s3_sync`; falta de memória aparece como `OutOfMemory` no evento do serviço |

## 7. Desligar e limpar (domingo, depois da apresentação)

```bash
cd infra
pnpm dlx aws-cdk@2 destroy CurtaMapApp --force
aws ecr batch-delete-image --repository-name curtamap \
  --image-ids "$(aws ecr list-images --repository-name curtamap --query 'imageIds' --output json)"
aws s3 rm "s3://$BUCKET" --recursive
pnpm dlx aws-cdk@2 destroy CurtaMapBase --force
aws s3 rb "s3://$BUCKET"          # o bucket é RETAIN, então é apagado à mão
```

## Contingência: demo local, sem AWS e sem internet

O código da interface não chama serviços externos: dados, modelo, calendário e bibliotecas
ficam na máquina (o Streamlit empacota o Plotly e as fontes). O teste com a rede desligada
ainda **não foi feito**; é o passo 2 abaixo. Na sexta, no notebook da apresentação:

1. Seguir a seção 1 (dados baixados e modelo treinado) e rodar `uv run pytest`.
2. Desligar o Wi-Fi e subir `uv run streamlit run src/curtamap/app.py`. Abrir
   `http://localhost:8501` e percorrer as três telas. As previsões ficam em cache depois da
   primeira emissão escolhida.
3. Se o Docker estiver disponível, a imagem local da seção 2 é uma segunda opção idêntica
   ao que roda na AWS.
4. Levar um roteiro de demo (diário, entrada da Etapa 4) e capturas de tela para o caso
   extremo de a máquina falhar.
