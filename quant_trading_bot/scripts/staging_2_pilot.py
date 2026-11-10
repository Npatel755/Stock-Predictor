"""staging_2: gap-sized D+ as the ladder's opening leg (research/staging_2/PROTOCOL.md), training 2010-23 only."""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
S1 = (ROOT / "scripts/staging_1_pilot.py").read_text()
ns = {"__file__": str(ROOT / "scripts/staging_1_pilot.py")}
exec(S1.split("# --- L3 D+ v2")[0], ns)                      # L1 + L2 trades, skew_below, NY, END
trades, NY, END, skew_below = ns["trades"], ns["NY"], ns["END"], ns["skew_below"]
d4 = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\ncrab = [")[0]; n4 = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}; exec(d4, n4)
for t in n4["base"]:
    trades.append(dict(leg="L3", t_in=pd.Timestamp(t["entry_ts"]).tz_convert(NY), t_out=pd.Timestamp(t["exit_ts"]).tz_convert(NY), worst=-float(t["stop_risk"]), net=float(t["net"]), gap2=bool(t["cont"])))
trades = [t for t in trades if t["t_out"] < END]; trades.sort(key=lambda t: t["t_in"])
for i, t in enumerate(trades): t["id"] = i; t["day"] = t["t_in"].date(); t["skew"] = skew_below(t["t_in"]); t.setdefault("gap2", False)
print({l: (sum(1 for t in trades if t["leg"] == l), round(sum(t["net"] for t in trades if t["leg"] == l), 2)) for l in ("L1", "L2", "L3")}, "gap2", sum(t["gap2"] for t in trades), flush=True)
ns["trades"] = trades
exec(S1.split("# --- policy engine")[1].split("POL = {")[0], ns)   # FLOOR, BOOK, SKEWBOOK, config, mult, run
BOOK, SKEWBOOK = ns["BOOK"], ns["SKEWBOOK"]
def config(policy, locked, cushion):
    pre = policy["pre"]
    if not policy.get("staged") or not locked or cushion < 500: return pre
    if cushion < 1500: return BOOK
    if cushion < 3000: return SKEWBOOK
    return "skew+L3G" if policy.get("gap") else "skew+L3"
def mult(cfg, t):
    if cfg == SKEWBOOK: return (2 if t["skew"] else 1) if t["leg"] in ("L1", "L2") else 0
    if cfg in ("skew+L3", "skew+L3G"): return ((2 if t["skew"] else 1) if t["leg"] in ("L1", "L2") else (2 if (cfg == "skew+L3G" and t["gap2"]) else 1))
    if cfg == "L3G": return (2 if t["gap2"] else 1) if t["leg"] == "L3" else 0
    return cfg.get(t["leg"], 0)
ns["config"], ns["mult"] = config, mult; run = ns["run"]
POL = {"S_3": dict(pre={"L3": 1}), "S_3G": dict(pre="L3G"), "P_L3": dict(pre={"L3": 1}, staged=True), "P_L3G": dict(pre="L3G", staged=True, gap=True)}
starts = pd.date_range("2010-01-01", "2023-01-01", freq="MS", tz=NY); out = {}
for name, pol in POL.items():
    res = {}
    for variant in ("A", "B"):
        rows = []
        for s0 in starts:
            e0 = s0 + pd.DateOffset(months=12); tr = [t for t in trades if s0 <= t["t_in"] < e0]
            r = run(pol, tr, variant, horizon_end=e0); rows.append(dict(start=str(s0.date()), **r))
        df = pd.DataFrame(rows); surv = df.breached.isna()
        res[variant] = dict(n_starts=len(df), survival=round(float(surv.mean()), 3), median_net_12m=round(float(df.closed[surv].median()), 2),
                            p10_net_12m=round(float(df.closed[surv].quantile(0.1)), 2), locked_share=round(float(df.lock_ts.notna().mean()), 3),
                            breach_starts=[r["start"] for r in rows if r["breached"]][:30])
        full = run(pol, trades, variant, restart=True); res[variant]["full_path_2010_23"] = dict(closed=full["closed"], n_breach=full["n_breach"], first_breach=full["breached"])
    out[name] = res; print(name, {v: {k: res[v][k] for k in ("survival", "median_net_12m", "p10_net_12m", "locked_share")} for v in res}, res["A"]["full_path_2010_23"], flush=True)
rng = np.random.default_rng(7); days = sorted(set(t["day"] for t in trades)); by_day = {}
for t in trades: by_day.setdefault(t["day"], []).append(t)
def synth_path():
    seq = []; n = 0
    while n < 252:
        i = rng.integers(0, len(days) - 20); seq.extend(days[i:i + 20]); n += 20
    base = pd.Timestamp("2030-01-04", tz=NY); outt = []; k = 0
    for d in seq[:252]:
        off = base + pd.Timedelta(days=k); k += 1
        for t in by_day.get(d, []):
            dur = t["t_out"] - t["t_in"]; tin = off + (t["t_in"] - pd.Timestamp(t["t_in"].date(), tz=NY)); outt.append(dict(t, t_in=tin, t_out=tin + dur))
    return outt
boot = {n: {"A": 0, "B": 0} for n in POL}; NB = 2000
for p in range(NB):
    sp = synth_path()
    for n, pol in POL.items():
        for v in ("A", "B"):
            if run(pol, sp, v)["breached"]: boot[n][v] += 1
for n in POL: out[n]["bootstrap_breach_1y"] = {v: round(boot[n][v] / NB, 3) for v in ("A", "B")}
print({n: out[n]["bootstrap_breach_1y"] for n in POL}, flush=True)
a, g = out["P_L3"], out["P_L3G"]
gates = dict(survival=g["A"]["survival"] >= a["A"]["survival"], boot=g["bootstrap_breach_1y"]["A"] <= 0.01, median=g["A"]["median_net_12m"] >= 1.2 * a["A"]["median_net_12m"], p10=g["A"]["p10_net_12m"] >= a["A"]["p10_net_12m"])
out["gates"] = {k: bool(v) for k, v in gates.items()}; out["pass"] = all(gates.values()); print("gates", out["gates"], flush=True)
json.dump(out, open(ROOT / "reports/STAGING_2_TRAINING.json", "w"), indent=1, default=str); print("DONE", flush=True)
