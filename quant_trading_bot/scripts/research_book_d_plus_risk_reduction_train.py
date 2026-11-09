"""Research Script: Book D+ Risk Reduction & Margin of Safety on 2010-2023 Training Data.
STRICTLY TRAINING DATA ONLY: 2010-2023.
Zero access to Validation (2024-2025) or Blind Test (2026).

Investigates:
Can the marked intraday trailing drawdown of Book D+ ($1,985.85) be reduced to $1,200-$1,400
(creating a +$600 to +$800 cushion under the $2,000 floor) by:
1. Gating overnight dip on days following CBOE VIX Backwardation (VIX > VIX3M)?
2. Gating overnight dip on days following extreme VIX spike (VIX > 30 or VIX > 35)?
3. Gating overnight dip when prior day S&P/Nasdaq closed down > 2% or 3%?
"""
import json, sys, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import mass_1m_search as m1
import research_vix_gate_architecture_d_train as r_vix

# 1. Overnight Dip Base Data
src3 = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("out = {")[0]
n3 = {"__file__": str(ROOT / "scripts/overnight_3_pilot.py")}
exec(src3, n3)

mn = n3["nights"]("MNQ")
ms = n3["nights"]("MES")
mg = ms.gap.reindex(mn.index)
msd = ms.sd20.reindex(mn.index)

mask_ovn_base = ((mn.gap <= -0.5 * mn.sd20) & (mg <= -0.5 * msd)).fillna(False)
p_on_raw = n3["pnl"](mn, "MNQ", ex="x0945")

# Adverse excursions
b = m1.load_bars("MNQ", 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "low"]]
et = b.timestamp_utc.dt.tz_convert("America/New_York")
b["date"] = et.dt.date
b["sod"] = et.dt.hour * 60 + et.dt.minute
low_open = b[(b.sod >= 570) & (b.sod < 585)].groupby("date").low.min()
dates = np.array(sorted(set(mn.index) | set(low_open.index)))

def next_day(d):
    i = dates.searchsorted(d, side="right")
    return dates[i] if i < len(dates) else None

# Load CBOE VIX data for night filtering
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df['date'] = pd.to_datetime(vix_df['DATE'], format='%m/%d/%Y').dt.date
vix_map = vix_df.set_index('date')['CLOSE'].astype(float).to_dict()

vix3m_path = ROOT / "data/external/VIX3M_History.csv"
vix3m_df = pd.read_csv(vix3m_path)
vix3m_df['date'] = pd.to_datetime(vix3m_df['DATE'], format='%m/%d/%Y').dt.date
vix3m_map = vix3m_df.set_index('date')['CLOSE'].astype(float).to_dict()

cboe_dates = np.array(sorted(list(vix_map.keys())))

def get_cboe_state(night_date):
    # Find last CBOE close strictly before or on this day
    # Since 18:05 ET occurs AFTER the 16:15 CBOE close on the same date,
    # the CBOE close of night_date is point-in-time available by 18:05!
    p = cboe_dates.searchsorted(night_date, side='right') - 1
    if p >= 0:
        d = cboe_dates[p]
        vx = vix_map.get(d, 20.0)
        v3 = vix3m_map.get(d, 20.0)
        return vx, v3, bool(vx > v3)
    return 20.0, 20.0, False

# 2. Intraday Architecture D+ trades
sim_res = r_vix.run_simulation(gate_morning_mnq=True, gate_mes=False)
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

intraday_events = []
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
        en_idx = t_entries[i]; ex_idx = t_exits[i]; net = float(t_nets[i]); risk = float(t_risk[i]) if i < len(t_risk) else 150.0
        t_en = pd.Timestamp(b_bar['timestamp_utc'].iloc[en_idx]).tz_convert("America/New_York")
        t_ex = pd.Timestamp(b_bar['timestamp_utc'].iloc[ex_idx]).tz_convert("America/New_York")
        intraday_events.append((t_en, "worst", -risk, 0.0, sl_name))
        intraday_events.append((t_ex, "close", 0.0, net, sl_name))

