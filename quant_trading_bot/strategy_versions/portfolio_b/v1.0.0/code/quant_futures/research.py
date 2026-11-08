from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import importlib.metadata
import json
import subprocess
import time
import uuid
import shutil
import zipfile
import ast
import gc
import joblib
import numpy as np
import pandas as pd
from .config import ResearchConfig, digest, file_hash
from .data import canonical, validate, SessionCalendar
from .features import build_features
from .labels import future_returns, meta_labels
from .strategies import BASELINES, baseline, regime_strategy, ensemble, causal_regime
from .models import fit_model, calibration_metrics
from .validation import walk_forward, freeze_candidate, reserve_holdout
from .backtest import run_backtest
from .metrics import summarize, account_monte_carlo
from .funded import FundedAccount, load_rule_scenarios


def json_write(path, value):
    def safe(v):
        if isinstance(v, dict):
            return {str(k): safe(x) for k, x in v.items()}
        if isinstance(v, (list, tuple, np.ndarray)):
            return [safe(x) for x in v]
        if isinstance(v, (float, np.floating)):
            return float(v) if np.isfinite(v) else None
        if isinstance(v, np.integer):
            return int(v)
        if isinstance(v, np.bool_):
            return bool(v)
        if isinstance(v, (pd.Timestamp, Path)):
            return str(v)
        return v
    path = Path(path)
    temporary = path.with_name(path.name+".tmp-"+uuid.uuid4().hex[:8])
    temporary.write_text(json.dumps(safe(value), indent=2, allow_nan=False), encoding="utf-8")
    # Windows sync/indexing readers can briefly hold a sharing lock on state.json.
    # Preserve atomic snapshots and retry boundedly; never fall back to torn writes.
    for attempt in range(8):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(min(.025*2**attempt, .5))


def code_identity():
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        commit = "unavailable"
    sources = {p.name: file_hash(p) for p in sorted(Path(__file__).parent.glob("*.py"))}
    return dict(code_commit=commit, source_hash=digest(sources), source_files=sources)


def _aggregate_partitions(files, minutes):
    import duckdb
    from .data import canonical
    if minutes not in (2, 5, 15, 30, 60):
        raise ValueError("Partitioned aggregation supports 2/5/15/30/60 completed minutes")
    connection = duckdb.connect()
    try:
        connection.execute("SET threads=1")
        connection.execute("SET TimeZone='UTC'")
        connection.execute("SET memory_limit='256MB'")
        connection.execute("SET enable_progress_bar=false")
        query = f"""SELECT time_bucket(INTERVAL '{minutes} minutes', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
            instrument, contract, arg_min(open,timestamp_utc) AS open, max(high) AS high,
            min(low) AS low, arg_max(close,timestamp_utc) AS close, sum(volume)::UBIGINT AS volume,
            time_bucket(INTERVAL '{minutes} minutes', CAST(timestamp_utc AS TIMESTAMPTZ))+INTERVAL '{minutes} minutes' AS available_at
            FROM read_parquet(?) GROUP BY 1, instrument, contract
            HAVING COUNT(*)={minutes} ORDER BY timestamp_utc"""
        table = connection.from_query(query, params=[[str(p) for p in files]]).to_arrow_table()
        return canonical(table.to_pandas())
    finally:
        connection.close()


