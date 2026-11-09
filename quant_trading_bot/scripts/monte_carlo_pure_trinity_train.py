"""Monte Carlo Risk-of-Ruin Audit: High-Expectancy Pure 3-Sleeve Trinity on 2010-2023 Training Data.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Evaluates:
- 5,000-path Stationary Block Bootstrap
- 1-Year (252 trading days / ~65 trades) funded account evaluation
- Trailing Drawdown Distribution vs $2,000 funded floor
- Ruin / Breach Probability
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

import research_frontier_priority_and_3sleeve_train as rf

print("=" * 80)
print("5,000-PATH STATIONARY BOOTSTRAP MONTE CARLO: HIGH-EXP TRINITY (2010-2023 TRAIN)")
print("=" * 80, flush=True)

# Generate trades for Configuration 6 (Gap-Crabel > 60m > MES)
res = rf.run_simulation(router_type="pure_3_sleeve", gap_align=True, label="High-Exp Trinity")

# Get trade series
# Reconstruct trade list directly
cond_bull = (rf.df_days['open_pos'] <= 0.20) & (rf.df_days['close_pos'] >= 0.80) & (rf.df_days['range'] >= 15.0) & (rf.df_days['gap'] >= 0.0)
cond_bear = (rf.df_days['open_pos'] >= 0.80) & (rf.df_days['close_pos'] <= 0.20) & (rf.df_days['range'] >= 15.0) & (rf.df_days['gap'] <= 0.0)
d_map = dict(zip(rf.df_days.index, np.where(cond_bull & ~rf.df_days['is_backw'], 1, np.where(cond_bear & ~rf.df_days['is_backw'], -1, 0))))

sig_c = np.zeros(len(rf.close_15), dtype=np.int8)
for i in range(len(rf.close_15)):
    if rf.is_1000_bar[i]:
        d = rf.dates_all_15[i]
        s = d_map.get(d, 0)
        if s != 0:
            m_dir = rf.mes_dir_1000.get(d, 0)
            if (s == 1 and m_dir < 0) or (s == -1 and m_dir > 0):
                s = 0
        sig_c[i] = s

r_c = rf.me.execute(rf.d_mnq_15, sig_c, rf.atr_15, rf.cfg_c)
act_c_15 = pd.Series(r_c['quantity'] != 0, index=rf.b_mnq_15['timestamp_utc'])

act_c_60 = act_c_15.reindex(rf.b_mnq_60['timestamp_utc'], method='ffill').fillna(False).to_numpy()
sig_2_routed = np.where(~act_c_60, rf.sig_2_gated, 0).astype(np.int8)
r_2 = rf.me.execute(rf.d_mnq_60, sig_2_routed, rf.f_2['atr'], rf.cfg_2)
act_2_60 = pd.Series(r_2['quantity'] != 0, index=rf.b_mnq_60['timestamp_utc'])

act_all_mnq = (act_c_15.reindex(rf.b_mes_30['timestamp_utc'], method='ffill').fillna(False) |
               act_2_60.reindex(rf.b_mes_30['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
sig_mes_routed = np.where(~act_all_mnq, rf.sig_mes_raw, 0).astype(np.int8)
r_mes = rf.me.execute(rf.d_mes_30, sig_mes_routed, rf.f_mes['atr'], rf.cfg_mes)

sleeves = [('Crabel', r_c, rf.d_mnq_15, rf.b_mnq_15), ('S2_60m', r_2, rf.d_mnq_60, rf.b_mnq_60), ('MES_30m', r_mes, rf.d_mes_30, rf.b_mes_30)]

tr_list = []
for s_name, r, d, b_bar in sleeves:
    if len(r['trade_entry']):
        y = d['year'][r['trade_entry']]
        net = r['trade_net']
        t_en = b_bar['timestamp_utc'].iloc[r['trade_entry']].values
        for yr, n, et in zip(y, net, t_en):
            tr_list.append({'sleeve': s_name, 'year': int(yr), 'net': float(n), 'entry_time': et})
            
df_tr = pd.DataFrame(tr_list).sort_values('entry_time').reset_index(drop=True)
trade_nets = df_tr['net'].to_numpy(dtype=float)

N = len(trade_nets)
print(f"Total Trades in 14-Year Training: {N}")
print(f"Mean Expectancy: ${trade_nets.mean():.2f}/trade")

# 5,000-Path Stationary Block Bootstrap Monte Carlo
NUM_PATHS = 5000
TRADES_PER_YEAR = int(N / 14.0)  # ~63 trades per year
AVG_BLOCK_SIZE = 8

rng = np.random.default_rng(42)
max_drawdowns_1y = []
annual_nets_1y = []
breaches_2k = 0

for path in range(NUM_PATHS):
    sim_trades = []
    while len(sim_trades) < TRADES_PER_YEAR:
        idx = rng.integers(0, N)
        block_len = rng.geometric(1.0 / AVG_BLOCK_SIZE)
        for b_i in range(block_len):
            sim_trades.append(trade_nets[(idx + b_i) % N])
            if len(sim_trades) == TRADES_PER_YEAR:
                break
                
    p = np.array(sim_trades)
    cum = np.cumsum(p)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    mdd = np.max(dd)
    
    max_drawdowns_1y.append(mdd)
    annual_nets_1y.append(cum[-1])
    if mdd >= 2000.0:
        breaches_2k += 1

mdd_arr = np.array(max_drawdowns_1y)
net_arr = np.array(annual_nets_1y)

p50_dd = np.percentile(mdd_arr, 50)
p90_dd = np.percentile(mdd_arr, 90)
p95_dd = np.percentile(mdd_arr, 95)
p99_dd = np.percentile(mdd_arr, 99)
max_mc_dd = np.max(mdd_arr)

breach_rate = (breaches_2k / NUM_PATHS) * 100.0

print("\n" + "=" * 80)
print("MONTE CARLO SIMULATION RESULTS (5,000 PATHS - 1 YEAR SIMULATION):")
print("=" * 80)
print(f"Breach Rate of $2,000 Floor:   {breach_rate:.4f}% ({breaches_2k} / {NUM_PATHS} paths)")
print(f"Median 1-Year Net Profit:     ${np.median(net_arr):>8,.2f}")
print(f"Median Max Drawdown (50th):   ${p50_dd:>8,.2f} (Cushion: +${2000-p50_dd:,.2f})")
print(f"90th Percentile Drawdown:     ${p90_dd:>8,.2f} (Cushion: +${2000-p90_dd:,.2f})")
print(f"95th Percentile Drawdown:     ${p95_dd:>8,.2f} (Cushion: +${2000-p95_dd:,.2f})")
print(f"99th Percentile Drawdown:     ${p99_dd:>8,.2f} (Cushion: +${2000-p99_dd:,.2f})")
print(f"Absolute Worst Path DD:       ${max_mc_dd:>8,.2f}")
print("=" * 80)

mc_summary = {
    "num_paths": NUM_PATHS,
    "trades_per_year": TRADES_PER_YEAR,
    "breach_rate_pct": breach_rate,
    "median_net": round(float(np.median(net_arr)), 2),
    "p50_dd": round(float(p50_dd), 2),
    "p90_dd": round(float(p90_dd), 2),
    "p95_dd": round(float(p95_dd), 2),
    "p99_dd": round(float(p99_dd), 2),
    "max_mc_dd": round(float(max_mc_dd), 2),
    "cushion_p95": round(float(2000 - p95_dd), 2)
}

with open(ROOT / "reports/MONTE_CARLO_HIGH_EXP_TRINITY_TRAIN.json", "w") as f:
    json.dump(mc_summary, f, indent=2)

print(f"[DONE] Saved Monte Carlo results to reports/MONTE_CARLO_HIGH_EXP_TRINITY_TRAIN.json", flush=True)
