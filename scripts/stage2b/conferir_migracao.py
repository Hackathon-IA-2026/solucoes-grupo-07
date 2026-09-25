"""Confere a migração da raiz da Etapa 2B para experiments/stage2b.

- Cada arquivo copiado (fora de junctions) tem o mesmo SHA-256 da origem.
- Cada arquivo listado no checksums.json de uma run existe pelo caminho do repositório
  (inclusive através das junctions) com o mesmo tamanho da origem.

Uso: uv run python scripts/stage2b/conferir_migracao.py <origem> <destino>
"""

import hashlib
import json
import os
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def copied_files(dest: Path):
    for root, dirs, files in os.walk(dest):
        dirs[:] = [d for d in dirs if not os.path.isjunction(os.path.join(root, d))]
        for name in files:
            yield Path(root) / name


def main(source: Path, dest: Path) -> int:
    problems, copied = [], 0
    for path in copied_files(dest):
        rel = path.relative_to(dest)
        origin = source / rel
        copied += 1
        if not origin.exists():
            problems.append(f"sem origem: {rel}")
        elif sha256(path) != sha256(origin):
            problems.append(f"hash diferente: {rel}")
    listed = 0
    for cs in (dest / "experimentos").glob("*/checksums.json"):
        run = cs.parent
        for rel in json.loads(cs.read_text(encoding="utf-8"))["files"]:
            listed += 1
            here, there = run / rel, source / "experimentos" / run.name / rel
            if not here.exists():
                problems.append(f"ausente no repo: {run.name}/{rel}")
            elif here.stat().st_size != there.stat().st_size:
                problems.append(f"tamanho diferente: {run.name}/{rel}")
    print(json.dumps({"copied_files": copied, "checksum_entries": listed, "problems": problems}))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
