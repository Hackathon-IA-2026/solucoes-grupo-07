"""Infraestrutura mínima do CurtaMap: ECR + S3 (base) e ECS Fargate atrás de um ALB (app).

Restrições do ambiente do hackathon (docs/aws-environment.md) codificadas aqui:

- papéis criados só podem ser passados a ECS, EC2, EFS e Bedrock. Os únicos papéis são os
  da tarefa ECS (execução e aplicação), assumidos por `ecs-tasks.amazonaws.com`;
- nada de Lambda nem recursos customizados. Por isso não há `autoDeleteObjects` no bucket
  nem `emptyOnDelete` no ECR, e o grupo de segurança padrão da VPC não é restringido por
  recurso customizado;
- sem `cdk bootstrap`, que cria papéis passados ao CloudFormation: as pilhas usam
  `BootstraplessSynthesizer` e não têm assets. A imagem é enviada ao ECR pela CLI do Docker.
"""

from dataclasses import dataclass

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct

CONTAINER_PORT = 8501
HEALTH_PATH = "/_stcore/health"
DATA_PREFIX = "raw/"
MODEL_PREFIX = "models/previsao/"


class BaseStack(Stack):
    """Recursos que existem antes da imagem: repositório ECR e bucket de dados."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.repository = ecr.Repository(
            self,
            "Repositorio",
            repository_name="curtamap",
            image_scan_on_push=True,
            removal_policy=RemovalPolicy.DESTROY,
            lifecycle_rules=[ecr.LifecycleRule(max_image_count=10)],
        )
        # RETAIN: sem Lambda de esvaziamento, um bucket com objetos travaria o destroy.
        # O esvaziamento é um passo explícito de docs/deploy.md.
        self.bucket = s3.Bucket(
            self,
            "Dados",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        CfnOutput(self, "RepositorioUri", value=self.repository.repository_uri)
        CfnOutput(self, "BucketDados", value=self.bucket.bucket_name)


@dataclass(frozen=True)
class AppSettings:
    image_tag: str = "latest"
    desired_count: int = 1
    cpu: int = 2048
    memory_mib: int = 8192
    # VPC existente (ex.: a padrão da conta), sem lookup: `cdk synth` não precisa de
    # credenciais. Sem ela, a pilha cria uma VPC pública sem NAT.
    vpc_id: str | None = None
    availability_zones: tuple[str, ...] = ()
    public_subnet_ids: tuple[str, ...] = ()


class AppStack(Stack):
    """Serviço Fargate com a interface Streamlit atrás de um ALB público."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        repository: ecr.IRepository,
        bucket: s3.IBucket,
        settings: AppSettings,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        vpc = self._vpc(settings)
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)
        log_group = logs.LogGroup(
            self,
            "Logs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )
        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "Servico",
            cluster=cluster,
            cpu=settings.cpu,
            memory_limit_mib=settings.memory_mib,
            desired_count=settings.desired_count,
            public_load_balancer=True,
            assign_public_ip=True,
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            # Com uma tarefa só, 100% evita derrubar a demo durante um deploy.
            min_healthy_percent=100,
            max_healthy_percent=200,
            # Tempo para baixar os Parquet do S3 antes do primeiro health check.
            health_check_grace_period=Duration.minutes(5),
            idle_timeout=Duration.minutes(5),
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(repository, settings.image_tag),
                container_port=CONTAINER_PORT,
                environment={
                    "CURTAMAP_DATA_S3_URI": bucket.s3_url_for_object(DATA_PREFIX),
                    "CURTAMAP_MODEL_S3_URI": bucket.s3_url_for_object(MODEL_PREFIX),
                },
                log_driver=ecs.LogDrivers.aws_logs(stream_prefix="curtamap", log_group=log_group),
            ),
        )
        # O ALB suporta WebSocket; a aderência mantém a sessão do Streamlit na mesma tarefa.
        service.target_group.configure_health_check(
            path=HEALTH_PATH, healthy_http_codes="200", interval=Duration.seconds(30)
        )
        service.target_group.enable_cookie_stickiness(Duration.hours(8))
        bucket.grant_read(service.task_definition.task_role)
        CfnOutput(self, "Url", value=f"http://{service.load_balancer.load_balancer_dns_name}")
        CfnOutput(self, "LogGroup", value=log_group.log_group_name)

    def _vpc(self, settings: AppSettings) -> ec2.IVpc:
        if settings.vpc_id:
            return ec2.Vpc.from_vpc_attributes(
                self,
                "Vpc",
                vpc_id=settings.vpc_id,
                availability_zones=list(settings.availability_zones),
                public_subnet_ids=list(settings.public_subnet_ids),
            )
        return ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=0,
            restrict_default_security_group=False,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="publica", subnet_type=ec2.SubnetType.PUBLIC)
            ],
        )
