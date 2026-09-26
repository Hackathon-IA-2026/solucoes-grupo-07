"""Entrada do CDK: `cd infra && pnpm dlx aws-cdk synth` (veja docs/deploy.md)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from aws_cdk import App  # noqa: E402
from curtamap_infra import build  # noqa: E402

app = App()
build(app)
app.synth()
