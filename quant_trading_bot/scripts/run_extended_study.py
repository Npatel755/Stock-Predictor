"""Bounded, predeclared development-only studies after the primary comparison."""
import os
for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[variable] = "1"
from pathlib import Path
from datetime import datetime, timezone
import json
import traceback
import joblib
import gc
import shutil
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression, Ridge
from threadpoolctl import threadpool_limits
from quant_futures.research import load_dataset, json_write, code_identity, _combined
from quant_futures.config import load_config, file_hash
from quant_futures.features import cross_market_features
from quant_futures.models import fit_model, FittedRegime, calibration_metrics
from quant_futures.labels import future_returns, triple_barrier
from quant_futures.backtest import run_backtest
from quant_futures.metrics import summarize
from quant_futures.optimization import nested_search, feature_ablation, training_permutation_importance
from quant_futures.advanced import train_network, train_rl, make_environment
from quant_futures.strategies import baseline, ensemble
from paper_compatibility import verify_compatibility

ROOT = Path(__file__).resolve().parents[1]
campaign = json.loads((ROOT/"reports/latest_market_campaign.json").read_text())
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
output = ROOT/"runs"/f"extended_{stamp}"
output.mkdir(exist_ok=False)
report = dict(created_at=datetime.now(timezone.utc).isoformat(), **code_identity(),
    script_sha256=file_hash(__file__), parent_campaign=campaign["created_at"], synthetic=False,
    test_accessed=False, deployment_eligible=False,
    policy="Predeclared bounded exploratory studies. Fixed 2023 training cutoff; 2024–2025 validation only. All choices add to the trial count. No new final-test candidate is selected here.",
    planned=dict(instruments=["MES", "MNQ"], horizons=[1, 3, 5, 10, 20],
        objectives=["return regression", "cost-aware three-way direction", "triple barrier"],
        neural=["mlp", "tcn", "lstm", "gru", "transformer"], neural_training_rows=3000, neural_epochs=3,
        rl=["ppo", "dqn"], rl_timesteps=2048, nested_trials_per_model=3,
        regime=["kmeans", "gmm"], cross_market=True), attempts=[])
json_write(output/"protocol.json", report)
shutil.copyfile(__file__, output/"study_script.py")
columns = ["return_1", "momentum_5", "momentum_20", "atr_relative", "volatility", "rsi", "adx", "vwap_deviation", "relative_volume", "persistence"]


def attempt(instrument, name, function):
    row = dict(instrument=instrument, name=name, started_at=datetime.now(timezone.utc).isoformat())
    try:
        row.update(status="completed", result=function())
    except Exception as error:
        row.update(status="failed", error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc(limit=3))
    report["attempts"].append(row)
    json_write(output/"results.json", report)
    print(instrument, name, row["status"], flush=True)


