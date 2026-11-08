"""Automatic paper testing for the frozen MES/MNQ ensemble candidates.

Every run re-executes the exact research engine (``scripts/mass_*.py`` plus
``training_5m_v2_policy.execution_cfg_5m_v2``) over 15-minute bars built from
an append-only store of completed 1-minute bars (a 15-minute bar exists only
when all 15 source minutes are present, exactly like the research DuckDB
query) and appends newly closed simulated trades to a per-candidate
``ledger.jsonl``.  Earlier ledgered trades are re-derived on
every run; any difference is recorded as a ``divergence`` record instead of
being overwritten, so batch and paper results are identical by construction.

Nothing here routes an order anywhere.  Bars come from a public delayed
continuous front-month feed (Yahoo ``MES=F``/``MNQ=F`` 1-minute history) unless
a file source is supplied.  On overlapping days it matched the Databento
research series to within a tick on highs/lows with ~2% of 15-minute bars
missing, but it is not that series and its roll handling is undisclosed, so
paper results are labeled as proxy results.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from quant_futures.session_calendar import apply_early_close

from .data import canonical

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
SOURCE_MINUTES = 1
BAR_MINUTES = 15
COMPLETION_GRACE = timedelta(minutes=2)
WARMUP_BARS = 400  # 15-minute bars kept before the paper start for indicator warm-up
INITIAL_BALANCE = 50000.0
FUNDED_DRAWDOWN = 2000.0
ENGINE_FILES = ("mass_research.py", "mass_execution.py", "mass_features.py", "mass_metrics.py", "mass_configurations.py",
                "mass_verify.py", "training_5m_v2_policy.py")
YAHOO_SYMBOLS = {"MES": "MES=F", "MNQ": "MNQ=F"}

_MES_MOM = dict(instrument="MES", family="momentum", lookback=16, threshold=1.5, stop_atr=1.75,
                target_r=2.5, hold_bars=32, session_start=585, session_end=945, trailing_atr=2.0)
_MNQ_BRK = dict(instrument="MNQ", family="breakout", lookback=10, threshold=1.25, stop_atr=1.75,
                target_r=2.25, hold_bars=8, session_start=600, session_end=720, trailing_atr=2.0)
_MNQ_VOL = dict(instrument="MNQ", family="volatility", lookback=8, threshold=0.5, stop_atr=2.0,
                target_r=5.0, hold_bars=32, session_start=600, session_end=720, trailing_atr=4.0)
_MNQ_HYB = dict(instrument="MNQ", family="hybrid", lookback=20, threshold=1.25, stop_atr=2.25,
                target_r=5.0, hold_bars=8, session_start=720, session_end=945, trailing_atr=0.0)
_MNQ_E57 = dict(instrument="MNQ", family="momentum", lookback=16, threshold=1.5, stop_atr=1.0,
                target_r=4.0, hold_bars=12, session_start=585, session_end=945, trailing_atr=2.0)


def _sleeve(name, base, contracts):
    return dict(name=name, **base, max_contracts=int(contracts))


CANDIDATES = {
    "portfolio_e": dict(
        version="1.0.0", label="Portfolio E (3 MES momentum + 2 MNQ breakout)",
        sleeves=[_sleeve("MES_MOM_3c", _MES_MOM, 3), _sleeve("MNQ_BRK_E_2c", _MNQ_BRK, 2)],
        provenance="runs/saved_portfolio_E_undisputed_champion_mes_mom_mnq_brk/portfolio_config.json; "
                   "reproduced train +19,095.50/DD 1,395.25, validation +3,142.25/1,744.25, test(2026) +6,562.25/964.75",
    ),
    "ensemble_epsilon": dict(
        version="1.0.0", label="Ensemble Epsilon (1 MES momentum + 1 MNQ volatility + 1 MNQ e57)",
        sleeves=[_sleeve("MES_MOM_1c", _MES_MOM, 1), _sleeve("MNQ_VOL_1c", _MNQ_VOL, 1), _sleeve("MNQ_E57_1c", _MNQ_E57, 1)],
        provenance="user screenshot numbers reproduced with MES_MOM_1c (scripts/evaluate_multi_strategy_ensembles.py "
                   "uses MES_MOM_2c); train +14,241.00/DD 2,186.00, validation +4,052.75/1,724.75, test(2026) +4,723.50/483.50",
    ),
    "portfolio_e_scaled": dict(
        version="1.0.0", label="Portfolio E Scaled (2 MES momentum + 2 MNQ breakout; research-grade)",
        sleeves=[_sleeve("MES_MOM_2c", _MES_MOM, 2), _sleeve("MNQ_BRK_E_2c", _MNQ_BRK, 2)],
        provenance="Codex 2026-11-08 size variant of portfolio_e chosen after the early-close fix; reproduced continuous "
                   "validation 2024-25 +2,808.25 / 172 trades (MES_MOM_2c +329, MNQ_BRK_E_2c +2,480), combined intrabar DD ~1,755. "
                   "Contract count was selected with validation in view: research-grade, not an independent candidate.",
    ),
    "ensemble_beta": dict(
        version="1.0.0", label="Ensemble Beta (2 MES momentum + 1 MNQ breakout + 1 MNQ hybrid)",
        sleeves=[_sleeve("MES_MOM_2c", _MES_MOM, 2), _sleeve("MNQ_BRK_E_1c", _MNQ_BRK, 1), _sleeve("MNQ_HYB_C_1c", _MNQ_HYB, 1)],
        provenance="scripts/evaluate_multi_strategy_ensembles.py; reproduced train +12,817.25/DD 1,080.75, "
                   "validation +787.00/1,343.62, test(2026) +3,182.25/908.38",
    ),
}


def _load(name):
    path = SCRIPTS / f"{name}.py"
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


_engine = None


def engine():
    global _engine
    if _engine is None:
        research = _load("mass_research")
        policy = _load("training_5m_v2_policy")
        _engine = dict(arrays=research.arrays, features=research.features, signal_for=research.signal_for,
                       execute=research.execute, reasons=research.TRADE_REASONS, execution_cfg=policy.execution_cfg_5m_v2)
    return _engine


def engine_identity():
    digest = hashlib.sha256()
    for name in ENGINE_FILES + ("ensemble_paper.py",):
        path = Path(__file__).parent / name if name == "ensemble_paper.py" else SCRIPTS / name
        digest.update(name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def utc_now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- bar store

class BarStore:
    """Append-only completed-bar store; first observation of a bar wins."""

    columns = ["timestamp_utc", "open", "high", "low", "close", "volume", "fetched_at"]

    def __init__(self, root, instrument):
        self.root = Path(root)
        self.instrument = instrument
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / f"{instrument}_1m.csv"
        self.revisions = self.root / f"{instrument}_revisions.jsonl"

    def read(self):
        if not self.path.exists():
            return pd.DataFrame(columns=self.columns)
        frame = pd.read_csv(self.path)
        frame["timestamp_utc"] = pd.to_datetime(frame.timestamp_utc, utc=True)
        frame = frame.drop_duplicates("timestamp_utc", keep="first").sort_values("timestamp_utc")
        return frame.reset_index(drop=True)

    def append(self, bars, fetched_at):
        """Append completed bars not yet stored; log price revisions of stored bars."""
        existing = self.read()
        known = existing.set_index("timestamp_utc") if len(existing) else None
        added = 0
        revised = 0
        new_rows = []
        for row in bars.itertuples(index=False):
            ts = pd.Timestamp(row.timestamp_utc)
            if known is not None and ts in known.index:
                old = known.loc[ts]
                if any(abs(float(old[c]) - float(getattr(row, c))) > 1e-9 for c in ("open", "high", "low", "close")):
                    revised += 1
                    with self.revisions.open("a") as handle:
                        handle.write(json.dumps(dict(timestamp_utc=ts.isoformat(), fetched_at=fetched_at.isoformat(),
                                                     stored={c: float(old[c]) for c in ("open", "high", "low", "close", "volume")},
                                                     seen={c: float(getattr(row, c)) for c in ("open", "high", "low", "close", "volume")})) + "\n")
                continue
            new_rows.append(dict(timestamp_utc=ts.isoformat(), open=float(row.open), high=float(row.high),
                                 low=float(row.low), close=float(row.close), volume=int(round(float(row.volume))),
                                 fetched_at=fetched_at.isoformat()))
            added += 1
        if new_rows:
            header = not self.path.exists()
            pd.DataFrame(new_rows, columns=self.columns).to_csv(self.path, mode="a", header=header, index=False)
        return dict(added=added, revised=revised, stored=len(existing) + added)


def completed(bars, now, minutes=SOURCE_MINUTES):
    """Keep bars whose interval closed before ``now`` minus the grace."""
    cutoff = pd.Timestamp(now) - pd.Timedelta(minutes=minutes) - COMPLETION_GRACE
    return bars[bars.timestamp_utc <= cutoff]


def aggregate(one_minute):
    """Exact-count 15-minute bars from 1-minute bars (all 15 source minutes required)."""
    frame = one_minute.sort_values("timestamp_utc").drop_duplicates("timestamp_utc")
    bucket = frame.timestamp_utc.dt.floor(f"{BAR_MINUTES}min")
    grouped = frame.groupby(bucket)
    bars = grouped.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), volume=("volume", "sum"))
    count = grouped.size()
    span = grouped.timestamp_utc.max() - grouped.timestamp_utc.min()
    keep = (count == BAR_MINUTES) & (span == pd.Timedelta(minutes=BAR_MINUTES - 1))
    bars = bars[keep].reset_index()
    bars.columns = ["timestamp_utc", "open", "high", "low", "close", "volume"]
    return bars


def normalize_bars(frame):
    """Normalize a vendor OHLCV frame (index or column timestamps) to store columns."""
    frame = frame.copy()
    if "timestamp_utc" not in frame.columns:
        frame = frame.reset_index().rename(columns={frame.index.name or "index": "timestamp_utc", "Datetime": "timestamp_utc",
                                                    "Date": "timestamp_utc"})
    frame.columns = [str(c).lower() for c in frame.columns]
    frame["timestamp_utc"] = pd.to_datetime(frame.timestamp_utc, utc=True)
    frame = frame[["timestamp_utc", "open", "high", "low", "close", "volume"]].dropna()
    frame = frame[frame.volume >= 0]
    frame = frame[frame.timestamp_utc.dt.second == 0]
    return frame.sort_values("timestamp_utc").drop_duplicates("timestamp_utc").reset_index(drop=True)


class YahooSource:
    """Public delayed continuous front-month 1m bars; not an exchange feed."""

    name = "yahoo MES=F/MNQ=F 1m continuous front month aggregated to 15m (delayed, unofficial proxy)"

    def __init__(self, period="8d"):
        self.period = period

    def fetch(self, instrument):
        import yfinance as yf
        history = yf.Ticker(YAHOO_SYMBOLS[instrument]).history(period=self.period, interval="1m", auto_adjust=False)
        if history is None or len(history) == 0:
            raise RuntimeError(f"No bars returned for {instrument}")
        history.index = pd.DatetimeIndex(history.index).tz_convert("UTC")
        history.index.name = "timestamp_utc"
        return normalize_bars(history)


class FileSource:
    """CSV 1-minute bars (timestamp_utc,open,high,low,close,volume) per instrument, for tests and replays."""

    name = "file"

    def __init__(self, paths):
        self.paths = {k: Path(v) for k, v in paths.items()}

    def fetch(self, instrument):
        return normalize_bars(pd.read_csv(self.paths[instrument]))


def ingest(root, source, now=None, instruments=("MES", "MNQ")):
    now = now or utc_now()
    report = {}
    for instrument in instruments:
        bars = completed(source.fetch(instrument), now)
        report[instrument] = BarStore(root, instrument).append(bars, now)
    return report


# ---------------------------------------------------------------- engine run

def canonical_bars(stored, instrument, contract_label):
    frame = stored[["timestamp_utc", "open", "high", "low", "close", "volume"]].copy()
    frame["high"] = frame[["open", "high", "low", "close"]].max(axis=1)
    frame["low"] = frame[["open", "high", "low", "close"]].min(axis=1)
    frame["volume"] = frame.volume.round().astype(float)
    frame["instrument"] = instrument
    frame["contract"] = contract_label
    return canonical(frame)


def run_sleeve(cfg, bars, start):
    """Exact research-engine run of one sleeve; execution starts at ``start``."""
    eng = engine()
    data = apply_early_close(eng["arrays"](bars), bars)
    features = eng["features"](bars, int(cfg["lookback"]))
    raw = eng["signal_for"](cfg, features).astype(np.int8)
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.day_of_week.to_numpy() < 5
    mask = (decision >= cfg["session_start"]) & (decision < cfg["session_end"]) & weekdays
    signal = np.where(mask, raw, 0).astype(np.int8)
    first = int((bars.timestamp_utc < pd.Timestamp(start)).sum())
    sliced = {k: np.ascontiguousarray(v[first:]) for k, v in data.items()}
    sliced["session"] = pd.factorize(sliced["session"], sort=False)[0].astype(np.int64)
    sliced["contract"] = pd.factorize(sliced["contract"], sort=False)[0].astype(np.int64)
    result = eng["execute"](sliced, signal[first:], np.ascontiguousarray(features["atr"][first:]), eng["execution_cfg"](cfg))
    stamps = pd.to_datetime(sliced["timestamp"], unit="ns", utc=True)
    trades = []
    for i in range(len(result["trade_entry"])):
        trades.append(dict(
            sleeve=cfg["name"], entry_ts=stamps[int(result["trade_entry"][i])].isoformat(),
            exit_ts=stamps[int(result["trade_exit"][i])].isoformat(), side=int(result["trade_side"][i]),
            qty=int(result["trade_qty"][i]), entry_price=float(result["trade_entryprice"][i]),
            exit_price=float(result["trade_exitprice"][i]), net=round(float(result["trade_net"][i]), 2),
            fees=round(float(result["trade_fees"][i]), 2), reason=eng["reasons"].get(int(result["trade_reason"][i]), "unknown")))
    curve = pd.DataFrame(dict(ts=stamps, cash=result["cash"], equity=result["equity"], worst=result["worst"]))
    position = dict(quantity=int(result["quantity"][-1]) if len(stamps) else 0,
                    unrealized=round(float(result["equity"][-1] - result["cash"][-1]), 2) if len(stamps) else 0.0,
                    last_close=float(sliced["close"][-1]) if len(stamps) else None)
    return dict(trades=trades, curve=curve, position=position, lock=result["lock_reason"],
                funded_failed=bool(np.any(result["funded_failed"])) if len(stamps) else False)


def combine(curves):
    merged = None
    for i, curve in enumerate(curves):
        part = curve[["ts", "cash", "equity", "worst"]].rename(columns={"cash": f"c{i}", "equity": f"e{i}", "worst": f"w{i}"})
        merged = part if merged is None else pd.merge(merged, part, on="ts", how="outer")
    merged = merged.sort_values("ts").ffill().fillna(INITIAL_BALANCE)
    realized = sum(merged[c] - INITIAL_BALANCE for c in merged if c.startswith("c"))
    equity = sum(merged[c] - INITIAL_BALANCE for c in merged if c.startswith("e"))
    worst = sum(merged[c] - INITIAL_BALANCE for c in merged if c.startswith("w"))
    peak = equity.cummax()
    return dict(realized=round(float(realized.iloc[-1]), 2), net=round(float(equity.iloc[-1]), 2),
                closed_drawdown=round(float((peak - equity).max()), 2),
                intrabar_drawdown=round(float((peak - worst).max()), 2),
                equity=pd.DataFrame(dict(ts=merged.ts, net=equity.to_numpy())))


def notify(title, body):
    """Push via ntfy.sh when NTFY_TOPIC is set; failures are logged, never raised."""
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return False
    try:
        request = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(), method="POST",
                                         headers={"Title": title, "Tags": "chart_with_upwards_trend", "Priority": "default"})
        urllib.request.urlopen(request, timeout=10).read()
        return True
    except Exception as error:  # noqa: BLE001
        print(f"ntfy failed: {error}", file=sys.stderr)
        return False


# ---------------------------------------------------------------- ledger

def read_ledger(path):
    records = []
    path = Path(path)
    if not path.exists():
        return records
    seen = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # incomplete final append
        if record["seq"] in seen:
            continue
        seen.add(record["seq"])
        records.append(record)
    return sorted(records, key=lambda r: r["seq"])


def append_records(path, records, start_seq):
    with Path(path).open("a") as handle:
        for offset, record in enumerate(records):
            handle.write(json.dumps(dict(seq=start_seq + offset, **record), sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    return start_seq + len(records)


def trade_key(trade):
    return (trade["sleeve"], trade["entry_ts"], trade["exit_ts"], trade["side"], trade["qty"],
            round(trade["entry_price"], 4), round(trade["exit_price"], 4), round(trade["net"], 2))


def update_candidate(root, key, spec, bars, start, now, source_name):
    folder = Path(root) / key
    folder.mkdir(parents=True, exist_ok=True)
    ledger_path = folder / "ledger.jsonl"
    ledger = read_ledger(ledger_path)
    next_seq = (ledger[-1]["seq"] + 1) if ledger else 0
    prior = [r for r in ledger if r["kind"] == "trade"]
    prior_keys = {trade_key(r) for r in prior}
    last_exit = max((r["exit_ts"] for r in prior), default=None)

    runs = {s["name"]: run_sleeve(s, bars[s["instrument"]], start) for s in spec["sleeves"]}
    trades = sorted((t for r in runs.values() for t in r["trades"]), key=lambda t: (t["exit_ts"], t["entry_ts"], t["sleeve"]))
    current_keys = {trade_key(t) for t in trades}
    missing = [r for r in prior if trade_key(r) not in current_keys]
    new_trades = [t for t in trades if trade_key(t) not in prior_keys and (last_exit is None or t["exit_ts"] > last_exit)]
    late = [t for t in trades if trade_key(t) not in prior_keys and last_exit is not None and t["exit_ts"] <= last_exit]

    records = []
    for trade in missing:
        records.append(dict(kind="divergence", detail="ledgered trade no longer reproduced", trade=trade_key(trade), run_ts=now.isoformat()))
    for trade in late:
        records.append(dict(kind="divergence", detail="new trade dated before the last ledgered exit", trade=trade_key(trade), run_ts=now.isoformat()))
    for trade in new_trades:
        records.append(dict(kind="trade", **trade))
    portfolio = combine([r["curve"] for r in runs.values()])
    run_record = dict(kind="run", run_ts=now.isoformat(), candidate=key, version=spec["version"],
                      bars_through={k: v.timestamp_utc.max().isoformat() for k, v in bars.items()},
                      start=pd.Timestamp(start).isoformat(), source=source_name, engine_sha256=engine_identity(),
                      trades=len(trades), net=portfolio["net"], realized=portfolio["realized"],
                      closed_drawdown=portfolio["closed_drawdown"], intrabar_drawdown=portfolio["intrabar_drawdown"],
                      positions={n: r["position"] for n, r in runs.items()}, locks={n: r["lock"] for n, r in runs.items()},
                      funded_failed=any(r["funded_failed"] for r in runs.values()),
                      divergences=len(missing) + len(late))
    records.append(run_record)
    append_records(ledger_path, records, next_seq)
    previous_run = next((r for r in reversed(ledger) if r["kind"] == "run"), None)
    for trade in new_trades:
        notify(f"{spec['label'].split(' (')[0]}: {trade['sleeve']} closed {trade['net']:+,.2f}",
               f"{'long' if trade['side'] > 0 else 'short'} x{trade['qty']} {trade['entry_price']:,.2f} -> {trade['exit_price']:,.2f} ({trade['reason']}); "
               f"candidate net {portfolio['net']:+,.2f}, intrabar DD {portfolio['intrabar_drawdown']:,.2f}")
    if previous_run is not None:
        for name, pos in run_record["positions"].items():
            before = previous_run.get("positions", {}).get(name, {}).get("quantity", 0)
            if pos["quantity"] and pos["quantity"] != before:
                notify(f"{spec['label'].split(' (')[0]}: {name} opened {'long' if pos['quantity'] > 0 else 'short'} x{abs(pos['quantity'])}",
                       f"last close {pos['last_close']:,.2f}; candidate net {portfolio['net']:+,.2f}")
    total_divergences = sum(1 for r in ledger if r["kind"] == "divergence") + len(missing) + len(late)
    status = dict(candidate=key, version=spec["version"], label=spec["label"], provenance=spec["provenance"],
                  updated=now.isoformat(), source=source_name, start=run_record["start"], bars_through=run_record["bars_through"],
                  net=portfolio["net"], realized=portfolio["realized"], unrealized=round(portfolio["net"] - portfolio["realized"], 2),
                  closed_drawdown=portfolio["closed_drawdown"], intrabar_drawdown=portfolio["intrabar_drawdown"],
                  funded_buffer=round(FUNDED_DRAWDOWN - portfolio["intrabar_drawdown"], 2), trades=len(trades),
                  wins=sum(1 for t in trades if t["net"] > 0), fees=round(sum(t["fees"] for t in trades), 2),
                  positions=run_record["positions"], locks=run_record["locks"], funded_failed=run_record["funded_failed"],
                  divergences=total_divergences, last_trades=trades[-5:],
                  engine_sha256=run_record["engine_sha256"],
                  bar_minutes=BAR_MINUTES,
                  disclaimer="Simulated fills on 15m bars from a delayed public continuous series; no orders are routed anywhere.")
    (folder / "status.json").write_text(json.dumps(status, indent=1, sort_keys=True))
    equity = portfolio["equity"].copy()
    equity["ts"] = equity.ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    equity.iloc[-min(len(equity), 2000):].to_csv(folder / "equity.csv", index=False)
    return status


def run_once(root, source, start, now=None, candidates=None):
    now = now or utc_now()
    root = Path(root)
    report = ingest(root / "bars", source, now)
    stored = {k: BarStore(root / "bars", k).read() for k in ("MES", "MNQ")}
    start_ts = pd.Timestamp(start).tz_localize("UTC") if pd.Timestamp(start).tzinfo is None else pd.Timestamp(start)
    bars = {}
    for instrument, frame in stored.items():
        if len(frame) == 0:
            raise RuntimeError(f"No stored bars for {instrument}")
        frame = aggregate(frame)
        if len(frame) == 0:
            raise RuntimeError(f"No complete {BAR_MINUTES}-minute bars for {instrument}")
        warm = frame[frame.timestamp_utc < start_ts].tail(WARMUP_BARS)
        live = frame[frame.timestamp_utc >= start_ts]
        bars[instrument] = canonical_bars(pd.concat([warm, live]), instrument, YAHOO_SYMBOLS[instrument])
    statuses = {}
    for key, spec in CANDIDATES.items():
        if candidates and key not in candidates:
            continue
        statuses[key] = update_candidate(root, key, spec, bars, start_ts, now, source.name)
    summary = dict(updated=now.isoformat(), ingest=report, start=start_ts.isoformat(), source=source.name,
                   candidates=statuses, total_net=round(sum(s["net"] for s in statuses.values()), 2))
    (root / "dashboard.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Automatic paper testing of the frozen MES/MNQ ensembles (no live orders).")
    parser.add_argument("command", choices=["run", "status"])
    parser.add_argument("--root", default=str(ROOT / "runs" / "paper_ensembles"))
    parser.add_argument("--start", default=None, help="Paper start (UTC date); default = stored in <root>/start.txt or today")
    parser.add_argument("--period", default="8d")
    parser.add_argument("--candidates", nargs="*", default=None)
    args = parser.parse_args(argv)
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    marker = root / "start.txt"
    if args.start:
        start = args.start
    elif marker.exists():
        start = marker.read_text().strip()
    else:
        start = utc_now().strftime("%Y-%m-%dT00:00:00+00:00")
    if not marker.exists():
        marker.write_text(start)
    if args.command == "status":
        path = root / "dashboard.json"
        print(path.read_text() if path.exists() else "{}")
        return 0
    summary = run_once(root, YahooSource(args.period), start, candidates=args.candidates)
    for key, status in summary["candidates"].items():
        print(f"{key}: net {status['net']:+.2f} realized {status['realized']:+.2f} intrabar DD {status['intrabar_drawdown']:.2f} "
              f"trades {status['trades']} divergences {status['divergences']} positions {status['positions']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
