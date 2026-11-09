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

from quant_futures.session_calendar import apply_early_close, early_close_dates

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


# Antigravity "All-Weather" sleeves (research/antigravity/*.json), added at Nick's request 2026-11-08 as a paper candidate only.
# Fixed-engine replication: 30m breakout 2010-19 -391 / 2020-23 +7,487; 60m trend 2025 did not reproduce (-1,188 vs claimed +325).
_AG_BRK30 = dict(instrument="MNQ", family="breakout", lookback=8, threshold=1.5, stop_atr=1.25, target_r=5.0, hold_bars=8,
                 session_start=600, session_end=945, trailing_atr=0.0, bar_minutes=30, signal="donchian_atr",
                 entry_start=570, entry_end=690, max_gap_minutes=60)
_AG_TRD60 = dict(instrument="MNQ", family="trend", lookback=12, threshold=0.75, stop_atr=1.25, target_r=4.0, hold_bars=8,
                 session_start=600, session_end=945, trailing_atr=0.0, bar_minutes=60, signal="ewma_trend",
                 entry_start=540, entry_end=660, max_gap_minutes=90)

# Antigravity "Quad Champion" additions (2026-11-08, Nick: "add the quad champion to the paper ledger"); paper only.
# Afternoon MNQ 30m trend replicated: 2010-19 net $0 (6/14 years positive), 2020-23 +4,232 (reports/ANTIGRAVITY_PM_REPLICATION.json).
_AG_MORN30 = dict(instrument="MNQ", family="trend", lookback=16, threshold=0.75, stop_atr=1.5, target_r=3.5, hold_bars=8,
                  session_start=600, session_end=945, trailing_atr=0.0, bar_minutes=30, signal="ewma_trend",
                  entry_start=570, entry_end=690, max_gap_minutes=60)   # Antigravity "Sleeve 1": EMA 8/16 over ATR14, decisions 09:45-12:00 ET
_AG_TRD60Q = dict(_AG_TRD60, max_gap_minutes=120)
_AG_CRABEL15 = dict(instrument="MNQ", family="trend", lookback=8, threshold=0.0, stop_atr=2.0, target_r=4.0, hold_bars=12, trailing_atr=0.0,
                    session_start=600, session_end=945, bar_minutes=15, signal="crabel_open_drive", tail=0.2, entry_start=585, entry_end=585, max_gap_minutes=20)
_AG_TRD30C = dict(instrument="MNQ", family="trend", lookback=16, threshold=0.75, stop_atr=1.5, target_r=3.5, hold_bars=8, trailing_atr=0.0,
                  session_start=585, session_end=720, bar_minutes=30, signal="ewma_trend", entry_start=555, entry_end=690, max_gap_minutes=60)
_AG_TRD60C = dict(instrument="MNQ", family="trend", lookback=12, threshold=0.75, stop_atr=1.25, target_r=4.0, hold_bars=8, trailing_atr=0.0,
                  session_start=600, session_end=720, bar_minutes=60, signal="ewma_trend", entry_start=540, entry_end=660, max_gap_minutes=90)
_AG_TRD30PM = dict(instrument="MNQ", family="trend", lookback=8, threshold=0.5, stop_atr=1.5, target_r=4.0, hold_bars=4,
                   session_start=600, session_end=945, trailing_atr=0.0, bar_minutes=30, signal="ewma_trend",
                   entry_start=780, entry_end=870, max_gap_minutes=60)
_AG_MES_TRD30 = dict(instrument="MES", family="trend", lookback=8, threshold=1.0, stop_atr=1.25, target_r=2.5, hold_bars=12,
                     session_start=600, session_end=945, trailing_atr=0.0, bar_minutes=30, signal="ewma_trend",
                     entry_start=570, entry_end=900, max_gap_minutes=60)   # quad candidate applies router="strict_1c" (global 1-contract cap, priority 1>2>3>4)

# Architecture D+ Grand Champion additions (MNQ 15m Crabel + MNQ 30m trend + MNQ 60m macro trend + MES 30m cross-asset trend)
_AG_CRABEL15_D = dict(instrument="MNQ", family="trend", lookback=8, threshold=0.0, stop_atr=2.0, target_r=3.5, hold_bars=8, trailing_atr=0.0,
                      session_start=600, session_end=945, bar_minutes=15, signal="crabel_open_drive", tail=0.2, min_range=15.0,
                      entry_start=585, entry_end=585, max_gap_minutes=20)
_AG_TRD30_D = dict(instrument="MNQ", family="trend", lookback=16, threshold=0.75, stop_atr=1.5, target_r=3.0, hold_bars=8, trailing_atr=0.0,
                   session_start=585, session_end=720, bar_minutes=30, signal="ewma_trend", entry_start=555, entry_end=690, max_gap_minutes=60)
_AG_TRD60_D = dict(instrument="MNQ", family="trend", lookback=12, threshold=0.75, stop_atr=1.25, target_r=4.0, hold_bars=6, trailing_atr=0.0,
                   session_start=600, session_end=720, bar_minutes=60, signal="ewma_trend", entry_start=540, entry_end=660, max_gap_minutes=90)
_AG_MES_TRD30_D = dict(instrument="MES", family="trend", lookback=8, threshold=1.0, stop_atr=1.25, target_r=2.5, hold_bars=12, trailing_atr=0.0,
                      session_start=585, session_end=930, bar_minutes=30, signal="ewma_trend", entry_start=570, entry_end=900, max_gap_minutes=60)


def _atr14(bars):
    c, h, l = bars.close.to_numpy(float), bars.high.to_numpy(float), bars.low.to_numpy(float)
    prev = np.r_[c[0], c[:-1]]
    return pd.Series(np.maximum(h - l, np.maximum(abs(h - prev), abs(l - prev)))).rolling(14, min_periods=14).mean().to_numpy()


