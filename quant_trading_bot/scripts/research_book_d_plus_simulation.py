"""Research Book D+ (Overnight Dip v2 + Grand Champion Architecture D+).
STRICTLY TRAINING DATA ONLY: 2010-2023.
Zero access to Validation (2024-2025) or Blind Test (2026).

Combines:
- Overnight Leg: overnight_dip_v2 (1 MNQ long 18:05 -> 09:45 ET when both MNQ & MES reopen <= -0.5 sd below 16:00 close)
- Intraday Leg: Architecture D+ (Crabel 15m at 10:00 ET + MNQ 30m trend + MNQ 60m trend + MES 30m idle trend; CBOE VIX backwardation gate on morning sleeves)
- Global strict 1-contract ceiling.
"""
import json, sys, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import mass_1m_search as m1

print("1. Loading Overnight Dip v2 Data...", flush=True)
src3 = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("out = {")[0]
n3 = {"__file__": str(ROOT / "scripts/overnight_3_pilot.py")}
exec(src3, n3)

mn = n3["nights"]("MNQ")
ms = n3["nights"]("MES")
mg = ms.gap.reindex(mn.index)
msd = ms.sd20.reindex(mn.index)

mask_ovn = ((mn.gap <= -0.5 * mn.sd20) & (mg <= -0.5 * msd)).fillna(False)
p_on = n3["pnl"](mn, "MNQ", ex="x0945")
p_on = p_on[mask_ovn & p_on.notna()]

print(f"Overnight Dip v2: {len(p_on)} nights, Net: ${float(p_on.sum()):.2f}")

# Overnight adverse excursion
b = m1.load_bars("MNQ", 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "low"]]
et = b.timestamp_utc.dt.tz_convert("America/New_York")
b["date"] = et.dt.date
b["sod"] = et.dt.hour * 60 + et.dt.minute
low_open = b[(b.sod >= 570) & (b.sod < 585)].groupby("date").low.min()
dates = np.array(sorted(set(mn.index) | set(low_open.index)))

def next_day(d):
    i = dates.searchsorted(d, side="right")
    return dates[i] if i < len(dates) else None

TV = 2.0
ev = [] # (time, kind, worst_unrealized, realized, sleeve)
for nk, p in p_on.items():
    ex_day = next_day(nk)
    e = float(mn.at[nk, "e1805"])
    lo = min(float(mn.at[nk, "low_night"]), float(low_open.get(ex_day, np.inf)))
    t_in = pd.Timestamp(f"{nk} 18:05", tz="America/New_York")
    t_out = pd.Timestamp(f"{ex_day} 09:45", tz="America/New_York")
    ev.append((t_in, "worst", (lo - e) * TV - 3.0, 0.0, "OVN"))
    ev.append((t_out, "close", 0.0, float(p), "OVN"))

print("\n2. Loading Architecture D+ Intraday Trades...", flush=True)
import research_vix_gate_architecture_d_train as r_vix

# Run simulation with morning MNQ VIX gate
sim_res = r_vix.run_simulation(gate_morning_mnq=True, gate_mes=False)
print(f"Architecture D+ Intraday: {sim_res['tot_trades']} trades, Net: ${sim_res['total_net']:.2f}, Max DD: ${sim_res['max_dd']:.2f}")

# Re-run simulation inside r_vix to get execution objects r_c, r_1, r_2, r_mes
s_c = r_vix.sig_crabel.copy()
s_1 = r_vix.sig_1_raw.copy()
s_2 = r_vix.sig_2_raw.copy()
s_m = r_vix.sig_mes_raw.copy()

dates_15 = r_vix.b_mnq_15['date'].to_numpy()
for i in range(len(s_c)):
    if s_c[i] != 0 and r_vix.prior_backw_map.get(dates_15[i], False):
        s_c[i] = 0
dates_30 = r_vix.b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York').dt.date.to_numpy()
for i in range(len(s_1)):
    if s_1[i] != 0 and r_vix.prior_backw_map.get(dates_30[i], False):
        s_1[i] = 0
dates_60 = r_vix.b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York').dt.date.to_numpy()
for i in range(len(s_2)):
    if s_2[i] != 0 and r_vix.prior_backw_map.get(dates_60[i], False):
        s_2[i] = 0

r_c = r_vix.me.execute(r_vix.d_mnq_15, s_c, r_vix.atr_15, r_vix.cfg_c)
act_c_15 = pd.Series(r_c['quantity'] != 0, index=r_vix.b_mnq_15['timestamp_utc'])