def execute(instrument):
    import torch
    cfg = load_config(ROOT/"configs"/f"{instrument.lower()}_market.yaml")
    parent = Path(campaign["runs"][instrument]["path"])
    bars, manifest, quality = load_dataset(instrument, minutes=15)
    features = pd.read_parquet(parent/"development_features.parquet")
    registry = json.loads((parent/"experiment.json").read_text())
    verify_compatibility(parent, registry)
    folds = [np.arange(fold["validation"][0], fold["validation"][1]+1) for fold in registry["validation_folds"]]
    train_end = pd.Timestamp(manifest["train_end_exclusive"])
    training = np.flatnonzero(bars.timestamp_utc < train_end)
    multiplier = 5 if instrument == "MES" else 2
    points = 2*cfg.costs.fee/multiplier+.25*(2*cfg.costs.slippage_ticks+cfg.costs.spread_ticks+2*cfg.costs.impact_ticks)
    preprocessing = make_pipeline(SimpleImputer(keep_empty_features=True), StandardScaler())
    x = features[columns]
    preprocessing.fit(x.iloc[training])
    scaled = preprocessing.transform(x).astype(np.float32)
    def score(signals):
        results = [run_backtest(bars.iloc[valid].reset_index(drop=True), pd.Series(signals).iloc[valid].reset_index(drop=True), cfg) for valid in folds]
        return summarize(_combined(results, cfg.initial_balance), cfg.initial_balance, trials=256)
    def target_model(horizon, objective):
        labels = future_returns(bars, horizon, points, minutes=15)
        eligible = np.flatnonzero((bars.timestamp_utc < train_end) & (pd.to_datetime(labels.label_end, utc=True) < train_end) & labels.forward_return.notna())
        if objective == "return":
            model = Ridge(alpha=10).fit(scaled[eligible], labels.forward_return.iloc[eligible])
            predicted = model.predict(scaled)
            band = points/bars.close.to_numpy()
            signals = np.select([predicted > band, predicted < -band], [1, -1], 0)
        elif objective == "three_way":
            model = LogisticRegression(C=.1, max_iter=300, random_state=cfg.seed).fit(scaled[eligible], labels.direction.iloc[eligible])
            probabilities = model.predict_proba(scaled)
            signals = np.zeros(len(bars))
            for value in (-1, 1):
                if value in model.classes_:
                    signals[probabilities[:, list(model.classes_).index(value)] > cfg.probability_threshold] = value
        else:
            events = triple_barrier(bars.iloc[:len(training)+horizon+1], horizon=horizon, minutes=15)
            eligible = np.flatnonzero((bars.timestamp_utc.iloc[:len(events)] < train_end) & (pd.to_datetime(events.label_end, utc=True) < train_end) & events.label.notna())
            model = LogisticRegression(C=.1, max_iter=300, random_state=cfg.seed).fit(scaled[eligible], events.label.iloc[eligible])
            probabilities = model.predict_proba(scaled)
            signals = np.zeros(len(bars))
            for value in (-1, 1):
                if value in model.classes_:
                    signals[probabilities[:, list(model.classes_).index(value)] > cfg.probability_threshold] = value
        training_returns = labels.forward_return.iloc[eligible]
        return dict(training_events=len(eligible), training_payoff_diagnostic=dict(
            probability_positive=float((training_returns > 0).mean()),
            mean_positive_return=float(training_returns[training_returns > 0].mean()),
            mean_negative_return=float(training_returns[training_returns < 0].mean()),
            holding_horizon_bars=horizon, costs_in_price_points=points,
            interpretation="Unconditional training-only payoff summary; not an out-of-sample expected-value forecast"), metrics=score(signals))
    for horizon in (1, 3, 5, 10, 20):
        for objective in ("return", "three_way"):
            attempt(instrument, f"{objective}_h{horizon}", lambda h=horizon, o=objective: target_model(h, o))
    attempt(instrument, "triple_barrier_h20", lambda: target_model(20, "triple"))
    labels = future_returns(bars, 5, points, minutes=15)
    eligible = np.flatnonzero((bars.timestamp_utc < train_end) & (pd.to_datetime(labels.label_end, utc=True) < train_end) & labels.forward_return.notna())
    # Sequence continuity is checked before sampling; no cross-roll or gap windows.
    segment = (bars.contract.ne(bars.contract.shift()) | (bars.timestamp_utc.diff() > pd.Timedelta(minutes=30))).cumsum().to_numpy()
    window = 8
    def windows(indexes):
        indexes = np.asarray(indexes)
        good = indexes[(indexes >= window-1) & (segment[indexes] == segment[np.maximum(0, indexes-window+1)])]
        return good, scaled[good[:, None]-np.arange(window-1, -1, -1)]
    # Even chronological training subsampling spans multiple historical regimes.
    sample = eligible[np.linspace(0, len(eligible)-1, min(4000, len(eligible))).astype(int)]
    ids, sequences = windows(sample)
    split = int(.75*len(ids))
    purge_end = bars.timestamp_utc.iloc[ids[split]]
    base = np.flatnonzero(pd.to_datetime(labels.label_end.iloc[ids[:split]], utc=True) < purge_end)
    y = (labels.forward_return.iloc[ids] > 0).astype(float).to_numpy()
    joblib.dump(dict(preprocessing=preprocessing, columns=columns, window=window,
        train_ids=ids[base], inner_calibration_ids=ids[split:], training_cutoff=str(train_end)), output/f"{instrument}_sequence_preprocessing.joblib", compress=3)
    valid_ids, valid_sequences = windows(np.concatenate(folds))
    for kind in ("mlp", "tcn", "lstm", "gru", "transformer"):
        def neural(kind=kind):
            model, history = train_network(kind, sequences[base], y[base], sequences[split:], y[split:], epochs=3)
            model.eval()
            predictions = []
            with torch.no_grad():
                for start in range(0, len(valid_sequences), 1024):
                    predictions.extend(torch.sigmoid(model(torch.tensor(valid_sequences[start:start+1024]))).numpy())
            probabilities = np.asarray(predictions)
            signal = np.zeros(len(bars))
            signal[valid_ids] = np.select([probabilities > .57, probabilities < .43], [1, -1], 0)
            torch.save(model.state_dict(), output/f"{instrument}_{kind}.pt")
            return dict(training_samples=len(base), inner_validation_samples=len(ids)-split, history=history,
                probability_calibration="Raw sigmoid; no extra calibration; not comparable as calibrated confidence", metrics=score(signal),
                calibration=calibration_metrics((labels.forward_return.iloc[valid_ids] > 0).astype(float).where(labels.forward_return.iloc[valid_ids].notna()), probabilities))
        attempt(instrument, kind, neural)
    inner = eligible[-5000:]
    for name in ("logistic", "lightgbm", "xgboost"):
        attempt(instrument, f"inner_search_{name}", lambda name=name: nested_search(name, bars.iloc[inner].reset_index(drop=True), features.iloc[inner].reset_index(drop=True), labels.iloc[inner].reset_index(drop=True), cfg, max_trials=3, use_optuna=True))
    attempt(instrument, "feature_ablation", lambda: feature_ablation("logistic", bars.iloc[inner].reset_index(drop=True), features.iloc[inner].reset_index(drop=True), labels.iloc[inner].reset_index(drop=True), cfg,
        dict(no_volume=["relative_volume", "volume_zscore", "price_volume_corr", "volume_imbalance_proxy"], no_structure=["high_distance", "low_distance", "breakout", "failed_breakout", "support_distance", "resistance_distance"])))
    def permutation():
        # Fit on an earlier training section; diagnostic input is later training,
        # not the campaign validation or test set.
        ids = inner[:3500]
        fitted = fit_model("logistic", features.iloc[ids].reset_index(drop=True), labels.iloc[ids].reset_index(drop=True), bars.iloc[ids].reset_index(drop=True), calibration="none")
        tail = inner[3500:]
        y = (labels.forward_return.iloc[tail] > 0).astype(int)
        importance = training_permutation_importance(fitted, features.iloc[tail], y)
        return dict(metric="classification accuracy; inner-training diagnostic only",
            importance=dict(zip(fitted.columns, importance.importances_mean.tolist())))
    attempt(instrument, "permutation_importance", permutation)
    def cross():
        other = "MNQ" if instrument == "MES" else "MES"
        other_bars, _, _ = load_dataset(other, minutes=15)
        cross_features = cross_market_features(bars, other_bars, minutes=15)
        extended = pd.concat([x.reset_index(drop=True), cross_features.reset_index(drop=True)], axis=1)
        transform = make_pipeline(SimpleImputer(keep_empty_features=True), StandardScaler())
        values = transform.fit_transform(extended.iloc[eligible])
        model = LogisticRegression(C=.1, max_iter=300, random_state=cfg.seed).fit(values, (labels.forward_return.iloc[eligible] > 0).astype(int))
        probability = model.predict_proba(transform.transform(extended))[:, 1]
        signals = np.select([probability > .57, probability < .43], [1, -1], 0)
        return dict(columns=list(extended), synchronization="Exact completed timestamp join; absent cross observations remain null before training-fit imputation", metrics=score(signals))
    attempt(instrument, "cross_market_logistic", cross)
    for method in ("kmeans", "gmm"):
        def regime(method=method):
            fitted = FittedRegime(method).fit(features.iloc[eligible])
            clusters = fitted.predict(features)
            # Cluster-to-expert mapping uses a chronological inner-training score.
            experts = {name: baseline(name, bars, features) for name in ("ema", "bollinger", "donchian")}
            mapping = {}
            for cluster in range(3):
                scores = {}
                sample = inner[-1500:]
                for name, signal in experts.items():
                    active = signal.iloc[sample].where(clusters[sample] == cluster, 0)
                    scores[name] = summarize(run_backtest(bars.iloc[sample].reset_index(drop=True), active.reset_index(drop=True), cfg))["net_pnl"]
                mapping[cluster] = max(scores, key=scores.get) if max(scores.values()) > 0 else None
            signal = np.zeros(len(bars))
            for cluster, expert in mapping.items():
                if expert:
                    signal[clusters == cluster] = experts[expert][clusters == cluster]
            return dict(mapping=mapping, mapping_source="last 1500 training observations only", metrics=score(signal))
        attempt(instrument, f"regime_{method}", regime)
    for algorithm in ("ppo", "dqn"):
        def rl(algorithm=algorithm):
            from stable_baselines3.common.vec_env import DummyVecEnv
            chunks = []
            for year in (2019, 2020, 2022, 2023):
                ids = np.flatnonzero(bars.timestamp_utc.dt.year == year)[-1000:]
                chunks.append((bars.iloc[ids].reset_index(drop=True), pd.DataFrame(scaled[ids])))
            env = DummyVecEnv([lambda b=b, f=f: make_environment(b, f, cfg) for b, f in chunks])
            model = train_rl(algorithm, env, total_timesteps=2048)
            model.save(output/f"{instrument}_{algorithm}")
            parts = []
            for valid in folds:
                evaluation = make_environment(bars.iloc[valid].reset_index(drop=True), pd.DataFrame(scaled[valid]), cfg)
                observation, _ = evaluation.reset(seed=cfg.seed)
                done = False
                while not done:
                    action, _ = model.predict(observation, deterministic=True)
                    observation, _, done, _, _ = evaluation.step(int(action))
                # Ended early on hard kill: the remaining bars are explicitly flat.
                for row in evaluation.rows[evaluation.i+1:]:
                    evaluation.sim.step(row, None)
                parts.append(evaluation.sim.finish())
            return dict(timesteps=2048, training_years=[2019, 2020, 2022, 2023],
                warning="Small experimental budget is not a convergence or superiority claim", metrics=summarize(_combined(parts, cfg.initial_balance), trials=256))
        attempt(instrument, algorithm, rl)


