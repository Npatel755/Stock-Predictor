import json, gc
from pathlib import Path
import numpy as np, pandas as pd

from quant_trading_bot.scripts.audit_days_to_pass_evaluation import dates, pnl_12c, pnl_8c, pnl_6c

def get_exact_dd(daily_pnl, label, target=4000.0, floor=2000.0, dll=1000.0, max_eval_days=90):
    total_starts = len(dates) - max_eval_days
    pass_drawdowns = []
    all_drawdowns_during_eval = []
    
    # Continuous equity curve drawdown across the entire 16.9 years (unstopped)
    all_nets = [daily_pnl[d]['net'] for d in dates]
    cum_all = np.cumsum(all_nets)
    hwm_all = np.maximum.accumulate(cum_all)
    dd_continuous = hwm_all - cum_all
    max_continuous_dd = np.max(dd_continuous)
    
    # Intraday MAE worst and worst single day
    worst_single_day_net = min(daily_pnl[d]['net'] for d in dates)
    worst_single_day_mae = min(daily_pnl[d]['mae'] for d in dates)

    for start_idx in range(total_starts):
        cum_pnl = 0.0
        hwm = 0.0
        max_dd_in_trial = 0.0
        busted = False
        passed = False
        max_single_day = -9999.0
        
        for step in range(max_eval_days):
            d = dates[start_idx + step]
            dp = daily_pnl[d]['net']
            dm = daily_pnl[d]['mae']
            
            # Check intraday breach
            cur_dd_intra = hwm - (cum_pnl + dm)
            if cur_dd_intra > max_dd_in_trial:
                max_dd_in_trial = cur_dd_intra
                
            if dp <= -dll or dm <= -dll or (hwm - (cum_pnl + dm)) >= floor or (cum_pnl + dm) <= -floor:
                busted = True
                break
                
            cum_pnl += dp
            if cum_pnl > hwm:
                hwm = cum_pnl
            
            cur_dd_close = hwm - cum_pnl
            if cur_dd_close > max_dd_in_trial:
                max_dd_in_trial = cur_dd_close
                
            if (hwm - cum_pnl) >= floor or cum_pnl <= -floor:
                busted = True
                break
                
            if dp > max_single_day:
                max_single_day = dp
                
            if cum_pnl >= target and max_single_day <= (target * 0.50):
                passed = True
                break
                
        if passed:
            pass_drawdowns.append(max_dd_in_trial)
        all_drawdowns_during_eval.append(max_dd_in_trial)

    print(f"=== {label} ===")
    print(f"Total trials: {total_starts}")
    print(f"Worst Continuous Drawdown Ever (16.9 Years Unstopped): ${max_continuous_dd:,.2f}")
    print(f"Worst Single Day Closed P&L Ever: ${worst_single_day_net:,.2f}")
    print(f"Worst Single Day Intraday Dip (MAE) Ever: ${worst_single_day_mae:,.2f}")
    print(f"Passing Accounts ({len(pass_drawdowns)}):")
    if pass_drawdowns:
        print(f"  Avg Drawdown on Pass: ${np.mean(pass_drawdowns):,.2f}")
        print(f"  Median Drawdown on Pass: ${np.median(pass_drawdowns):,.2f}")
        print(f"  Min Drawdown on Pass: ${np.min(pass_drawdowns):,.2f}")
        print(f"  Max (Worst) Drawdown on Pass: ${np.max(pass_drawdowns):,.2f}")
    print(f"All Accounts:")
    print(f"  Max Drawdown Hit Before Bust/Pass: ${np.max(all_drawdowns_during_eval):,.2f}")
    print()

get_exact_dd(pnl_12c, '12 MNQ (Aggressive Sprint Tier)')
get_exact_dd(pnl_8c, '8 MNQ (Balanced Tier)')
get_exact_dd(pnl_6c, '6 MNQ (Conservative Tier)')

# Multi-sleeve print
from quant_trading_bot.scripts.research_multi_sleeve_time_to_pass_train import df_all, all_days, vix_dict

