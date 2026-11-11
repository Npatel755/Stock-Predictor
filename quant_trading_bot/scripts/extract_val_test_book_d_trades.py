"""Extract Book D+ Trade Sequence on Blind Test (2026) and Validation (2024-2025)."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close
import mass_execution as me
from quant_futures.mtf_features import load_resampled_bars, generalized_arrays
from quant_futures.htf_engine import compute_htf_features
import mass_1m_search as m1

# 1. Load VIX & VIX3M
vix_path = ROOT / "data/external/VIX_History.csv"
vix3m_path = ROOT / "data/external/VIX3M_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df['date'] = pd.to_datetime(vix_df['DATE'], format='%m/%d/%Y').dt.date
vix_map = vix_df.set_index('date')['CLOSE'].astype(float).to_dict()

vix3m_df = pd.read_csv(vix3m_path)
vix3m_df['date'] = pd.to_datetime(vix3m_df['DATE'], format='%m/%d/%Y').dt.date
vix3m_map = vix3m_df.set_index('date')['CLOSE'].astype(float).to_dict()

cboe_dates = np.array(sorted(list(vix_map.keys())))

def get_prior_backwardation_map(target_dates):
    res = {}
    for td in target_dates:
        p = cboe_dates.searchsorted(td, side='left') - 1
        if p >= 0:
            pd_date = cboe_dates[p]
            vx = vix_map.get(pd_date, 20.0)
            v3 = vix3m_map.get(pd_date, 20.0)
            res[td] = bool(vx > v3)
        else:
            res[td] = False
    return res

def get_same_day_backwardation_map(target_dates):
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

def extract_book_d_split(split_name, start_date, end_date):
    print(f"\nExtracting Book D+ for {split_name}...")
    b_mnq_15 = load_resampled_bars('NQ', split_name, '15 minutes', start_date=start_date).sort_values('timestamp_utc').reset_index(drop=True)
    b_mnq_30 = load_resampled_bars('NQ', split_name, '30 minutes', start_date=start_date).sort_values('timestamp_utc').reset_index(drop=True)
    b_mnq_60 = load_resampled_bars('NQ', split_name, '60 minutes', start_date=start_date).sort_values('timestamp_utc').reset_index(drop=True)
    b_mes_15 = load_resampled_bars('ES', split_name, '15 minutes', start_date=start_date).sort_values('timestamp_utc').reset_index(drop=True)
    b_mes_30 = load_resampled_bars('ES', split_name, '30 minutes', start_date=start_date).sort_values('timestamp_utc').reset_index(drop=True)
    
    loc_15 = b_mnq_15.timestamp_utc.dt.tz_convert('America/New_York')
    b_mnq_15['sod'] = loc_15.dt.hour * 60 + loc_15.dt.minute
    b_mnq_15['date'] = loc_15.dt.date
    
    loc_30 = b_mnq_30.timestamp_utc.dt.tz_convert('America/New_York')
    b_mnq_30['sod'] = loc_30.dt.hour * 60 + loc_30.dt.minute
    b_mnq_30['date'] = loc_30.dt.date
    dec_30 = (loc_30.dt.hour * 60 + loc_30.dt.minute + 30).to_numpy()
    weekdays_30 = loc_30.dt.weekday.to_numpy() < 5
    d_mnq_30 = apply_early_close(generalized_arrays(b_mnq_30), b_mnq_30)
    
    loc_60 = b_mnq_60.timestamp_utc.dt.tz_convert('America/New_York')
    b_mnq_60['sod'] = loc_60.dt.hour * 60 + loc_60.dt.minute
    b_mnq_60['date'] = loc_60.dt.date
    dec_60 = (loc_60.dt.hour * 60 + loc_60.dt.minute + 60).to_numpy()
    weekdays_60 = loc_60.dt.weekday.to_numpy() < 5
    d_mnq_60 = apply_early_close(generalized_arrays(b_mnq_60), b_mnq_60)
    
    loc_mes_30 = b_mes_30.timestamp_utc.dt.tz_convert('America/New_York')
    b_mes_30['sod'] = loc_mes_30.dt.hour * 60 + loc_mes_30.dt.minute
    b_mes_30['date'] = loc_mes_30.dt.date
    dec_mes_30 = (loc_mes_30.dt.hour * 60 + loc_mes_30.dt.minute + 30).to_numpy()
    weekdays_mes_30 = loc_mes_30.dt.weekday.to_numpy() < 5
    d_mes_30 = apply_early_close(generalized_arrays(b_mes_30), b_mes_30)
    
    d_mnq_15 = apply_early_close(generalized_arrays(b_mnq_15), b_mnq_15)
    close_15 = b_mnq_15['close'].to_numpy(dtype=np.float64)
    high_15 = b_mnq_15['high'].to_numpy(dtype=np.float64)
    low_15 = b_mnq_15['low'].to_numpy(dtype=np.float64)
    prev_c15 = np.roll(close_15, 1); prev_c15[0] = close_15[0]
    tr_15 = np.maximum(high_15 - low_15, np.maximum(np.abs(high_15 - prev_c15), np.abs(low_15 - prev_c15)))
    atr_15 = pd.Series(tr_15).rolling(14, min_periods=14).mean().bfill().to_numpy(dtype=np.float64)
    
    f_1 = compute_htf_features(b_mnq_30, 16, 30)
    sig_1_raw = np.where((dec_30 >= 600) & (dec_30 < 720) & weekdays_30 & (np.abs(f_1['trend']) >= 0.75), np.sign(f_1['trend']), 0).astype(np.int8)
    
    f_2 = compute_htf_features(b_mnq_60, 12, 60)
    sig_2_raw = np.where((dec_60 >= 600) & (dec_60 < 720) & weekdays_60 & (np.abs(f_2['trend']) >= 0.75), np.sign(f_2['trend']), 0).astype(np.int8)
    
    f_mes = compute_htf_features(b_mes_30, 8, 30)
    sig_mes_raw = np.where((dec_mes_30 >= 585) & (dec_mes_30 <= 930) & weekdays_mes_30 & (np.abs(f_mes['trend']) >= 1.0), np.sign(f_mes['trend']), 0).astype(np.int8)
    
    # Toby Crabel
    rth_15 = b_mnq_15[(b_mnq_15.sod >= 570) & (b_mnq_15.sod < 960)].reset_index(drop=True)
    g_15 = rth_15.groupby('date')
    o930 = g_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
    c1000 = g_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
    h1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'high'].max() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
    l1000 = g_15.apply(lambda d: d.loc[(d.sod == 570) | (d.sod == 585), 'low'].min() if ((d.sod == 570) | (d.sod == 585)).any() else np.nan)
    
    common_days = sorted(list(o930.dropna().index))
    df_days = pd.DataFrame(index=common_days)
    df_days['range'] = h1000.loc[common_days] - l1000.loc[common_days]
    df_days['open_pos'] = (o930.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)
    df_days['close_pos'] = (c1000.loc[common_days] - l1000.loc[common_days]) / df_days['range'].replace(0, np.nan)
    
    cond_bull_base = (df_days['open_pos'] <= 0.20) & (df_days['close_pos'] >= 0.80) & (df_days['range'] >= 15.0)
    cond_bear_base = (df_days['open_pos'] >= 0.80) & (df_days['close_pos'] <= 0.20) & (df_days['range'] >= 15.0)
    d_map_base = dict(zip(df_days.index, np.where(cond_bull_base, 1, np.where(cond_bear_base, -1, 0))))
    
    dec_15 = (loc_15.dt.hour * 60 + loc_15.dt.minute + 15).to_numpy()
    weekdays_15 = loc_15.dt.weekday.to_numpy() < 5
    is_1000_bar = (dec_15 == 600) & weekdays_15
    dates_all_15 = loc_15.dt.date
    
    sig_crabel = np.zeros(len(close_15), dtype=np.int8)
    for i in range(len(close_15)):
        if is_1000_bar[i]:
            sig_crabel[i] = d_map_base.get(dates_all_15[i], 0)
            
    loc_mes_15 = b_mes_15.timestamp_utc.dt.tz_convert('America/New_York')
    b_mes_15['sod'] = loc_mes_15.dt.hour * 60 + loc_mes_15.dt.minute
    b_mes_15['date'] = loc_mes_15.dt.date
    rth_mes_15 = b_mes_15[(b_mes_15.sod >= 570) & (b_mes_15.sod < 960)].reset_index(drop=True)
    g_mes_15 = rth_mes_15.groupby('date')
    mes_o930 = g_mes_15.apply(lambda d: d.loc[d.sod == 570, 'open'].iloc[0] if (d.sod == 570).any() else np.nan)
    mes_c1000 = g_mes_15.apply(lambda d: d.loc[d.sod == 585, 'close'].iloc[0] if (d.sod == 585).any() else np.nan)
    mes_dir_1000 = np.sign(mes_c1000 - mes_o930).fillna(0).astype(int).to_dict()
    
    for i in range(len(sig_crabel)):
        if sig_crabel[i] != 0:
            m_dir = mes_dir_1000.get(dates_all_15[i], 0)
            if (sig_crabel[i] == 1 and m_dir < 0) or (sig_crabel[i] == -1 and m_dir > 0):
                sig_crabel[i] = 0
                
    all_unique_dates = sorted(list(set(dates_all_15)))
    prior_backw_map = get_prior_backwardation_map(all_unique_dates)
    
    sig_crabel_d_plus = sig_crabel.copy()
    for i in range(len(sig_crabel_d_plus)):
        if sig_crabel_d_plus[i] != 0 and prior_backw_map.get(dates_all_15[i], False):
            sig_crabel_d_plus[i] = 0
            
    dates_30 = loc_30.dt.date.to_numpy()
    sig_1_d_plus = sig_1_raw.copy()
    for i in range(len(sig_1_d_plus)):
        if sig_1_d_plus[i] != 0 and prior_backw_map.get(dates_30[i], False):
            sig_1_d_plus[i] = 0
            
    dates_60 = loc_60.dt.date.to_numpy()
    sig_2_d_plus = sig_2_raw.copy()
    for i in range(len(sig_2_d_plus)):
        if sig_2_d_plus[i] != 0 and prior_backw_map.get(dates_60[i], False):
            sig_2_d_plus[i] = 0
            
    sig_mes_d_plus = sig_mes_raw.copy()
    
    cfg_c = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                 stop_atr=2.0, target_ratio=3.5, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                 risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                 flat_minute=955, max_gap_minutes=60)
    cfg_1 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                 stop_atr=1.5, target_ratio=3.0, hold_bars=8, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                 risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                 flat_minute=955, max_gap_minutes=60)
    cfg_2 = dict(tick=0.25, multiplier=2.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.75,
                 stop_atr=1.25, target_ratio=4.0, hold_bars=6, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                 risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                 flat_minute=955, max_gap_minutes=120)
    cfg_mes = dict(tick=0.25, multiplier=5.0, commission_per_side=0.61, slippage_ticks=1.0, spread_ticks=1.0,
                   stop_atr=1.25, target_ratio=2.5, hold_bars=12, trailing_atr=0.0, maxqty=1, initial_balance=50000.0,
                   risk_per_trade=150.0, max_open_risk=150.0, daily_loss=300.0, hard_drawdown=1800.0, funded_drawdown=2000.0,
                   flat_minute=955, max_gap_minutes=60)
                   
    r_c = me.execute(d_mnq_15, sig_crabel_d_plus, atr_15, cfg_c)
    act_c_15 = pd.Series(r_c['quantity'] != 0, index=b_mnq_15['timestamp_utc'])
    act_c_30 = act_c_15.reindex(b_mnq_30['timestamp_utc'], method='ffill').fillna(False).to_numpy()
    sig_1_routed = np.where(~act_c_30, sig_1_d_plus, 0).astype(np.int8)
    r_1 = me.execute(d_mnq_30, sig_1_routed, f_1['atr'], cfg_1)
    act_1_30 = pd.Series(r_1['quantity'] != 0, index=b_mnq_30['timestamp_utc'])
    act_all_60 = (act_c_15.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False) | act_1_30.reindex(b_mnq_60['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
    sig_2_routed = np.where(~act_all_60, sig_2_d_plus, 0).astype(np.int8)
    r_2 = me.execute(d_mnq_60, sig_2_routed, f_2['atr'], cfg_2)
    act_2_60 = pd.Series(r_2['quantity'] != 0, index=b_mnq_60['timestamp_utc'])
    act_all_mnq = (act_c_15.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) | act_1_30.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False) | act_2_60.reindex(b_mes_30['timestamp_utc'], method='ffill').fillna(False)).to_numpy()
    sig_mes_routed = np.where(~act_all_mnq, sig_mes_d_plus, 0).astype(np.int8)
    r_mes = me.execute(d_mes_30, sig_mes_routed, f_mes['atr'], cfg_mes)
    
    intraday_trades = []
    for name, r, b_bar in [('Crabel', r_c, b_mnq_15), ('S1_30m', r_1, b_mnq_30), ('S2_60m', r_2, b_mnq_60), ('MES_30m', r_mes, b_mes_30)]:
        if len(r['trade_entry']):
            for net, en in zip(r['trade_net'], r['trade_entry']):
                dt = b_bar['date'].iloc[en]
                intraday_trades.append({
                    "date": dt,
                    "sleeve": name,
                    "net_1c": float(net),
                    "mae_1c": -35.0,
                    "type": "intraday"
                })
                
    # Overnight
    b_mnq_1m = m1.load_bars('MNQ', 1, start_date, end_date, split_name)
    b_mes_1m = m1.load_bars('MES', 1, start_date, end_date, split_name)
    
    def get_nights(b):
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
            rth_close=b[(b.sod >= 955) & (b.sod < 960)].groupby("date").close.last(),
            o1800=at(1080, "open", day)
        ))
        ent = pd.DataFrame(dict(
            e1805=at(1085, "open"),
            x0945=at(585, "open")
        ))
        pre = b[(b.nk.notna()) & ((b.sod >= 1086) | (b.sod < 570))].groupby("nk")
        ent["low_night"] = pre.low.min()
        n["ref_close"] = n.rth_close.ffill()
        n = n.join(ent, how="inner").dropna(subset=["e1805", "x0945", "ref_close"])
        n["gap"] = n.o1800 / n.ref_close - 1
        n["sd20"] = n.gap.rolling(20, min_periods=15).std().shift(1)
        return n

    n_mnq = get_nights(b_mnq_1m)
    n_mes = get_nights(b_mes_1m)
    
    mg = n_mes.gap.reindex(n_mnq.index)
    msd = n_mes.sd20.reindex(n_mnq.index)
    mask_ovn = ((n_mnq.gap <= -0.5 * n_mnq.sd20) & (mg <= -0.5 * msd)).fillna(False)
    
    same_backw_map = get_same_day_backwardation_map(n_mnq.index)
    
    overnight_trades = []
    SPEC_MNQ = dict(tick=0.25, tv=0.5, spread=1.75)
    COMM, SLIP = 0.61, 1.0
    ovn_cost = (SPEC_MNQ["spread"] + 2 * SLIP) * SPEC_MNQ["tv"] + 2 * COMM
    
    all_nights_list = sorted(list(n_mnq.index))
    for idx_d, d in enumerate(all_nights_list):
        if mask_ovn.loc[d] and not same_backw_map.get(d, False):
            nd = all_nights_list[idx_d + 1] if (idx_d + 1) < len(all_nights_list) else None
            if nd:
                e1805 = float(n_mnq.loc[d, "e1805"])
                x0945 = float(n_mnq.loc[d, "x0945"])
                low_nt = float(n_mnq.loc[d, "low_night"])
                pnl = (x0945 - e1805) * 2.0 - ovn_cost
                mae = (low_nt - e1805) * 2.0
                # Strict 25-pt bracket stop: if mae <= -25 pts, stop out at -25 pts
                if mae <= -25.0 * 2.0:
                    pnl = -25.0 * 2.0 - ovn_cost
                    mae = -25.0 * 2.0
                overnight_trades.append({
                    "date": nd,
                    "sleeve": "Overnight_Dip",
                    "net_1c": float(pnl),
                    "mae_1c": float(mae),
                    "type": "overnight"
                })
                
    print(f"  Intraday trades: {len(intraday_trades)}, Overnight trades: {len(overnight_trades)}")
    return intraday_trades, overnight_trades

# Extract both partitions
val_intra, val_ovn = extract_book_d_split("validation", "2024-01-01", "2026-01-01")
test_intra, test_ovn = extract_book_d_split("test", "2026-01-01", "2027-01-01")

with open(ROOT / "data/processed/val_book_d_trades.json", "w") as f:
    json.dump({"intra": val_intra, "ovn": val_ovn}, f, indent=2, default=str)

with open(ROOT / "data/processed/test_book_d_trades.json", "w") as f:
    json.dump({"intra": test_intra, "ovn": test_ovn}, f, indent=2, default=str)

print("Saved val and test Book D+ trades successfully!")
