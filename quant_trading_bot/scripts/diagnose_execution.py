"""Explain registered validation trade outcomes; never reads reserved test prices."""
from pathlib import Path
import json
import pandas as pd
from quant_futures.research import json_write

ROOT = Path(__file__).resolve().parents[1]
rows = []
for path in sorted((ROOT/"reports").glob("final_market_campaign_*m.json")):
    study = json.loads(path.read_text())
    for instrument, run in study["runs"].items():
        directory = Path(run["path"])
        for model in json.loads((directory/"leaderboard.json").read_text()):
            trades = pd.read_parquet(directory/f"{model['candidate_id']}_trades.parquet")
            reasons = trades.reason.value_counts().to_dict() if len(trades) else {}
            rows.append(dict(instrument=instrument, timeframe_minutes=study["timeframe_minutes"], candidate_id=model["candidate_id"],
                trades=len(trades), net_pnl=model["net_pnl"], gross_pnl=model["gross_pnl"], cash_fees=model["fees"],
                exposed_fraction=model["exposed_fraction"], exit_reasons=reasons,
                ambiguous_stop_fraction=reasons.get("stop_ambiguous", 0)/len(trades) if len(trades) else None))
json_write(ROOT/"reports/execution_diagnostics.json", dict(test_accessed=False,
    interpretation="Gross P&L already contains adverse execution prices; cash fees are separated. Ambiguous stops are conservative OHLC bounds, not observed tick paths. No-trade models have no estimated edge. Different participation is not evidence that ML adds alpha.", rows=rows))
print(json.dumps(dict(candidates=len(rows), trading_candidates=sum(row["trades"] > 0 for row in rows))))
