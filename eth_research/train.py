"""Benchmark ETHUSD models with purged walk-forward CV and a locked holdout."""
import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from .backtest import Assumptions, simulate
from .data import ROOT, SOURCE, TICKER
from .features import build_features, eligible_indices
from .neural import TorchClassifier
from .perpetual_data import SOURCE as PERPETUAL_SOURCE, TICKER as PERPETUAL_TICKER


def candidates(epochs=8, sequence_length=24):
    return {
        "majority_baseline": lambda: DummyClassifier(strategy="prior"),
        "logistic_c01": lambda: make_pipeline(StandardScaler(), LogisticRegression(C=.1, max_iter=500)),
        "logistic_c1": lambda: make_pipeline(StandardScaler(), LogisticRegression(C=1., max_iter=500)),
        "random_forest": lambda: RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=100,
                                                         max_samples=.7, n_jobs=4, random_state=42),
        "extra_trees": lambda: ExtraTreesClassifier(n_estimators=200, max_depth=10, min_samples_leaf=60,
                                                     n_jobs=4, random_state=42),
        "hist_boost_shallow": lambda: HistGradientBoostingClassifier(max_iter=180, max_leaf_nodes=7,
                                                                       learning_rate=.04, l2_regularization=10,
                                                                       early_stopping=False, random_state=42),
        "hist_boost_medium": lambda: HistGradientBoostingClassifier(max_iter=200, max_leaf_nodes=15,
                                                                      learning_rate=.03, l2_regularization=20,
                                                                      early_stopping=False, random_state=42),
        "xgboost_shallow": lambda: XGBClassifier(n_estimators=250, max_depth=3, learning_rate=.03,
                                                  subsample=.8, colsample_bytree=.8, min_child_weight=100,
                                                  reg_lambda=20, tree_method="hist", n_jobs=4, random_state=42),
        "xgboost_medium": lambda: XGBClassifier(n_estimators=300, max_depth=5, learning_rate=.025,
                                                 subsample=.8, colsample_bytree=.8, min_child_weight=100,
                                                 reg_lambda=30, tree_method="hist", n_jobs=4, random_state=42),
        "mlp_32": lambda: TorchClassifier("mlp", hidden=32, epochs=epochs, sequence_length=sequence_length),
        "mlp_64": lambda: TorchClassifier("mlp", hidden=64, learning_rate=.0003, epochs=epochs, sequence_length=sequence_length),
        "lstm_24": lambda: TorchClassifier("lstm", hidden=24, epochs=epochs, sequence_length=sequence_length),
        "lstm_32": lambda: TorchClassifier("lstm", hidden=32, learning_rate=.0003, epochs=epochs, sequence_length=sequence_length),
        "cnn_32": lambda: TorchClassifier("cnn", hidden=32, epochs=epochs, sequence_length=sequence_length),
    }


def fit_model(model, x, y, indices):
    if isinstance(model, TorchClassifier):
        return model.fit(x, y, indices)
    return model.fit(x[indices], y[indices].astype(int))


def probability(model, x, indices):
    if isinstance(model, TorchClassifier):
        return model.predict_probability(x, indices)
    return model.predict_proba(x[indices])[:, 1]