# 3. Test Function for Combined Book D+ with Overnight Filters
TV = 2.0
def evaluate_book_d(ovn_filter_type=None, ovn_vix_max=None):
    # Filter overnight nights
    p_on = p_on_raw.copy()
    keep_mask = mask_ovn_base.copy()
    
    if ovn_filter_type == "no_backwardation":
        for nk in mn.index:
            if keep_mask.loc[nk]:
                _, _, is_back = get_cboe_state(nk)
                if is_back:
                    keep_mask.loc[nk] = False
    elif ovn_filter_type == "vix_max" and ovn_vix_max is not None:
        for nk in mn.index:
            if keep_mask.loc[nk]:
                vx, _, _ = get_cboe_state(nk)
                if vx >= ovn_vix_max:
                    keep_mask.loc[nk] = False
    elif ovn_filter_type == "back_and_vix35":
        for nk in mn.index:
            if keep_mask.loc[nk]:
                vx, _, is_back = get_cboe_state(nk)
                if is_back or vx >= 35.0:
                    keep_mask.loc[nk] = False
                    
    p_on = p_on[keep_mask & p_on.notna()]
    
    events = list(intraday_events)
    for nk, p in p_on.items():
        ex_day = next_day(nk)
        e = float(mn.at[nk, "e1805"])
        lo = min(float(mn.at[nk, "low_night"]), float(low_open.get(ex_day, np.inf)))
        t_in = pd.Timestamp(f"{nk} 18:05", tz="America/New_York")
        t_out = pd.Timestamp(f"{ex_day} 09:45", tz="America/New_York")
        events.append((t_in, "worst", (lo - e) * TV - 3.0, 0.0, "OVN"))
        events.append((t_out, "close", 0.0, float(p), "OVN"))
        
    events.sort(key=lambda x: x[0])
    
    closed = 0.0; hwm = 0.0; worst_tdd = 0.0; worst_when = None
    br2000 = 0; in_br2000 = False; yearly_pnl = {}
    
    for ts, kind, unreal, real, sl_name in events:
        if kind == "worst":
            eq = closed + unreal
        else:
            closed += real
            eq = closed
            hwm = max(hwm, eq)
            yr = ts.year
            yearly_pnl[yr] = yearly_pnl.get(yr, 0.0) + real
            
        tdd = hwm - eq
        if tdd > worst_tdd:
            worst_tdd = tdd
            worst_when = str(ts)
        if tdd >= 2000.0 and not in_br2000:
            br2000 += 1
            in_br2000 = True
        if tdd < 1000.0:
            in_br2000 = False
            
    tot_tr = len(p_on) + sim_res['tot_trades']
    exp = closed / tot_tr if tot_tr else 0.0
    cushion = 2000.0 - worst_tdd
    pos_years = sum(1 for v in yearly_pnl.values() if v > 0)
    pre_net = sum(v for y, v in yearly_pnl.items() if y < 2020)
    post_net = sum(v for y, v in yearly_pnl.items() if y >= 2020)
    
    closed_trades = [real for ts, kind, unreal, real, sl_name in events if kind == "close"]
    return dict(net=closed, trades=tot_tr, exp=exp, max_dd=worst_tdd, cushion=cushion,
                breaches=br2000, pos_years=pos_years, pre_net=pre_net, post_net=post_net, worst_when=worst_when,
                ovn_nights=len(p_on), ovn_net=float(p_on.sum()), closed_trades=closed_trades)

print("\n" + "=" * 125)
print(f"{'Variant':<42} | {'Net ($)':<10} | {'Trades':<6} | {'Exp ($)':<8} | {'MarkedDD':<9} | {'Cushion':<9} | {'Pre-2020':<10} | {'Post-2020':<10} | {'Breaches'}")
print("=" * 125)

# Baseline Book D+
b_base = evaluate_book_d(None)
print(f"{'Book D+ (Unfiltered Overnight Leg)':<42} | +${b_base['net']:8.2f} | {b_base['trades']:6d} | +${b_base['exp']:6.2f} | ${b_base['max_dd']:7.2f} | +${b_base['cushion']:7.2f} | +${b_base['pre_net']:8.2f} | +${b_base['post_net']:8.2f} | {b_base['breaches']}")

# 1. No Backwardation on Overnight Leg
b_back = evaluate_book_d("no_backwardation")
print(f"{'Book D+ (Overnight Skip VIX Backwardation)':<42} | +${b_back['net']:8.2f} | {b_back['trades']:6d} | +${b_back['exp']:6.2f} | ${b_back['max_dd']:7.2f} | +${b_back['cushion']:7.2f} | +${b_back['pre_net']:8.2f} | +${b_back['post_net']:8.2f} | {b_back['breaches']}")

# 2. VIX Level Filters on Overnight Leg
for v_lvl in [40.0, 35.0, 30.0, 25.0]:
    b_v = evaluate_book_d("vix_max", ovn_vix_max=v_lvl)
    print(f"{f'Book D+ (Overnight Skip VIX >= {v_lvl})':<42} | +${b_v['net']:8.2f} | {b_v['trades']:6d} | +${b_v['exp']:6.2f} | ${b_v['max_dd']:7.2f} | +${b_v['cushion']:7.2f} | +${b_v['pre_net']:8.2f} | +${b_v['post_net']:8.2f} | {b_v['breaches']}")

# 3. Backwardation + VIX >= 35 on Overnight Leg
b_combo = evaluate_book_d("back_and_vix35")
print(f"{'Book D+ (Skip Backwardation OR VIX >= 35)':<42} | +${b_combo['net']:8.2f} | {b_combo['trades']:6d} | +${b_combo['exp']:6.2f} | ${b_combo['max_dd']:7.2f} | +${b_combo['cushion']:7.2f} | +${b_combo['pre_net']:8.2f} | +${b_combo['post_net']:8.2f} | {b_combo['breaches']}")

print("=" * 125)