act_c_30 = act_c_15.reindex(r_vix.b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
s_1_routed = np.where(~act_c_30, s_1, 0).astype(np.int8)
r_1 = r_vix.me.execute(r_vix.d_mnq_30, s_1_routed, r_vix.f_1['atr'], r_vix.cfg_1)
act_1_30 = pd.Series(r_1['quantity'] != 0, index=r_vix.b_mnq_30['timestamp_utc'])

act_all_60 = (act_c_15.reindex(r_vix.b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | 
              act_1_30.reindex(r_vix.b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
s_2_routed = np.where(~act_all_60, s_2, 0).astype(np.int8)
r_2 = r_vix.me.execute(r_vix.d_mnq_60, s_2_routed, r_vix.f_2['atr'], r_vix.cfg_2)
act_2_60 = pd.Series(r_2['quantity'] != 0, index=r_vix.b_mnq_60['timestamp_utc'])

act_all_mnq = (act_c_15.reindex(r_vix.b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
               act_1_30.reindex(r_vix.b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
               act_2_60.reindex(r_vix.b_mes_30['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
s_mes_routed = np.where(~act_all_mnq, s_m, 0).astype(np.int8)
r_mes = r_vix.me.execute(r_vix.d_mes_30, s_mes_routed, r_vix.f_mes['atr'], r_vix.cfg_mes)

for r, d, b_bar, mult, sl_name in [
    (r_c, r_vix.d_mnq_15, r_vix.b_mnq_15, 2.0, "CRABEL"),
    (r_1, r_vix.d_mnq_30, r_vix.b_mnq_30, 2.0, "MNQ30"),
    (r_2, r_vix.d_mnq_60, r_vix.b_mnq_60, 2.0, "MNQ60"),
    (r_mes, r_vix.d_mes_30, r_vix.b_mes_30, 5.0, "MES30")
]:

    t_entries = r['trade_entry']
    t_exits = r['trade_exit']
    t_nets = r['trade_net']
    t_risk = r.get('trade_stop_risk', np.full(len(t_entries), 150.0))
    
    for i in range(len(t_entries)):
        en_idx = t_entries[i]
        ex_idx = t_exits[i]
        net = float(t_nets[i])
        risk = float(t_risk[i]) if i < len(t_risk) else 150.0
        
        t_en = pd.Timestamp(b_bar['timestamp_utc'].iloc[en_idx]).tz_convert("America/New_York")
        t_ex = pd.Timestamp(b_bar['timestamp_utc'].iloc[ex_idx]).tz_convert("America/New_York")
        
        ev.append((t_en, "worst", -risk, 0.0, sl_name))
        ev.append((t_ex, "close", 0.0, net, sl_name))

print(f"\nTotal combined event markers: {len(ev)}")
ev.sort(key=lambda x: x[0])

# 3. Simulate Combined Equity and Intraday Trailing Drawdown
closed = 0.0
hwm = 0.0
worst_tdd = 0.0
worst_when = None
br = {2000: 0, 2500: 0, 3000: 0}
in_breach = {f: False for f in br}
day_worst = {}
yearly_pnl = {}

for ts, kind, unreal, real, sl_name in ev:
    if kind == "worst":
        eq = closed + unreal
    else:
        closed += real
        eq = closed
        hwm = max(hwm, eq)
        yr = ts.year
        yearly_pnl[yr] = yearly_pnl.get(yr, 0.0) + real
        
    tdd = hwm - eq
    d = ts.date()
    day_worst[d] = min(day_worst.get(d, 0.0), eq - (closed - real if kind == "close" else closed))
    
    if tdd > worst_tdd:
        worst_tdd = tdd
        worst_when = str(ts)
        
    for f in br:
        if tdd >= f and not in_breach[f]:
            br[f] += 1
            in_breach[f] = True
        if tdd < f * 0.5:
            in_breach[f] = False

print("\n" + "=" * 90)
print("BOOK D+ PERFORMANCE SUMMARY (2010-2023 TRAINING DATA)")
print("=" * 90)
print(f"Closed Net Profit:              +${closed:.2f}")
print(f"Total Completed Trades/Nights:   {len(p_on) + sim_res['tot_trades']}")
print(f"Per-Unit Expectancy:            +${closed / (len(p_on) + sim_res['tot_trades']):.2f}/unit")
print(f"Marked Intraday-Trailing DD:     ${worst_tdd:.2f}")
print(f"Safety Cushion under $2k Floor: +${2000.0 - worst_tdd:.2f}")
print(f"Breaches of $2,000 Floor:        {br[2000]}")
print(f"Winning Calendar Years:          {sum(1 for v in yearly_pnl.values() if v > 0)} / {len(yearly_pnl)}")
print(f"Pre-2020 Net Profit:            +${sum(v for y, v in yearly_pnl.items() if y < 2020):.2f}")
print(f"Post-2020 Net Profit:           +${sum(v for y, v in yearly_pnl.items() if y >= 2020):.2f}")
print("=" * 90)

print("\nAnnual Breakdown:")
for y in sorted(yearly_pnl.keys()):
    print(f"  {y}: +${yearly_pnl[y]:.2f}")
