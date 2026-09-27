from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

DATASET_FOLDER_URL = "https://drive.google.com/drive/folders/11mEbcOI69XQsK7bHUJLg-EWo47KNh5VL"
ONS_FOLDER = "Dados - ONS"


class RemoteFile(Protocol):
    id: str
    path: str


@dataclass(frozen=True)
class DownloadItem:
    file_id: str
    remote_path: str
    target: Path


def build_download_plan(
    files: Sequence[RemoteFile],
    output_dir: Path,
    *,
    include_tutorials: bool = False,
) -> list[DownloadItem]:
    """Converte a listagem remota em destinos locais seguros."""
    plan: list[DownloadItem] = []

    for remote in files:
        # No Windows, o gdown devolve caminhos com barra invertida.
        remote_path = PurePosixPath(remote.path.replace("\\", "/"))
        if remote_path.is_absolute() or ".." in remote_path.parts:
            raise ValueError(f"Caminho remoto inseguro: {remote.path}")

        if not include_tutorials and remote_path.parts[0] != ONS_FOLDER:
            continue

        relative = (
            PurePosixPath(*remote_path.parts[1:])
            if remote_path.parts[0] == ONS_FOLDER
            else remote_path
        )
        plan.append(
            DownloadItem(
                file_id=remote.id,
                remote_path=remote.path,
                target=output_dir.joinpath(*relative.parts),
            )
        )

    return plan


def _load_gdown():
    try:
        import gdown
    except ImportError as error:
        raise SystemExit("Dependência ausente. Execute: uv sync --extra data --dev") from error
    return gdown


def discover_files() -> Sequence[RemoteFile]:
    gdown = _load_gdown()
    return gdown.download_folder(
        url=DATASET_FOLDER_URL,
        output="data/raw",
        quiet=True,
        use_cookies=False,
        skip_download=True,
    )


def download(plan: Sequence[DownloadItem], *, force: bool = False) -> None:
    gdown = _load_gdown()
    for item in plan:
        if item.target.exists() and not force:
            print(f"preservado: {item.target}")
            continue

        item.target.parent.mkdir(parents=True, exist_ok=True)
        print(f"baixando: {item.remote_path} -> {item.target}")
        result = gdown.download(
            id=item.file_id,
            output=str(item.target),
            quiet=False,
            use_cookies=False,
            resume=not force,
        )
        if result is None:
            raise RuntimeError(f"Falha ao baixar {item.remote_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Baixa as bases oficiais do Zelo.")
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    parser.add_argument("--include-tutorials", action="store_true")
    parser.add_argument("--list", action="store_true", dest="list_only")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plan = build_download_plan(
        discover_files(),
        output_dir=args.output,
        include_tutorials=args.include_tutorials,
    )

    if args.list_only:
        for item in plan:
            status = "existente" if item.target.exists() else "pendente"
            print(f"{status:9} {item.remote_path} -> {item.target}")
        return

    download(plan, force=args.force)


if __name__ == "__main__":
    main()
