import json

cat = json.load(open('quant_trading_bot/data/catalog.json'))
for sym in ['MNQ', 'MES', 'NQ', 'ES']:
    for sp in ['train', 'validation', 'test']:
        c = cat['instruments'][sym]['splits'][sp]['coverage']
        print(f"{sym:4} {sp:10}: {c['start']} to {c['end']} ({c['rows']:,} rows)")
