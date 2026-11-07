"""Bounded one-minute reference features and external-memory model helpers.

Features are a separately versioned causal price-only definition; they are not
claimed identical to the earlier 15-minute feature set. No volume transfer.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import SGDClassifier, LogisticRegression
from quant_futures.data import canonical
from quant_futures.config import file_hash
from quant_futures.research import json_write

COLUMNS = ["return_1", "momentum_5", "momentum_20", "momentum_60", "momentum_120",
    "volatility_20", "volatility_60", "volatility_ratio", "range", "body", "upper_wick", "lower_wick",
    "zscore_20", "zscore_120", "trend_20_120", "high_distance_60", "low_distance_60", "clock_sin", "clock_cos"]


def price_features(bars):
    b = canonical(bars)
    boundaries = b.contract.ne(b.contract.shift()) | (b.timestamp_utc.diff() > pd.Timedelta(minutes=5))
    pieces = []
    for _, group in b.groupby(boundaries.cumsum(), sort=False):
        close, high, low, opening = group.close, group.high, group.low, group.open
        returns = close.pct_change(fill_method=None)
        f = pd.DataFrame(index=group.index)
        f["return_1"] = returns
        for count in (5, 20, 60, 120):
            f[f"momentum_{count}"] = close.pct_change(count, fill_method=None)
        f["volatility_20"], f["volatility_60"] = returns.rolling(20).std(), returns.rolling(60).std()
        f["volatility_ratio"] = f.volatility_20/f.volatility_60.replace(0, np.nan)
        span = (high-low).replace(0, np.nan)
        f["range"] = (high-low)/close
        f["body"] = (close-opening)/span
        f["upper_wick"] = (high-pd.concat([opening, close], axis=1).max(axis=1))/span
        f["lower_wick"] = (pd.concat([opening, close], axis=1).min(axis=1)-low)/span
        for count in (20, 120):
            f[f"zscore_{count}"] = (close-close.rolling(count).mean())/close.rolling(count).std().replace(0, np.nan)
        f["trend_20_120"] = (close.rolling(20).mean()-close.rolling(120).mean())/close
        f["high_distance_60"] = close/high.shift().rolling(60).max()-1
        f["low_distance_60"] = close/low.shift().rolling(60).min()-1
        local = group.timestamp_utc.dt.tz_convert("America/New_York")
        clock = local.dt.hour*60+local.dt.minute
        f["clock_sin"], f["clock_cos"] = np.sin(clock*2*np.pi/1440), np.cos(clock*2*np.pi/1440)
        pieces.append(f)
    return pd.concat(pieces).sort_index()[COLUMNS].replace([np.inf, -np.inf], np.nan).astype("float32")


def contract_frames(path):
    pending = pd.DataFrame()
    with pq.ParquetFile(path) as parquet:
        for batch in parquet.iter_batches(batch_size=100000):
            frame = pd.concat([pending, batch.to_pandas()], ignore_index=True)
            last = frame.contract.iloc[-1]
            for contract, group in frame[frame.contract != last].groupby("contract", sort=False):
                yield contract, group.reset_index(drop=True)
            pending = frame[frame.contract == last].reset_index(drop=True)
    if len(pending):
        yield pending.contract.iloc[0], pending


def build_shards(source, destination, horizon=20):
    source, destination = Path(source), Path(destination)
    destination.mkdir(exist_ok=False)
    metadata = json.loads(source.with_suffix(".manifest.json").read_text())
    if metadata.get("split_role") != "train" or metadata["instrument"] not in ("ES", "NQ"):
        raise PermissionError("Only reference training partitions may create fitting shards")
    if file_hash(source) != metadata["dataset_version"]:
        raise ValueError("Reference source checksum mismatch")
    report = dict(source_dataset_version=metadata["dataset_version"], reference=metadata["instrument"],
        input_rows=0, eligible_rows=0, columns=COLUMNS, horizon_minutes=horizon,
        dtype="float32", no_row_sampling=True, no_volume_features=True, shards=[])
    for contract, bars in contract_frames(source):
        if not bars.timestamp_utc.lt(pd.Timestamp("2024-01-01T00:00Z")).all():
            raise PermissionError("Reference fitting cannot include 2024 onward")
        features = price_features(bars)
        from quant_futures.labels import future_returns
        labels = future_returns(bars, horizon=horizon, minutes=1)
        eligible = features.notna().all(axis=1) & labels.forward_return.notna() & pd.to_datetime(labels.label_end, utc=True).lt(pd.Timestamp("2024-01-01T00:00Z"))
        path = destination/f"{contract}.npz"
        ts = pd.DatetimeIndex(bars.timestamp_utc[eligible]).as_unit("ns").asi8
        end = pd.DatetimeIndex(labels.label_end[eligible]).as_unit("ns").asi8
        x = features.loc[eligible].to_numpy(dtype=np.float32)
        y = (labels.forward_return[eligible] > 0).to_numpy(dtype=np.float32)
        np.savez_compressed(path, x=x, y=y, timestamp=ts, label_end=end)
        report["input_rows"] += len(bars)
        report["eligible_rows"] += len(x)
        report["shards"].append(dict(path=str(path), contract=contract, rows=len(x), sha256=file_hash(path)))
        json_write(destination/"manifest.json", report)
        print(metadata["instrument"], contract, "1m shard", f"{len(x):,}", flush=True)
    if report["input_rows"] != metadata["coverage"]["rows"]:
        raise ValueError("Sharding lost source rows")
    return report


def batches(shards, start=None, end=None):
    low = pd.Timestamp(start).value if start else None
    high = pd.Timestamp(end).value if end else None
    for item in shards:
        with np.load(item["path"]) as batch:
            mask = np.ones(len(batch["y"]), dtype=bool)
            if low is not None:
                mask &= batch["timestamp"] >= low
            if high is not None:
                mask &= (batch["timestamp"] < high) & (batch["label_end"] < high)
            if mask.any():
                yield batch["x"][mask], batch["y"][mask]


def train_streaming_logistic(shards, end):
    scaler = StandardScaler()
    count = 0
    for x, _ in batches(shards, end=end):
        scaler.partial_fit(x)
        count += len(x)
    model = SGDClassifier(loss="log_loss", alpha=.001, random_state=20261106, learning_rate="optimal", average=True)
    for _ in range(3):
        for x, y in batches(shards, end=end):
            model.partial_fit(scaler.transform(x), y, classes=np.array([0., 1.]))
    return dict(kind="streaming_logistic", model=model, scaler=scaler, calibration=None, fitting_rows=count)


def train_external_xgboost(shards, end, cache_directory):
    import xgboost as xgb
    cache_directory = Path(cache_directory)
    cache_directory.mkdir(exist_ok=False)
    class Iterator(xgb.DataIter):
        def __init__(self):
            super().__init__(cache_prefix=str(cache_directory/"pages"))
            self.iterator = iter(batches(shards, end=end))
        def reset(self):
            self.iterator = iter(batches(shards, end=end))
        def next(self, input_data):
            try:
                x, y = next(self.iterator)
            except StopIteration:
                return False
            input_data(data=x, label=y)
            return True
    iterator = Iterator()
    matrix = xgb.ExtMemQuantileDMatrix(iterator, max_bin=63)
    model = xgb.train(dict(objective="binary:logistic", tree_method="hist", max_bin=63,
        max_depth=3, eta=.04, subsample=.8, colsample_bytree=.8, nthread=1, seed=20261106), matrix, num_boost_round=80)
    return dict(kind="external_xgboost", model=model, scaler=None, calibration=None, fitting_rows=matrix.num_row())


def predict(bundle, x):
    out = []
    for start in range(0, len(x), 8192):
        part = np.asarray(x[start:start+8192], dtype=np.float32)
        if bundle["kind"] == "external_xgboost":
            values = bundle["model"].inplace_predict(part)
        else:
            values = bundle["model"].predict_proba(bundle["scaler"].transform(part))[:, 1]
        if bundle.get("calibration") is not None:
            values = bundle["calibration"].predict_proba(values.reshape(-1, 1))[:, 1]
        out.append(values)
    return np.concatenate(out) if out else np.empty(0)


def calibrate(bundle, shards, start, end):
    prediction, truth = [], []
    for x, y in batches(shards, start=start, end=end):
        prediction.append(predict(bundle, x))
        truth.append(y)
    p, y = np.concatenate(prediction), np.concatenate(truth)
    bundle["calibration"] = LogisticRegression(C=1, random_state=20261106).fit(p.reshape(-1, 1), y)
    bundle["calibration_rows"] = len(y)
    return bundle