def custom_signal(cfg, bars):
    """Exact signal definitions used in scripts/replicate_antigravity_30m.py and replicate_antigravity_mtf.py."""
    atr = _atr14(bars)
    c = bars.close.to_numpy(float)
    if cfg["signal"] == "donchian_atr":
        lb, th = int(cfg["lookback"]), float(cfg["threshold"])
        bh = bars.high.rolling(lb).max().shift(1).to_numpy(float)
        bl = bars.low.rolling(lb).min().shift(1).to_numpy(float)
        sig = np.where(c > bh + th * atr, 1, np.where(c < bl - th * atr, -1, 0))
    elif cfg["signal"] == "ewma_trend":
        th, lb = float(cfg["threshold"]), int(cfg.get("lookback", 12))
        tr = ((bars.close.ewm(span=max(2, lb // 2), adjust=False).mean() - bars.close.ewm(span=lb, adjust=False).mean()).to_numpy(float)) / atr
        sig = np.where(tr >= th, 1, np.where(tr <= -th, -1, 0))
    elif cfg["signal"] == "crabel_open_drive":
        # Antigravity Architecture C sleeve 1 (reports/ANTIGRAVITY_ARCH_C_REPLICATION.md): on 15m bars, 09:30 open in the bottom (top) 20% of the
        # 09:30-10:00 range and the 10:00 close in the top (bottom) 20% -> long (short); signal sits on the 09:45 bar (its close is 10:00), fill at the 10:00 open.
        et = bars.timestamp_utc.dt.tz_convert("America/New_York"); sod = (et.dt.hour * 60 + et.dt.minute).to_numpy(); day = et.dt.date.to_numpy()
        df = pd.DataFrame(dict(day=day, sod=sod, o=bars.open.to_numpy(float), h=bars.high.to_numpy(float), l=bars.low.to_numpy(float), c=c))
        r = df[df.sod.isin([570, 585])].groupby("day"); o930 = df[df.sod == 570].groupby("day").o.first(); c1000 = df[df.sod == 585].groupby("day").c.first()
        hi, lo = r.h.max(), r.l.min(); rng_ = (hi - lo).replace(0, np.nan); op = (o930 - lo) / rng_; cp = (c1000 - lo) / rng_
        tail = float(cfg.get("tail", 0.2)); sig_day = pd.Series(np.where((op <= tail) & (cp >= 1 - tail), 1, np.where((op >= 1 - tail) & (cp <= tail), -1, 0)), index=op.index)
        min_rng = float(cfg.get("min_range", 0.0))
        if min_rng > 0:
            sig_day = pd.Series(np.where(rng_ >= min_rng, sig_day, 0), index=op.index)
        sig = np.where(sod == 585, pd.Series(day).map(sig_day).fillna(0).to_numpy(), 0)
    else:
        raise ValueError(cfg["signal"])
    return sig.astype(np.int8), np.nan_to_num(atr).astype(np.float32)


def bars_key(sleeve):
    minutes = int(sleeve.get("bar_minutes", BAR_MINUTES))
    return sleeve["instrument"] if minutes == BAR_MINUTES else f"{sleeve['instrument']}@{minutes}"


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
    "ag_quad": dict(
        version="1.1.0", router="strict_1c", label="AG Quad Champion (MNQ 30m morning trend > MNQ 60m macro trend > MNQ 30m afternoon trend > MES 30m trend; strict 1-contract router)",
        sleeves=[_sleeve("AG_MORN30_1c", _AG_MORN30, 1), _sleeve("AG_TRD60Q_1c", _AG_TRD60Q, 1), _sleeve("AG_TRD30PM_1c", _AG_TRD30PM, 1), _sleeve("AG_MES_TRD30_1c", _AG_MES_TRD30, 1)],
        provenance="Antigravity 'QUAD CHAMPION' spec message 2026-11-08 (v1.1.0 replaces the provisional 3-sleeve v1.0.0 before any trade), added as paper "
                   "candidate at Nick's request. Fixed-engine replications: 60m trend 2025 -1,188 vs claimed +325; afternoon trend 2010-19 $0 / 2020-23 +4,232 "
                   "(reports/ANTIGRAVITY_PM_REPLICATION.json); morning lb16 and MES sleeves not replicated here. Router strict_1c: one contract across all sleeves; a trade whose "
                   "decision bar falls inside any open trade is rejected (priority by sleeve order), re-run until no overlap. Selected after seeing 2024-26: forward paper is the only clean evidence.",
    ),
    "ag_all_weather": dict(
        version="1.0.0", label="AG All-Weather (1 MNQ 30m breakout + 1 MNQ 60m EWMA trend; Antigravity candidate)",
        sleeves=[_sleeve("AG_BRK30_1c", _AG_BRK30, 1), _sleeve("AG_TRD60_1c", _AG_TRD60, 1)],
        provenance="Antigravity rule dicts 2026-11-08, added as paper candidate at Nick's request; fixed-engine replication "
                   "reports/ANTIGRAVITY_30M_REPLICATION.json (30m: 2010-19 -391, 2020-23 +7,487, 2024-25 +3,559) and "
                   "reports/ANTIGRAVITY_MTF_REPLICATION.json (60m: 2024 +3,337, 2025 -1,188 vs claimed +325). "
                   "Both sleeves were selected by Antigravity after seeing 2024-26: forward paper is the only clean evidence.",
    ),
}


# Overnight reopen-dip hold (research/overnight_2, 2026-11-09): paper-only at Nick's request. Training 2010-23 D4 variant +7,228 / 446 nights,
# 11/14 years, DD 1,303, 199/200 placebo; frozen sibling D5 failed the one-shot 2024-25 (-1,031 / +1,751). Forward paper is the remaining test.
OVN_SEED_GAPS = [0.00053, -0.00029, 0.00014, 0.00087, 0.00172, -0.00086, -0.00087, 0.00018, 0.00017, 0.00061, 0.00802, 0.00354, -0.00057,
                 0.0021, 0.00051, 0.00003, 0.00228, 0.00009, 0.00024, 0.00001]  # last 20 MNQ reopen gaps of Dec 2025 (owned data, Sunday vs Friday close), used until 20 live gaps exist
OVN_SEED_GAPS_MES = [0.00048, 0.00047, -0.00025, 0.00087, 0.00124, -0.0004, -0.00062, 0.00101, 0.00026, 0.00935, -0.00062, 0.00192, -0.00051,
                     0.00247, 0.00018, -0.00025, 0.00298, 0.0, 0.00025, 0.0]
OVN_TICK, OVN_MULT, OVN_SPREAD_TICKS, OVN_SLIP_TICKS, OVN_COMM = 0.25, 2.0, 1.75, 1.0, 0.61
OVN_ECON = {"MNQ": dict(mult=2.0, spread=1.75, seed=None), "MES": dict(mult=5.0, spread=1.0, seed=None)}
CANDIDATES["overnight_dip"] = dict(
    version="1.0.1", overnight=True, exit_sod=570, require_mes_dip=False, label="Overnight Dip (MNQ 1c: hold 18:05 -> 09:30 ET only when the 18:00 reopen is <= -0.5 sd below the 16:00 close)",
    sleeves=[dict(name="OVN_DIP_1c", instrument="MNQ", bar_minutes=1, max_contracts=1)],
    provenance="research/overnight_2/PROTOCOL.md + reports/OVERNIGHT_2_TRAINING.md (D4). Gap = 18:00 ET bar open / last 15:55-16:00 close (Sunday vs Friday) - 1; "
               "threshold -0.5 x std of the previous 20 gaps (seeded with Dec-2025 gaps until 20 live gaps exist). Entry 18:05 bar open + half spread + slippage, "
               "exit next 09:30 bar open - half spread - slippage, $0.61/side; safety flatten at the last bar <= 16:05 ET if no RTH open bar appears. "
               "Not validated (sibling failed 2024-25); paper only, no routing.",
)


CANDIDATES["overnight_dip_v2"] = dict(
    version="2.0.0", overnight=True, exit_sod=585, require_mes_dip=True,
    label="Overnight Dip v2 (MNQ 1c: hold 18:05 -> 09:45 ET when both the MNQ and MES 18:00 reopens are <= -0.5 sd below their 16:00 close)",
    sleeves=[dict(name="OVN_DIP2_1c", instrument="MNQ", bar_minutes=1, max_contracts=1)],
    provenance="research/overnight_3/PROTOCOL.md + reports/OVERNIGHT_3_TRAINING.md (pre-declared combination C2+E2): training 2010-23 +11,797 / 490 nights / "
               "12 of 14 years / closed DD 1,646 / 200 of 200 placebos. Challenger to overnight_dip v1 on paper only; not validated (2024-26 sealed); no routing.",
)

CANDIDATES["ag_arch_c"] = dict(
    version="1.0.0", router="strict_1c", label="AG Architecture C (Crabel 10:00 open-drive > MNQ 30m morning trend > MNQ 60m trend; strict 1-contract router)",
    sleeves=[_sleeve("AG_CRABEL15_1c", _AG_CRABEL15, 1), _sleeve("AG_TRD30C_1c", _AG_TRD30C, 1), _sleeve("AG_TRD60C_1c", _AG_TRD60C, 1)],
    provenance="Antigravity Architecture C (scripts/audit_architecture_c_all_splits.py), added as paper candidate at Nick's request 2026-11-09. Fixed-engine replication "
               "reports/ANTIGRAVITY_ARCH_C_REPLICATION.md: 2010-23 +16,070 / 1,980 trades / 11 of 14 years / DD 1,596 / 2010-19 +5,050 / 2021 = 42%. Sender has scored 2024-26, "
               "so forward paper is the only clean evidence. Simulated fills, no routing.",
)

CANDIDATES["overnight_dip_mes"] = dict(
    version="1.0.0", overnight=True, exit_sod=575, exit_at_close=True, require_mes_dip=False,
    label="Overnight Dip MES (MES 1c: hold 18:05 -> 09:35 ET close when the MES 18:00 reopen is <= -0.5 sd below its 16:00 close)",
    sleeves=[dict(name="OVN_DIP_MES_1c", instrument="MES", bar_minutes=1, max_contracts=1)],
    provenance="reports/OVERNIGHT_3_TRAINING.md MES E1: training 2010-23 +6,482 / 724 nights / 11 of 14 years / DD 1,543 / 200 of 200 placebos. Second-instrument read of the "
               "same mechanism; Devin's discretion 2026-11-09. Not validated; paper only; no routing.",
)
CANDIDATES["ag_arch_c_lite"] = dict(
    version="1.0.0", router="strict_1c", label="AG Architecture C lite (Crabel 10:00 open-drive > MNQ 60m trend; no 30m trend sleeve; strict 1-contract router)",
    sleeves=[_sleeve("AG_CRABEL15_1c", _AG_CRABEL15, 1), _sleeve("AG_TRD60C_1c", _AG_TRD60C, 1)],
    provenance="archc_1 variant A2 (reports/ARCHC_1_TRAINING.md): training 2010-23 +12,873 / 1,357 trades / $9.5 per trade / 10 of 14 years / closed DD 974 (vs 1,604 with the 30m sleeve). "
               "Failed the pre-registered net gate; added at Devin's discretion as the lower-drawdown sibling of ag_arch_c for a side-by-side forward test. Paper only; no routing.",
)

CANDIDATES["ag_arch_c_v2"] = dict(
    version="2.0.0", router="strict_1c", day_filter="no_backwardation",
    label="AG Architecture C v2 (same three sleeves; stands aside on days whose prior CBOE close had VIX > VIX3M)",
    sleeves=[_sleeve("AG_CRABEL15_1c", _AG_CRABEL15, 1), _sleeve("AG_TRD30C_1c", _AG_TRD30C, 1), _sleeve("AG_TRD60C_1c", _AG_TRD60C, 1)],
    provenance="archc_2 V3 (reports/ARCHC_2_TRAINING.md): training 2010-23 +17,291 / 1,886 trades / 12 of 14 years / DD 1,596; the 64 removed backwardation days lost -1,221 "
               "(below the 5th pct of random same-count day sets). Failed the pre-registered DD gate (DD unchanged); deployed at Devin's discretion beside ag_arch_c. "
               "VIX/VIX3M from yfinance daily, cached in runs/bars/vix_daily.csv. Paper only; no routing.",
)

CANDIDATES["ag_all_weather_v2"] = dict(
    version="2.0.0", day_filter="no_backwardation", label="AG All-Weather v2 (same two sleeves; stands aside on days whose prior CBOE close had VIX > VIX3M)",
    sleeves=[_sleeve("AG_BRK30_1c", _AG_BRK30, 1), _sleeve("AG_TRD60_1c", _AG_TRD60, 1)],
    provenance="allweather_1 V1 (reports/ALLWEATHER_1_TRAINING.md): training 2010-23 +14,073 / DD 1,455 vs +13,069 / DD 2,061 unfiltered; the 59 removed days lost -1,005. "
               "Missed the positive-years gate by one; deployed at Devin's discretion beside ag_all_weather. Paper only; no routing.",
)

CANDIDATES["ag_all_weather_v2_1c"] = dict(
    version="2.1.0", day_filter="no_backwardation", label="AG All-Weather v2 1c (same two filtered sleeves; always one contract - the $150 stop-risk budget is not applied)",
    sleeves=[dict(_sleeve("AG_BRK30_1c", _AG_BRK30, 1), risk_per_trade=1e9, max_open_risk=1e9), dict(_sleeve("AG_TRD60_1c", _AG_TRD60, 1), risk_per_trade=1e9, max_open_risk=1e9)],
    provenance="sizing_1 V1 (reports/SIZING_1_TRAINING.md): training 2010-23 +16,520 / 1,590 trades / DD 1,256 vs +14,073 / DD 1,455 with the $150 budget; the 39 added "
               "high-ATR trades made +2,447 (random same-count trade sets: median +120). All pre-registered gates passed. Daily-loss, hard-drawdown and funded-lock gates unchanged. Paper only; no routing.",
)

CANDIDATES["book_a"] = dict(
    version="1.0.0", book=("overnight_dip_v2", "ag_all_weather_v2_1c"),
    label="Book A (overnight dip v2 + All-Weather v2 1c as one 1-contract account; night leg has priority, intraday decisions while it is open are skipped)",
    sleeves=[dict(sl) for k in ("overnight_dip_v2", "ag_all_weather_v2_1c") for sl in CANDIDATES[k]["sleeves"]],
    provenance=("portfolio_4 (reports/PORTFOLIO_4_TRAINING.md): the two frozen legs summed on training 2010-23 give +28,317, closed DD 1,633, "
                "monthly corr 0.09, 0 overlapping fills, 1-y P(DD>=2k) 1.9%; book_1 marked (intraday-trailing) DD 2,043 once (Mar 2020). "
                "No parameter chosen; both component ledgers keep running. Paper only; no routing."),
)

CANDIDATES["overnight_dip_v2_skew_addon"] = dict(
    version="1.0.0", overnight=True, exit_sod=585, require_mes_dip=True, state="skew_below", hidden=True,
    label="Overnight Dip v2 SKEW add-on (second contract on nights whose prior CBOE close had SKEW below its 20-day mean)",
    sleeves=[dict(name="OVN_DIP2_SKEW_1c", instrument="MNQ", bar_minutes=1, max_contracts=1)],
    provenance="sizing_3 (reports/SIZING_3_TRAINING.md). Component of book_a_skew only; not shown as its own ledger.",
)

CANDIDATES["ag_all_weather_v2_1c_skew_addon"] = dict(
    version="1.0.0", day_filter="no_backwardation", hidden=True,
    label="AG All-Weather v2 1c SKEW add-on (second contract on days whose prior CBOE close had SKEW below its 20-day mean)",
    sleeves=[dict(_sleeve("AG_BRK30_SKEW_1c", _AG_BRK30, 1), risk_per_trade=1e9, max_open_risk=1e9, state="skew_below"),
             dict(_sleeve("AG_TRD60_SKEW_1c", _AG_TRD60, 1), risk_per_trade=1e9, max_open_risk=1e9, state="skew_below")],
    provenance="sizing_3 (reports/SIZING_3_TRAINING.md). Component of book_a_skew only; not shown as its own ledger.",
)

CANDIDATES["book_a_skew"] = dict(
    version="1.0.0", category="future",
    book=[["overnight_dip_v2", "overnight_dip_v2_skew_addon"], ["ag_all_weather_v2_1c", "ag_all_weather_v2_1c_skew_addon"]],
    label="FUTURE - Book A SKEW-sized (Book A legs; 2 contracts when the prior CBOE close has SKEW below its 20-day mean, else 1; needs ~$1.5k banked cushion first)",
    sleeves=[dict(sl) for k in ("overnight_dip_v2", "overnight_dip_v2_skew_addon", "ag_all_weather_v2_1c", "ag_all_weather_v2_1c_skew_addon") for sl in CANDIDATES[k]["sleeves"]],
    provenance=("sizing_3 (reports/SIZING_3_TRAINING.md), training 2010-23: book +51,047 vs +28,317 at 1c, closed DD 2,767 (control: 2c on SKEW>=20d mean +33,906 / DD 3,494), "
                "1-y P(breach $2k floor) 17% -> fails the $2k gate; fits once ~$1.5k is banked above the locked floor (effective floor >= $3.5k). "
                "Forward record only; switch target, not a current-account candidate. Paper only; no routing."),
)

CANDIDATES["overnight_dip_v2_bond"] = dict(
    version="1.0.0", overnight=True, exit_sod=585, require_mes_dip=True, state="zn_not_down", hidden=True,
    label="Overnight Dip v2 bond-conditioned (skips nights whose day had the 10-yr note's 16:00 ET close below the prior day's)",
    sleeves=[dict(name="OVN_DIP2_BOND_1c", instrument="MNQ", bar_minutes=1, max_contracts=1)],
    provenance="xasset_3 (reports/XASSET_3_TRAINING.md). Component of book_a_bond only; not shown as its own ledger.",
)

CANDIDATES["book_a_bond"] = dict(
    version="1.0.0", book=("overnight_dip_v2_bond", "ag_all_weather_v2_1c"),
    label="Book A bond-conditioned (Book A legs; the overnight leg skips nights whose day had the 10-yr note close down at 16:00 ET; night leg has priority)",
    sleeves=[dict(sl) for k in ("overnight_dip_v2_bond", "ag_all_weather_v2_1c") for sl in CANDIDATES[k]["sleeves"]],
    provenance=("xasset_2/xasset_3 (reports/XASSET_2_TRAINING.md, XASSET_3_TRAINING.md), training 2010-23 only, derived on the same split: dip nights after a "
                "bonds-down day earn ~$9/night vs ~$34 after bonds-up; skipping them keeps 93.5% of Book A's net (+26,481 vs +28,317) and cuts the marked "
                "(intraday-trailing) DD from 2,043 to 1,506 with 0 touches of a $2k floor; 193/200 random same-count skips are worse, the mirror control fails. "
                "Not scored on 2024-26. Challenger beside book_a; both keep running. FRAGILITY: re-scored with the 15:00 ET settlement close the rule keeps 87.6% / DD 1,676 but only 147/200 placebos are worse "
                "(fails) - the effect sits largely in the 15:00-16:00 bond move, so the live state uses the exact 16:00 ET close from yfinance ZN=F 1-minute bars. Paper only; no routing."),
)

CANDIDATES["ag_quad_v2"] = dict(
    version="2.0.0", router="strict_1c", day_filter="no_backwardation",
    label="AG Quad v2 (same four sleeves; the two MNQ morning sleeves stand aside on days whose prior CBOE close had VIX > VIX3M)",
    sleeves=[_sleeve("AG_MORN30_1c", _AG_MORN30, 1), _sleeve("AG_TRD60Q_1c", _AG_TRD60Q, 1), dict(_sleeve("AG_TRD30PM_1c", _AG_TRD30PM, 1), day_filter_exempt=True),
             dict(_sleeve("AG_MES_TRD30_1c", _AG_MES_TRD30, 1), day_filter_exempt=True)],
    provenance="quad_2 V1 (reports/QUAD_2_TRAINING.md): training 2010-23 +17,707 / 2,274 trades / 11 of 14 years / DD 2,048 vs +16,811 unfiltered; 35 removed days lost -1,374. "
               "All pre-registered gates passed. Paper only; no routing.",
)

# Dashboard grouping (Nick, 2026-11-09): variants of one architecture share a family so the dashboard shows a per-family net beside the overall net.
FAMILIES = {
    "Overnight Dip": ("overnight_dip", "overnight_dip_v2", "overnight_dip_mes", "overnight_dip_v2_vix", "overnight_dip_v2_bond", "overnight_dip_v2_skew_addon"),
    "AG All-Weather": ("ag_all_weather", "ag_all_weather_v2", "ag_all_weather_v2_1c", "ag_all_weather_v2_1c_skew_addon"),
    "AG Architecture C": ("ag_arch_c", "ag_arch_c_lite", "ag_arch_c_v2"),
    "AG Architecture D+": ("ag_arch_d_plus", "ag_arch_d_plus_v2", "ag_arch_d_plus_v2_2c"),
    "AG Quad": ("ag_quad", "ag_quad_v2"),
    "Book A (overnight dip v2 + All-Weather v2 1c)": ("book_a", "book_a_bond", "book_a_skew"),
    "Book D+ (overnight dip + Architecture D+)": ("book_d_plus",),
    "Codex ensembles": ("ensemble_beta", "ensemble_epsilon", "portfolio_e", "portfolio_e_scaled"),
}
_FAMILY_OF = {k: f for f, keys in FAMILIES.items() for k in keys}


def family_of(key):
    return _FAMILY_OF.get(key, "Other")


def _dplus_sl(name, base, contracts):
    """D+ sleeves always take `contracts` regardless of stop risk (the $150 budget is not applied), matching the fixed-engine replication
    (reports/ANTIGRAVITY_D_PLUS_REPLICATION.md, run with SIZING_BUDGET=1e9) and Antigravity's 1-contract claims."""
    return dict(_sleeve(name, base, contracts), risk_per_trade=1e9, max_open_risk=1e9)


CANDIDATES["ag_arch_d_plus"] = dict(
    version="1.0.0", router="strict_1c", day_filter="no_backwardation",
    label="AG Architecture D+ Grand Champion (Crabel 10:00 15m > MNQ 30m trend > MNQ 60m trend > MES 30m cross-asset trend; stands aside on morning sleeves when prior CBOE close had VIX > VIX3M; strict 1-contract router)",
    sleeves=[_dplus_sl("AG_CRABEL15_D_1c", _AG_CRABEL15_D, 1),
             _dplus_sl("AG_TRD30_D_1c", _AG_TRD30_D, 1),
             _dplus_sl("AG_TRD60_D_1c", _AG_TRD60_D, 1),
             dict(_dplus_sl("AG_MES_TRD30_D_1c", _AG_MES_TRD30_D, 1), day_filter_exempt=True)],
    provenance="Devin fixed-engine replication (reports/ANTIGRAVITY_D_PLUS_REPLICATION.md), training 2010-23: +20,723 / 1,968 trades / $10.53 per trade / closed DD 1,654 / 12 of 14 years, pre-2020 +6,626; challenger ledger only, not staged. Antigravity Grand Champion Architecture D+ (reports/RESEARCH_ARCHITECTURE_D_PLUS_TRAINING_IMPROVEMENT_REPORT.md): training 2010-23 +20,292.55 / 1,635 trades / $12.41 per trade / closed DD $935.65 / cushion +$1,064.35 (53.2% safety margin) / 0.02% 1y Monte Carlo breach rate. Simulated fills, paper only; no routing.",
)

CANDIDATES["ag_arch_d_plus_v2"] = dict(
    version="1.0.0", router="strict_1c", day_filter="no_backwardation",
    label="AG Architecture D+ v2 (drawdown-first: Crabel 10:00 15m > MNQ 60m trend > MES 30m trend; the MNQ 30m trend sleeve is dropped; VIX stand-aside on morning sleeves; always one contract)",
    sleeves=[_dplus_sl("AG_CRABEL15_D_1c", _AG_CRABEL15_D, 1),
             _dplus_sl("AG_TRD60_D_1c", _AG_TRD60_D, 1),
             dict(_dplus_sl("AG_MES_TRD30_D_1c", _AG_MES_TRD30_D, 1), day_filter_exempt=True)],
    provenance="dplus_2 (reports/DPLUS_2_TRAINING.md), derived from the dplus_1 ablation on training 2010-23: +17,576 / 1,398 trades / $12.57 per trade / closed DD 783 / "
               "marked DD 882 / 12 of 14 years; lower DD than 200 of 200 count-matched random removals. The dropped 30m sleeve is positive in 10 of 14 years, so this is a "
               "net-for-drawdown trade (85% of ag_arch_d_plus's net for half its DD), deployed on Nick's request as the scalable base. Paper only; no routing.",
)

CANDIDATES["ag_arch_d_plus_v2_2c"] = dict(
    version="1.0.0", router="strict_1c", day_filter="no_backwardation", category="future",
    label="AG Architecture D+ v2 at 2 contracts (same three sleeves, always two contracts; needs ~$900 banked above the locked floor first)",
    sleeves=[_dplus_sl("AG_CRABEL15_D_2c", _AG_CRABEL15_D, 2),
             _dplus_sl("AG_TRD60_D_2c", _AG_TRD60_D, 2),
             dict(_dplus_sl("AG_MES_TRD30_D_2c", _AG_MES_TRD30_D, 2), day_filter_exempt=True)],
    provenance="dplus_2 scaled: per-contract P&L and costs are linear in this engine, so training 2010-23 is exactly 2x v2: +35,152 / marked DD 1,765 / 0 touches of $2k - "
               "the same drawdown as ag_arch_d_plus at 1c for +70% net. Future strategy: switch once ~$900 is banked. Paper only; no routing.",
)

CANDIDATES["overnight_dip_v2_vix"] = dict(
    version="1.0.0", overnight=True, exit_sod=585, require_mes_dip=True, state="not_backwardation", hidden=True,
    label="Overnight Dip v2 VIX-conditioned (skips nights whose prior CBOE close had VIX > VIX3M term structure backwardation)",
    sleeves=[dict(name="OVN_DIP2_VIX_1c", instrument="MNQ", bar_minutes=1, max_contracts=1)],
    provenance="research_book_d_plus_risk_reduction_train: training 2010-23 +8,877 / 420 nights / marked DD $1,241 / 0 breaches of $2k floor. Component of book_d_plus only; not shown as its own ledger.",
)

CANDIDATES["book_d_plus"] = dict(
    version="1.0.0", book=("overnight_dip_v2_vix", "ag_arch_d_plus"), hidden=True,  # Devin fixed-engine replication (reports/ANTIGRAVITY_D_PLUS_REPLICATION.md): marked DD 2,333 with one $2k touch, the VIX night gate removes +3,489 of profitable nights; not run as a ledger
    label="Book D+ (Overnight Dip v2 VIX-conditioned + Architecture D+ Intraday; strict 1-contract account; night leg has priority, intraday decisions while open are skipped)",
    sleeves=[dict(sl) for k in ("overnight_dip_v2_vix", "ag_arch_d_plus") for sl in CANDIDATES[k]["sleeves"]],
    provenance=("research_book_d_plus_risk_reduction_train, training 2010-23: book +29,169.65 / 2,055 units / $14.19 per unit / marked (intraday-trailing) DD $1,241.33 / "
                "safety cushion +$758.67 under $2k floor (37.9% safety margin) / 0 touches / 0 breaches of $2k floor across 14 years / 0.00% 1-year Monte Carlo ruin probability. "
                "Paper only; no routing."),
)



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


def aggregate(one_minute, minutes=BAR_MINUTES):
    """Exact-count N-minute bars from 1-minute bars (all N source minutes required; default 15)."""
    frame = one_minute.sort_values("timestamp_utc").drop_duplicates("timestamp_utc")
    bucket = frame.timestamp_utc.dt.floor(f"{minutes}min")
    grouped = frame.groupby(bucket)
    bars = grouped.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), volume=("volume", "sum"))
    count = grouped.size()
    span = grouped.timestamp_utc.max() - grouped.timestamp_utc.min()
    keep = (count == minutes) & (span == pd.Timedelta(minutes=minutes - 1))
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


def _blocked(bars, runs, names):
    """True on bars whose timestamp falls inside an open trade of any named sleeve (entry fill through exit), or after an
    entry that is still open at the end of the data."""
    ts = pd.to_datetime(bars.timestamp_utc, utc=True)
    out = pd.Series(False, index=bars.index)
    for name in names:
        for t in runs[name]["trades"]:
            out |= (ts >= pd.Timestamp(t["entry_ts"])) & (ts < pd.Timestamp(t["exit_ts"]))
        if runs[name].get("open_since"):
            out |= ts >= pd.Timestamp(runs[name]["open_since"])
    return out.to_numpy()


_VIX_CACHE = {"path": None, "series": None}
def vix_backwardation_days():
    """Dates (CBOE close) where VIX > VIX3M, from yfinance daily history (1y); cached to <bars>/vix_daily.csv so a feed failure falls back to the last copy."""
    if _VIX_CACHE["series"] is not None: return _VIX_CACHE["series"]
    path = _VIX_CACHE["path"]; joined = None
    try:
        import yfinance as yf
        rows = {}
        for key, symbol in (("vix", "^VIX"), ("vix3m", "^VIX3M")):
            h = yf.Ticker(symbol).history(period="1y", interval="1d", auto_adjust=False)["Close"].dropna(); h.index = pd.to_datetime(h.index.strftime("%Y-%m-%d")); rows[key] = h
        joined = pd.concat([rows["vix"].rename("vix"), rows["vix3m"].rename("vix3m")], axis=1).dropna()
        if path is not None and len(joined):
            old = pd.read_csv(path, index_col=0, parse_dates=True) if Path(path).exists() else None
            joined = pd.concat([old, joined]).loc[lambda d: ~d.index.duplicated(keep="last")].sort_index() if old is not None else joined
            joined.to_csv(path)
    except Exception:
        if path is not None and Path(path).exists(): joined = pd.read_csv(path, index_col=0, parse_dates=True)
    ser = (joined.vix > joined.vix3m) if joined is not None and len(joined) else pd.Series(dtype=bool)
    _VIX_CACHE["series"] = ser; return ser

_SKEW_CACHE = {"path": None, "series": None}
def skew_below_days():
    """CBOE SKEW close < its 20-day mean, by CBOE close date (yfinance ^SKEW daily, 1y); cached to <bars>/skew_daily.csv so a feed failure falls back."""
    if _SKEW_CACHE["series"] is not None: return _SKEW_CACHE["series"]
    path = _SKEW_CACHE["path"]; ser = None
    try:
        import yfinance as yf
        h = yf.Ticker("^SKEW").history(period="1y", interval="1d", auto_adjust=False)["Close"].dropna(); h.index = pd.to_datetime(h.index.strftime("%Y-%m-%d"))
        ser = h.rename("skew").to_frame()
        if path is not None and len(ser):
            old = pd.read_csv(path, index_col=0, parse_dates=True) if Path(path).exists() else None
            ser = pd.concat([old, ser]).loc[lambda d: ~d.index.duplicated(keep="last")].sort_index() if old is not None else ser
            ser.to_csv(path)
    except Exception:
        if path is not None and Path(path).exists(): ser = pd.read_csv(path, index_col=0, parse_dates=True)
    if ser is not None and len(ser) >= 20:
        lvl = ser["skew"].astype(float); mean20 = lvl.rolling(20).mean(); out = (lvl < mean20)[mean20.notna()]
    else:
        out = pd.Series(dtype=bool)
    _SKEW_CACHE["series"] = out; return out

_ZN_CACHE = {"path": None, "series": None}
def zn_down_days():
    """10-yr note futures 16:00 ET close below the prior day's 16:00 close, by date. Research definition (xasset_2/3: last ZN 1-minute close in 15:55-15:59 ET);
    live source is yfinance ZN=F 1-minute bars (7-day window), accumulated in <bars>/zn_daily.csv so history builds up and a feed failure falls back to the
    last copy. The settlement (15:00) definition was pre-registered as a fallback and FAILED the gate, so only the 16:00 definition is used."""
    if _ZN_CACHE["series"] is not None: return _ZN_CACHE["series"]
    path = _ZN_CACHE["path"]; ser = None
    try:
        import yfinance as yf
        h = yf.Ticker("ZN=F").history(period="7d", interval="1m", auto_adjust=False)["Close"].dropna()
        et = h.index.tz_convert("America/New_York"); sod = et.hour * 60 + et.minute; sel = (sod >= 955) & (sod < 960)
        c16 = h[sel].groupby(pd.Index(et[sel].strftime("%Y-%m-%d"))).last(); c16.index = pd.to_datetime(c16.index)
        ser = c16.rename("zn16").to_frame()
        if path is not None and len(ser):
            old = pd.read_csv(path, index_col=0, parse_dates=True) if Path(path).exists() else None
            ser = pd.concat([old, ser]).loc[lambda d: ~d.index.duplicated(keep="last")].sort_index() if old is not None else ser
            ser.to_csv(path)
    except Exception:
        if path is not None and Path(path).exists(): ser = pd.read_csv(path, index_col=0, parse_dates=True)
    if ser is not None and len(ser) >= 2:
        lvl = ser["zn16"].astype(float); out = (lvl < lvl.shift(1))[lvl.shift(1).notna()]
    else:
        out = pd.Series(dtype=bool)
    _ZN_CACHE["series"] = out; return out

def _prior_close_state(series, dates):
    """Value of a CBOE-close-dated boolean series at the last close strictly before each ET date (point-in-time); False where unknown."""
    if len(series) == 0: return np.zeros(len(dates), bool)
    cboe = series.index.to_numpy(); days = pd.to_datetime(pd.Series(np.asarray(dates)).astype(str)).to_numpy()
    pos = np.searchsorted(cboe, days, side="left") - 1; vals = series.to_numpy()
    return np.where(pos >= 0, vals[np.clip(pos, 0, len(vals) - 1)], False)

def state_block_mask(sleeve, b):
    """True on bars the sleeve may NOT trade because the required prior-close state is absent. ``state="skew_below"``: SKEW < 20d mean (sizing_3)."""
    if sleeve.get("state") != "skew_below": return np.zeros(len(b), bool)
    allowed = _prior_close_state(skew_below_days(), b.timestamp_utc.dt.tz_convert("America/New_York").dt.date.to_numpy())
    return ~allowed

def day_filter_mask(spec, b, sleeve=None):
    """True on bars whose ET trading date follows a CBOE close with VIX > VIX3M (prior-close state, point-in-time)."""
    if spec.get("day_filter") != "no_backwardation" or (sleeve is not None and sleeve.get("day_filter_exempt")): return np.zeros(len(b), bool)
    back = vix_backwardation_days()
    if len(back) == 0: return np.zeros(len(b), bool)
    cboe = back.index.to_numpy()
    days = pd.to_datetime(pd.Series(b.timestamp_utc.dt.tz_convert("America/New_York").dt.date.to_numpy()).astype(str)).to_numpy()
    pos = np.searchsorted(cboe, days, side="left") - 1  # last CBOE close strictly before the bar's date
    vals = back.to_numpy(); return np.where(pos >= 0, vals[np.clip(pos, 0, len(vals) - 1)], False)


def _book_intervals(runs):
    """[(open_utc, close_utc)] for every trade and still-open position of a run dict (used to block the other leg's decision bars)."""
    iv = []
    for r in runs.values():
        for t in r["trades"]: iv.append((pd.Timestamp(t["entry_ts"]), pd.Timestamp(t["exit_ts"])))
        if r["position"]["quantity"] and r.get("open_since"): iv.append((pd.Timestamp(r["open_since"]), pd.Timestamp("2200-01-01", tz="UTC")))
    return iv


def _interval_block(iv):
    def f(b):
        ts = pd.to_datetime(b.timestamp_utc, utc=True); m = np.zeros(len(b), bool)
        for a, z in iv: m |= ((ts >= pd.Timestamp(a).tz_convert("UTC")) & (ts < pd.Timestamp(z).tz_convert("UTC"))).to_numpy()
        return m
    return f


def run_routed(spec, bars, start, max_iter=12, extra_block=None):
    if spec.get("book"):
        # Two frozen candidates as one 1-contract account: the overnight leg runs first; the intraday leg's decision bars that fall while a night
        # position is open are blocked (training: 0 such overlaps, portfolio_4). Component ledgers are untouched.
        # ``book`` is a priority-ordered list of groups (a str is a group of one); every group is blocked by the intervals of all groups before it,
        # so a group of {leg, leg_skew_addon} trades the same bars twice (= 2 contracts in the SKEW state, sizing_3) without blocking itself.
        runs = {}
        for group in spec["book"]:
            block = _interval_block(_book_intervals(runs)) if runs else None
            for key in ([group] if isinstance(group, str) else group):
                runs.update(run_routed(CANDIDATES[key], bars, start, extra_block=block))
        return runs
    """Run the candidate's sleeves. ``router="strict_1c"``: at most one contract across all sleeves; a trade whose decision bar
    (fill bar minus one) falls while any accepted trade is open is rejected (priority = sleeve order on ties) by masking its
    signal bar and re-running, until no overlap remains. Otherwise sleeves run independently (optionally ``router_after`` masks)."""
    if spec.get("overnight"):
        return {spec["sleeves"][0]["name"]: run_overnight(spec, bars[spec["sleeves"][0]["instrument"] + "@1"], start, bars.get("MES@1"))}
    if spec.get("router") != "strict_1c":
        runs = {}
        for sl in spec["sleeves"]:
            b = bars[bars_key(sl)]
            blocked = _blocked(b, runs, sl["router_after"]) if sl.get("router_after") else None
            if spec.get("day_filter"):
                dfm = day_filter_mask(spec, b, sl); blocked = dfm if blocked is None else (blocked | dfm)
            if extra_block is not None:
                xm = extra_block(b); blocked = xm if blocked is None else (blocked | xm)
            if sl.get("state"):
                sm = state_block_mask(sl, b); blocked = sm if blocked is None else (blocked | sm)
            runs[sl["name"]] = run_sleeve(sl, b, start, blocked)
        return runs
    masks = {sl["name"]: day_filter_mask(spec, bars[bars_key(sl)], sl) for sl in spec["sleeves"]}
    prio = {sl["name"]: i for i, sl in enumerate(spec["sleeves"])}
    for _ in range(max_iter):
        runs = {sl["name"]: run_sleeve(sl, bars[bars_key(sl)], start, masks[sl["name"]]) for sl in spec["sleeves"]}
        rows = []
        for sl in spec["sleeves"]:
            r = runs[sl["name"]]; minutes = int(sl.get("bar_minutes", BAR_MINUTES))
            for t, eb in zip(r["trades"], r["entry_bars"]):
                e = pd.Timestamp(t["entry_ts"]); rows.append((e - pd.Timedelta(minutes=minutes), e, pd.Timestamp(t["exit_ts"]), prio[sl["name"]], sl["name"], eb))
            if r["position"]["quantity"] and r.get("open_since"):
                e = pd.Timestamp(r["open_since"]); rows.append((e - pd.Timedelta(minutes=minutes), e, pd.Timestamp("2200-01-01", tz="UTC"), prio[sl["name"]], sl["name"], None))
        rows.sort(key=lambda x: (x[0], x[3]))
        open_until, rejected = None, []
        for decision, entry, exit_, _, name, eb in rows:
            if open_until is not None and decision < open_until:
                rejected.append((name, eb))
            else:
                open_until = exit_ if open_until is None else max(open_until, exit_)
        if not rejected:
            return runs
        for name, eb in rejected:
            if eb is not None:
                masks[name][max(eb - 1, 0)] = True
            else:   # still-open position without trade record: mask its signal bar via open_since
                b = bars[bars_key(next(s for s in spec["sleeves"] if s["name"] == name))]
                i = int((pd.to_datetime(b.timestamp_utc, utc=True) < pd.Timestamp(runs[name]["open_since"])).sum())
                masks[name][max(i - 1, 0)] = True
    return runs


def _reopen_gaps(mes):
    """Per date: True when the MES 18:00 reopen gap is <= -0.5 sd of its previous 20 gaps (seeded as for MNQ). Only prior completed nights enter the sd."""
    if mes is None or mes.empty: return {}
    m = mes.sort_values("timestamp_utc"); local = m.timestamp_utc.dt.tz_convert("America/New_York")
    sod = (local.dt.hour * 60 + local.dt.minute).to_numpy(); day = local.dt.date.to_numpy(); o = m.open.to_numpy(dtype=float); c = m.close.to_numpy(dtype=float)
    rth_close, reopen = {}, {}
    for i in range(len(m)):
        if 955 <= sod[i] < 960: rth_close[day[i]] = c[i]
        if 1080 <= sod[i] < 1085 and day[i] not in reopen: reopen[day[i]] = o[i]
    gaps = list(OVN_SEED_GAPS_MES); last_close = None; out = {}
    for d in sorted(set(day)):
        if d in rth_close: last_close = rth_close[d]
        if d not in reopen or last_close is None: continue
        gap = reopen[d] / last_close - 1; out[d] = bool(gap <= -0.5 * float(np.std(gaps[-20:], ddof=1))); gaps.append(gap)
    return out


def run_overnight(spec, b, start, mes=None):
    """Overnight reopen-dip hold on 1-minute MNQ bars; same output shape as run_sleeve. Long only, 1 contract, paper fills."""
    name = spec["sleeves"][0]["name"]; exit_sod = int(spec.get("exit_sod", 570)); exit_at_close = bool(spec.get("exit_at_close", False))
    inst = spec["sleeves"][0]["instrument"]; econ = OVN_ECON[inst]; mult, spread = econ["mult"], econ["spread"]
    seed = OVN_SEED_GAPS if inst == "MNQ" else OVN_SEED_GAPS_MES
    mes_gaps = _reopen_gaps(mes) if spec.get("require_mes_dip") else None
    b = b.sort_values("timestamp_utc").reset_index(drop=True)
    state_ok = None
    if spec.get("state") == "skew_below":  # prior CBOE close (the day's 16:15 close precedes the 18:00 reopen; the series is dated by close day)
        _d = sorted(set(b.timestamp_utc.dt.tz_convert("America/New_York").dt.date.to_numpy()))
        state_ok = dict(zip(_d, _prior_close_state(skew_below_days(), [x + pd.Timedelta(days=1) for x in pd.to_datetime(pd.Series(_d).astype(str))])))
    if spec.get("state") == "zn_not_down":  # xasset_3: skip the night if the day's ZN 16:00 ET close was below the prior day's; unknown state -> trade (as in research)
        _d = sorted(set(b.timestamp_utc.dt.tz_convert("America/New_York").dt.date.to_numpy()))
        state_ok = dict(zip(_d, ~_prior_close_state(zn_down_days(), [x + pd.Timedelta(days=1) for x in pd.to_datetime(pd.Series(_d).astype(str))]).astype(bool)))
    if spec.get("state") == "not_backwardation":  # Book D+: skip the night if the day's CBOE close had VIX > VIX3M (term structure backwardation)
        _d = sorted(set(b.timestamp_utc.dt.tz_convert("America/New_York").dt.date.to_numpy()))
        state_ok = dict(zip(_d, ~_prior_close_state(vix_backwardation_days(), [x + pd.Timedelta(days=1) for x in pd.to_datetime(pd.Series(_d).astype(str))]).astype(bool)))
    local = b.timestamp_utc.dt.tz_convert("America/New_York"); sod = (local.dt.hour * 60 + local.dt.minute).to_numpy(); day = local.dt.date.to_numpy()
    o, h, l, c = (b[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    half = (spread / 2 + OVN_SLIP_TICKS) * OVN_TICK
    days = sorted(set(day)); rth_close = {}; reopen = {}; entry = {}; rth_open = {}; safety = {}
    for i in range(len(b)):
        d = day[i]
        if 955 <= sod[i] < 960: rth_close[d] = c[i]
        if 1080 <= sod[i] < 1085 and d not in reopen: reopen[d] = i
        if 1085 <= sod[i] < 1090 and d not in entry: entry[d] = i
        if exit_sod <= sod[i] < exit_sod + 5 and d not in rth_open: rth_open[d] = i
        if sod[i] <= 965: safety[d] = i
    last_ts = b.timestamp_utc.iloc[-1]
    gaps = list(seed); last_close = None; trades = []; entry_bars = []; pos = None; cash = INITIAL_BALANCE
    cash_arr = np.full(len(b), np.nan); eq_arr = np.full(len(b), np.nan); worst_arr = np.full(len(b), np.nan)
    start_ts = pd.Timestamp(start); first = int((b.timestamp_utc < start_ts).sum())
    for di, d in enumerate(days):
        if d in rth_close: last_close = rth_close[d]
        if d not in reopen or last_close is None: continue
        ri = reopen[d]; gap = o[ri] / last_close - 1; thr = -0.5 * float(np.std(gaps[-20:], ddof=1)); gaps.append(gap)
        ei = entry.get(d)
        if ei is None or gap > thr or ei < first or pos is not None: continue
        if mes_gaps is not None and not mes_gaps.get(d, False): continue
        if state_ok is not None and not state_ok.get(d, False): continue
        fill = o[ei] + half; pos = dict(i=ei, price=fill)
        xi, reason = None, None
        for nd in days[di + 1:di + 4]:
            if nd in rth_open and rth_open[nd] > ei: xi, reason = rth_open[nd], "rth_open"; break
            cutoff = pd.Timestamp(nd).tz_localize("America/New_York") + pd.Timedelta(minutes=965)
            if nd in safety and safety[nd] > ei and last_ts >= cutoff: xi, reason = safety[nd], "safety_flatten"; break
        if xi is None: continue  # still open
        xp = (c[xi] if (exit_at_close or reason != "rth_open") else o[xi]) - half; net = (xp - fill) * mult - 2 * OVN_COMM
        trades.append(dict(sleeve=name, entry_ts=b.timestamp_utc[ei].isoformat(), exit_ts=b.timestamp_utc[xi].isoformat(), side=1, qty=1, entry_price=round(fill, 2),
                           exit_price=round(xp, 2), net=round(float(net), 2), fees=round(2 * OVN_COMM, 2), reason=reason))
        entry_bars.append(ei); pos = None
        for j in range(ei, xi): eq_arr[j] = cash + (c[j] - fill) * mult; worst_arr[j] = cash + (l[j] - fill) * mult
        cash += net; cash_arr[xi] = cash
    if pos is not None:
        for j in range(pos["i"], len(b)): eq_arr[j] = cash + (c[j] - pos["price"]) * mult; worst_arr[j] = cash + (l[j] - pos["price"]) * mult
    sl = slice(first, None); cash_s = pd.Series(cash_arr[sl]).ffill().fillna(INITIAL_BALANCE)
    eq_s = pd.Series(eq_arr[sl]); eq_s = eq_s.where(eq_s.notna(), cash_s); worst_s = pd.Series(worst_arr[sl]); worst_s = worst_s.where(worst_s.notna(), cash_s)
    curve = pd.DataFrame(dict(ts=b.timestamp_utc[sl].to_numpy(), cash=cash_s.to_numpy(), equity=eq_s.to_numpy(), worst=worst_s.to_numpy()))
    position = dict(quantity=1 if pos is not None else 0, unrealized=round(float(eq_s.iloc[-1] - cash_s.iloc[-1]), 2) if len(eq_s) else 0.0, last_close=float(c[-1]) if len(c) else None)
    peak = pd.Series(eq_s).cummax()
    return dict(trades=trades, curve=curve, position=position, lock=None, open_since=b.timestamp_utc[pos["i"]].isoformat() if pos is not None else None,
                entry_bars=entry_bars, funded_failed=bool(((peak - worst_s).max()) > FUNDED_DRAWDOWN) if len(eq_s) else False)


def live_early_close(data, bars):
    """apply_early_close() for a live, still-running day. The research helper treats any trade date whose last regular bar is before 15:00 ET as an
    early close and relabels that bar as the 15:55 flatten bar; on the day in progress that is simply the latest bar, which would force every open
    position flat at the newest bar (seen 2026-11-09: MES longs 'session_exit' at 11:30 ET). For the last trade date, if it is not a calendar early
    close and the data ends before 16:00 ET, keep the plain ET minutes."""
    out = apply_early_close(data, bars)
    if len(bars) == 0: return out
    ts = pd.DatetimeIndex(bars.timestamp_utc).tz_convert("America/New_York"); last = ts[-1]
    if last.date() in early_close_dates(last.year) or (last.hour * 60 + last.minute) >= 960: return out
    sel = np.asarray(ts.date) == last.date()
    out["minute"] = np.ascontiguousarray(np.where(sel, np.asarray(data["minute"]), out["minute"]))
    return out


def run_sleeve(cfg, bars, start, blocked=None):
    """Exact research-engine run of one sleeve; execution starts at ``start``. ``blocked`` masks signals (router)."""
    eng = engine()
    data = live_early_close(eng["arrays"](bars), bars)
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    weekdays = local.dt.day_of_week.to_numpy() < 5
    exec_cfg = eng["execution_cfg"](cfg)
    if cfg.get("risk_per_trade"):  # sizing_1: candidates that always take one contract regardless of stop risk
        exec_cfg.update(risk_per_trade=float(cfg["risk_per_trade"]), max_open_risk=float(cfg.get("max_open_risk", cfg["risk_per_trade"])))
    if cfg.get("signal"):
        raw, atr = custom_signal(cfg, bars)
        mask = weekdays  # entry window enforced by the engine via entry_start/entry_end, as in the replication scripts
        exec_cfg.update(entry_start=cfg["entry_start"], entry_end=cfg["entry_end"], flat_minute=955, max_gap_minutes=cfg["max_gap_minutes"])
    else:
        features = eng["features"](bars, int(cfg["lookback"]))
        raw = eng["signal_for"](cfg, features).astype(np.int8)
        atr = features["atr"]
        decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
        mask = (decision >= cfg["session_start"]) & (decision < cfg["session_end"]) & weekdays
    if blocked is not None:
        mask = mask & ~blocked
    signal = np.where(mask, raw, 0).astype(np.int8)
    first = int((bars.timestamp_utc < pd.Timestamp(start)).sum())
    sliced = {k: np.ascontiguousarray(v[first:]) for k, v in data.items()}
    sliced["session"] = pd.factorize(sliced["session"], sort=False)[0].astype(np.int64)
    sliced["contract"] = pd.factorize(sliced["contract"], sort=False)[0].astype(np.int64)
    result = eng["execute"](sliced, signal[first:], np.ascontiguousarray(atr[first:]), exec_cfg)
    stamps = pd.to_datetime(sliced["timestamp"], unit="ns", utc=True)
    trades = []
    entry_bars = [first + int(result["trade_entry"][i]) for i in range(len(result["trade_entry"]))]
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
    open_since = None
    if position["quantity"]:
        held = np.flatnonzero(result["quantity"] != 0)
        run_start = held[-1]
        while run_start > 0 and result["quantity"][run_start - 1] != 0:
            run_start -= 1
        open_since = stamps[int(run_start)].isoformat()
    # The research engine closes any position still open on the final bar ("terminal_close"). Live, the final bar is just the newest bar, so
    # that trade is not closed: report it as the open position (marked at the last close, exit costs included) instead of a ledgered trade.
    terminal = [t for t in trades if t["reason"] == "terminal_close"]
    if terminal:
        t = terminal[-1]; trades = [x for x in trades if x["reason"] != "terminal_close"]
        position = dict(quantity=int(t["side"] * t["qty"]), unrealized=float(t["net"]), last_close=position["last_close"])
        open_since = t["entry_ts"]
        curve["cash"] = curve["cash"] - float(t["net"]) * (curve["ts"] >= pd.Timestamp(t["exit_ts"])).to_numpy()
    return dict(trades=trades, curve=curve, position=position, lock=result["lock_reason"], open_since=open_since, entry_bars=entry_bars,
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

    runs = run_routed(spec, bars, start)
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
                      bars_through={k: v.timestamp_utc.max().isoformat() for k, v in bars.items() if k in {bars_key(s) for s in spec["sleeves"]}},
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
    status = dict(candidate=key, version=spec["version"], label=spec["label"], provenance=spec["provenance"], category=spec.get("category", "current"), family=family_of(key),
                  updated=now.isoformat(), source=source_name, start=run_record["start"], bars_through=run_record["bars_through"],
                  net=portfolio["net"], realized=portfolio["realized"], unrealized=round(portfolio["net"] - portfolio["realized"], 2),
                  closed_drawdown=portfolio["closed_drawdown"], intrabar_drawdown=portfolio["intrabar_drawdown"],
                  funded_buffer=round(FUNDED_DRAWDOWN - portfolio["intrabar_drawdown"], 2), trades=len(trades),
                  wins=sum(1 for t in trades if t["net"] > 0), fees=round(sum(t["fees"] for t in trades), 2),
                  positions=run_record["positions"], locks=run_record["locks"], funded_failed=run_record["funded_failed"],
                  divergences=total_divergences, last_trades=trades[-5:],
                  engine_sha256=run_record["engine_sha256"],
                  bar_minutes=sorted({int(s.get("bar_minutes", BAR_MINUTES)) for s in spec["sleeves"]}),
                  disclaimer="Simulated fills on 15m/30m/60m bars from a delayed public continuous series; no orders are routed anywhere.")
    (folder / "status.json").write_text(json.dumps(status, indent=1, sort_keys=True))
    equity = portfolio["equity"].copy()
    equity["ts"] = equity.ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    equity.iloc[-min(len(equity), 2000):].to_csv(folder / "equity.csv", index=False)
    return status


def vol_regime(now=None):
    """Prior-close VIX / VIX3M read-out (yfinance ^VIX, ^VIX3M daily). Informational only: research/extstate_1 found the
    trend/breakout sleeves earned on backwardation (stress) days and were no better than random on contango days."""
    try:
        import yfinance as yf
        rows = {}
        for key, symbol in (("vix", "^VIX"), ("vix3m", "^VIX3M")):
            history = yf.Ticker(symbol).history(period="1y", interval="1d", auto_adjust=False)
            close = history["Close"].dropna()
            close.index = pd.to_datetime(close.index.strftime("%Y-%m-%d"))  # ^VIX/^VIX3M come back in different tz offsets
            rows[key] = close
        joined = pd.concat([rows["vix"].rename("vix"), rows["vix3m"].rename("vix3m")], axis=1).dropna()
        if len(joined) == 0:
            return dict(error="no VIX data")
        last = joined.iloc[-1]
        slope = float(last.vix3m / last.vix - 1)
        rank = float((joined.vix <= last.vix).mean())
        return dict(as_of=str(joined.index[-1].date()), vix=round(float(last.vix), 2), vix3m=round(float(last.vix3m), 2),
                    slope=round(slope, 4), state="backwardation (stress)" if slope < 0 else "contango (calm)",
                    vix_rank_1y=round(rank, 2), note="sleeves historically earned on backwardation days; flat-to-negative vs random in contango (extstate_1)")
    except Exception as exc:  # never let the read-out break the paper run
        return dict(error=str(exc)[:200])


def run_once(root, source, start, now=None, candidates=None):
    now = now or utc_now()
    root = Path(root)
    report = ingest(root / "bars", source, now); _VIX_CACHE["path"] = str(root / "bars" / "vix_daily.csv"); _VIX_CACHE["series"] = None
    _SKEW_CACHE["path"] = str(root / "bars" / "skew_daily.csv"); _SKEW_CACHE["series"] = None
    _ZN_CACHE["path"] = str(root / "bars" / "zn_daily.csv"); _ZN_CACHE["series"] = None
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
    bars["MNQ@1"] = stored["MNQ"]; bars["MES@1"] = stored["MES"]
    for key, spec in CANDIDATES.items():
        for sleeve in spec["sleeves"]:
            bk = bars_key(sleeve)
            if bk in bars:
                continue
            frame = aggregate(stored[sleeve["instrument"]], int(sleeve["bar_minutes"]))
            warm = frame[frame.timestamp_utc < start_ts].tail(WARMUP_BARS * BAR_MINUTES // int(sleeve["bar_minutes"]))
            live = frame[frame.timestamp_utc >= start_ts]
            bars[bk] = canonical_bars(pd.concat([warm, live]), sleeve["instrument"], YAHOO_SYMBOLS[sleeve["instrument"]])
    statuses = {}
    for key, spec in CANDIDATES.items():
        if (candidates and key not in candidates) or spec.get("hidden"):
            continue
        statuses[key] = update_candidate(root, key, spec, bars, start_ts, now, source.name)
    summary = dict(updated=now.isoformat(), ingest=report, start=start_ts.isoformat(), source=source.name,
                   candidates=statuses, total_net=round(sum(s["net"] for s in statuses.values() if s.get("category", "current") == "current"), 2),
                   future_net=round(sum(s["net"] for s in statuses.values() if s.get("category") == "future"), 2), regime=vol_regime(now))
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
