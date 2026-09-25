"""Confere a integridade da raiz da Etapa 2B vista pelo repositório.

Para cada run em `experiments/stage2b/experimentos`, recalcula o SHA-256 de todos os arquivos
listados no `checksums.json`, lendo pelo caminho do repositório: arquivos leves e modelos
estão no próprio repositório; previsões são lidas através das junctions. Também lista as
junctions existentes e para onde apontam.

Uso: uv run python scripts/stage2b/conferir_migracao.py [raiz]   (padrão: experiments/stage2b)
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


def main(root: Path) -> int:
    problems, checked = [], 0
    for cs in sorted((root / "experimentos").glob("*/checksums.json")):
        run = cs.parent
        for rel, expected in json.loads(cs.read_text(encoding="utf-8"))["files"].items():
            checked += 1
            path = run / rel
            if not path.exists():
                problems.append(f"ausente: {run.name}/{rel}")
            elif sha256(path) != expected:
                problems.append(f"hash difere: {run.name}/{rel}")
        status = "PROBLEMA" if any(run.name in p for p in problems) else "ok"
        print(run.name, status, flush=True)
    links = {}
    for dirpath, dirs, _ in os.walk(root):
        for d in list(dirs):
            full = os.path.join(dirpath, d)
            if os.path.isjunction(full):
                links[os.path.relpath(full, root)] = os.readlink(full)
                dirs.remove(d)
    print(
        json.dumps(
            {"checksum_entries": checked, "problems": problems, "junctions": links},
            indent=1,
            ensure_ascii=False,
        )
    )
    return 1 if problems else 0


if __name__ == "__main__":
    default = Path(__file__).resolve().parents[2] / "experiments" / "stage2b"
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else default))
