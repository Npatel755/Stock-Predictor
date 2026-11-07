import sqlite3
import json

db = sqlite3.connect('quant_trading_bot/runs/training_search_100k_v1/checkpoints.sqlite')
print("Total rows:", db.execute("SELECT COUNT(*) FROM results").fetchone()[0])

query = "SELECT payload FROM results WHERE instrument='MNQ'"
candidates = []
for (payload,) in db.execute(query):
    r = json.loads(payload)
    if r['family'] == 'breakout' and r['net_pnl'] > 5000 and r['intrabar_drawdown'] < 1800:
        candidates.append(r)

print(f"MNQ breakout candidates with Net > 5000 & Intrabar DD < 1800: {len(candidates)}")
candidates.sort(key=lambda x: -x['net_pnl'])
for c in candidates[:10]:
    p = c['parameters']
    print(f"{c['config_id']} | Net: ${c['net_pnl']:,.2f} | DD: ${c['intrabar_drawdown']:,.2f} | PF: {c['profit_factor']:.2f} | TargetR: {p['target_r']} | StopATR: {p['stop_atr']} | TrailATR: {p['trailing_atr']} | Qualified: {c.get('qualified')} | Folds: {c.get('positive_folds')}")
