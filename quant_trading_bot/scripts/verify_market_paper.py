"""Bounded actual-market replay/restart parity. Does not use reserved test data."""
from pathlib import Path
import json
import joblib
import pandas as pd
from quant_futures.research import load_dataset, candidate_signal, json_write, code_identity
from quant_futures.features import build_features
from quant_futures.backtest import run_backtest
from quant_futures.config import ResearchConfig
from quant_futures.durable_paper import DurablePaperSession, read_ledger
from quant_futures.paper import compare_paper_backtest
from paper_compatibility import paper_bundle

ROOT = Path(__file__).resolve().parents[1]
campaign = json.loads((ROOT/"reports/latest_market_campaign.json").read_text())
checks = []
for instrument, run in campaign["runs"].items():
    directory = Path(run["path"])
    bundle = paper_bundle(directory, json.loads((directory/"experiment.json").read_text()))
    bars, _, _ = load_dataset(instrument+":validation", minutes=bundle["config"]["timeframe_minutes"])
    # Replay intentionally starts cold on the same bounded market observations
    # for both engines; it is a software comparison, not a forward paper record.
    bars = bars.iloc[-240:].reset_index(drop=True)
    cfg = ResearchConfig.model_validate(bundle["config"])
    output = directory/("recovery_parity_"+code_identity()["source_hash"][:10])
    session = DurablePaperSession(bundle, output, test_receipt=ROOT/"reports/test_receipt.json", replay=True)
    for index, record in enumerate(bars.to_dict("records")):
        session.on_bar(record)
        if index == 119:
            session = DurablePaperSession(bundle, output, test_receipt=ROOT/"reports/test_receipt.json", replay=True, resume=True)
    # Terminal accounting close is explicit, matching historical Simulator.finish.
    terminal = session.simulator.finish()
    ledger = read_ledger(output)
    curve = pd.DataFrame([entry["curve"] for entry in ledger])
    curve.timestamp_utc = pd.to_datetime(curve.timestamp_utc, utc=True)
    curve.iloc[-1] = terminal["curve"].iloc[-1]
    trades = pd.DataFrame([trade for entry in ledger for trade in entry["trades"]]+session.simulator.trades)
    signals = candidate_signal(bundle["candidate"], bars, build_features(bars, cfg.timeframe_minutes), cfg, bundle["model"])
    expected = run_backtest(bars, signals, cfg)
    comparison = compare_paper_backtest(dict(curve=curve, trades=trades), expected)
    assert comparison["accounting_matches"]
    pd.testing.assert_series_equal(curve.equity.astype(float), expected["curve"].equity.astype(float), check_names=False)
    session.stop()
    checks.append(dict(instrument=instrument, timeframe_minutes=cfg.timeframe_minutes, rows=len(bars), restart_after=120, **comparison,
        note="2025 historical completed-bar replay with checkpoint resume; not forward paper evidence"))
receipt = ROOT/"reports/market_paper_verification.json"
if receipt.exists():
    prior = json.loads(receipt.read_text())
    if prior["source_hash"] == code_identity()["source_hash"]:
        for entry in prior["checks"]:
            entry.setdefault("timeframe_minutes", 15)
            if not any(row["instrument"] == entry["instrument"] and row["timeframe_minutes"] == entry["timeframe_minutes"] for row in checks):
                checks.append(entry)
json_write(receipt, dict(passed=True, **code_identity(), test_accessed=False, checks=checks))
print(json.dumps(checks, indent=2))
