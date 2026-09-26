"""App CDK do CurtaMap (Python). Veja docs/deploy.md."""

from aws_cdk import App, BootstraplessSynthesizer, Environment

from curtamap_infra.stacks import AppSettings, AppStack, BaseStack

DEFAULT_REGION = "us-east-1"
REGIONS = ("us-east-1", "us-west-2")


def _list(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in (value or "").split(",") if item.strip())


def settings_from_context(app: App) -> AppSettings:
    ctx = app.node.try_get_context
    return AppSettings(
        image_tag=ctx("imageTag") or "latest",
        desired_count=int(ctx("desiredCount") or 1),
        cpu=int(ctx("cpu") or 2048),
        memory_mib=int(ctx("memoryMiB") or 8192),
        vpc_id=ctx("vpcId") or None,
        availability_zones=_list(ctx("availabilityZones")),
        public_subnet_ids=_list(ctx("publicSubnetIds")),
    )


def build(app: App) -> tuple[BaseStack, AppStack]:
    region = app.node.try_get_context("region") or DEFAULT_REGION
    if region not in REGIONS:
        raise ValueError(f"região {region} fora das liberadas no hackathon: {REGIONS}")
    env = Environment(region=region)
    base = BaseStack(app, "CurtaMapBase", env=env, synthesizer=BootstraplessSynthesizer())
    service = AppStack(
        app,
        "CurtaMapApp",
        repository=base.repository,
        bucket=base.bucket,
        settings=settings_from_context(app),
        env=env,
        synthesizer=BootstraplessSynthesizer(),
    )
    return base, service
