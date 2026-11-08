"""Audit and extract the top discoveries from the overnight research on Training data."""
import pandas as pd
from pathlib import Path

RUN_DIR = Path('quant_trading_bot/runs/overnight_institutional_research')

print("=" * 75)
print("OVERNIGHT INSTITUTIONAL RESEARCH AUDIT (TRAINING DATA 2020-2023)")
print("=" * 75)

# 1. Sizing Mechanics
if (RUN_DIR / 'sizing_mechanics_comparison.csv').exists():
    df_sz = pd.read_csv(RUN_DIR / 'sizing_mechanics_comparison.csv')
    cols = [c for c in ['type', 'budget', 'net_pnl', 'intrabar_dd', 'win_rate', 'profit_factor', 'calmar', 'trades'] if c in df_sz.columns]
    print("\n--- 1. SIZING MECHANICS COMPARISON ---")
    print(df_sz[cols].to_string(index=False))

# 2. Breakeven Ratchet
if (RUN_DIR / 'breakeven_ratchet_train_results.csv').exists():
    df_be = pd.read_csv(RUN_DIR / 'breakeven_ratchet_train_results.csv')
    cols = [c for c in ['be_threshold', 'net_pnl', 'intrabar_dd', 'win_rate', 'profit_factor', 'calmar', 'trades'] if c in df_be.columns]
    print("\n--- 2. BREAKEVEN RATCHET EFFICIENCY ---")
    print(df_be[cols].to_string(index=False))

# 3. Cross-Asset MES Confirmation Filter
if (RUN_DIR / 'cross_asset_confirmation_results.csv').exists():
    df_ca = pd.read_csv(RUN_DIR / 'cross_asset_confirmation_results.csv')
    cols = [c for c in ['mes_filter_thresh', 'net_pnl', 'intrabar_dd', 'win_rate', 'profit_factor', 'calmar', 'trades'] if c in df_ca.columns]
    print("\n--- 3. CROSS-ASSET CONFIRMATION FILTER ---")
    print(df_ca[cols].to_string(index=False))

# 4. Afternoon Sleeve Grid
if (RUN_DIR / 'afternoon_sleeve_grid_results.csv').exists():
    df_pm = pd.read_csv(RUN_DIR / 'afternoon_sleeve_grid_results.csv')
    cols = [c for c in ['thresh', 'stop', 'target', 'net_pnl', 'intrabar_dd', 'win_rate', 'profit_factor', 'calmar', 'trades'] if c in df_pm.columns]
    print("\n--- 4. TOP 5 AFTERNOON SLEEVE CANDIDATES (trades >= 100) ---")
    filtered = df_pm[df_pm['trades'] >= 100].sort_values('profit_factor', ascending=False).head(5)
    print(filtered[cols].to_string(index=False))

# 5. Volatility Targeting Qualifiers
if (RUN_DIR / 'cross_asset_vol_target_qualifiers_train.csv').exists():
    df_vt = pd.read_csv(RUN_DIR / 'cross_asset_vol_target_qualifiers_train.csv')
    print("\n--- 5. TOP 5 VOLATILITY TARGETING QUALIFIERS ---")
    print(df_vt.head(5).to_string(index=False))

# 6. Multi-Timeframe 60m Qualifiers
if (RUN_DIR / 'round_2_multi_timeframe_qualifiers_train.csv').exists():
    df_mt = pd.read_csv(RUN_DIR / 'round_2_multi_timeframe_qualifiers_train.csv')
    print("\n--- 6. MULTI-TIMEFRAME (60m) QUALIFIERS ---")
    print(df_mt.to_string(index=False))