with threadpool_limits(limits=1):
    for instrument in ("MES", "MNQ"):
        execute(instrument)
        gc.collect()
    def portfolio_study():
        from quant_futures.portfolio import run_portfolio
        datasets, cfgs = {}, {}
        for instrument in ("MES", "MNQ"):
            data, _, _ = load_dataset(instrument+":validation", minutes=15)
            datasets[instrument] = data
            cfgs[instrument] = load_config(ROOT/"configs"/f"{instrument.lower()}_market.yaml")
        common = pd.Index(datasets["MES"].timestamp_utc).intersection(pd.Index(datasets["MNQ"].timestamp_utc))
        omitted = {name: len(data)-len(common) for name, data in datasets.items()}
        datasets = {name: data[data.timestamp_utc.isin(common)].reset_index(drop=True) for name, data in datasets.items()}
        from quant_futures.features import build_features
        signals = {name: baseline("ema", data, build_features(data, 15)) for name, data in datasets.items()}
        from quant_futures.funded import load_rule_scenarios, FundedAccount
        account = FundedAccount(load_rule_scenarios(ROOT/"configs/lucidflex.yaml")["consistency_0.5_dll_None"])
        result = run_portfolio(datasets, signals, cfgs, account=account)
        result["curve"].to_parquet(output/"joint_ema_equity.parquet", index=False)
        result["trades"].to_parquet(output/"joint_ema_trades.parquet", index=False)
        return dict(alignment="Explicit common timestamps, never price filling; no independent sleeve capital added", omitted_bars=omitted,
            interpretation="Continuous one-account diagnostic; distinct from reset-fold leaderboards", metrics=summarize(result, trials=256), funded_account=account.summary())
    attempt("MES+MNQ", "shared_account_ema", portfolio_study)
report["completed_at"] = datetime.now(timezone.utc).isoformat()
json_write(output/"results.json", report)
json_write(ROOT/"reports/latest_extended_study.json", dict(path=str(output), **report))
