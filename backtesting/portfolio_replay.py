"""Joint ETH v1.11 + BNB crypto_v0_1 account replay against Breakout 50k rules (reporting only).

Adds the two frozen historical equity paths (each simulated alone at $100 risk) after scaling
each by risk/100, on one $50k balance, 2024-01-01 .. 2026-10-28. Nothing is re-selected:
ETH's path is the funded_replay curve, BNB's is the round-1 validation + held-out curve.
Limits: BNB marks are 5-minute closes (no intrabar worst), so BNB drawdown is understated
by at most one bar's range; ETH 2024-26 is in-sample for v1.11; margin interaction between
the two positions is not modeled (both are far below 5x leverage limits at these sizes).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .paths import ROOT

START, END = '2024-01-01', '2026-10-28'
FLOOR, TARGET, DAILY = 3000., 5000., 1500.
ETH_CURVE = ROOT/'artifacts/funded_accounts/v1_11_breakout_50k/curve_risk100.parquet'
BNB_CURVES = [ROOT/'artifacts/crypto_research/crypto_round1/validation/BNB/time_series_momentum_4h_patient/equity.parquet',
              ROOT/'artifacts/crypto_research/crypto_round1/test/test_full/fill8/equity.parquet']


def pnl_path(frames, column):
    """Cumulative P&L per 5-minute mark on the shared grid (each frame restarts at $50k)."""
    pieces, offset = [], 0.
    for frame in frames:
        p = frame[column].to_numpy(dtype=float)-50000.
        pieces.append(pd.Series(p+offset, index=pd.DatetimeIndex(frame.timestamp)))
        offset += p[-1]
    series = pd.concat(pieces)
    series = series[(series.index >= pd.Timestamp(START, tz='UTC')) & (series.index < pd.Timestamp(END, tz='UTC')+pd.Timedelta(minutes=5))]
    return series-series.iloc[0]


def load():
    eth = pd.read_parquet(ETH_CURVE)
    bnb = [pd.read_parquet(p) for p in BNB_CURVES]
    eth_worst = pnl_path([eth], 'intrabar_worst_equity')
    eth_close = pnl_path([eth], 'equity')
    bnb_close = pnl_path(bnb, 'equity')
    grid = eth_close.index.intersection(bnb_close.index)
    if len(grid) < .99*len(bnb_close):
        raise ValueError('ETH and BNB grids do not overlap')
    return eth_close.reindex(grid), eth_worst.reindex(grid), bnb_close.reindex(grid)


def stats(path, worst):
    """path: close-marked cumulative P&L; worst: intrabar-worst cumulative P&L (same index)."""
    peak = np.maximum.accumulate(path.to_numpy())
    drawdown = float((peak-worst.to_numpy()).max())
    daily = path.resample('1D').last().diff().dropna()
    monthly = path.resample('MS').last().diff().dropna()
    # Breakout static floor: $3k below the START balance, checked on intrabar worst marks.
    breach_from_start = bool((worst.to_numpy() <= -FLOOR).any())
    # From every monthly start, days until +$5k on close marks (None if never) and whether the floor was hit first.
    months, hits, breaches, worst_from_start = [], [], 0, 0.
    for when in pd.date_range(START, '2026-05-01', freq='MS', tz='UTC'):
        rel = path[path.index >= when]
        base = rel.iloc[0]
        rel_worst = worst[worst.index >= when]
        worst_from_start = max(worst_from_start, float(base-rel_worst.min()))
        hit = rel[rel-base >= TARGET]
        fail = rel_worst[rel_worst-base <= -FLOOR]
        first_hit = hit.index[0] if len(hit) else None
        first_fail = fail.index[0] if len(fail) else None
        if first_fail is not None and (first_hit is None or first_fail < first_hit):
            breaches += 1
        elif first_hit is not None:
            hits.append((first_hit-when).days/30.4)
        months.append(when)
    return dict(net=float(path.iloc[-1]), worst_drawdown=drawdown, worst_loss_from_any_start=worst_from_start, worst_day=float(-daily.min()), daily_breaches=int((daily <= -DAILY).sum()),
                floor_breach_from_start=breach_from_start, starts=len(months), starts_breached=breaches, starts_reached_target=len(hits),
                median_months_to_target=float(np.median(hits)) if hits else None, monthly=monthly)


def main():
    eth_close, eth_worst, bnb_close = load()
    rows = []
    corr = float(eth_close.resample('MS').last().diff().corr(bnb_close.resample('MS').last().diff()))
    for eth_risk in [0., 100., 150.]:
        for bnb_risk in [0., 100., 150., 200., 250., 300.]:
            if eth_risk == 0. and bnb_risk == 0.:
                continue
            close = eth_close*eth_risk/100.+bnb_close*bnb_risk/100.
            worst = eth_worst*eth_risk/100.+bnb_close*bnb_risk/100.
            s = stats(close, worst)
            rows.append(dict(eth_risk=eth_risk, bnb_risk=bnb_risk, **{k: v for k, v in s.items() if k != 'monthly'}))
    table = pd.DataFrame(rows)
    lines = ['# ETH v1.11 + BNB crypto_v0_1 joint replay, Breakout 50k rules, 2024-01-01 .. 2026-10-28', '',
             'Historical equity paths added on one balance (reporting only; see module docstring for limits). '
             f'Monthly P&L correlation ETH vs BNB: {corr:+.2f}.', '',
             '| ETH risk | BNB risk | Net 34 mo | Worst peak-to-trough | Worst loss from any monthly start | Worst day | Monthly starts breached / reached $5k (of n) | Median months to $5k |',
             '|---|---|---|---|---|---|---|---|']
    for r in rows:
        med = f"{r['median_months_to_target']:.1f}" if r['median_months_to_target'] is not None else 'never'
        lines.append(f"| ${r['eth_risk']:.0f} | ${r['bnb_risk']:.0f} | ${r['net']:,.0f} | ${r['worst_drawdown']:,.0f} | ${r['worst_loss_from_any_start']:,.0f} | ${r['worst_day']:,.0f} | "
                     f"{r['starts_breached']} / {r['starts_reached_target']} (of {r['starts']}) | {med} |")
    out = ROOT/'reports/eth_bnb_joint_replay.md'
    out.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    table.to_csv(ROOT/'artifacts/funded_accounts/eth_bnb_joint_replay.csv', index=False)
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
