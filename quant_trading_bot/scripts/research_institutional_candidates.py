import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import mass_research as engine
from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
from training_10m_universe import config_id

def load_training_bars(sym):
    path = ROOT / 'runs/training_search_10m_institutional/cache' / f'{sym}_15m.parquet'
    bars = pd.read_parquet(path)
    return bars

bars_mes = load_training_bars('MES')
bars_mnq = load_training_bars('MNQ')

# Define candidate sleeves from ranked.csv (discovered purely on Training data 2020-2023)
mnq_morning_breakout = {
    'config_id': 'm10_cf4656e61c0cedd759b9',
    'instrument': 'MNQ',
    'family': 'breakout',
    'lookback': 16,
    'threshold': 1.25,
    'stop_atr': 1.75,
    'target_r': 2.25,
    'hold_bars': 6,
    'session_start': 600,
    'session_end': 720,
    'trailing_atr': 0.0,
}

mnq_afternoon_trend = {
    'config_id': 'm10_44cc6301fcaf39b2fbaf',
    'instrument': 'MNQ',
    'family': 'trend',
    'lookback': 20,
    'threshold': 0.75,
    'stop_atr': 2.0,
    'target_r': 3.5,
    'hold_bars': 16,
    'session_start': 780,
    'session_end': 945,
    'trailing_atr': 2.5,
}

mes_trend_core = {
    'config_id': 'm10_5f5118c01957ba55505d',
    'instrument': 'MES',
    'family': 'trend',
    'lookback': 10,
    'threshold': 1.0,
    'stop_atr': 1.75,
    'target_r': 2.0,
    'hold_bars': 32,
    'session_start': 585,
    'session_end': 945,
    'trailing_atr': 2.0,
}

def run_sleeve_train(cfg, bars, contracts=1, dynamic_risk=0):
    data = apply_early_close(engine.arrays(bars), bars)
    features = engine.features(bars, int(cfg['lookback']))
    raw_sig = engine.signal_for(cfg, features).astype(np.int8)

    local = bars.timestamp_utc.dt.tz_convert('America/New_York')
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.weekday.to_numpy() < 5
    mask = (decision >= cfg['session_start']) & (decision < cfg['session_end']) & weekdays
    sig = np.where(mask, raw_sig, 0).astype(np.int8)

    mult = 2.0 if cfg['instrument'] == 'MNQ' else 5.0
    tick = 0.25 if cfg['instrument'] == 'MNQ' else 0.25

    ecfg = {
        'initial': 50000.0,
        'trade_risk': dynamic_risk if dynamic_risk > 0 else 50000.0,
        'open_risk': 50000.0,
        'daily_loss': 1000.0,
        'hard_dd': 2000.0,
        'stop_ticks': 0,
        'stop_atr': float(cfg['stop_atr']),
        'target_ratio': float(cfg['target_r']),
        'trailing_atr': float(cfg.get('trailing_atr', 0.0)),
        'hold_bars': int(cfg['hold_bars']),
        'flat_minute': 955,
        'entry_start': int(cfg['session_start']),
        'entry_end': int(cfg['session_end']),
        'max_contracts': int(contracts),
        'tick_size': tick,
        'multiplier': mult,
        'adverse_ticks': 1.0,
        'fee_per_contract': 0.61,
        'participation_cap': 1.0,
        'max_losses': 100,
        'funded_drawdown': 2000.0,
        'funded_cap': 50000.0,
    }
    res = engine.execute(data, sig, features['atr'], ecfg)
    sm = engine.summarize_execution(res, data)
    ts = pd.to_datetime(data['timestamp'], unit='ns', utc=True)
    df = pd.DataFrame({'ts': ts, 'cash': res['cash'], 'worst': res['worst']})
    return df, sm

print("Evaluating individual candidate sleeves on 2020-2023 Training:")
for name, c, b in [
    ('MNQ Morning Breakout 1c', mnq_morning_breakout, bars_mnq),
    ('MNQ Morning Breakout 2c', mnq_morning_breakout, bars_mnq),
    ('MNQ Afternoon Trend 1c', mnq_afternoon_trend, bars_mnq),
    ('MES Trend Core 1c', mes_trend_core, bars_mes),
    ('MES Trend Core 2c', mes_trend_core, bars_mes),
]:
    qty = 2 if '2c' in name else 1
    df, sm = run_sleeve_train(c, b, contracts=qty)
    print(f"{name:<25}: Net={sm['net_pnl']:>9.2f} | Max DD={sm['intrabar_drawdown']:>8.2f} | Trades={sm['trades']:>3} | WinRate={sm['win_rate']*100:.1f}% | PF={sm['profit_factor']:.2f}")
