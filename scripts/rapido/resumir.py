"""Resume as runs rápidas (`rapido-*`) numa tabela por fonte, tarefa e rodada."""

import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[2] / "experiments" / "stage2b" / "experimentos"
prefix = sys.argv[1] if len(sys.argv) > 1 else "rapido-"
for path in sorted(EXP.glob(f"{prefix}*/resultado.json")):
    d = json.loads(path.read_text("utf-8"))
    m = d.get("metrics", {})
    w = m.get("weekly_ap_diff", {})
    line = f"{path.parent.name:34s} {d['source']:12s} {d['round']} {d['task']:20s}"
    if "model_ap" in m:
        line += (
            f" AP {m['model_ap']:.4f} vs {m['baseline_historico_ap']:.4f}"
            f" dif {m['model_ap'] - m['baseline_historico_ap']:+.4f}"
            f" Brier {m['model_brier']:.4f} vs {m['baseline_historico_brier']:.4f}"
            f" sem {w.get('wins')}/{w.get('weeks')} IC {[round(x, 3) for x in w.get('ci95', [])]}"
        )
    else:
        line += " " + json.dumps({k: v for k, v in m.items() if k != "rows"})
    line += f" pico {d.get('peak_rss_gib') or 0:.1f}GiB {d.get('phases', {}).get('fim')}s"
    print(line)