def classification(y, p):
    pred = p >= .5
    return {"accuracy": float(accuracy_score(y, pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
            "roc_auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
            "log_loss": float(log_loss(y, p, labels=[0, 1])), "brier_score": float(brier_score_loss(y, p)),
            "samples": len(y), "up_fraction": float(np.mean(y))}


def block_bootstrap_accuracy_delta(y, selected, baseline, days, seed=42):
    """Paired UTC-day block bootstrap; preserves within-day serial dependence."""
    delta = ((selected >= .5) == y).astype(float) - ((baseline >= .5) == y).astype(float)
    daily = pd.DataFrame({"day": days, "delta": delta}).groupby("day").delta.agg(["sum", "count"])
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(daily), (2000, len(daily)))
    samples = daily["sum"].to_numpy()[draws].sum(axis=1) / daily["count"].to_numpy()[draws].sum(axis=1)
    return {"delta": float(delta.mean()), "ci_95": np.quantile(samples, [.025, .975]).tolist(),
            "method": "paired UTC-day block bootstrap, 2000 replicates"}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def train(args):
    # Bound native thread pools, including sklearn histogram boosting.
    from threadpoolctl import threadpool_limits
    threadpool_limits(limits=4)
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    if args.epochs < 1 or args.sequence_length < 2:
        raise ValueError("Epochs must be positive and sequence length must be at least two")
    ticker = PERPETUAL_TICKER if args.market == "binance_perpetual" else TICKER
    source = PERPETUAL_SOURCE if args.market == "binance_perpetual" else SOURCE
    # Read once so parsing and the recorded checksum always refer to the same bytes.
    source_bytes = args.bars.read_bytes()
    raw = pd.read_csv(io.BytesIO(source_bytes))
    if "ticker" not in raw or not raw.ticker.eq(ticker).all():
        raise ValueError(f"Training requires exclusively {ticker} rows with ticker provenance")
    if (pd.to_datetime(raw.timestamp, utc=True) + pd.Timedelta(minutes=5) > pd.Timestamp.now(tz="UTC")).any():
        raise ValueError("Incomplete or future bars cannot be used for training")
    (out / "dataset_snapshot.csv").write_bytes(source_bytes)
    frame, columns = build_features(raw, expected_ticker=ticker)
    indices = eligible_indices(frame, args.sequence_length)
    if len(indices) < 10000:
        raise ValueError("At least 10,000 complete labeled samples are required")
    x = frame[columns].to_numpy(dtype=np.float32)
    y = frame.target.to_numpy()
    cut = int(len(indices) * .8)
    development, test = indices[:cut - 2], indices[cut:]
    splits = [(development[a], development[b]) for a, b in TimeSeriesSplit(n_splits=3, gap=2).split(development)]
    for a, b in splits + [(development, test)]:
        if frame.iloc[a].label_end.max() > frame.iloc[b].information_time.min():
            raise AssertionError("Purged split contains overlapping labels")
    cfg = Assumptions(fee_bps_per_side=args.fee_bps, slippage_bps_per_side=args.slippage_bps,
                      notional_fraction=args.notional_fraction, daily_loss_limit=args.daily_loss_limit,
                      total_loss_limit=args.total_loss_limit)
    factories = candidates(args.epochs, args.sequence_length)
    if args.models:
        requested = args.models.split(",")
        factories = {name: factory for name, factory in factories.items() if name in requested or name == "majority_baseline"}
        if set(requested) - factories.keys():
            raise ValueError("Unknown model name")
    raw_times = pd.to_datetime(raw.timestamp, utc=True).sort_values()
    missing_intervals = int(raw_times.diff().gt(pd.Timedelta(minutes=5)).sum())
    missing_bars = int((raw_times.diff().dropna() / pd.Timedelta(minutes=5) - 1).clip(lower=0).sum())
    metadata = {"instrument": "Breakout ETHUSD research", "training_ticker": ticker, "market": args.market, "source": source,
                "timeframe": "5min", "target": "next five-minute bar close > open; flat is non-UP",
                "signal_time": "current completed bar close", "entry_time": "next bar open",
                "data_sha256": hashlib.sha256(source_bytes).hexdigest(),
                "raw_bars": len(raw), "missing_bar_intervals": missing_intervals, "missing_bars": missing_bars,
                "eligible_samples": len(indices), "features": columns,
                "sequence_length": args.sequence_length, "epochs_cap": args.epochs,
                "development_samples": len(development), "holdout_samples": len(test),
                "development_start": str(frame.iloc[development[0]].timestamp),
                "development_end": str(frame.iloc[development[-1]].label_end),
                "holdout_start": str(frame.iloc[test[0]].timestamp), "holdout_end": str(frame.iloc[test[-1]].label_end),
                "selection_metric": "mean purged walk-forward validation accuracy; holdout never selects model or threshold",
                "cost_assumptions": asdict(cfg), "python": platform.python_version(),
                "versions": {p: importlib.metadata.version(p) for p in ["numpy", "pandas", "scikit-learn", "xgboost", "torch", "joblib"]}}
    write_json(out / "run_metadata.json", metadata)
    cv_results, oof = [], {}
    for name, factory in factories.items():
        started = time.monotonic()
        folds, predictions, rows = [], [], []
        for fold, (a, b) in enumerate(splits, 1):
            model = fit_model(factory(), x, y, a)
            p = probability(model, x, b)
            scores = classification(y[b], p)
            folds.append({"fold": fold, "train_samples": len(a), **scores})
            predictions.append(p)
            rows.append(b)
            print(f"CV {name} fold {fold}/3: accuracy={scores['accuracy']:.4%}", flush=True)
        result = {"model": name, "cv_accuracy": float(np.mean([f["accuracy"] for f in folds])),
                  "cv_accuracy_std": float(np.std([f["accuracy"] for f in folds])),
                  "cv_roc_auc": float(np.mean([f["roc_auc"] for f in folds])),
                  "seconds": time.monotonic() - started, "folds": folds}
        cv_results.append(result)
        oof[name] = (np.concatenate(rows), np.concatenate(predictions))
        write_json(out / "cv_results.json", cv_results)
        print(f"Completed {name}: CV={result['cv_accuracy']:.4%}, {result['seconds']:.1f}s", flush=True)
    learned = [r for r in cv_results if r["model"] != "majority_baseline"]
    if not learned:
        raise ValueError("Select at least one learned model")
    selected = max(learned, key=lambda r: (r["cv_accuracy"], r["cv_roc_auc"]))["model"]
    oof_rows, oof_p = oof[selected]
    policy_results = []
    for threshold in [.5, .52, .55, .6, .65, .7, .8, 1.0]:
        metrics, _ = simulate(frame.iloc[oof_rows].reset_index(drop=True), oof_p, threshold, cfg)
        policy_results.append({"threshold": threshold, **metrics})
    eligible_policies = [p for p in policy_results if p["trades"] >= 100 or p["threshold"] == 1.0]
    threshold = max(eligible_policies, key=lambda p: (p["net_return"], -p["trades"]))["threshold"]
    # Freeze BOTH decisions before inspecting any final-period model performance.
    selection = {"model": selected, "confidence_threshold": threshold,
                 "policy_selection": "highest development OOF net return, >=100 trades; explicit no-trade alternative",
                 "policies": policy_results}
    write_json(out / "selection.json", selection)
    print(f"Frozen before holdout: {selected}, threshold={threshold}", flush=True)
    final_results, final_probabilities = [], {}
    for name, factory in factories.items():
        model = fit_model(factory(), x, y, development)
        p = probability(model, x, test)
        scores = classification(y[test], p)
        final_probabilities[name] = p
        costs, _ = simulate(frame.iloc[test].reset_index(drop=True), p, .5, cfg)
        final_results.append({"model": name, **scores, "always_trade_costs": costs})
        if name == selected:
            bundle = {"format_version": 1, "model_name": name, "kind": "torch" if isinstance(model, TorchClassifier) else "sklearn",
                      "model": model.export() if isinstance(model, TorchClassifier) else model,
                      "feature_columns": columns, "sequence_length": args.sequence_length,
                      "confidence_threshold": threshold, "metadata": metadata}
            joblib.dump(bundle, out / "selected_model.joblib")
        write_json(out / "holdout_results.json", final_results)
        print(f"HOLDOUT {name}: accuracy={scores['accuracy']:.4%}, always-trade net={costs['net_return']:.3%}", flush=True)
    p = final_probabilities[selected]
    policy_metrics, trades = simulate(frame.iloc[test].reset_index(drop=True), p, threshold, cfg)
    trades.to_csv(out / "holdout_trades.csv", index=False)
    comparison = frame.iloc[test][["timestamp", "target"]].reset_index(drop=True)
    for name, p_model in final_probabilities.items():
        comparison[name] = p_model
    comparison.to_csv(out / "holdout_predictions.csv", index=False)
    delta = block_bootstrap_accuracy_delta(y[test], p, final_probabilities["majority_baseline"],
                                            frame.iloc[test].timestamp.dt.date.to_numpy())
    selected_result = next(r for r in final_results if r["model"] == selected)
    baseline_result = next(r for r in final_results if r["model"] == "majority_baseline")
    summary = {"selected_model": selected, "holdout": selected_result, "baseline": baseline_result,
               "accuracy_delta_vs_baseline": delta, "selected_policy": policy_metrics,
               "confidence_threshold": threshold,
               "ready_for_funded_trading": False,
               "limitations": ["Training source is separate from Breakout execution data: " + source,
                               "No spread, order book, latency, or actual funding history; slippage is assumed",
                               "Plan and account size were not supplied; rule compliance is not certified",
                               "Payout is an illustrative 90% of positive aggregate net profit, not an actual payout request",
                               "The bounded model search does not establish the best possible accuracy",
                               "All final-period scores are diagnostics; the model remains the development-CV winner"]}
    write_json(out / "summary.json", summary)
    rows = []
    for r in sorted(cv_results, key=lambda item: item["cv_accuracy"], reverse=True):
        h = next(v for v in final_results if v["model"] == r["model"])
        rows.append(f"| {r['model']} | {r['cv_accuracy']:.2%} | {h['accuracy']:.2%} | {h['roc_auc']:.4f} | {h['always_trade_costs']['net_return']:.2%} |")
    report = f"""# ETHUSD five-minute model comparison

Selected by development walk-forward accuracy: **{selected}**.
Final-period accuracy: **{selected_result['accuracy']:.2%}**; majority baseline: **{baseline_result['accuracy']:.2%}**.
Accuracy advantage: {delta['delta'] * 100:.2f} percentage points; paired day-block 95% interval: [{delta['ci_95'][0] * 100:.2f}, {delta['ci_95'][1] * 100:.2f}] percentage points.

{source}.
{len(raw):,} raw bars; {len(indices):,} eligible samples; {len(columns)} causal features.
Data gaps: {missing_intervals} intervals, representing {missing_bars} missing five-minute bars. No values are interpolated.
Holdout: {metadata['holdout_start']} through {metadata['holdout_end']} ({len(test):,} samples).

| Model | Walk-forward accuracy | Holdout accuracy | Holdout AUC | Always-trade net return |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

## Cost-aware policy

Confidence threshold chosen on development OOF data: **{threshold}** (1.0 means no trading).
Holdout trades: {policy_metrics['trades']:,}; net return: {policy_metrics['net_return']:.2%};
maximum intrabar drawdown: {policy_metrics['max_intrabar_drawdown']:.2%}.
Illustrative trader share of positive net profit: {policy_metrics['trader_share_of_positive_net_profit']:.2%} of initial capital.
Every trade uses at most {cfg.notional_fraction:.0%} of initial capital, unlevered; round-trip orders pay {cfg.fee_bps_per_side}bp fee + {cfg.slippage_bps_per_side}bp assumed slippage per side.
Terminal swap assumption: {cfg.swap_bps_daily}bp/day at four-hour snapshots. Profit share: {cfg.profit_share:.0%}.
Rules assessed: {policy_metrics['rule_compliance_evaluated']}. Actual plan and account size remain unspecified.

## Validation and limits

Three expanding-window validation folds, two-sample purge at each boundary, last 20% held out.
Scalers fit only training history. Neural networks use an internal chronological 15% training tail for early stopping.
All models see the same eligible sample timestamps. Signals use completed bars; entries are the next bar open, exits the next bar close.
Missing intervals reset rolling features and sequence windows. Unknown final labels are excluded.
Flat candles are included in the non-UP class; the majority comparator includes those observations.
The model and trade threshold were frozen before the holdout was evaluated. The selected artifact is trained only on development data.

This result is **research only, not approved for funded trading**. It does not demonstrate execution-feed performance or an account payout.
Accuracy alone is insufficient; the no-trade policy is retained when development predictions cannot cover costs.
Do not reselect a model using this holdout without obtaining a new untouched evaluation period.

## Sources checked 2026-11-02

- [Massive crypto bars](https://massive.com/docs/rest/crypto/aggregates/custom-bars)
- [Binance official perpetual futures archive](https://github.com/binance/binance-public-data)
- [Breakout ETHUSD symbols, fees, leverage and financing](https://www.breakoutprop.com/symbols/)
- [Funded trading fees](https://intercom.help/breakoutprop/en/articles/11647195-what-are-the-trading-fees-and-commissions-in-a-funded-account)
- [Funded agreement](https://www.breakoutprop.com/funded-trader-agreement/)
"""
    (out / "report.md").write_text(report, encoding="utf-8")
    # Small reviewable results live outside ignored model/data directories.
    if args.publish_report:
        args.publish_report.parent.mkdir(parents=True, exist_ok=True)
        args.publish_report.write_text(report, encoding="utf-8")
    print(json.dumps({"selected_model": selected, "accuracy": selected_result["accuracy"],
                      "baseline": baseline_result["accuracy"], "threshold": threshold,
                      "policy_net_return": policy_metrics["net_return"], "report": str(out / "report.md")}), flush=True)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--bars", type=Path, default=ROOT / "data/ethusd/perpetual/bars.csv")
    result.add_argument("--market", choices=["binance_perpetual", "massive_spot_proxy"], default="binance_perpetual")
    result.add_argument("--output", type=Path, default=ROOT / "artifacts/ethusd")
    result.add_argument("--publish-report", type=Path, default=ROOT / "reports/ethusd_model_comparison.md")
    result.add_argument("--epochs", type=int, default=8)
    result.add_argument("--sequence-length", type=int, default=24)
    result.add_argument("--models", help="Optional comma separated subset of candidate names")
    result.add_argument("--fee-bps", type=float, default=4.)
    result.add_argument("--slippage-bps", type=float, default=2.)
    result.add_argument("--notional-fraction", type=float, default=.10)
    result.add_argument("--daily-loss-limit", type=float)
    result.add_argument("--total-loss-limit", type=float)
    return result


if __name__ == "__main__":
    train(parser().parse_args())
