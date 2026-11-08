import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

import compute_split_statistics as cs

# Extract results
res = cs.results

print("="*80)
print("INDIVIDUAL SPLIT STATISTICS (TRAIN vs VALIDATION vs TEST)")
print("PORTFOLIO 1 vs PORTFOLIO 3")
print("="*80)

rows_p1 = []
rows_p3 = []
rows_am1 = []
rows_am2 = []
rows_pm1 = []

for split_name in ['TRAIN (2020-2023)', 'VAL (2024-2025)', 'TEST (2026)']:
    data = res[split_name]
    
    p1 = data['portfolio_1']
    p3 = data['portfolio_3']
    am1 = data['sleeve_am_1c']
    am2 = data['sleeve_am_2c']
    pm1 = data['sleeve_pm_1c']
    
    rows_p1.append({
        'Split': split_name,
        'Net P&L ($)': f"+${p1['net']:,.2f}" if p1['net'] >= 0 else f"-${abs(p1['net']):,.2f}",
        'Max DD ($)': f"${p1['dd']:,.2f}",
        'Trades': p1['trades'],
        'Win Rate (%)': f"{p1['win_rate']*100:.1f}%",
        'Profit Factor': f"{p1['pf']:.2f}",
        'Distance to $2k DD': f"+${2000.0 - p1['dd']:,.2f}",
    })
    
    rows_p3.append({
        'Split': split_name,
        'Net P&L ($)': f"+${p3['net']:,.2f}" if p3['net'] >= 0 else f"-${abs(p3['net']):,.2f}",
        'Max DD ($)': f"${p3['dd']:,.2f}",
        'Trades': p3['trades'],
        'Win Rate (%)': f"{p3['win_rate']*100:.1f}%",
        'Profit Factor': f"{p3['pf']:.2f}",
        'Distance to $2k DD': f"+${2000.0 - p3['dd']:,.2f}",
    })
    
    rows_am1.append({
        'Split': split_name,
        'Net P&L ($)': f"+${am1['net_pnl']:,.2f}" if am1['net_pnl'] >= 0 else f"-${abs(am1['net_pnl']):,.2f}",
        'Max DD ($)': f"${am1['intrabar_drawdown']:,.2f}",
        'Trades': am1['trades'],
        'Win Rate (%)': f"{am1['win_rate']*100:.1f}%",
        'Profit Factor': f"{am1['profit_factor']:.2f}",
    })

    rows_am2.append({
        'Split': split_name,
        'Net P&L ($)': f"+${am2['net_pnl']:,.2f}" if am2['net_pnl'] >= 0 else f"-${abs(am2['net_pnl']):,.2f}",
        'Max DD ($)': f"${am2['intrabar_drawdown']:,.2f}",
        'Trades': am2['trades'],
        'Win Rate (%)': f"{am2['win_rate']*100:.1f}%",
        'Profit Factor': f"{am2['profit_factor']:.2f}",
    })

    rows_pm1.append({
        'Split': split_name,
        'Net P&L ($)': f"+${pm1['net_pnl']:,.2f}" if pm1['net_pnl'] >= 0 else f"-${abs(pm1['net_pnl']):,.2f}",
        'Max DD ($)': f"${pm1['intrabar_drawdown']:,.2f}",
        'Trades': pm1['trades'],
        'Win Rate (%)': f"{pm1['win_rate']*100:.1f}%",
        'Profit Factor': f"{pm1['profit_factor']:.2f}",
    })

print("\n--- PORTFOLIO 1 (MNQ Morning 1c + Afternoon 1c) ---")
print(pd.DataFrame(rows_p1).to_string(index=False))

print("\n--- PORTFOLIO 3 (MNQ Morning 2c + Afternoon 1c) ---")
print(pd.DataFrame(rows_p3).to_string(index=False))

print("\n--- SLEEVE 1: MORNING BREAKOUT 1c (10:00-12:00 EST) ---")
print(pd.DataFrame(rows_am1).to_string(index=False))

print("\n--- SLEEVE 1: MORNING BREAKOUT 2c (10:00-12:00 EST) ---")
print(pd.DataFrame(rows_am2).to_string(index=False))

print("\n--- SLEEVE 2: AFTERNOON TREND 1c (13:00-15:45 EST) ---")
print(pd.DataFrame(rows_pm1).to_string(index=False))
