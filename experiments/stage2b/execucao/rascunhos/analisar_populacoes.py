"""Confere o relatório de populações contra a verificação aprovada e projeta memória.

Coeficientes históricos do handoff da sessão 01 (estimativas, não medições deste relatório):
84 B/linha de trecho materializado, 148 B/linha de CSR, 556 B/linha no pico de fit_transform.
"""

import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
verif = json.load(
    open(
        r"Y:\CurtaMap Etapa 2B\execucao\verificacoes\dataset-noturno_dia_util-eolica-v2-002.json",
        encoding="utf-8",
    )
)
GiB = 1024**3
cells = {(c["round"], c["segment"], c["task"]): c for c in report["populations"]}
rounds = ["V1", "V2", "V3", "V4"]
tasks = ["corte_positivo", "restricao_registrada", "volume_condicional", "causa"]
segs = ["initial", "tuning", "refit", "calibration", "validation"]

checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))


check("status", report["status"] == "complete", report["status"])
check("partições", report["completed_partitions"] == 942, report["completed_partitions"])
check("linhas", report["dataset_rows"] == 339_738_048, report["dataset_rows"])
check("dias sem partição", report["days_without_partition"] == ["2023-10-01"],
      report["days_without_partition"])
check("first_t0", str(report["first_t0"]).startswith("2023-10-02") and "19:30" in str(report["first_t0"]),
      report["first_t0"])
ent = report["distributions"]["entity"]
check("entidades", len(ent) == 180, len(ent))
hz = report["distributions"]["horizon"]
check("horizontes", len(hz) == 48 and all(h["rows"] == 7_077_876 for h in hz),
      sorted({h["rows"] for h in hz}))
expected_pred = {"V1": 42_851_184, "V2": 43_830_768, "V3": 43_109_184, "V4": 42_194_016}
for r in rounds:
    for t in tasks:
        c = cells[(r, "validation", t)]
        check(f"prediction_rows {r} {t}", c["prediction_rows"] == expected_pred[r], c["prediction_rows"])
v4max = max(str(cells[("V4", "validation", t)]["t0_max"]) for t in tasks)
check("V4 t0_max <= 2026-04-30 00:00", v4max <= "2026-04-30T00:00:00", v4max)
for r in rounds:
    for t in tasks:
        i, rf = cells[(r, "initial", t)]["rows"], cells[(r, "refit", t)]["rows"]
        check(f"refit>=initial {r} {t}", rf >= i, (i, rf))
        for s in ("volume_condicional", "causa"):
            c = cells[(r, "calibration", s)]
            check(f"calib não usada {r} {s}", c["used"] is False and c["rows"] is None, c["used"])
for r in rounds:
    b, vb = report["boundaries"][r], verif["validation_boundaries"][r]
    for mine, theirs in (
        ("tuning_start", "internal_tuning_start"),
        ("calibration_start", "internal_calibration_start"),
        ("cutoff", "internal_cutoff"),
        ("validation_start", "start"),
        ("validation_end", "end_exclusive"),
        ("last_validation_emission_inclusive", "last_emission"),
    ):
        check(f"fronteira {r} {mine}", str(b[mine]).replace(" ", "T") == vb[theirs],
              (b[mine], vb[theirs]))
print("== Checagens ==")
fails = [c for c in checks if not c[1]]
print(f"{len(checks) - len(fails)}/{len(checks)} aprovadas")
for c in fails:
    print("FALHA", c)
print(json.dumps(report["boundaries"], indent=1, default=str, ensure_ascii=False))
print("verificação (rodadas):", json.dumps(verif.get("rounds", verif.get("round_boundaries", "?")),
                                           default=str, ensure_ascii=False)[:1500])

print("\n== Contagens (rows) por rodada × segmento × tarefa ==")
for r in rounds:
    print(f"-- {r}")
    for s in segs:
        row = []
        for t in tasks:
            c = cells[(r, s, t)]
            row.append("—" if c["rows"] is None else f"{c['rows']:,}".replace(",", "."))
        extra = ""
        c0 = cells[(r, s, "corte_positivo")]
        extra = f" t0[{c0['t0_min']} .. {c0['t0_max']}]"
        print(f"{s:12s} " + " | ".join(f"{x:>13s}" for x in row) + extra)
    print(
        "  validação eligible_rows:",
        {t: cells[(r, "validation", t)]["eligible_rows"] for t in tasks},
        "observed:",
        {t: cells[(r, "validation", t)]["observed_rows"] for t in tasks},
        "pos_volume:",
        cells[(r, "validation", "volume_condicional")]["positive_volume_rows"],
    )
    for s in ("initial", "refit"):
        c = cells[(r, s, "corte_positivo")]
        print(f"  prevalência {s} corte_positivo: {c['positive_rows'] / c['rows']:.4f}"
              if c["rows"] else "")

print("\n== Projeção (GiB) ==")
B_CHUNK, B_CSR, B_FIT = 84, 148, 556
for r in rounds:
    for t in tasks:
        I = cells[(r, "initial", t)]["rows"]
        T = cells[(r, "tuning", t)]["rows"]
        R = cells[(r, "refit", t)]["rows"]
        Ca = cells[(r, "calibration", t)]["rows"] or 0
        resident = B_CHUNK * (I + T + R + Ca)
        fit_initial = B_FIT * I + B_CSR * T
        fit_refit = B_FIT * R
        peak = resident + max(fit_initial, fit_refit)
        print(
            f"{r} {t:21s} residente={resident / GiB:6.1f} fit_inicial={fit_initial / GiB:6.1f} "
            f"fit_refit={fit_refit / GiB:6.1f} pico≈{peak / GiB:6.1f}"
        )
