"""Inventário (caminho relativo, tamanho, SHA-256) da raiz externa da Etapa 2B.

Arquivos listados em `checksums.json` de runs já auditadas (auditoria-runs-2b-001, checksums
recalculados e íntegros) reutilizam o SHA-256 registrado; todos os demais são calculados aqui.
Exclui `temporarios/`, `worktrees/`, `handoff/` (hashes próprios em SHA256SUMS-handoff.txt),
`execucao/CHECKPOINT-*.md` (log vivo) e o diretório do próprio passo (logs em escrita).
Versão 2: substitui inventario-2b-001, que incluía arquivos ainda em escrita.
"""

import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("Y:/CurtaMap Etapa 2B")
INCLUDE = ["experimentos", "execucao", "cache", "sondas", "env.ps1"]
SELF_STEP = "execucao/passos/inventario-2b-002/"


def excluded(rel):
    return rel.startswith(SELF_STEP) or (rel.startswith("execucao/CHECKPOINT-") and rel.endswith(".md"))
AUDIT = ROOT / "execucao" / "verificacoes" / "auditoria-runs-2b-001.json"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main(out_csv, out_json):
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    verified = {}
    for group in ("main", "sensitivity"):
        for run_id, a in audit[group].items():
            if not a["checksums"]["ok"]:
                continue
            cs = json.loads((ROOT / "experimentos" / run_id / "checksums.json").read_text(encoding="utf-8"))
            for rel, digest in cs["files"].items():
                verified[f"experimentos/{run_id}/{rel}"] = digest

    skip = {Path(out_csv).resolve(), Path(out_json).resolve()}
    rows, totals = [], defaultdict(lambda: [0, 0])
    for item in INCLUDE:
        base = ROOT / item
        files = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file())
        for p in files:
            if p.resolve() in skip:
                continue
            rel = p.relative_to(ROOT).as_posix()
            if excluded(rel):
                continue
            size = p.stat().st_size
            if rel in verified:
                digest, origin = verified[rel], "checksums.json verificado"
            else:
                digest, origin = sha256(p), "calculado"
            rows.append((rel, size, digest, origin))
            parts = rel.split("/")
            key = "/".join(parts[:2]) if parts[0] in ("experimentos", "execucao") and len(parts) > 2 else parts[0]
            totals[key][0] += 1
            totals[key][1] += size
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["caminho_relativo", "bytes", "sha256", "origem_hash"])
        w.writerows(rows)
    summary = {
        "root": str(ROOT),
        "files": len(rows),
        "bytes": sum(r[1] for r in rows),
        "hash_reused_from_verified_checksums": sum(1 for r in rows if r[3] != "calculado"),
        "hash_computed": sum(1 for r in rows if r[3] == "calculado"),
        "excluded": ["temporarios/", "worktrees/", "handoff/", "execucao/CHECKPOINT-*.md", SELF_STEP],
        "supersedes": "inventario-2b-001 (handoff/inventario-etapa-2b-001.csv)",
        "groups": {k: {"files": v[0], "bytes": v[1]} for k, v in sorted(totals.items())},
        "csv_sha256": sha256(out_csv),
    }
    Path(out_json).write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("files", "bytes", "hash_reused_from_verified_checksums", "hash_computed")}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
