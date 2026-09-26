"""Restrições do ambiente AWS do hackathon, verificadas no template sintetizado.

Precisa do extra `infra` e de Node no PATH (o `aws-cdk-lib` roda sobre jsii).
"""

import shutil
import sys
from pathlib import Path

import pytest

if shutil.which("node") is None:
    pytest.skip("Node ausente: o aws-cdk-lib precisa dele", allow_module_level=True)
pytest.importorskip("aws_cdk", reason="extra infra não instalado")

from aws_cdk import App  # noqa: E402
from aws_cdk.assertions import Match, Template  # noqa: E402

sys.path.insert(0, str(Path(__file__).parents[1] / "infra"))
from curtamap_infra import build  # noqa: E402


@pytest.fixture(scope="module")
def templates() -> tuple[Template, Template]:
    base, service = build(App())
    return Template.from_stack(base), Template.from_stack(service)


def _all(templates: tuple[Template, Template], kind: str) -> dict:
    found = {}
    for template in templates:
        found |= template.find_resources(kind)
    return found


def test_no_lambda_or_custom_resource(templates) -> None:
    assert not _all(templates, "AWS::Lambda::Function")
    assert not _all(templates, "Custom::S3AutoDeleteObjects")
    for template in templates:
        resources = template.to_json()["Resources"].values()
        assert not [r for r in resources if r["Type"].startswith("Custom::")]


def test_created_roles_are_only_assumed_by_ecs_tasks(templates) -> None:
    roles = _all(templates, "AWS::IAM::Role")
    assert roles
    for role in roles.values():
        statements = role["Properties"]["AssumeRolePolicyDocument"]["Statement"]
        assert [s["Principal"] for s in statements] == [{"Service": "ecs-tasks.amazonaws.com"}]


def test_service_runs_the_ecr_image_on_8501_behind_an_alb(templates) -> None:
    _, service = templates
    service.has_resource_properties(
        "AWS::ECS::TaskDefinition",
        {
            "RequiresCompatibilities": ["FARGATE"],
            "ContainerDefinitions": Match.array_with(
                [
                    Match.object_like(
                        {
                            "PortMappings": [Match.object_like({"ContainerPort": 8501})],
                            "Environment": Match.array_with(
                                [Match.object_like({"Name": "CURTAMAP_DATA_S3_URI"})]
                            ),
                            "LogConfiguration": Match.object_like({"LogDriver": "awslogs"}),
                        }
                    )
                ]
            ),
        },
    )
    service.has_resource_properties(
        "AWS::ElasticLoadBalancingV2::TargetGroup",
        {"HealthCheckPath": "/_stcore/health", "Port": 80},
    )
    service.resource_count_is("AWS::ElasticLoadBalancingV2::LoadBalancer", 1)


def test_data_bucket_is_private_and_logs_expire(templates) -> None:
    base, service = templates
    base.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        },
    )
    base.resource_count_is("AWS::ECR::Repository", 1)
    service.has_resource_properties("AWS::Logs::LogGroup", {"RetentionInDays": 7})


def test_synth_needs_no_bootstrap(templates) -> None:
    for template in templates:
        assert "BootstrapVersion" not in template.to_json().get("Parameters", {})


def test_region_outside_the_hackathon_is_refused() -> None:
    with pytest.raises(ValueError, match="região"):
        build(App(context={"region": "sa-east-1"}))


def test_existing_vpc_is_used_without_lookup() -> None:
    app = App(
        context={
            "vpcId": "vpc-123",
            "availabilityZones": "us-east-1a,us-east-1b",
            "publicSubnetIds": "subnet-a,subnet-b",
        }
    )
    _, service = build(app)

    Template.from_stack(service).resource_count_is("AWS::EC2::VPC", 0)


def test_without_alb_the_task_is_exposed_on_8501() -> None:
    _, service = build(App(context={"semAlb": "true"}))
    template = Template.from_stack(service)

    template.resource_count_is("AWS::ElasticLoadBalancingV2::LoadBalancer", 0)
    template.resource_count_is("AWS::ECS::Service", 1)
    template.has_resource_properties(
        "AWS::EC2::SecurityGroup",
        {"SecurityGroupIngress": [Match.object_like({"FromPort": 8501, "ToPort": 8501})]},
    )
