import pandas as pd
import json

df = pd.read_csv('quant_trading_bot/runs/training_search_10m_institutional/ranked.csv')
records = []
for _, row in df.iterrows():
    p = json.loads(row['payload'])
    if p.get('contracts') == 1 and p.get('positive_folds') == 4 and p.get('intrabar_drawdown', 9999) < 650:
        cfg = json.loads(p['payload'])
        records.append({
            'config_id': p['config_id'],
            'instrument': p['instrument'],
            'family': p['family'],
            'net_pnl': p['net_pnl'],
            'dd': p['intrabar_drawdown'],
            'trades': p['trades'],
            'pf': p['profit_factor'],
            'exp': p['net_pnl'] / p['trades'],
            'calmar': p['net_pnl'] / max(p['intrabar_drawdown'], 1),
            'cfg': cfg
        })

print(f"Total qualifying 1c with 4/4 pos folds and DD < 650: {len(records)}")
rdf = pd.DataFrame(records)
if not rdf.empty:
    print(rdf.groupby(['instrument', 'family']).size())
    
    print('\n=== TOP 5 MES QUALIFIERS ===')
    mes = rdf[rdf.instrument=='MES'].sort_values('calmar', ascending=False)
    for _, r in mes.head(5).iterrows():
        c = r['cfg']
        print(f"{r['config_id']} | {c['family']} lb={c['lookback']} th={c['threshold']} stop={c['stop_atr']} tgt={c['target_r']} hold={c['hold_bars']} sess={c['session_start']}-{c['session_end']} trail={c['trailing_atr']} | Net: ${r['net_pnl']:,.2f} | DD: ${r['dd']:.2f} | PF: {r['pf']:.2f} | Exp: ${r['exp']:.2f} | Calmar: {r['calmar']:.2f}")

    print('\n=== TOP 10 MNQ QUALIFIERS ===')
    mnq = rdf[rdf.instrument=='MNQ'].sort_values('calmar', ascending=False)
    for _, r in mnq.head(10).iterrows():
        c = r['cfg']
        print(f"{r['config_id']} | {c['family']} lb={c['lookback']} th={c['threshold']} stop={c['stop_atr']} tgt={c['target_r']} hold={c['hold_bars']} sess={c['session_start']}-{c['session_end']} trail={c['trailing_atr']} | Net: ${r['net_pnl']:,.2f} | DD: ${r['dd']:.2f} | PF: {r['pf']:.2f} | Exp: ${r['exp']:.2f} | Calmar: {r['calmar']:.2f}")

    print('\n=== TOP 10 MNQ BREAKOUT QUALIFIERS ===')
    mnq_b = rdf[(rdf.instrument=='MNQ') & (rdf.family=='breakout')].sort_values('calmar', ascending=False)
    for _, r in mnq_b.head(10).iterrows():
        c = r['cfg']
        print(f"{r['config_id']} | {c['family']} lb={c['lookback']} th={c['threshold']} stop={c['stop_atr']} tgt={c['target_r']} hold={c['hold_bars']} sess={c['session_start']}-{c['session_end']} trail={c['trailing_atr']} | Net: ${r['net_pnl']:,.2f} | DD: ${r['dd']:.2f} | PF: {r['pf']:.2f} | Exp: ${r['exp']:.2f} | Calmar: {r['calmar']:.2f}")
