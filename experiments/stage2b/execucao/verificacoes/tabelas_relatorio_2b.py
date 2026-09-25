"""Gera tabelas factuais (recorte global) das runs 2B para o relatório de handoff.

Somente leitura. Sem ranking: apenas valores registrados nos arquivos de métricas.
"""

import json
import sys
from pathlib import Path

EXP = Path("Y:/CurtaMap Etapa 2B/experimentos")
MAIN = {
    ("eolica", "V1"): "main-eolica-v1-002",
    ("eolica", "V2"): "main-eolica-v2-004",
    ("eolica", "V3"): "main-eolica-v3-001",
    ("eolica", "V4"): "main-eolica-v4-001",
    ("fotovoltaica", "V1"): "main-fotovoltaica-v1-001",
    ("fotovoltaica", "V2"): "main-fotovoltaica-v2-001",
    ("fotovoltaica", "V3"): "main-fotovoltaica-v3-001",
    ("fotovoltaica", "V4"): "main-fotovoltaica-v4-001",
}
BASE = ["ultimo_valor", "mesmo_horario_dia_anterior", "mesmo_horario_recente", "historico"]


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def glob_(rows):
    return next(r["metrics"] for r in rows if r["slice"] == "global")


def v(m, k):
    x = m.get(k)
    if isinstance(x, dict):
        x = x.get("value")
    return x


def f(x, n=4):
    if x is None:
        return "—"
    if isinstance(x, int):
        return f"{x:,}".replace(",", ".")
    return f"{x:.{n}f}"


def empty_slices(rows):
    out = []
    for r in rows:
        m = r["metrics"]
        s = m.get("support")
        if not s:
            out.append(r["slice"])
    return out


out = []
p = out.append
empties = {}
sens_meta = {}
for (src, rnd), run in MAIN.items():
    d = EXP / run / "metrics"
    delay = EXP / f"delay-{src}-{rnd.lower()}-001"
    rep = load(delay / "reports" / f"sensitivity-{src}-{rnd}.json")
    sens_meta[f"{src}-{rnd}"] = {"models_retrained": rep.get("models_retrained"), "scenario": rep.get("scenario")}
    sd = delay / "metrics"
    p(f"\n#### {src} {rnd} — `{run}` (sensibilidade: `{delay.name}`)\n")
    for task in ("restricao_registrada", "corte_positivo"):
        p(f"\n{task} (recorte global)\n")
        p("| origem | AP | Brier | limiar | precisão | recall | F2 | prevalência | suporte | AP +24h | Brier +24h | recall +24h |")
        p("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for fam in ("linear", "lightgbm"):
            rows = load(d / f"{src}-{rnd}-{task}-{fam}.json")
            m = glob_(rows)
            empties[f"{run}:{task}-{fam}"] = empty_slices(rows)
            srows = load(sd / f"sensitivity-{src}-{rnd}-{task}-{fam}.json")
            s = glob_(srows)
            empties[f"{delay.name}:{task}-{fam}"] = empty_slices(srows)
            p(f"| modelo {fam} | {f(v(m,'average_precision'))} | {f(v(m,'brier'))} | {f(m.get('threshold'))} | {f(v(m,'precision'))} | {f(v(m,'recall'))} | {f(v(m,'f2'))} | {f(m.get('prevalence'))} | {f(m.get('support'))} | {f(v(s,'average_precision'))} | {f(v(s,'brier'))} | {f(v(s,'recall'))} |")
        for b in BASE:
            m = glob_(load(d / f"{src}-{rnd}-baseline-{b}-{task}.json"))
            p(f"| baseline {b} | {f(v(m,'average_precision'))} | {f(v(m,'brier'))} | {f(m.get('threshold'))} | {f(v(m,'precision'))} | {f(v(m,'recall'))} | {f(v(m,'f2'))} | {f(m.get('prevalence'))} | {f(m.get('support'))} | — | — | — |")
    p("\nvolume (recorte global; MAE em MWmed)\n")
    p("| origem | MAE total | MAE condicional | WAPE | viés | cobertura | suporte | MAE total +24h | WAPE +24h |")
    p("|---|---|---|---|---|---|---|---|---|")
    names = [f"volume-{a}-{b}" for a in ("linear", "lightgbm") for b in ("linear", "lightgbm")] + [
        f"volume_condicional-{a}" for a in ("linear", "lightgbm")
    ]
    for n in names:
        rows = load(d / f"{src}-{rnd}-{n}.json")
        m = glob_(rows)
        empties[f"{run}:{n}"] = empty_slices(rows)
        s = glob_(load(sd / f"sensitivity-{src}-{rnd}-{n}.json"))
        p(f"| {n} | {f(v(m,'mae_full'),2)} | {f(v(m,'mae_conditional'),2)} | {f(v(m,'wape'))} | {f(v(m,'bias'),2)} | {f(m.get('coverage'))} | {f(m.get('support'))} | {f(v(s,'mae_full'),2)} | {f(v(s,'wape'))} |")
    for b in BASE:
        m = glob_(load(d / f"{src}-{rnd}-baseline-{b}-volume_pipeline.json"))
        p(f"| baseline {b} | {f(v(m,'mae_full'),2)} | {f(v(m,'mae_conditional'),2)} | {f(v(m,'wape'))} | {f(v(m,'bias'),2)} | {f(m.get('coverage'))} | {f(m.get('support'))} | — | — |")
    p("\ncausa (recorte global)\n")
    p("| origem | macro-F1 | recall REL | recall CNF | recall ENE | suporte | macro-F1 +24h |")
    p("|---|---|---|---|---|---|---|")
    for fam in ("linear", "lightgbm"):
        rows = load(d / f"{src}-{rnd}-causa-{fam}.json")
        m = glob_(rows)
        empties[f"{run}:causa-{fam}"] = empty_slices(rows)
        s = glob_(load(sd / f"sensitivity-{src}-{rnd}-causa-{fam}.json"))
        pc = m.get("per_class", {})
        p(f"| modelo {fam} | {f(v(m,'macro_f1'))} | {f(pc.get('REL',{}).get('recall'))} | {f(pc.get('CNF',{}).get('recall'))} | {f(pc.get('ENE',{}).get('recall'))} | {f(m.get('support'))} | {f(v(s,'macro_f1'))} |")
    for b in BASE:
        m = glob_(load(d / f"{src}-{rnd}-baseline-{b}-causa.json"))
        pc = m.get("per_class", {})
        p(f"| baseline {b} | {f(v(m,'macro_f1'))} | {f(pc.get('REL',{}).get('recall'))} | {f(pc.get('CNF',{}).get('recall'))} | {f(pc.get('ENE',{}).get('recall'))} | {f(m.get('support'))} | — |")

Path(sys.argv[1]).write_text("\n".join(out) + "\n", encoding="utf-8")
summary = {
    "sensitivity_meta": sens_meta,
    "empty_slices": {k: v_ for k, v_ in empties.items() if v_},
}
Path(sys.argv[2]).write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
print(json.dumps(summary["sensitivity_meta"]))
print("arquivos com recortes vazios:", len(summary["empty_slices"]))
cnt = {}
for k, sl in summary["empty_slices"].items():
    for s_ in sl:
        cnt[s_] = cnt.get(s_, 0) + 1
print(cnt)