def get_ms_dd(contracts_tier=6, daily_lock=1750.0, daily_stop=400.0, target=4000.0, floor=2000.0, dll=1000.0, max_eval_days=90):
    daily_results = {}
    for d, group in df_all.groupby('day'):
        vix = vix_dict.get(d, 18.0)
        if vix < 15.0:
            daily_results[d] = {'net': 0.0, 'mae': 0.0}
            continue
        day_pnl = 0.0
        day_mae = 0.0
        group_sorted = group.sort_values('entry_ts')
        for _, tr in group_sorted.iterrows():
            if tr['is_crabel'] and tr['cont']:
                size = contracts_tier
            elif tr['is_crabel']:
                size = max(2, contracts_tier // 2)
            else:
                size = max(2, contracts_tier // 2)
            pnl = tr['net_1c'] * size
            mae = tr['mae_1c'] * size
            if (day_pnl + mae) < day_mae:
                day_mae = day_pnl + mae
            day_pnl += pnl
            if day_pnl >= daily_lock or day_pnl <= -daily_stop:
                break
        daily_results[d] = {'net': day_pnl, 'mae': day_mae}

    all_nets = [daily_results[d]['net'] for d in all_days if d in daily_results]
    cum_all = np.cumsum(all_nets)
    hwm_all = np.maximum.accumulate(cum_all)
    dd_continuous = hwm_all - cum_all
    max_continuous_dd = np.max(dd_continuous)

    worst_single_day_net = min(daily_results[d]['net'] for d in all_days if d in daily_results)
    worst_single_day_mae = min(daily_results[d]['mae'] for d in all_days if d in daily_results)

    total_starts = len(all_days) - max_eval_days
    pass_drawdowns = []

    for i in range(total_starts):
        cum = 0.0
        hwm = 0.0
        max_dd_in_trial = 0.0
        busted = False
        pass_run = False
        max_d = -9999.0
        for step in range(max_eval_days):
            d = all_days[i + step]
            if d not in daily_results:
                continue
            dp = daily_results[d]['net']
            dm = daily_results[d]['mae']
            cur_dd_intra = hwm - (cum + dm)
            if cur_dd_intra > max_dd_in_trial:
                max_dd_in_trial = cur_dd_intra
            if dp <= -dll or dm <= -dll or (hwm - (cum + dm)) >= floor or (cum + dm) <= -floor:
                busted = True
                break
            cum += dp
            if cum > hwm:
                hwm = cum
            cur_dd_close = hwm - cum
            if cur_dd_close > max_dd_in_trial:
                max_dd_in_trial = cur_dd_close
            if (hwm - cum) >= floor or cum <= -floor:
                busted = True
                break
            if dp > max_d:
                max_d = dp
            if cum >= target and max_d <= (target * 0.50):
                pass_run = True
                break
        if pass_run:
            pass_drawdowns.append(max_dd_in_trial)

    print(f"=== Multi-Sleeve Ensemble {contracts_tier} MNQ ===")
    print(f"Worst Continuous Drawdown (14-Year Training Unstopped): ${max_continuous_dd:,.2f}")
    print(f"Worst Single Day Closed P&L: ${worst_single_day_net:,.2f}")
    print(f"Worst Single Day Intraday MAE: ${worst_single_day_mae:,.2f}")
    if pass_drawdowns:
        print(f"Passing Accounts ({len(pass_drawdowns)}):")
        print(f"  Avg Drawdown on Pass: ${np.mean(pass_drawdowns):,.2f}")
        print(f"  Median Drawdown on Pass: ${np.median(pass_drawdowns):,.2f}")
        print(f"  Min Drawdown on Pass: ${np.min(pass_drawdowns):,.2f}")
        print(f"  Max (Worst) Drawdown on Pass: ${np.max(pass_drawdowns):,.2f}")
    print()

get_ms_dd(6)
get_ms_dd(10)
get_ms_dd(12)
