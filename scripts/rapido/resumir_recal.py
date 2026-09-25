"""Aplica a regra pré-registrada (`docs/reports/rapido/recalibracao-regra.md`) às simulações."""

import json
from pathlib import Path

EXP = Path(__file__).resolve().parents[2] / "experiments" / "stage2b" / "experimentos"
results = [json.loads(p.read_text("utf-8")) for p in sorted((EXP / "rapido-recal").glob("*.json"))]

for source in ("fotovoltaica", "eolica"):
    rows = sorted(
        (r for r in results if r["source"] == source and r["task"] == "corte_positivo"),
        key=lambda r: r["round"],
    )
    if rows:
        print(f"\n## Corte {source}: recalibrado × congelado × historico")
        print("rodada | AP cong/recal/hist | ΔAP | Brier cong/recal/hist | ΔBrier | IC sem.")
        for r in rows:
            f, c, h = r["frozen"], r["recal"], r["historico"]
            w = r["weekly_ap_diff_recal_vs_historico"]
            print(
                f"{r['round']} | {f['ap']:.4f}/{c['ap']:.4f}/{h['ap']:.4f} | "
                f"{c['ap'] - f['ap']:+.4f} | {f['brier']:.4f}/{c['brier']:.4f}/{h['brier']:.4f} | "
                f"{c['brier'] - f['brier']:+.4f} | {w['wins']}/{w['weeks']} "
                f"[{w['ci95'][0]:+.3f}, {w['ci95'][1]:+.3f}]"
            )
        by = {r["round"]: r for r in rows}
        if "V2" in by:
            v2 = by["V2"]["frozen"]["brier"] - by["V2"]["recal"]["brier"]
            worst_brier = max(r["recal"]["brier"] - r["frozen"]["brier"] for r in rows)
            worst_ap = min(r["recal"]["ap"] - r["frozen"]["ap"] for r in rows)
            ok = v2 >= 0.02 and worst_brier <= 0.005 and worst_ap >= -0.005
            print(
                f"regra: queda Brier V2 {v2:+.4f} (≥0,02) | pior ΔBrier {worst_brier:+.4f} "
                f"(≤0,005) | pior ΔAP {worst_ap:+.4f} (≥−0,005) → "
                f"{'ADOTA' if ok else 'REPROVA'}"
            )

    rows = sorted(
        (r for r in results if r["source"] == source and r["task"] == "volume_total"),
        key=lambda r: r["round"],
    )
    if rows:
        cid = rows[0]["comparator_id"]
        print(f"\n## Volume {source}: recalibrado × congelado × {cid}")
        print("rodada | MAE cong/recal/comp | variação recal | WAPE recal/comp | viés cong/recal")
        for r in rows:
            f, c, b = r["frozen"], r["recal"], r["comparator"]
            print(
                f"{r['round']} | {f['mae']:.2f}/{c['mae']:.2f}/{b['mae']:.2f} | "
                f"{c['mae'] / b['mae'] - 1:+.1%} | {c['wape']:.3f}/{b['wape']:.3f} | "
                f"{f['bias']:+.2f}/{c['bias']:+.2f}"
            )
        if len(rows) == 4:
            mae = sum(r["recal"]["mae"] for r in rows) / sum(r["comparator"]["mae"] for r in rows)
            wape = sum(r["recal"]["wape"] for r in rows) <= sum(
                r["comparator"]["wape"] for r in rows
            )
            wins = sum(r["recal"]["mae"] < r["comparator"]["mae"] for r in rows)
            worst = max(r["recal"]["mae"] / r["comparator"]["mae"] - 1 for r in rows)
            ok = mae - 1 <= -0.05 and wape and wins >= 3 and worst <= 0.10
            print(
                f"§11: MAE médio {mae - 1:+.2%} (≤−5%) | WAPE não pior {wape} | "
                f"{wins}/4 melhores | pior rodada {worst:+.1%} (≤+10%) → "
                f"{'PASSA' if ok else 'NÃO PASSA'}"
            )

causes = sorted((r for r in results if r["task"] == "causa"), key=lambda r: r["round"])
if causes:
    print("\n## Causa: diferença semanal de macro-F1")
    for r in causes:
        for key in ("weekly_macro_f1_diff_vs_historico", "weekly_macro_f1_diff_vs_ultimo_valor"):
            w = r[key]
            print(
                f"{r['source']} {r['round']} {key.rsplit('_vs_', 1)[1]}: média {w['mean']:+.4f} "
                f"{w['wins']}/{w['weeks']} IC [{w['ci95'][0]:+.3f}, {w['ci95'][1]:+.3f}]"
            )
