"""Cushion-scaled risk on the frozen ETH v1.11 + BNB crypto_v0_1 paths (reporting only).

Breakout's $3,000 drawdown is static (floor fixed at $47k), so profit already banked is a
cushion that can never be re-charged. A pre-stated mechanical rule raises risk per trade in
steps as the cushion grows and lowers it again if the cushion shrinks. Risk only changes while
that sleeve is flat (a trade keeps the size it was opened with). No parameter here was chosen by
looking at outcomes; the step rules are listed in RULES and all are reported.
Limits are those of portfolio_replay (BNB marks are closes; ETH 2024-26 is in-sample).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .paths import ROOT
from .portfolio_replay import BNB_CURVES, END, ETH_CURVE, FLOOR, START, TARGET, load, pnl_path

BASE = dict(eth=100., bnb=200.)
# name -> (cushion step $, size increase per step as fraction of base, cap as multiple of base)
RULES = {'fixed (no scaling)': (None, 0., 1.),
         '+50% per $1,500 cushion, cap 2x': (1500., .5, 2.),
         '+50% per $1,500 cushion, cap 3x': (1500., .5, 3.),
         '+25% per $1,000 cushion, cap 3x': (1000., .25, 3.),
         '+100% per $3,000 cushion, cap 3x': (3000., 1., 3.)}


def positions():
    eth = pd.read_parquet(ETH_CURVE)
    bnb = [pd.read_parquet(p) for p in BNB_CURVES]
    e = pd.Series(eth.position_qty.to_numpy(), index=pd.DatetimeIndex(eth.timestamp))
    b = pd.concat([pd.Series(f.position_qty.to_numpy(), index=pd.DatetimeIndex(f.timestamp)) for f in bnb])
    return e, b


def multiplier(cushion, rule):
    step, gain, cap = rule
    if step is None:
        return 1.
    return float(min(cap, 1.+gain*np.floor(max(cushion, 0.)/step)))


def replay(start_index, d_eth, eth_worst_rel, d_bnb, eth_flat, bnb_flat, rule):
    """Scaled close P&L and intrabar-worst P&L from start_index onward; returns (close, worst) arrays."""
    n = len(d_eth)-start_index
    close, worst = np.empty(n), np.empty(n)
    acc = 0.
    m_eth, m_bnb = BASE['eth']/100., BASE['bnb']/100.
    for k in range(n):
        i = start_index+k
        if eth_flat[i]:
            m_eth = BASE['eth']/100.*multiplier(acc, rule)
        if bnb_flat[i]:
            m_bnb = BASE['bnb']/100.*multiplier(acc, rule)
        worst[k] = acc+m_eth*eth_worst_rel[i]+m_bnb*min(d_bnb[i], 0.)
        acc += m_eth*d_eth[i]+m_bnb*d_bnb[i]
        close[k] = acc
    return close, worst


def main():
    eth_close, eth_worst, bnb_close = load()
    e_pos, b_pos = positions()
    grid = eth_close.index
    eth_flat = np.isclose(e_pos.reindex(grid).fillna(0.).to_numpy(), 0.)
    bnb_flat = np.isclose(b_pos.reindex(grid).fillna(0.).to_numpy(), 0.)
    d_eth = eth_close.diff().fillna(0.).to_numpy()
    d_bnb = bnb_close.diff().fillna(0.).to_numpy()
    eth_worst_rel = np.minimum(eth_worst.to_numpy()-eth_close.shift().fillna(0.).to_numpy(), 0.)
    starts = pd.date_range(START, '2026-05-01', freq='MS', tz='UTC')
    start_idx = [int(grid.searchsorted(s)) for s in starts]
    rows = []
    for name, rule in RULES.items():
        hits, breaches, worst_loss, twelve = [], 0, 0., []
        full_net = None
        for s, i0 in zip(starts, start_idx):
            close, worst = replay(i0, d_eth, eth_worst_rel, d_bnb, eth_flat, bnb_flat, rule)
            worst_loss = max(worst_loss, float(-worst.min()))
            hit = np.flatnonzero(close >= TARGET)
            fail = np.flatnonzero(worst <= -FLOOR)
            first_hit = hit[0] if len(hit) else None
            first_fail = fail[0] if len(fail) else None
            if first_fail is not None and (first_hit is None or first_fail < first_hit):
                breaches += 1
            elif first_hit is not None:
                hits.append((grid[i0+first_hit]-s).days/30.4)
            year = int(grid.searchsorted(s+pd.DateOffset(years=1)))-i0
            if year < len(close):
                twelve.append(float(close[year-1]))
            if s == starts[0]:
                full_net = float(close[-1])
        rows.append(dict(rule=name, net_from_jan_2024=full_net, median_12m_net=float(np.median(twelve)), worst_loss_from_any_start=worst_loss,
                         starts=len(starts), breached=breaches, reached=len(hits), median_months=float(np.median(hits)) if hits else None))
    lines = [f'# Cushion-scaled risk, ETH v1.11 ${BASE["eth"]:.0f} + BNB crypto_v0_1 ${BASE["bnb"]:.0f} base, Breakout 50k static floor, {START} .. {END}', '',
             'Risk per trade = base x multiplier(cushion), cushion = closed P&L above the starting balance; multiplier re-evaluated only while that sleeve is flat. '
             'Reporting only; see module docstring.', '',
             '| Rule | Net from Jan-2024 | Median 12-month net (all starts) | Worst loss from any start | Starts breached / reached $5k (of n) | Median months to $5k |',
             '|---|---|---|---|---|---|']
    for r in rows:
        med = f"{r['median_months']:.1f}" if r['median_months'] is not None else 'never'
        lines.append(f"| {r['rule']} | ${r['net_from_jan_2024']:,.0f} | ${r['median_12m_net']:,.0f} | ${r['worst_loss_from_any_start']:,.0f} | "
                     f"{r['breached']} / {r['reached']} (of {r['starts']}) | {med} |")
    (ROOT/'reports/eth_bnb_cushion_scaling.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    pd.DataFrame(rows).to_csv(ROOT/'artifacts/funded_accounts/eth_bnb_cushion_scaling.csv', index=False)
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