def load_dataset(path, calendar=None, purpose="research", minutes=1):
    from .dataset_catalog import resolve_dataset
    path = resolve_dataset(path)
    if path.name.endswith(".dataset.json"):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        frames = []
        for partition in manifest["files"]:
            part_manifest = json.loads(Path(partition).with_suffix(".manifest.json").read_text())
            if part_manifest.get("split_role") not in ("train", "validation") or part_manifest.get("split_protocol_id") != manifest.get("split_protocol_id"):
                raise PermissionError("Development descriptor must contain only matching train/validation partitions")
            if file_hash(partition) != manifest["file_hashes"][partition]:
                raise ValueError("Development partition hash mismatch")
            if minutes == 1:
                frames.append(pd.read_parquet(partition))
        data = pd.concat(frames, ignore_index=True) if minutes == 1 else _aggregate_partitions(manifest["files"], minutes)
        bars, quality = validate(data, minutes=minutes, calendar=calendar)
        if quality["fatal"] or bars.timestamp_utc.duplicated().any():
            raise ValueError("Invalid development partitions")
        return bars, manifest, quality
    manifest_path = path.with_suffix(".manifest.json")
    if not manifest_path.exists():
        raise ValueError("Dataset manifest required: import with provenance first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("split_role") == "test" and purpose not in ("final_test", "quality"):
        raise PermissionError("Reserved test partition cannot be used for model development")
    if manifest.get("dataset_version") != file_hash(path):
        raise ValueError("Dataset hash mismatch")
    if not isinstance(manifest.get("synthetic"), bool):
        raise ValueError("Explicit synthetic flag required")
    if not manifest.get("raw_contract_prices", manifest["synthetic"]):
        raise ValueError("Explicit raw contract price provenance required for tradable P&L")
    data = pd.read_parquet(path) if minutes == 1 else _aggregate_partitions([path], minutes)
    bars, quality = validate(data, minutes=minutes, calendar=calendar)
    if quality["fatal"] or bars.timestamp_utc.duplicated().any() or bars.instrument.nunique() != 1:
        raise ValueError("Select one tradable contract per timestamp and resolve fatal quality failures")
    return bars, manifest, quality


def _combined(parts, initial):
    curves, trades, offset = [], [], 0.0
    for fold, result in enumerate(parts):
        curve = result["curve"].copy()
        for name in ("equity", "cash", "intrabar_worst_bound"):
            curve[name] += offset
        offset = float(curve.equity.iloc[-1]-initial)
        curve["fold"] = fold
        curves.append(curve)
        trade = result["trades"].copy()
        trade["fold"] = fold
        trades.append(trade)
    return dict(curve=pd.concat(curves, ignore_index=True), trades=pd.concat(trades, ignore_index=True), events=[])


def candidate_signal(candidate, bars, features, cfg, fitted=None):
    family, name = candidate["family"], candidate["name"]
    if family == "baseline":
        return baseline(name, bars, features, parameter=candidate.get("parameter", 1.0), session=candidate.get("session", "all"))
    if family == "regime":
        return regime_strategy(bars, features)
    if family == "ensemble":
        return ensemble({s: baseline(s, bars, features) for s in ("ema", "bollinger", "donchian", "momentum")})
    if family == "meta":
        primary = baseline("donchian", bars, features)
        p = fitted.predict_probability(features)
        return primary.where(p > cfg.probability_threshold, 0)
    if family == "ml":
        return fitted.signal(features, cfg.probability_threshold)
    raise ValueError(family)


def _fit(candidate, features, labels, bars, cfg):
    target = None
    if candidate["family"] == "meta":
        target = meta_labels(baseline("donchian", bars, features), labels)
    return fit_model(candidate.get("model", candidate["name"]), features, labels, bars,
        seed=cfg.seed, calibration=cfg.calibration, params=candidate.get("hyperparameters"), target=target)


def stress_test(bars, signals, cfg):
    result = {}
    scenarios = [(f"cost_{factor}x", cfg.model_copy(update={"costs": cfg.costs.scaled(factor)})) for factor in (1, 1.5, 2, 3)]
    for name, update in (
        ("latency_2bars", {"delay_bars": 2}),
        ("latency_3bars", {"delay_bars": 3}),
        ("partial_capacity", {"participation": max(.0001, cfg.execution.participation/4)}),
        ("missed_25pct", {"missed_entry_fraction": .25}),
    ):
        scenarios.append((name, cfg.model_copy(update={"execution": cfg.execution.model_copy(update=update)})))
    for name, scenario in scenarios:
        try:
            result[name] = summarize(run_backtest(bars, signals, scenario), cfg.initial_balance, seed=cfg.seed)
        except (ValueError, RuntimeError) as error:
            result[name] = dict(error=str(error))
    return result


def feature_definition_hash(source):
    tree = ast.parse(source)
    return digest([ast.dump(node, include_attributes=False) for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in ("rma", "_one", "build_features")])


def run_research(dataset, cfg: ResearchConfig, output, rules_path=None, feature_cache=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    start_clock = time.monotonic()
    identity = code_identity()
    with zipfile.ZipFile(output/"code_snapshot.zip", "w", zipfile.ZIP_DEFLATED) as snapshot:
        for source in Path(__file__).parent.glob("*.py"):
            snapshot.write(source, "quant_futures/"+source.name)
    calendar = SessionCalendar(pd.read_csv(cfg.calendar_schedule)) if cfg.calendar_schedule else None
    bars, manifest, quality = load_dataset(dataset, calendar=calendar, minutes=cfg.timeframe_minutes)
    if manifest.get("split_role") in ("train", "validation"):
        raise ValueError("Use the instrument development alias to compare models on the declared validation period")
    if calendar is not None and quality["counts"].get("outside_calendar", 0):
        raise ValueError("Bars fall outside declared session schedule")
    if not bars.instrument.eq(cfg.instrument).all():
        raise ValueError("Instrument/config mismatch")
    explicit = manifest.get("kind") == "partitioned_development"
    cutoff = len(bars) if explicit else int(len(bars)*(1-cfg.holdout_fraction))
    holdout_start = pd.Timestamp(manifest["test_start_inclusive"]) if explicit else bars.timestamp_utc.iloc[cutoff]
    # Final-test OHLC values are excluded before any feature/label/model work.
    dev = bars.iloc[:cutoff].reset_index(drop=True)
    feature_file = output/"development_features.parquet"
    feature_definition = feature_definition_hash((Path(__file__).parent/"features.py").read_text(encoding="utf-8"))
    if feature_cache is not None:
        parent = Path(feature_cache)
        registration = json.loads((parent/"experiment.json").read_text())
        cached = parent/"development_features.parquet"
        prior_definition = registration.get("feature_definition_hash")
        if prior_definition is None:
            archive = parent/"code_snapshot.zip"
            if not archive.exists():
                archive = Path(__file__).resolve().parents[2]/"reports"/f"source_{registration['source_hash']}.zip"
            with zipfile.ZipFile(archive) as snapshot:
                prior_source = snapshot.read("quant_futures/features.py").decode("utf-8")
                import hashlib
                if hashlib.sha256(prior_source.encode()).hexdigest() != registration["source_files"]["features.py"]:
                    raise ValueError("Feature cache source snapshot mismatch")
                prior_definition = feature_definition_hash(prior_source)
        if registration["dataset_version"] != manifest["dataset_version"] or registration["timeframe"] != cfg.timeframe_minutes or prior_definition != feature_definition or file_hash(cached) != registration["feature_set"]:
            raise ValueError("Feature cache provenance mismatch")
        features = pd.read_parquet(cached)
        if len(features) != len(dev):
            raise ValueError("Feature cache development boundary mismatch")
        try:
            feature_file.hardlink_to(cached)
        except OSError:
            shutil.copyfile(cached, feature_file)
    else:
        features = build_features(dev, cfg.timeframe_minutes)
        features.to_parquet(feature_file, index=False)
    features_hash = file_hash(output/"development_features.parquet")
    spec_mult = {"MES": 5, "MNQ": 2}[cfg.instrument]
    costs_points = 2*cfg.costs.fee/spec_mult + .25*(2*cfg.costs.slippage_ticks+cfg.costs.spread_ticks+2*cfg.costs.impact_ticks)
    labels = future_returns(dev, cfg.label_horizon, costs_points, cfg.timeframe_minutes)
    minimum_train = max(cfg.minimum_training_bars, int((dev.timestamp_utc < pd.Timestamp(manifest["train_end_exclusive"])).sum())) if explicit else cfg.minimum_training_bars
    folds = list(walk_forward(dev, labels.label_end, minimum_train, cfg.validation_bars, cfg.embargo_bars))
    if explicit and cfg.validation_mode == "fixed":
        train_end = pd.Timestamp(manifest["train_end_exclusive"])
        fixed_train = np.flatnonzero((dev.timestamp_utc < train_end) & (pd.to_datetime(labels.label_end, utc=True) < train_end))
        fixed_train = fixed_train[-cfg.maximum_training_rows:]
        folds = [(fixed_train, validation) for _, validation in folds]
    else:
        folds = [(train[-cfg.maximum_training_rows:], validation) for train, validation in folds]
    if explicit and folds and folds[-1][1][-1]+1 < len(dev):
        tail = np.arange(folds[-1][1][-1]+1, len(dev))
        if len(tail) >= 10:
            if cfg.validation_mode == "fixed":
                folds.append((fixed_train, tail))
            else:
                boundary = dev.timestamp_utc.iloc[tail[0]]
                eligible = np.flatnonzero((dev.timestamp_utc < boundary-pd.Timedelta(minutes=cfg.embargo_bars*cfg.timeframe_minutes)) & (pd.to_datetime(labels.label_end, utc=True) < boundary))
                folds.append((eligible[-cfg.maximum_training_rows:], tail))
    if not folds:
        raise ValueError("Insufficient history for requested walk-forward windows")
    registry = dict(experiment_id=str(uuid.uuid4()), created_at=datetime.now(timezone.utc).isoformat(),
        **identity, dataset_version=manifest["dataset_version"], synthetic=manifest["synthetic"],
        instrument=cfg.instrument, timeframe=cfg.timeframe_minutes, config=cfg.model_dump(), config_hash=digest(cfg.model_dump()),
        feature_set=features_hash, hyperparameters="predeclared defaults; no outer-validation hyperparameter search",
        feature_definition_hash=feature_definition,
        train_period=[str(dev.timestamp_utc.iloc[folds[0][0][0]]), str(dev.timestamp_utc.iloc[folds[0][0][-1]])],
        development_period=[str(dev.timestamp_utc.iloc[0]), str(dev.timestamp_utc.iloc[-1])],
        validation_period=[str(dev.timestamp_utc.iloc[folds[0][1][0]]), str(dev.timestamp_utc.iloc[folds[-1][1][-1]])],
        feature_cache_parent=None if feature_cache is None else str(feature_cache),
        validation_folds=[dict(train=[int(t[0]), int(t[-1])], validation=[int(v[0]), int(v[-1])]) for t, v in folds],
        final_test_period=[str(holdout_start), manifest["test_partition"]["coverage"]["end"] if explicit else str(bars.timestamp_utc.iloc[-1])],
        split_protocol_id=manifest.get("split_protocol_id"),
        commission_model=cfg.costs.model_dump(), slippage_model="adverse ticks and spread; tick rounding",
        risk_configuration=cfg.risk.model_dump(), random_seed=cfg.seed, results_path=str(output),
        python_packages={d.metadata["Name"]: d.version for d in importlib.metadata.distributions() if d.metadata["Name"] in ["numpy", "pandas", "scikit-learn", "lightgbm", "xgboost"]})
    json_write(output/"experiment.json", registry)
    json_write(output/"data_quality.json", quality)
    candidates = [dict(family="baseline", name=name) for name in BASELINES]
    candidates += [dict(family="regime", name="regime_switch"), dict(family="ensemble", name="equal_weight")]
    candidates += [dict(family="ml", name=name) for name in cfg.models]
    if cfg.models:
        candidates += [dict(family="meta", name="donchian_meta", model="logistic")]
    leaderboard, attempts, artifacts, model_analysis = [], [], {}, {}
    for number, candidate in enumerate(candidates):
        cid = f"{candidate['family']}_{candidate['name']}"
        attempt = dict(candidate=candidate, candidate_id=cid, instrument=cfg.instrument, timeframe=cfg.timeframe_minutes,
            feature_hash=features_hash, risk_hash=digest(cfg.risk.model_dump()), label_horizon=cfg.label_horizon,
            exit_rule=cfg.execution.model_dump(), random_seed=cfg.seed, started_at=datetime.now(timezone.utc).isoformat())
        if number >= cfg.maximum_trials or time.monotonic()-start_clock > cfg.maximum_runtime_seconds:
            attempt.update(status="skipped_budget")
            attempts.append(attempt)
            continue
        directory_bytes = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        if directory_bytes > cfg.maximum_disk_gb*1024**3:
            attempt.update(status="skipped_disk_budget")
            attempts.append(attempt)
            continue
        parts, fold_metrics, probabilities, truths, signals_by_fold, probability_regimes, model_folds = [], [], [], [], [], [], []
        cached_fitted = None
        try:
            for fold_no, (train, valid) in enumerate(folds):
                if time.monotonic()-start_clock > cfg.maximum_runtime_seconds:
                    raise TimeoutError("Research runtime budget exhausted")
                fitted = None
                if candidate["family"] in ("ml", "meta"):
                    if cached_fitted is not None and explicit and cfg.validation_mode == "fixed":
                        fitted = cached_fitted
                    else:
                        fitted = _fit(candidate, features.iloc[train].reset_index(drop=True), labels.iloc[train].reset_index(drop=True), dev.iloc[train].reset_index(drop=True), cfg)
                        cached_fitted = fitted
                if candidate["family"] in ("ml", "meta"):
                    signals = candidate_signal(candidate, dev.iloc[valid], features.iloc[valid], cfg, fitted).reset_index(drop=True)
                else:
                    signals = candidate_signal(candidate, dev, features, cfg, fitted).iloc[valid].reset_index(drop=True)
                result = run_backtest(dev.iloc[valid].reset_index(drop=True), signals, cfg)
                parts.append(result)
                signals_by_fold.append(signals)
                fold_metrics.append(summarize(result, cfg.initial_balance, len(candidates), cfg.seed))
                if fitted is not None:
                    p = fitted.predict_probability(features.iloc[valid])
                    y = (labels.forward_return.iloc[valid] > 0).astype(float).where(labels.forward_return.iloc[valid].notna())
                    if candidate["family"] == "meta":
                        y = meta_labels(baseline("donchian", dev, features), labels).iloc[valid]
                    probabilities.extend(p)
                    truths.extend(y)
                    probability_regimes.extend(causal_regime(features).iloc[valid])
                    underlying = fitted.base[-1]
                    importance = getattr(underlying, "feature_importances_", None)
                    if importance is None and hasattr(underlying, "coef_"):
                        importance = np.abs(underlying.coef_).ravel()
                    model_folds.append(dict(fold=fold_no, columns=fitted.columns, constant=fitted.constant,
                        importance=None if importance is None else dict(zip(fitted.columns, importance.tolist())),
                        calibration_method=fitted.calibration_method, calibration_fitted=fitted.calibrator is not None))
            combined = _combined(parts, cfg.initial_balance)
            metrics = summarize(combined, cfg.initial_balance, len(candidates), cfg.seed)
            row = dict(candidate_id=cid, family=candidate["family"], model=candidate["name"], **metrics,
                positive_fold_fraction=float(np.mean([m["net_pnl"] > 0 for m in fold_metrics])),
                fold_net_pnl=[m["net_pnl"] for m in fold_metrics], synthetic=manifest["synthetic"],
                calibration=calibration_metrics(truths, probabilities) if probabilities else None)
            if probabilities:
                regimes_array = np.asarray(probability_regimes)
                row["calibration_by_regime"] = {regime: calibration_metrics(np.asarray(truths)[regimes_array == regime], np.asarray(probabilities)[regimes_array == regime]) for regime in sorted(set(probability_regimes))}
                model_analysis[cid] = dict(folds=model_folds, feature_selection="training-only variance/correlation pruning", importance_note="Training estimator diagnostics; not causal explanations")
            # Eligibility requires confidence, sample, profitability and stability.
            row["research_eligible"] = bool(not manifest["synthetic"] and row["net_pnl"] > 0 and
                quality["calendar_verified"] and not any((quality["missing_expected"] or {}).values()) and
                row["trades"] >= cfg.minimum_trades and row["session_days"] >= cfg.minimum_oos_days and
                row["positive_fold_fraction"] >= .6 and row["max_drawdown"] < cfg.risk.max_drawdown and
                row["uncertainty"]["mean_ci"][0] > 0 and row["uncertainty"]["multiple_testing_pvalue_upper"] < .05)
            row["deployment_eligible"] = False
            leaderboard.append(row)
            artifacts[cid] = dict(candidate=candidate, signals=pd.concat(signals_by_fold, ignore_index=True))
            combined["curve"].to_parquet(output/f"{cid}_equity.parquet", index=False)
            combined["trades"].to_parquet(output/f"{cid}_trades.parquet", index=False)
            attempt.update(status="completed", metrics=row)
        except (ImportError, ValueError, RuntimeError, TimeoutError, MemoryError) as error:
            attempt.update(status="failed", error_type=type(error).__name__, error=str(error))
        attempts.append(attempt)
        parts.clear()
        if "combined" in locals():
            del combined
        gc.collect()
        # Append after each candidate, retaining failures as well as successful runs.
        with open(output/"attempts.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(attempt, default=str)+"\n")
        json_write(output/"leaderboard.json", leaderboard)
    json_write(output/"attempts.json", attempts)
    json_write(output/"model_analysis.json", model_analysis)
    if not leaderboard:
        json_write(output/"summary.json", dict(status="no_completed_candidates", no_deployable_candidate=True))
        return output
    ranked = sorted(leaderboard, key=lambda r: (r["research_eligible"], r["positive_fold_fraction"], r["net_pnl"]/(1+r["max_drawdown"])), reverse=True)
    best = ranked[0]
    chosen = artifacts[best["candidate_id"]]
    chosen["result"] = dict(curve=pd.read_parquet(output/f"{best['candidate_id']}_equity.parquet"),
        trades=pd.read_parquet(output/f"{best['candidate_id']}_trades.parquet"))
    valid_indexes = np.concatenate([v for _, v in folds])
    oos_bars = dev.iloc[valid_indexes].reset_index(drop=True)
    stress = stress_test(oos_bars, chosen["signals"], cfg)
    json_write(output/"stress.json", stress)
    best["stress_pass"] = all(x.get("net_pnl", -np.inf) > 0 for x in stress.values())
    robustness = dict(parameter_neighborhood={}, sessions={}, signal_degradation=[])
    if chosen["candidate"]["family"] == "baseline":
        for parameter in (.9, 1, 1.1):
            variant = {**chosen["candidate"], "parameter": parameter}
            signal = candidate_signal(variant, dev, features, cfg).iloc[valid_indexes].reset_index(drop=True)
            robustness["parameter_neighborhood"][str(parameter)] = summarize(run_backtest(oos_bars, signal, cfg), cfg.initial_balance)
        for session in ("rth", "overnight", "open", "midday", "close"):
            variant = {**chosen["candidate"], "session": session}
            signal = candidate_signal(variant, dev, features, cfg).iloc[valid_indexes].reset_index(drop=True)
            robustness["sessions"][session] = summarize(run_backtest(oos_bars, signal, cfg), cfg.initial_balance)
    for retention in (1, .9, .75, .5):
        wr, aw, al = best.get("win_rate"), best.get("average_win"), best.get("average_loss")
        ev = None if wr is None or aw is None or al is None else (wr*retention)*(aw*retention)+(1-wr*retention)*al
        robustness["signal_degradation"].append(dict(win_probability_and_average_win_retention=retention,
            estimated_net_expectancy=ev, note="Net trade-payoff sensitivity; costs already included; not a forecast"))
    json_write(output/"robustness.json", robustness)
    from .statistics import reality_check, deflated_sharpe_diagnostic
    daily_matrix = pd.DataFrame({r["candidate_id"]: r["daily_pnl"] for r in leaderboard}).sort_index()/cfg.initial_balance
    trial_sharpes = [r["sharpe"]/np.sqrt(252) for r in leaderboard if r.get("sharpe") is not None]
    json_write(output/"statistical_validation.json", dict(reality_check=reality_check(daily_matrix.to_numpy()),
        deflated_sharpe=deflated_sharpe_diagnostic(daily_matrix[best["candidate_id"]], trial_sharpes),
        final_holdout_evaluated=False, synthetic=manifest["synthetic"],
        uncertainty=best["uncertainty"], limitations="Development selection diagnostics; failed and prior searches can increase selection bias"))
    # Optional regime/session attribution uses only already OOS observations.
    oos_curve = chosen["result"]["curve"].copy()
    incremental = oos_curve.equity.diff().fillna(oos_curve.equity.iloc[0]-cfg.initial_balance)
    regime = causal_regime(features).iloc[valid_indexes].reset_index(drop=True)
    bucket = features.session_bucket.iloc[valid_indexes].reset_index(drop=True)
    json_write(output/"attribution.json", dict(regime=incremental.groupby(regime).sum().to_dict(),
        session_bucket=incremental.groupby(bucket).sum().to_dict(),
        note="retrospective OOS attribution; no causal performance weighting fitted on these results"))
    if rules_path:
        funded_report = {}
        for name, rules in load_rule_scenarios(rules_path).items():
            account = FundedAccount(rules)
            run_backtest(oos_bars, chosen["signals"], cfg, account)
            curve = chosen["result"]["curve"]
            grouped = curve.groupby("session_id", sort=False)
            closing = grouped.equity.last()
            opening = closing.shift(1).fillna(cfg.initial_balance)
            excursions = grouped.intrabar_worst_bound.min().to_numpy()-opening.to_numpy()
            funded_report[name] = dict(replay=account.summary(), monte_carlo=account_monte_carlo(
                list(best["daily_pnl"].values()), rules, seed=cfg.seed, worst_excursions=excursions))
        json_write(output/"funded_account.json", funded_report)
    eligible_train = np.flatnonzero(labels.label_end.notna() & labels.forward_return.notna())
    if explicit and cfg.validation_mode == "fixed":
        eligible_train = eligible_train[(pd.to_datetime(labels.label_end.iloc[eligible_train], utc=True) < pd.Timestamp(manifest["train_end_exclusive"])).to_numpy()]
    eligible_train = eligible_train[-cfg.maximum_training_rows:]
    fitted = None
    if chosen["candidate"]["family"] in ("ml", "meta"):
        fitted = _fit(chosen["candidate"], features.iloc[eligible_train].reset_index(drop=True),
            labels.iloc[eligible_train].reset_index(drop=True), dev.iloc[eligible_train].reset_index(drop=True), cfg)
    bundle = dict(candidate=chosen["candidate"], model=fitted, config=cfg.model_dump(), dataset_version=manifest["dataset_version"],
        synthetic=manifest["synthetic"], holdout_start=str(holdout_start), feature_columns=list(features.columns),
        holdout_end=manifest["test_partition"]["coverage"]["end"] if explicit else str(bars.timestamp_utc.iloc[-1]),
        test_partition=manifest.get("test_partition"), split_protocol_id=manifest.get("split_protocol_id"),
        **identity, created_at=datetime.now(timezone.utc).isoformat(), deployment_eligible=False)
    joblib.dump(bundle, output/"candidate.joblib", compress=3)
    if code_identity()["source_hash"] != identity["source_hash"]:
        raise RuntimeError("Source changed during research; results cannot be frozen")
    frozen = dict(candidate_id=best["candidate_id"], candidate=chosen["candidate"],
        model_hash=file_hash(output/"candidate.joblib"), dataset_version=manifest["dataset_version"],
        config_hash=digest(cfg.model_dump()), holdout_start=str(holdout_start), **identity)
    frozen["test_partition"] = manifest.get("test_partition")
    frozen["split_protocol_id"] = manifest.get("split_protocol_id")
    freeze_candidate(output/"frozen_candidate.json", frozen)
    json_write(output/"leaderboard.json", ranked)
    json_write(output/"summary.json", dict(status="functional_research_complete", synthetic=manifest["synthetic"],
        completed=len(leaderboard), failed=sum(a["status"] == "failed" for a in attempts),
        no_deployable_candidate=True, selected_for_research_only=best["candidate_id"],
        holdout_evaluated=False, runtime_seconds=time.monotonic()-start_clock,
        blockers=["Real contract-level data and official session schedule required" if manifest["synthetic"] else "Forward paper review and account-setting confirmation required",
                  "Research selection is not deployment approval", "Final holdout remains untouched"]))
    _report(output, ranked, manifest)
    return output


def evaluate_holdout(dataset, frozen_directory, governance_directory):
    frozen_directory, governance_directory = Path(frozen_directory), Path(governance_directory)
    frozen = json.loads((frozen_directory/"frozen_candidate.json").read_text())
    candidate = frozen["candidate"]
    if digest(candidate) != frozen["candidate_hash"]:
        raise ValueError("Frozen candidate manifest changed")
    artifact = frozen_directory/"candidate.joblib"
    if file_hash(artifact) != candidate["model_hash"]:
        raise ValueError("Artifact hash mismatch")
    bundle = joblib.load(artifact)  # Trusted local artifact; hash checked before deserialization.
    cfg = ResearchConfig.model_validate(bundle["config"])
    bars, manifest, _ = load_dataset(dataset, minutes=cfg.timeframe_minutes)
    if manifest["dataset_version"] != candidate["dataset_version"]:
        raise ValueError("Dataset version mismatch")
    identity = code_identity()
    if identity["source_hash"] != candidate["source_hash"]:
        raise ValueError("Source changed since freeze; refuse final-test evaluation")
    start = pd.Timestamp(candidate["holdout_start"])
    # Global dataset+boundary key, independent of model and run directory.
    test_partition = candidate.get("test_partition")
    if test_partition and test_partition["dataset_version"] != manifest.get("test_partition", {}).get("dataset_version"):
        raise ValueError("Frozen test partition provenance changed")
    key = digest(dict(test_partition=test_partition["dataset_version"])) if test_partition else digest(dict(dataset=manifest["dataset_version"], start=str(start)))
    reserve_holdout(governance_directory/f"{key}.json", dataset_version=manifest["dataset_version"],
        dates=[str(start), test_partition["coverage"]["end"] if test_partition else str(bars.timestamp_utc.iloc[-1])], model_version=candidate["model_hash"],
        code_commit=identity["code_commit"], config_hash=candidate["config_hash"], source_hash=identity["source_hash"])
    if test_partition:
        # Selection is frozen and the reservation has been consumed before any
        # test OHLC values or targets are loaded.
        test_bars, _, _ = load_dataset(test_partition["path"], purpose="final_test", minutes=cfg.timeframe_minutes)
        bars = pd.concat([bars, test_bars], ignore_index=True)
    f = build_features(bars, cfg.timeframe_minutes)
    signals = candidate_signal(bundle["candidate"], bars, f, cfg, bundle["model"])
    mask = bars.timestamp_utc >= start
    result = run_backtest(bars.loc[mask].reset_index(drop=True), signals.loc[mask].reset_index(drop=True), cfg)
    result["curve"].to_parquet(frozen_directory/"holdout_equity.parquet", index=False)
    report = dict(synthetic=manifest["synthetic"], single_use=True, metrics=summarize(result, cfg.initial_balance), deployment_eligible=False)
    json_write(frozen_directory/"holdout_results.json", report)
    return report


def _report(output, rows, manifest):
    label = "SYNTHETIC FUNCTIONAL TEST ONLY" if manifest["synthetic"] else "Historical out-of-sample development selection"
    lines = [f"# {label}", "", "No deployable candidate was found. Final holdout was not evaluated.", "",
        "All attempted candidates, including failures, are in attempts.json. Fees are assumed, not broker-verified.", "",
        "| Candidate | Net P&L | Max DD | Trades | Positive folds |", "|---|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['candidate_id']} | {r['net_pnl']:.2f} | {r['max_drawdown']:.2f} | {r['trades']} | {r['positive_fold_fraction']:.2f} |")
    lines += ["", "These values cannot establish market edge when the input is synthetic. Candidate selection uses only walk-forward development folds.",
        "Confidence intervals assume weakly stationary blocks; multiple testing uses a conservative Bonferroni diagnostic. Short samples remain insufficient."]
    (output/"report.md").write_text("\n".join(lines), encoding="utf-8")
