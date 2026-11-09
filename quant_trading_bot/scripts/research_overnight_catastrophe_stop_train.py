"""Research Script: Overnight Dip Catastrophe Stop Loss Optimization.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Hypothesis:
Can an intra-night catastrophe stop loss (evaluated at 1-minute resolution from 18:05 to 09:45 ET)
eliminate extreme adverse excursions without prematurely stopping out profitable overnight mean-reversion?
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

import mass_1m_search as m1

print("=" * 80)
print("RESEARCH: OVERNIGHT DIP CATASTROPHE STOP LOSS ON 2010-2023 TRAINING DATA")
print("=" * 80, flush=True)

# 1. Load CBOE VIX data for backwardation filtering
vix_path = ROOT / "data/external/VIX_History.csv"
vix3m_path = ROOT / "data/external/VIX3M_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df['date'] = pd.to_datetime(vix_df['DATE'], format='%m/%d/%Y').dt.date
vix_map = vix_df.set_index('date')['CLOSE'].astype(float).to_dict()

vix3m_df = pd.read_csv(vix3m_path)
vix3m_df['date'] = pd.to_datetime(vix3m_df['DATE'], format='%m/%d/%Y').dt.date
vix3m_map = vix3m_df.set_index('date')['CLOSE'].astype(float).to_dict()

cboe_dates = np.array(sorted(list(vix_map.keys())))

def get_same_day_cboe_backwardation_map(target_dates):
    res = {}
    for td in target_dates:
        p = cboe_dates.searchsorted(td, side='right') - 1
        if p >= 0:
            cd = cboe_dates[p]
            vx = vix_map.get(cd, 20.0)
            v3 = vix3m_map.get(cd, 20.0)
            res[td] = bool(vx > v3)
        else:
            res[td] = False
    return res

# 2. Load 1-minute bars for Training (2010-2023)
print("[1/3] Loading 1-minute Training bars (MNQ and MES)...", flush=True)
b_mnq = m1.load_bars('MNQ', 1, "2010-01-01", "2024-01-01", "train")
b_mes = m1.load_bars('MES', 1, "2010-01-01", "2024-01-01", "train")

def compute_nights_df(b):
    et = pd.to_datetime(b.timestamp_utc, utc=True).dt.tz_convert("America/New_York")
    b = b.copy()
    b["sod"] = (et.dt.hour * 60 + et.dt.minute).to_numpy()
    b["date"] = et.dt.date.to_numpy()
    dates = sorted(set(b["date"]))
    prev = {d: p for p, d in zip(dates[:-1], dates[1:])}
    nk = np.where(b["sod"] >= 1080, b["date"], np.where(b["sod"] <= 600, pd.Series(b["date"]).map(prev).to_numpy(), None))
    b["nk"] = nk
    day = b.groupby("date")
    g = b[b.nk.notna()].groupby("nk")
    def at(sod, col, grp=g):
        s = b[b.sod == sod]
        return s.groupby("nk" if grp is g else "date")[col].first()

    n = pd.DataFrame(dict(
        rth_open=at(570, "open", day),
        rth_close=b[(b.sod >= 955) & (b.sod < 960)].groupby("date").close.last(),
        c1659=b[(b.sod >= 1015) & (b.sod < 1020)].groupby("date").close.last(),
        day_low=b[(b.sod >= 570) & (b.sod < 960)].groupby("date").low.min(),
        o1800=at(1080, "open", day),
        dow=pd.Series({d: pd.Timestamp(d).dayofweek for d in dates})
    ))
    ent = pd.DataFrame(dict(
        e1805=at(1085, "open"),
        x0930=at(570, "open"),
        x0945=at(585, "open")
    ))
    n["ref_close"] = n.rth_close.ffill()
    n = n.join(ent, how="inner").dropna(subset=["e1805", "x0945", "ref_close"])
    n["year"] = [pd.Timestamp(d).year for d in n.index]
    n["gap"] = n.o1800 / n.ref_close - 1
    n["sd20"] = n.gap.rolling(20, min_periods=15).std().shift(1)
    return n, b

n_mnq, b_mnq = compute_nights_df(b_mnq)
n_mes, b_mes = compute_nights_df(b_mes)

# Same-day CBOE close backwardation map for 18:05 ET entry
same_day_backw_map = get_same_day_cboe_backwardation_map(n_mnq.index)

# Reopen condition on MNQ and MES
mg = n_mes.gap.reindex(n_mnq.index)
msd = n_mes.sd20.reindex(n_mnq.index)
mask_ovn = ((n_mnq.gap <= -0.5 * n_mnq.sd20) & (mg <= -0.5 * msd)).fillna(False)

# Filter backwardation days
mask_vix_ok = pd.Series([not same_day_backw_map.get(d, False) for d in n_mnq.index], index=n_mnq.index)
qualifying_nights = n_mnq.index[mask_ovn & mask_vix_ok]

print(f"Total Qualifying Overnight Dip Nights in Training (2010-2023): {len(qualifying_nights)}", flush=True)

# 3. Extract 1-minute trajectory for each qualifying night
print("\n[2/3] Extracting 1-minute intra-night price paths...", flush=True)

# Map night bars for each qualifying night
# Night bars span from 18:05 (sod==1085) of night_date to 09:45 (sod==585) of next day
b_mnq_by_nk = b_mnq[b_mnq['nk'].isin(qualifying_nights)].copy()

# Sort by timestamp
b_mnq_by_nk = b_mnq_by_nk.sort_values('timestamp_utc').reset_index(drop=True)

trajectories = {}
grouped = b_mnq_by_nk.groupby('nk')

SPEC_MNQ = dict(tick=0.25, tv=0.5, spread=1.75)
POINT_VALUE = SPEC_MNQ['tv'] / SPEC_MNQ['tick']  # $2.00 per full index point
COMM, SLIP = 0.61, 1.0
round_trip_cost = (SPEC_MNQ["spread"] + 2 * SLIP) * SPEC_MNQ["tv"] + 2 * COMM

for nk, grp in grouped:
    # Filter bars between 18:05 of nk and 09:45 of next day
    # Exclude bars strictly before 18:05
    sub_bars = grp[(grp['sod'] >= 1085) | (grp['sod'] <= 585)].sort_values('timestamp_utc')
    if len(sub_bars) < 10:
        continue
    # Bar at 18:05
    b_1805 = sub_bars[sub_bars['sod'] == 1085]
    if len(b_1805) == 0:
        continue
    e_price = float(b_1805.iloc[0]['open'])
    
    # Target exit at 09:45
    b_0945 = sub_bars[sub_bars['sod'] == 585]
    x_price = float(b_0945.iloc[0]['open']) if len(b_0945) > 0 else float(sub_bars.iloc[-1]['close'])
    
    # Trajectory of subsequent bars after 18:05
    subseq = sub_bars[sub_bars['timestamp_utc'] > b_1805.iloc[0]['timestamp_utc']]
    
    trajectories[nk] = {
        'year': int(pd.Timestamp(nk).year),
        'entry_price': e_price,
        'unconditional_exit': x_price,
        'lows': subseq['low'].to_numpy(dtype=float),
        'opens': subseq['open'].to_numpy(dtype=float),
        'sods': subseq['sod'].to_numpy(dtype=int)
    }

print(f"Constructed trajectories for {len(trajectories)} nights.", flush=True)

# 4. Evaluate Catastrophe Stop-Loss Variants
print("\n[3/3] Simulating Catastrophe Stop-Loss Levels on 2010-2023 Training Data...", flush=True)

def simulate_stop(stop_dollars):
    """Simulate stop loss of `stop_dollars` on MNQ position ($2.00/point)."""
    trade_nets = []
    trade_maes = []
    stops_hit = 0
    
    stop_pts = stop_dollars / POINT_VALUE if stop_dollars is not None else None
    
    for nk, tr in trajectories.items():
        e = tr['entry_price']
        lows = tr['lows']
        opens = tr['opens']
        x_uncond = tr['unconditional_exit']
        
        hit_stop = False
        exit_price = x_uncond
        
        if stop_pts is not None:
            stop_lvl = e - stop_pts
            for lo, op in zip(lows, opens):
                if lo <= stop_lvl:
                    # Stopped out at stop level or open if gap
                    exit_price = min(stop_lvl, op) - SLIP * SPEC_MNQ['tick']
                    hit_stop = True
                    stops_hit += 1
                    break
                    
        pnl = (exit_price - e) * POINT_VALUE - round_trip_cost
        trade_nets.append(pnl)
        
        # Max Adverse Excursion
        min_lo = np.min(lows) if len(lows) > 0 else e
        mae = max(0.0, (e - min_lo) * POINT_VALUE)
        trade_maes.append(mae)
        
    nets = np.array(trade_nets)
    cum = np.cumsum(nets)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    max_closed_dd = float(np.max(dd))
    
    tot_net = float(np.sum(nets))
    n_tr = len(nets)
    exp = tot_net / n_tr
    wr = float(np.mean(nets > 0) * 100.0)
    
    return {
        'stop_dollars': stop_dollars if stop_dollars else "None (Unconditional)",
        'net_profit': round(tot_net, 2),
        'trades': n_tr,
        'expectancy': round(exp, 2),
        'win_rate': round(wr, 1),
        'stops_hit': stops_hit,
        'max_closed_dd': round(max_closed_dd, 2),
        'max_mae': round(float(np.max(trade_maes)), 2),
        'p95_mae': round(float(np.percentile(trade_maes, 95)), 2)
    }

stop_levels = [None, 150.0, 200.0, 250.0, 300.0, 350.0, 400.0, 500.0, 600.0, 800.0, 1000.0]
results = []

for sl in stop_levels:
    res = simulate_stop(sl)
    results.append(res)
    label = f"${sl:.0f}" if sl else "Unconditional"
    print(f"Stop: {label:15s} | Net: ${res['net_profit']:>9,.2f} | Exp: ${res['expectancy']:>6.2f}/tr | WR: {res['win_rate']:>5.1f}% | Stops Hit: {res['stops_hit']:>3d} | Closed DD: ${res['max_closed_dd']:>8.2f}")

# Save results
out_path = ROOT / "reports/RESEARCH_OVERNIGHT_CATASTROPHE_STOP_TRAIN.json"
with open(out_path, "w") as f:
    json.dump(results, f, indent=2)

print(f"\n[DONE] Saved stop loss sweep to {out_path}", flush=True)
