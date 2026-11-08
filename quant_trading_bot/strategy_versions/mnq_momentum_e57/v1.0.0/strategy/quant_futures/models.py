from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.tree import DecisionTreeClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss


def estimator(name, seed=20261106, params=None):
    params = params or {}
    if name == "logistic":
        model = LogisticRegression(C=params.get("C", .1), max_iter=300, random_state=seed)
    elif name == "ridge":
        model = Ridge(alpha=params.get("alpha", 10))
    elif name == "tree":
        model = DecisionTreeClassifier(max_depth=params.get("max_depth", 3), min_samples_leaf=30, random_state=seed)
    elif name == "lightgbm":
        from lightgbm import LGBMClassifier
        model = LGBMClassifier(n_estimators=80, max_depth=params.get("max_depth", 3), num_leaves=7,
            min_child_samples=30, learning_rate=.04, n_jobs=1, verbosity=-1, random_state=seed)
    elif name == "xgboost":
        from xgboost import XGBClassifier
        model = XGBClassifier(n_estimators=80, max_depth=params.get("max_depth", 3), learning_rate=.04,
            subsample=.8, colsample_bytree=.8, n_jobs=1, random_state=seed, eval_metric="logloss")
    else:
        raise ValueError(name)
    return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(), model)


FEATURE_COLUMNS = ["return_1", "log_return", "momentum_3", "momentum_5", "momentum_10", "momentum_20",
    "momentum_60", "range", "body", "upper_wick", "lower_wick", "atr_relative", "volatility", "parkinson",
    "garman_klass", "vol_of_vol", "vol_percentile", "vol_ratio", "zscore", "trend_slope", "rsi", "adx",
    "high_distance", "low_distance", "breakout", "failed_breakout", "relative_volume", "volume_zscore",
    "price_volume_corr", "volume_imbalance_proxy", "vwap_deviation", "session_high_distance", "session_low_distance",
    "range_expansion", "support_distance", "resistance_distance", "rth", "session_bucket", "opening_location", "persistence"]


@dataclass
class FittedModel:
    name: str
    columns: list
    base: object
    calibrator: object | None
    calibration_method: str
    constant: float | None = None
    return_scale: float = 1.0

    def raw_probability(self, features):
        if self.constant is not None:
            return np.full(len(features), self.constant)
        pieces = []
        for start in range(0, len(features), 2048):
            x = features.iloc[start:start+2048][self.columns]
            if self.name == "ridge":
                pieces.append(1/(1+np.exp(-np.clip(self.base.predict(x)/self.return_scale, -20, 20))))
            else:
                pieces.append(self.base.predict_proba(x)[:, 1])
        return np.concatenate(pieces) if pieces else np.empty(0)

    def predict_probability(self, features):
        raw = self.raw_probability(features)
        if self.calibrator is not None:
            raw = self.calibrator.predict(raw) if self.calibration_method == "isotonic" else self.calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]
        return np.clip(raw, 1e-6, 1-1e-6)

    def signal(self, features, threshold=.57):
        p = self.predict_probability(features)
        return pd.Series(np.select([p > threshold, p < 1-threshold], [1, -1], default=0), index=features.index)


def fit_model(name, features, labels, bars, *, seed=20261106, calibration="sigmoid", params=None, target=None):
    """Training-only pruning, scaling, fitting, and chronologically later calibration.

    Calibration boundary is purged by label end, rather than a random sklearn CV.
    Single-class fitting is explicitly a constant benchmark, never a hidden failure.
    """
    if len(features) < 50:
        raise ValueError("At least 50 training observations required")
    cutoff = max(30, int(.75*len(features)))
    # Fit indices use event endings strictly before calibration starts.
    eligible = pd.to_datetime(labels.label_end, utc=True) < bars.timestamp_utc.iloc[cutoff]
    y = (labels.forward_return > 0).astype(int) if target is None else target
    fit_indexes = np.flatnonzero(eligible & y.notna() & labels.forward_return.notna())
    cal_indexes = np.arange(cutoff, len(features))
    cal_indexes = cal_indexes[(labels.forward_return.iloc[cal_indexes].notna() & y.iloc[cal_indexes].notna()).to_numpy()]
    if len(fit_indexes) < 20:
        raise ValueError("Insufficient purged training observations")
    # All availability/variance/correlation decisions use base-fit data only.
    available = [c for c in FEATURE_COLUMNS if c in features and features[c].iloc[fit_indexes].notna().sum() >= 10 and features[c].iloc[fit_indexes].nunique() > 1]
    corr = features[available].iloc[fit_indexes].corr().abs()
    selected = []
    for column in available:
        if not selected or not (corr.loc[column, selected] > .98).any():
            selected.append(column)
    if not selected:
        raise ValueError("No eligible training features")
    base = estimator(name, seed, params)
    distinct = y.iloc[fit_indexes].unique()
    fitted = FittedModel(name, selected, base, None, calibration, float(distinct[0]) if len(distinct) == 1 else None)
    if fitted.constant is None:
        fit_target = labels.forward_return if name == "ridge" and target is None else y
        if name == "ridge" and target is None:
            fitted.return_scale = max(1e-8, float(fit_target.iloc[fit_indexes].std()))
        base.fit(features[selected].iloc[fit_indexes], fit_target.iloc[fit_indexes])
    if calibration != "none" and len(cal_indexes) >= 20 and y.iloc[cal_indexes].nunique() == 2:
        raw = fitted.raw_probability(features.iloc[cal_indexes])
        if calibration == "isotonic":
            calibrator = IsotonicRegression(out_of_bounds="clip").fit(raw, y.iloc[cal_indexes])
        else:
            calibrator = LogisticRegression(C=1, random_state=seed).fit(raw.reshape(-1, 1), y.iloc[cal_indexes])
        fitted.calibrator = calibrator
    return fitted


def calibration_metrics(y, p, bins=10):
    y, p = np.asarray(y), np.asarray(p)
    valid = np.isfinite(y) & np.isfinite(p)
    y, p = y[valid].astype(int), np.clip(p[valid], 1e-6, 1-1e-6)
    if not len(y):
        return dict(observations=0)
    diagram, error = [], 0.0
    for i in range(bins):
        mask = (p >= i/bins) & (p < (i+1)/bins)
        if mask.any():
            confidence, frequency = float(p[mask].mean()), float(y[mask].mean())
            error += mask.sum()/len(y)*abs(confidence-frequency)
            diagram.append(dict(count=int(mask.sum()), probability=confidence, frequency=frequency))
    return dict(observations=len(y), brier=float(brier_score_loss(y, p)),
                log_loss=float(log_loss(y, p, labels=[0, 1])), calibration_error=float(error), reliability=diagram)


class FittedRegime:
    """Optional unsupervised training-only clustering with a reusable transform."""
    columns = ["adx", "volatility", "relative_volume", "persistence"]

    def __init__(self, method="kmeans", seed=20261106):
        from sklearn.cluster import KMeans
        from sklearn.mixture import GaussianMixture
        self.preprocess = make_pipeline(SimpleImputer(keep_empty_features=True), StandardScaler())
        self.model = KMeans(n_clusters=3, n_init=10, random_state=seed) if method == "kmeans" else GaussianMixture(n_components=3, random_state=seed)

    def fit(self, f):
        self.model.fit(self.preprocess.fit_transform(f[self.columns]))
        return self

    def predict(self, f):
        return self.model.predict(self.preprocess.transform(f[self.columns]))
