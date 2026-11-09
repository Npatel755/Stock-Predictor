"""Research Script: Toby Crabel Open Drive on MES (S&P 500) across 2010-2023 Training Data.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Tests:
1. Baseline Toby Crabel Open Drive on MES (15m bars, 10:00 entry, 8 hold bars, 2.0 ATR stop, 3.5 R target).
2. Range threshold sweep (min_range: 0, 2, 3, 4, 5 ES points).
3. Gap Continuation on MES (drive == gap).
4. Cross-Asset Synergy: When MNQ has no Crabel drive, does MES take the trade?
   What is the correlation between MNQ Crabel and MES Crabel?
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays

print("=" * 80)
print("RESEARCH: MES CRABEL OPEN-DRIVE HYPOTHESIS (2010-2023 TRAINING ONLY)")
print("=" * 80, flush=True)

# Contract specifications
SPEC_MES = dict(mult=5.0, tick=0.25, tv=1.25, comm=0.61, spread=1.0, slip=1.0)
SPEC_MNQ = dict(mult=2.0, tick=0.25, tv=0.50, comm=0.61, spread=1.75, slip=1.0)

# 1. Load 14-Year Training Bars
b_mes_15 = load_resampled_bars('ES', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)
b_mnq_15 = load_resampled_bars('NQ', 'train', '15 minutes', start_date=None).sort_values('timestamp_utc').reset_index(drop=True)

loc_mes = b_mes_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mes_15['sod'] = loc_mes.dt.hour * 60 + loc_mes.dt.minute
b_mes_15['date'] = loc_mes.dt.date
b_mes_15['year'] = loc_mes.dt.year

loc_mnq = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
b_mnq_15['sod'] = loc_mnq.dt.hour * 60 + loc_mnq.dt.minute
b_mnq_15['date'] = loc_mnq.dt.date
b_mnq_15['year'] = loc_mnq.dt.year

# 2. Extract 09:30-10:00 opening drive features for MES
df_mes = pd.DataFrame({
    'date': b_mes_15['date'],
    'year': b_mes_15['year'],
    'sod': b_mes_15['sod'],
    'open': b_mes_15['open'],
    'high': b_mes_15['high'],
    'low': b_mes_15['low'],
    'close': b_mes_15['close']
})

r_mes = df_mes[df_mes['sod'].isin([570, 585])].groupby('date')
o930_mes = df_mes[df_mes['sod'] == 570].groupby('date')['open'].first()
c1000_mes = df_mes[df_mes['sod'] == 585].groupby('date')['close'].first()
hi_mes = r_mes['high'].max()
lo_mes = r_mes['low'].min()
rng_mes = (hi_mes - lo_mes).replace(0, np.nan)
op_mes = (o930_mes - lo_mes) / rng_mes
cp_mes = (c1000_mes - lo_mes) / rng_mes

# Daily close for gap calculation
daily_close_mes = df_mes.groupby('date')['close'].last()
prev_close_mes = daily_close_mes.shift(1).reindex(op_mes.index)
gap_mes = (o930_mes - prev_close_mes) / prev_close_mes

tail = 0.2
bull_drive_mes = (op_mes <= tail) & (cp_mes >= 1.0 - tail)
bear_drive_mes = (op_mes >= 1.0 - tail) & (cp_mes <= tail)

# Prepare mass_execution arrays
d_mes_15 = apply_early_close(generalized_arrays(b_mes_15), b_mes_15)
# Compute ATR 14 on 15m bars
tr_15 = np.maximum(d_mes_15['high'] - d_mes_15['low'],
                   np.maximum(np.abs(d_mes_15['high'] - np.roll(d_mes_15['close'], 1)),
                              np.abs(d_mes_15['low'] - np.roll(d_mes_15['close'], 1))))
tr_15[0] = d_mes_15['high'][0] - d_mes_15['low'][0]
atr_mes_15 = pd.Series(tr_15).ewm(span=14, adjust=False).mean().to_numpy()

cfg_mes = dict(tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
               stop_atr=2.0, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
               risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
               flat_minute=955, max_gap_minutes=60)

# CBOE backwardation
vix_path = ROOT / "data/external/VIX_History.csv"
vix3m_path = ROOT / "data/external/VIX3M_History.csv"
vix_df = pd.read_csv(vix_path); vix_df['date'] = pd.to_datetime(vix_df['DATE'], format='%m/%d/%Y').dt.date
vix_map = vix_df.set_index('date')['CLOSE'].astype(float).to_dict()
vix3m_df = pd.read_csv(vix3m_path); vix3m_df['date'] = pd.to_datetime(vix3m_df['DATE'], format='%m/%d/%Y').dt.date
vix3m_map = vix3m_df.set_index('date')['CLOSE'].astype(float).to_dict()
cboe_dates = np.array(sorted(list(vix_map.keys())))

def is_prior_backwardation(d):
    p = cboe_dates.searchsorted(d, side='left') - 1
    if p >= 0:
        cd = cboe_dates[p]
        return bool(vix_map.get(cd, 20.0) > vix3m_map.get(cd, 20.0))
    return False

is_backw = pd.Series([is_prior_backwardation(d) for d in op_mes.index], index=op_mes.index)

dec_15 = (loc_mes.dt.hour * 60 + loc_mes.dt.minute + 15).to_numpy()
weekdays_15 = loc_mes.dt.weekday.to_numpy() < 5
is_1000_bar = (dec_15 == 600) & weekdays_15
dates_all_15 = loc_mes.dt.date

def evaluate_mes_crabel(cond_bull, cond_bear, label, min_range=0.0):
    sig_series_bull = (cond_bull & (rng_mes >= min_range) & ~is_backw).fillna(False)
    sig_series_bear = (cond_bear & (rng_mes >= min_range) & ~is_backw).fillna(False)
    
    d_map = dict(zip(op_mes.index, np.where(sig_series_bull, 1, np.where(sig_series_bear, -1, 0))))
    sig = np.zeros(len(d_mes_15['close']), dtype=np.int8)
    for i in range(len(sig)):
        if is_1000_bar[i]:
            sig[i] = d_map.get(dates_all_15[i], 0)
            
    r = me.execute(d_mes_15, sig, atr_mes_15, cfg_mes)
    tn = r['trade_net']
    n_tr = len(tn)
    if n_tr == 0:
        print(f"[{label}] No trades.")
        return None
        
    net = float(tn.sum())
    exp = net / n_tr
    wr = float(np.mean(tn > 0) * 100)
    
    cum = np.cumsum(tn)
    hwm = np.maximum.accumulate(cum)
    dd = hwm - cum
    max_dd = float(np.max(dd))
    
    ex_idx = r['trade_exit']
    exit_years = [dates_all_15[x].year for x in ex_idx]
    df_y = pd.DataFrame({'year': exit_years, 'net': tn})
    yr = df_y.groupby('year')['net'].sum()
    pos_years = int((yr > 0).sum())
    
    print(f"[{label}]")
    print(f"  Trades: {n_tr} | Net: +${net:,.2f} | Exp: +${exp:.2f}/tr | WR: {wr:.1f}%")
    print(f"  Max Realized DD: ${max_dd:,.2f} | Positive Years: {pos_years}/14 ({pos_years/14*100:.1f}%)")
    print(f"  Yearly: " + ", ".join([f"{y}: ${v:+,.0f}" for y, v in yr.items()]))
    
    return {
        'label': label, 'trades': n_tr, 'net': round(net, 2),
        'exp': round(exp, 2), 'wr': round(wr, 1), 'max_dd': round(max_dd, 2),
        'pos_years': pos_years, 'by_year': {int(y): round(float(v), 2) for y, v in yr.items()}
    }

# 1. Baseline Unconstrained MES Crabel
print("\n--- 1. Baseline MES Crabel Open Drive ---")
evaluate_mes_crabel(bull_drive_mes, bear_drive_mes, "MES Crabel Baseline (min_rng=0)")
evaluate_mes_crabel(bull_drive_mes, bear_drive_mes, "MES Crabel (min_rng=3.0 ES pts)", min_range=3.0)
evaluate_mes_crabel(bull_drive_mes, bear_drive_mes, "MES Crabel (min_rng=5.0 ES pts)", min_range=5.0)

# 2. Gap Continuation on MES Crabel
print("\n--- 2. Gap-Continuation MES Crabel (drive == gap) ---")
bull_cont_mes = bull_drive_mes & (gap_mes >= 0.0)
bear_cont_mes = bear_drive_mes & (gap_mes <= 0.0)
evaluate_mes_crabel(bull_cont_mes, bear_cont_mes, "MES Crabel Gap-Continuation (min_rng=0)")
evaluate_mes_crabel(bull_cont_mes, bear_cont_mes, "MES Crabel Gap-Continuation (min_rng=3.0)", min_range=3.0)
evaluate_mes_crabel(bull_cont_mes, bear_cont_mes, "MES Crabel Gap-Continuation (min_rng=5.0)", min_range=5.0)

# 3. Gap Fade on MES Crabel
print("\n--- 3. Gap-Fade MES Crabel (drive != gap) ---")
bull_fade_mes = bull_drive_mes & (gap_mes < 0.0)
bear_fade_mes = bear_drive_mes & (gap_mes > 0.0)
evaluate_mes_crabel(bull_fade_mes, bear_fade_mes, "MES Crabel Gap-Fade (min_rng=0)")
