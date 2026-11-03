import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from eth_research.backtest import Assumptions, simulate
from eth_research.data import TICKER, validate_bars, write_csv_atomic
from eth_research.features import build_features, eligible_indices
from eth_research.neural import TorchClassifier
from eth_research.perpetual_data import TICKER as PERPETUAL_TICKER, archive


def sample_bars(n=500):
    rng = np.random.default_rng(42)
    close = 2000 * np.exp(np.cumsum(rng.normal(0, .002, n)))
    op = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"timestamp": pd.date_range("2025-01-01", periods=n, freq="5min", tz="UTC"),
                         "ticker": TICKER, "open": op, "close": close,
                         "high": np.maximum(close, op) * 1.001, "low": np.minimum(close, op) * .999,
                         "volume": rng.uniform(10, 100, n)})


class FeatureTests(unittest.TestCase):
    def test_future_price_changes_do_not_change_past_features(self):
        bars = sample_bars()
        first, columns = build_features(bars)
        altered = bars.copy()
        altered.loc[400:, ["open", "high", "low", "close"]] *= 3
        second, _ = build_features(altered)
        cutoff = bars.iloc[399].timestamp
        pd.testing.assert_frame_equal(first.loc[first.timestamp <= cutoff, columns], second.loc[second.timestamp <= cutoff, columns])

    def test_final_observation_remains_unlabeled_but_available_for_inference(self):
        frame, _ = build_features(sample_bars())
        self.assertTrue(pd.isna(frame.iloc[-1].target))
        self.assertNotIn(len(frame) - 1, eligible_indices(frame))
        self.assertIn(len(frame) - 1, eligible_indices(frame, labeled=False))
        row = frame.iloc[-2]
        self.assertEqual(row.target, float(row.exit > row.entry))

    def test_gap_resets_warmup_and_sequence(self):
        bars = sample_bars().drop(index=250)
        frame, _ = build_features(bars)
        after = frame[frame.timestamp > pd.Timestamp("2025-01-01 20:50", tz="UTC")]
        self.assertGreaterEqual(after.iloc[0].timestamp, bars.loc[251].timestamp + pd.Timedelta(minutes=96 * 5))
        i = eligible_indices(frame)
        for idx in i:
            self.assertEqual(frame.iloc[idx].timestamp - frame.iloc[idx - 23].timestamp, pd.Timedelta(minutes=23 * 5))

    def test_wrong_instrument_and_duplicates_are_rejected(self):
        bars = sample_bars()
        with self.assertRaises(ValueError):
            validate_bars(bars.assign(ticker="AAPL"))
        with self.assertRaises(ValueError):
            validate_bars(pd.concat([bars, bars.iloc[:1]]))

    def test_spot_and_perpetual_sources_cannot_be_mixed(self):
        spot = sample_bars()
        perp = spot.assign(ticker=PERPETUAL_TICKER)
        frame, _ = build_features(perp, expected_ticker=PERPETUAL_TICKER)
        self.assertGreater(len(frame), 0)
        with self.assertRaises(ValueError):
            build_features(perp)
        with self.assertRaises(ValueError):
            build_features(pd.concat([spot.iloc[:250], perp.iloc[250:]]), expected_ticker=PERPETUAL_TICKER)


class ArchiveTests(unittest.TestCase):
    def test_failed_download_write_cannot_publish_a_partial_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bars.csv"
            path.write_text("old complete dataset", encoding="utf-8")
            def partial_write(frame, stream, **kwargs):
                stream.write("partial")
                raise OSError("interrupted write")
            with patch.object(pd.DataFrame, "to_csv", partial_write):
                with self.assertRaises(OSError):
                    write_csv_atomic(sample_bars(), path)
            self.assertEqual(path.read_text(encoding="utf-8"), "old complete dataset")
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_corrupt_cached_archive_is_rejected_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "ETHUSDT-5m-2025-01.zip").write_bytes(b"corrupt")
            (path / "ETHUSDT-5m-2025-01.zip.CHECKSUM").write_text("0" * 64 + " filename")
            session = Mock()
            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                archive(session, "2025-01", "monthly", path)
            session.get.assert_not_called()


class SimulationTests(unittest.TestCase):
    def fixture(self):
        frame, _ = build_features(sample_bars())
        return frame.dropna(subset=["target"]).iloc[-100:].reset_index(drop=True)

    def test_costs_reduce_returns_and_payout_only_applies_to_positive_profit(self):
        frame = self.fixture()
        perfect = np.where(frame.forward_return > 0, .9, .1)
        free, _ = simulate(frame, perfect, .5, Assumptions(fee_bps_per_side=0, slippage_bps_per_side=0, swap_bps_daily=0))
        paid, _ = simulate(frame, perfect)
        self.assertLess(paid["net_return"], free["net_return"])
        self.assertAlmostEqual(paid["trader_share_of_positive_net_profit"], max(0, paid["net_return"]) * .9)

    def test_no_trade_has_zero_return_and_no_payout(self):
        metrics, trades = simulate(self.fixture(), np.ones(100), 1.)
        self.assertEqual(metrics["trades"], 0)
        self.assertEqual(metrics["net_return"], 0)
        self.assertEqual(metrics["trader_share_of_positive_net_profit"], 0)
        self.assertFalse(trades.executed.any())

    def test_intrabar_breach_stops_subsequent_trades(self):
        frame = self.fixture()
        frame.loc[0, "exit_low"] = frame.loc[0, "entry"] * .5
        metrics, trades = simulate(frame, np.ones(100) * .9, assumptions=Assumptions(total_loss_limit=.03, daily_loss_limit=.03))
        self.assertEqual(len(metrics["breaches"]), 1)
        self.assertEqual(int(trades.executed.sum()), 1)
        self.assertGreater(metrics["max_intrabar_drawdown"], .03)

    def test_four_hour_swap_snapshot_uses_nanosecond_units(self):
        frame = self.fixture().iloc[:1].copy()
        frame["entry_time"] = pd.Timestamp("2025-01-01 03:55", tz="UTC")
        frame["label_end"] = pd.Timestamp("2025-01-01 04:00", tz="UTC")
        cfg = Assumptions(fee_bps_per_side=0, slippage_bps_per_side=0, swap_bps_daily=3.3)
        charged, _ = simulate(frame, [.9], assumptions=cfg)
        cfg.swap_bps_daily = 0
        free, _ = simulate(frame, [.9], assumptions=cfg)
        self.assertAlmostEqual(free["net_return"] - charged["net_return"], .1 * 3.3 / 6 / 10000)


class NeuralTests(unittest.TestCase):
    def test_train_and_serialization_for_all_network_families(self):
        frame, columns = build_features(sample_bars(600))
        x = frame[columns].to_numpy(dtype=np.float32)
        y = frame.target.to_numpy()
        indices = eligible_indices(frame)
        train, test = indices[:300], indices[310:320]
        for kind in ["mlp", "lstm", "cnn"]:
            with self.subTest(kind=kind):
                model = TorchClassifier(kind, epochs=1, hidden=8)
                model.fit(x, y, train)
                expected = model.predict_probability(x, test)
                restored = TorchClassifier.restore(model.export(), len(columns))
                actual = restored.predict_probability(x, test)
                np.testing.assert_allclose(actual, expected)
                self.assertTrue(((actual >= 0) & (actual <= 1)).all())


if __name__ == "__main__":
    unittest.main()
