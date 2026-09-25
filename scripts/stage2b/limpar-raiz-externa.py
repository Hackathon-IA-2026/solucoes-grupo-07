"""Reduz a raiz externa da Etapa 2B ao que não cabe no repositório.

Mantém apenas `experimentos/<run>/predictions`, `experimentos/stage2b-datasets` e
`temporarios`. Todo o resto só é removido se cada arquivo tiver cópia com o mesmo SHA-256
em experiments/stage2b (ou se for uma junction/diretório vazio). Sem `--apagar`, apenas relata.

Uso: uv run python scripts/stage2b/limpar-raiz-externa.py [--apagar]
"""

import hashlib
import os
import sys
from pathlib import Path

SOURCE = Path("Y:/CurtaMap Etapa 2B")
REPO = Path(__file__).resolve().parents[2] / "experiments" / "stage2b"
RENAMED = {
    "_migrado-para-repo-20260924-execucao": "execucao",
    "_migrado-para-repo-20260924-handoff": "handoff",
}
# Versão anterior à parametrização; preservada no Git (commit f0e4e5a).
KNOWN_CHANGED = {"_migrado-para-repo-20260924-execucao/run-step.ps1"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def keep(rel: Path) -> bool:
    parts = rel.parts
    if parts[0] == "temporarios":
        return True
    if parts[0] == "experimentos" and len(parts) > 1:
        return parts[1] == "stage2b-datasets" or (len(parts) > 2 and parts[2] == "predictions")
    return False


def repo_path(rel: Path) -> Path:
    first = RENAMED.get(rel.parts[0], rel.parts[0])
    return REPO.joinpath(first, *rel.parts[1:])


def main(delete: bool) -> int:
    links, files, problems = [], [], []
    for root, dirs, names in os.walk(SOURCE):
        root = Path(root)
        for d in list(dirs):
            rel = (root / d).relative_to(SOURCE)
            if keep(rel):
                dirs.remove(d)
            elif os.path.isjunction(root / d):
                links.append(root / d)
                dirs.remove(d)
        for n in names:
            p = root / n
            rel = p.relative_to(SOURCE)
            if keep(rel):
                continue
            files.append(p)
            if rel.as_posix() in KNOWN_CHANGED:
                continue
            q = repo_path(rel)
            if not q.exists():
                problems.append(f"sem cópia no repo: {rel}")
            elif sha256(p) != sha256(q):
                problems.append(f"hash difere: {rel}")
    print(f"junctions a remover: {len(links)}; arquivos a remover: {len(files)}")
    for p in problems:
        print("PROBLEMA", p)
    if problems or not delete:
        return 1 if problems else 0
    for link in links:
        os.rmdir(link)  # remove só o link da junction
    for p in files:
        p.unlink()
    # Diretórios que ficaram vazios, do mais profundo para o mais raso.
    for root, _dirs, _names in sorted(os.walk(SOURCE), key=lambda x: -len(x[0])):
        r = Path(root)
        if r != SOURCE and not keep(r.relative_to(SOURCE)) and not any(r.iterdir()):
            r.rmdir()
    print("limpeza concluída")
    return 0


if __name__ == "__main__":
    sys.exit(main("--apagar" in sys.argv))
