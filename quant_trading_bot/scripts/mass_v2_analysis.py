"""Descriptive analysis of the mass_v2 training run (reads runs/mass_v2/results.sqlite; training data only).

Writes reports/MASS_V2_ANALYSIS.md: gate-failure attribution, years-positive distribution, nearest misses per
instrument (research-only, NOT candidates - the pre-registered gate is the only path to validation).
"""
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import os
SUFFIX = os.environ.get('MASS_V2_SUFFIX', '')
con = sqlite3.connect(f"file:{ROOT / f'runs/mass_v2/results{SUFFIX}.sqlite'}?mode=ro", uri=True)
df = pd.read_sql("SELECT * FROM results", con)
df["annual_l"] = df.annual.map(json.loads)
n = len(df)
lines = [f"# mass_v2 training analysis ({n:,} configurations, ES/NQ 2010-2023 as MES/MNQ, 1 contract, today's costs; bar rule: {SUFFIX.strip('_') or 'strict'})\n"]
g = dict(G1_net_pos=(df.net > 0), G1_years10=(df.years_pos >= 10), G2_dd1k=(df.worst_dd < 1000), G3_trades140=(df.trades >= 140),
         G3_topyear40=(df.top_year_share.notna() & (df.top_year_share <= 0.4)))
lines += ["| gate | configs passing | share |", "|---|---:|---:|"]
for k, m in g.items():
    lines.append(f"| {k} | {int(m.sum()):,} | {m.mean():.2%} |")
allg = np.logical_and.reduce(list(g.values()))
lines.append(f"| all G1-G3 | {int(allg.sum()):,} | {allg.mean():.3%} |")
lines += ["\n## Years positive (of 14) across all configurations\n", "| +years | configs |", "|---|---:|"]
for k, v in df.years_pos.value_counts().sort_index(ascending=False).items():
    lines.append(f"| {k} | {v:,} |")
lines += ["\n## Positive-net configurations by instrument and family\n", "| instrument | family | configs | net>0 | +years>=10 | best net | best +years |", "|---|---|---:|---:|---:|---:|---:|"]
for (inst, fam), s in df.groupby(["instrument", "family"]):
    lines.append(f"| {inst} | {fam} | {len(s):,} | {int((s.net > 0).sum()):,} | {int((s.years_pos >= 10).sum())} | {s.net.max():,.0f} | {s.years_pos.max()} |")
for inst in sorted(df.instrument.unique()):
    s = df[(df.instrument == inst) & (df.net > 0)].copy()
    s = s.drop_duplicates("fp").sort_values(["years_pos", "net"], ascending=False).head(12)
    lines += [f"\n## {inst}: nearest misses (unique trade fingerprints; research-only, none passed the gate)\n",
              "| rule | net 14y | +yrs | worst DD | trades | $/trade | top-year share | best year | failed |", "|---|---:|---:|---:|---:|---:|---:|---|---|"]
    for r in s.itertuples():
        ann = r.annual_l
        best_y = 2010 + int(np.argmax(ann))
        failed = [k for k, m in g.items() if not m.loc[r.Index]]
        rule = f"{r.family} lb{r.lookback} th{r.threshold} {r.session_start}-{r.session_end} stop{r.stop_atr} tgt{r.target_r} hold{r.hold_bars} trail{r.trailing_atr}"
        lines.append(f"| {rule} | {r.net:,.0f} | {r.years_pos} | {r.worst_dd:,.0f} | {r.trades} | {r.per_trade:.1f} | {'-' if pd.isna(r.top_year_share) else f'{r.top_year_share:.2f}'} | {best_y} ({max(ann):,.0f}) | {', '.join(failed)} |")
pos = df[df.net > 0]
if len(pos):
    share2020 = pos.annual_l.map(lambda a: a[10] / sum(a) if sum(a) > 0 else np.nan)
    lines.append(f"\nAmong the {len(pos):,} net-positive configurations, the 2020 year supplies a median {np.nanmedian(share2020):.0%} of total 14-year profit "
                 f"(2020 is the year the earlier 2020-2023 searches weighted most).")
out = ROOT / "reports" / f"MASS_V2_ANALYSIS{SUFFIX.upper()}.md"
out.write_text("\n".join(lines) + "\n")
print("\n".join(lines[:12]), "...", f"\nwritten {out}")
