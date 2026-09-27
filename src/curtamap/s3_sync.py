"""Baixa dados e modelos do S3 para os diretórios locais, na inicialização do contêiner.

Os Parquet e o modelo nunca entram na imagem. Com `CURTAMAP_DATA_S3_URI` e
`CURTAMAP_MODEL_S3_URI` definidos, o conteúdo desses prefixos vai para
`CURTAMAP_DATA_DIR/processed` e `CURTAMAP_MODEL_DIR/previsao`. Sem as variáveis, nada acontece:
os dados podem vir de um volume montado. Arquivos com o mesmo tamanho não são baixados de
novo. Uso: `python -m curtamap.s3_sync`.
"""

import os
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath

from curtamap.config import settings

DATA_ENV = "CURTAMAP_DATA_S3_URI"
MODEL_ENV = "CURTAMAP_MODEL_S3_URI"


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """`s3://bucket/prefixo` → (bucket, "prefixo/")."""
    if not uri.startswith("s3://") or not uri[5:].split("/", 1)[0]:
        raise ValueError(f"URI S3 inválida: {uri!r}")
    bucket, _, prefix = uri[5:].partition("/")
    prefix = prefix.strip("/")
    return bucket, f"{prefix}/" if prefix else ""


def plan_sync(
    objects: Iterable[tuple[str, int]], prefix: str, dest: Path
) -> list[tuple[str, Path]]:
    """Objetos a baixar: ignora "pastas" e arquivos locais do mesmo tamanho."""
    plan = []
    for key, size in objects:
        relative = PurePosixPath(key[len(prefix) :])
        if key.endswith("/") or not relative.parts:
            continue
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"caminho inseguro no S3: {key}")
        target = dest.joinpath(*relative.parts)
        if target.exists() and target.stat().st_size == size:
            continue
        plan.append((key, target))
    return plan


def _client():
    try:
        import boto3
    except ImportError as error:
        raise SystemExit("Dependência ausente. Instale o extra aws: uv sync --extra aws") from error
    return boto3.client("s3")


def sync(uri: str, dest: Path, *, client=None) -> list[Path]:
    bucket, prefix = parse_s3_uri(uri)
    client = client or _client()
    objects = [
        (item["Key"], item["Size"])
        for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
        for item in page.get("Contents", [])
    ]
    written = []
    for key, target in plan_sync(objects, prefix, Path(dest)):
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"baixando s3://{bucket}/{key} -> {target}", flush=True)
        client.download_file(Bucket=bucket, Key=key, Filename=str(target))
        written.append(target)
    return written


def sync_from_env(
    env: Mapping[str, str], *, data_dir: Path, model_dir: Path, client=None
) -> list[Path]:
    targets = {DATA_ENV: Path(data_dir) / "processed", MODEL_ENV: Path(model_dir) / "previsao"}
    written = []
    for name, dest in targets.items():
        if env.get(name):
            written += sync(env[name], dest, client=client or _client())
    return written


def main() -> None:
    written = sync_from_env(os.environ, data_dir=settings.data_dir, model_dir=settings.model_dir)
    print(f"{len(written)} arquivo(s) baixado(s) do S3", flush=True)


if __name__ == "__main__":
    main()
