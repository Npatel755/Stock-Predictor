"""Compute detailed pass velocity and portfolio ensemble statistics on Validation data."""
import json
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

with open(ROOT / 'runs/training_search_2m_v1/validation_curves.json') as f:
    data = json.load(f)

by_id = {d['config_id']: d for d in data}

c_mes_trend = by_id['m2_a1f1cc46771107c0a9f9']  # MES Trend (2 contracts, 7.0R)
c_mnq_mom   = by_id['m2_2a6dc4bf5f9f7a7836f4']  # MNQ Momentum (1 contract, 10.0R)
c_mnq_hyb   = by_id['m2_95c765ba5d3a7183fc3e']  # MNQ Hybrid (1 contract, 6.0R)
c_mnq_brk   = by_id['m2_eaa56d8ebf97ab0a5540']  # MNQ Breakout (1 contract, 3.0R)

df1 = pd.DataFrame({'ts': pd.to_datetime(c_mes_trend['timestamps']), 'pnl1': np.array(c_mes_trend['equity_curve']) - 50000.0})
df2 = pd.DataFrame({'ts': pd.to_datetime(c_mnq_mom['timestamps']),   'pnl2': np.array(c_mnq_mom['equity_curve']) - 50000.0})
df3 = pd.DataFrame({'ts': pd.to_datetime(c_mnq_hyb['timestamps']),   'pnl3': np.array(c_mnq_hyb['equity_curve']) - 50000.0})
df4 = pd.DataFrame({'ts': pd.to_datetime(c_mnq_brk['timestamps']),   'pnl4': np.array(c_mnq_brk['equity_curve']) - 50000.0})

df_comb = pd.merge(df1, df2, on='ts', how='outer').sort_values('ts').ffill().fillna(0)
df_comb = pd.merge(df_comb, df3, on='ts', how='outer').sort_values('ts').ffill().fillna(0)
df_comb = pd.merge(df_comb, df4, on='ts', how='outer').sort_values('ts').ffill().fillna(0)

portfolios = {
    "MES Trend (2c) + MNQ Momentum (10R)": df_comb['pnl1'] + df_comb['pnl2'],
    "MES Trend (2c) + MNQ Hybrid (6R)": df_comb['pnl1'] + df_comb['pnl3'],
    "MNQ Momentum (10R) + MNQ Hybrid (6R)": df_comb['pnl2'] + df_comb['pnl3'],
    "Tri-Asset: MES Trend + MNQ Momentum + MNQ Breakout": df_comb['pnl1'] + df_comb['pnl2'] + df_comb['pnl4'],
}

def analyze_portfolio(pnl_series, ts_series, target=3000.0, max_dd_limit=2000.0):
    total_net = float(pnl_series.iloc[-1])
    peak = pnl_series.cummax()
    dd_series = peak - pnl_series
    max_dd = float(dd_series.max())
    cushion = 2000.0 - max_dd

    df = pd.DataFrame({'ts': ts_series, 'pnl': pnl_series})
    df['week'] = df['ts'].dt.to_period('W')
    weekly = df.groupby('week')['pnl'].last().values
    
    n_weeks = len(weekly)
    pass_times = []
    passed_starts = 0
    failed_starts = 0

    for i in range(n_weeks - 2):
        start_pnl = weekly[i]
        peak_w = start_pnl
        passed = False
        breached = False
        for j in range(i + 1, n_weeks):
            curr_pnl = weekly[j]
            peak_w = max(peak_w, curr_pnl)
            if peak_w - curr_pnl >= max_dd_limit:
                breached = True
                break
            if curr_pnl - start_pnl >= target:
                pass_times.append(j - i)
                passed = True
                break
        if passed:
            passed_starts += 1
        elif breached:
            failed_starts += 1

    total_tested = passed_starts + failed_starts
    pass_rate = (passed_starts / total_tested * 100.0) if total_tested > 0 else 0.0
    fastest = min(pass_times) if pass_times else None
    median_time = float(np.median(pass_times)) if pass_times else None
    mean_time = float(np.mean(pass_times)) if pass_times else None
    weekly_gain = total_net / max(1.0, len(weekly))
    monthly_gain = weekly_gain * 4.333

    return {
        'net_pnl': total_net,
        'max_dd': max_dd,
        'dd_cushion': cushion,
        'weekly_gain': weekly_gain,
        'monthly_gain': monthly_gain,
        'fastest_weeks': fastest,
        'median_weeks': median_time,
        'mean_weeks': mean_time,
        'pass_rate_pct': pass_rate,
        'windows_tested': total_tested
    }

print("=== ENSEMBLE PORTFOLIO PASS VELOCITY AUDIT ON VALIDATION (2024-2025) ===")
print("Zero parameter tuning | Authentic LucidFlex execution economics ($2,000 liquidation line)\n")

ensemble_stats = {}
for name, pnl_col in portfolios.items():
    stats = analyze_portfolio(pnl_col, df_comb['ts'])
    ensemble_stats[name] = stats
    print(f"Portfolio: {name}")
    print(f"  Validation Total Net PnL: ${stats['net_pnl']:,.2f}")
    print(f"  Validation Max Drawdown:  ${stats['max_dd']:,.2f} (Safety Cushion: ${stats['dd_cushion']:,.2f})")
    print(f"  Avg Monthly Gain:         ${stats['monthly_gain']:,.2f}/month")
    print(f"  Avg Weekly Gain:          ${stats['weekly_gain']:,.2f}/week")
    print(f"  Fastest Streak to $3k:    {stats['fastest_weeks']} weeks")
    print(f"  Median Time to Pass $3k:  {stats['median_weeks']:.1f} weeks")
    print(f"  Funded Pass Success Rate: {stats['pass_rate_pct']:.1f}% ({stats['windows_tested']} starting dates tested)")
    print("-" * 75)

# Save ensemble stats to json
with open(ROOT / 'reports/ensemble_velocity_results.json', 'w') as f:
    json.dump(ensemble_stats, f, indent=2)
