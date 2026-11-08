"""Bounded nested searches. Outer validation and final holdout are not accepted inputs."""
import time
import numpy as np
from sklearn.inspection import permutation_importance
from .models import fit_model
from .validation import walk_forward
from .backtest import run_backtest
from .metrics import summarize


def nested_search(name, bars, features, labels, cfg, max_trials=6, use_optuna=False):
    folds = list(walk_forward(bars, labels.label_end, max(50, len(bars)//2), max(20, len(bars)//5), cfg.embargo_bars))
    if not folds:
        raise ValueError("Insufficient inner training history")
    started = time.monotonic()
    attempts = []

    def score(params):
        scores = []
        if time.monotonic()-started > cfg.maximum_runtime_seconds:
            raise TimeoutError("Nested search time budget exceeded")
        for train, valid in folds:
            fitted = fit_model(name, features.iloc[train].reset_index(drop=True), labels.iloc[train].reset_index(drop=True),
                bars.iloc[train].reset_index(drop=True), seed=cfg.seed, calibration=cfg.calibration, params=params)
            signals = fitted.signal(features.iloc[valid], cfg.probability_threshold)
            metrics = summarize(run_backtest(bars.iloc[valid].reset_index(drop=True), signals, cfg), cfg.initial_balance)
            scores.append(metrics["net_pnl"]-metrics["max_drawdown"])
        value = float(np.mean(scores))
        attempts.append(dict(hyperparameters=params, inner_scores=scores, objective=value))
        return value

    if use_optuna:
        import optuna
        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=cfg.seed))
        def objective(trial):
            params = {"C": trial.suggest_float("C", .01, 1, log=True)} if name == "logistic" else {"alpha": trial.suggest_float("alpha", 1, 100, log=True)} if name == "ridge" else {"max_depth": trial.suggest_int("max_depth", 2, 4)}
            return score(params)
        study.optimize(objective, n_trials=min(max_trials, cfg.maximum_trials), timeout=cfg.maximum_runtime_seconds, n_jobs=1)
        best = study.best_params
    else:
        grid = [{"C": c} for c in (.01, .1, 1)] if name == "logistic" else [{"alpha": a} for a in (1, 10, 100)] if name == "ridge" else [{"max_depth": d} for d in (2, 3, 4)]
        for params in grid[:min(max_trials, cfg.maximum_trials)]:
            score(params)
        best = max(attempts, key=lambda a: a["objective"])["hyperparameters"]
    return dict(best_hyperparameters=best, trials=attempts, method="nested chronological net P&L minus drawdown", final_test_accessed=False)


def training_permutation_importance(fitted, validation_features, validation_target, seed=20261106):
    # Use inner validation only; this helper never chooses features from final test.
    return permutation_importance(fitted.base, validation_features[fitted.columns], validation_target,
                                  n_repeats=3, random_state=seed, n_jobs=1)


def feature_ablation(name, bars, features, labels, cfg, groups):
    # Every feature ablation is a separate registered inner experiment.
    result = {}
    for group, excluded in groups.items():
        result[group] = nested_search(name, bars, features.drop(columns=excluded, errors="ignore"), labels, cfg, max_trials=1)
    return result
