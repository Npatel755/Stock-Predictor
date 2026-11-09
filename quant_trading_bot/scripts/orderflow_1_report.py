"""Render reports/ORDERFLOW_1_PILOT.md from reports/ORDERFLOW_1_PILOT.json (pre-registered decision rule in research/orderflow_1/PROTOCOL.md)."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
J = json.load(open(ROOT / "reports" / "ORDERFLOW_1_PILOT.json"))
L = ["# orderflow_1 pilot result: MNQ.c.0 bbo-1s 2023 (pre-registered research/orderflow_1/PROTOCOL.md)", ""]
d = J["data"]
L += ["## Data", f"- RTH rows {d['rows']:,} over {d['days']} sessions; spread mean {d['spread_mean_ticks']} ticks, 1-tick share {d['spread_1tick_share']:.1%}; median L1 size bid {d['bid_sz_med']:.0f} / ask {d['ask_sz_med']:.0f}; last-trade sides {d['side_counts']}.",
      "- Note: the engine's 1-tick spread assumption is optimistic for MNQ (mean 1.5-2.0 ticks RTH 2019-2025 in bbo-1m).", ""]
t1 = J["test1"]
L += ["## Test 1: predictive (30 s mean imbalance decile -> forward mid change, RTH, day-block t)", "", "| horizon | slope (ticks per unit imb) | t | top-minus-bottom decile (ticks) | RT cost (ticks) | bottom..top decile means |", "|---|---:|---:|---:|---:|---|"]
for h in (10, 60, 300):
    r = t1[f"imb30_h{h}"]
    L.append(f"| {h} s | {r['slope']} | {r['t_dayblock']} | {r['top_minus_bottom_ticks']} | {r['rt_cost_ticks']} | {r['decile_means_ticks']} |")
L += ["", f"Time-of-day baseline R²: 10 s {t1['tod_baseline_h10_r2']}, 60 s {t1['tod_baseline_h60_r2']}, 300 s {t1['tod_baseline_h300_r2']}.", ""]
for key, title in (("test2_with_imbalance", "Test 2: executable rule WITH imbalance (18 configs, 20 placebos each)"), ("test3_against_imbalance", "Test 3: executable rule AGAINST imbalance")):
    L += [f"## {title}", "", "| q | hold s | stop ticks | net $ | trades | $/trade | months>0 /12 | placebo mean ± sd | placebo p |", "|---:|---:|---:|---:|---:|---:|---:|---|---:|"]
    for r in J[key]:
        L.append(f"| {r['q']} | {r['hold_s']} | {r['stop_ticks']:.0f} | {r['net']:,.0f} | {r['trades']:,} | {r['per_trade']} | {r['months_pos']} | {r['placebo_mean']:,.0f} ± {r['placebo_sd']:,.0f} | {r['placebo_p']} |")
    L.append("")
best2 = max(J["test2_with_imbalance"] + J["test3_against_imbalance"], key=lambda r: r["net"])
sig1 = any(abs(t1[f"imb30_h{h}"]["t_dayblock"]) > 4 and t1[f"imb30_h{h}"]["top_minus_bottom_ticks"] > t1[f"imb30_h{h}"]["rt_cost_ticks"] for h in (60, 300))
exe = any(r["net"] > 0 and r["months_pos"] >= 9 and r["placebo_p"] < 0.05 for r in J["test2_with_imbalance"] + J["test3_against_imbalance"])
verdict = "SUPPORTED" if sig1 and exe else ("PROXY-ONLY" if sig1 else "REJECTED")
L += ["## Decision (rule fixed in protocol)", f"- Test 1 significant beyond cost: **{sig1}**. Executable config net>0, >=9/12 months, placebo p<0.05: **{exe}**.",
      f"- Best executable config: q={best2['q']} hold={best2['hold_s']}s stop={best2['stop_ticks']:.0f} contra={best2['contra']}: net ${best2['net']:,.0f} on {best2['trades']:,} trades.",
      f"- **Verdict: {verdict}.** No further Databento spend on this hypothesis; 2024-2026 data of any schema untouched; nothing promoted to paper.", ""]
(ROOT / "reports" / "ORDERFLOW_1_PILOT.md").write_text("\n".join(L)); print(verdict)
