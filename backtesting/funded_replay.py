"""Historical funded-account scenarios on frozen ETH v1.11 trade paths.

Replays fixed dollar sizing, not live outcomes or independent probability trials.
Challenge promotion is checked only when flat, then a fresh funded balance starts.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from . import alternative_strategies
from .engine import Broker
from .generalization_policy import assert_historical_period
from .market_data import BAR, load_history, utc
from .numbered_profiles import load_profile
from .paths import PARQUET, ROOT
from .regime_filters import RegimeFilter, apply_filter, prepare_features


def observed_curve(bars, rule, cfg, signals):
    """Observe every broker mark, including adverse intrabar marks, without edits."""
    records = []

    class ObservedBroker(Broker):
        current = None

        def bar(self, row):
            self.current = row
            super().bar(row)

        def mark(self, price):
            super().mark(price)
            if self.current is None:
                return
            timestamp = self.current.timestamp + BAR
            value = self.equity_at(price)
            if not records or records[-1]['timestamp'] != timestamp:
                records.append(dict(timestamp=timestamp, intrabar_worst_equity=value))
            record = records[-1]
            record['intrabar_worst_equity'] = min(record['intrabar_worst_equity'], value)
            record.update(cash=self.cash, equity=value,
                          position_qty=self.position.direction*self.position.quantity if self.position else 0.)

    with patch.object(alternative_strategies, 'Broker', ObservedBroker):
        metrics, trades, events = alternative_strategies.simulate(bars, rule, cfg, signals=signals)
    curve = pd.DataFrame(records)
    if len(curve) != len(bars) or abs(curve.equity.iloc[-1]-metrics['final_equity']) > 1e-6:
        raise ValueError('Observed broker curve failed reconciliation')
    return curve, metrics, trades, events


class AccountReplay:
    def __init__(self, curve, capital=50000., target=.10, drawdown=.06, daily=.03, share=.90):
        if not (capital > 0 and 0 < target < 1 and 0 < drawdown < 1 and 0 < daily < 1 and 0 < share <= 1):
            raise ValueError('Invalid account assumptions')
        self.curve = curve.reset_index(drop=True)
        self.times = pd.DatetimeIndex(curve.timestamp).as_unit('ns')
        if not self.times.is_monotonic_increasing or self.times.has_duplicates:
            raise ValueError('Curve timestamps must be unique and ordered')
        if len(curve) > 1 and not np.all(np.diff(self.times.asi8) == BAR.value):
            raise ValueError('Account replay requires gap-free five-minute observations')
        self.cash = curve.cash.to_numpy(dtype=float)
        self.worst = curve.intrabar_worst_equity.to_numpy(dtype=float)
        self.flat = np.isclose(curve.position_qty.to_numpy(dtype=float), 0., atol=1e-12)
        if not np.isfinite(self.cash).all() or not np.isfinite(self.worst).all():
            raise ValueError('Account curve must be finite')
        self.capital, self.target, self.floor = capital, capital*target, capital*(1-drawdown)
        self.daily, self.share = daily, share
        # A row ending at 00:30 belongs to the OLD daily floor. Its final cash
        # sets the floor for the NEXT bar, whose open is 00:30 UTC.
        reset = np.where((self.times.hour == 0) & (self.times.minute == 30), np.arange(len(curve)), -1)
        self.reset = np.r_[-1, np.maximum.accumulate(reset)[:-1]]

    def stage(self, start, stop, *, funded=False):
        """Return pass/fail/payout events for a fresh balance at this flat boundary."""
        base = self.cash[start-1] if start else self.capital
        paid_indices, paid_totals, payouts = [], [], []
        total = 0.
        cursor = start
        while cursor < stop:
            indices = np.arange(cursor, stop)
            reset = self.reset[cursor:stop]
            valid_reset = reset >= start
            paid_at_reset = np.zeros(len(indices))
            if paid_indices:
                previous = np.searchsorted(paid_indices, reset, side='right')-1
                mask = previous >= 0
                paid_at_reset[mask] = np.asarray(paid_totals)[previous[mask]]
            day_balance = np.full(len(indices), self.capital, dtype=float)
            day_balance[valid_reset] += self.cash[reset[valid_reset]]-base-paid_at_reset[valid_reset]
            # Withdrawals lower today's daily floor by the FULL gross debit.
            daily_floor = day_balance*(1-self.daily)-(total-paid_at_reset)
            equity_low = self.capital+self.worst[cursor:stop]-base-total
            breached = (equity_low <= self.floor) | (equity_low <= daily_floor)
            failures = np.flatnonzero(breached)
            failure = cursor+int(failures[0]) if len(failures) else stop
            profit = self.cash[cursor:stop]-base-total
            checkpoint = self.flat[cursor:stop] & (profit*self.share >= 50. if funded else profit >= self.target)
            hits = np.flatnonzero(checkpoint)
            hit = cursor+int(hits[0]) if len(hits) else stop
            # Breach wins ties: a flat close cannot erase an earlier intrabar breach.
            if failure <= hit and failure < stop:
                return dict(status='breached', index=failure, payouts=payouts)
            if hit == stop:
                return dict(status='unfinished' if not funded else 'active', index=None, payouts=payouts)
            if not funded:
                return dict(status='passed', index=hit, payouts=[])
            gross = self.cash[hit]-base-total
            payouts.append(dict(timestamp=str(self.times[hit]), gross_debit=float(gross), trader_amount=float(gross*self.share)))
            total += gross
            paid_indices.append(hit)
            paid_totals.append(total)
            cursor = hit+1
        return dict(status='active' if funded else 'unfinished', index=None, payouts=payouts)

    def trial(self, when, days, *, already_funded=False):
        when = utc(when)
        end = when+pd.Timedelta(days=days)
        if end > self.times[-1]:
            raise ValueError('Incomplete observation horizon')
        start = int(self.times.searchsorted(when+BAR))
        stop = int(self.times.searchsorted(end, side='right'))
        # Do not inherit a trade entered before the requested account start.
        while start < stop and start > 0 and not self.flat[start-1]:
            start += 1
        if start >= stop:
            raise ValueError('No flat account boundary in this horizon')
        evaluation = None if already_funded else self.stage(start, stop)
        passed = evaluation is not None and evaluation['status'] == 'passed'
        funded_start = start if already_funded else evaluation['index']+1 if passed else stop
        funded = self.stage(funded_start, stop, funded=True) if funded_start < stop else None
        payouts = funded['payouts'] if funded else []
        return dict(start=str(when), actual_start=str(self.times[start]-BAR), days=days,
                    already_funded=already_funded, passed=passed,
                    evaluation_status=evaluation['status'] if evaluation else None,
                    pass_time=str(self.times[evaluation['index']]) if passed else None,
                    days_to_pass=float((self.times[evaluation['index']]-when)/pd.Timedelta(days=1)) if passed else None,
                    funded_status=funded['status'] if funded else None,
                    payout_count=len(payouts), trader_payout=sum(p['trader_amount'] for p in payouts),
                    first_payout=payouts[0]['timestamp'] if payouts else None, payouts=payouts)


def summarize(rows):
    frame = pd.DataFrame(rows)
    output = []
    for (risk, days, funded), group in frame.groupby(['risk_usd', 'days', 'already_funded']):
        paid = group.payout_count > 0
        output.append(dict(risk_usd=float(risk), days=int(days), already_funded=bool(funded),
                           trials=len(group), passes=int(group.passed.sum()),
                           evaluation_breaches=int(group.evaluation_status.eq('breached').sum()),
                           unfinished=int(group.evaluation_status.eq('unfinished').sum()),
                           accounts_with_payout=int(paid.sum()), funded_breaches=int(group.funded_status.eq('breached').sum()),
                           median_days_to_pass=float(group.days_to_pass.dropna().median()) if group.passed.any() else None,
                           median_payout_all_starts=float(group.trader_payout.median()),
                           median_payout_paid_starts=float(group.loc[paid, 'trader_payout'].median()) if paid.any() else None,
                           median_payout_count_all_starts=float(group.payout_count.median())))
    return output


def main():
    directory = ROOT/'artifacts/funded_accounts/v1_11_breakout_50k'
    directory.mkdir(parents=True, exist_ok=True)
    rule, config, metadata, _ = load_profile(version='v1.11')
    bars, _ = load_history(PARQUET)
    bars = bars[bars.timestamp < utc('2026-10-28')].reset_index(drop=True)
    assert_historical_period(bars.timestamp.max()+BAR)
    signals = apply_filter(prepare_features(bars, rule), RegimeFilter(**metadata['entry_filters']))
    rows, reference = [], []
    for risk in [100., 150.]:
        cfg = replace(config, risk_usd=risk)
        curve, metrics, trades, events = observed_curve(bars, rule, cfg, signals)
        if risk == 100. and abs(metrics['final_equity']-50000.-metadata['same_period_net_usd']) > 1e-6:
            raise ValueError('Frozen v1.11 saved reference did not reproduce')
        curve.to_parquet(directory/f'curve_risk{risk:g}.parquet', index=False)
        trades.to_csv(directory/f'trades_risk{risk:g}.csv', index=False)
        events.to_csv(directory/f'events_risk{risk:g}.csv', index=False)
        account = AccountReplay(curve)
        for days in [90, 180, 365, 730]:
            for when in pd.date_range('2023-01-01', '2026-10-01', freq='MS', tz='UTC'):
                if when+pd.Timedelta(days=days) > curve.timestamp.iloc[-1]:
                    continue
                for funded in [False, True]:
                    rows.append(dict(risk_usd=risk, **account.trial(when, days, already_funded=funded)))
        reference.append(dict(risk_usd=risk, metrics=metrics,
                              from_first_date=account.trial('2023-01-01', 1396),
                              already_funded_from_first_date=account.trial('2023-01-01', 1396, already_funded=True)))
        print(f'Completed risk ${risk:g}: {metrics["entries"]} entries; final equity ${metrics["final_equity"]:.2f}', flush=True)
    summary = summarize(rows)
    payload = dict(strategy='ETH v1.11', firm='Breakout', assumed_plan='1-Step Classic',
                   capital=50000, target=.10, static_drawdown=.06, daily_loss=.03, reset_utc='00:30',
                   profit_share=.90, minimum_trader_payout=50.,
                   period=['2023-01-01', '2026-10-28'], configuration_sha256=metadata['configuration_sha256'],
                   data_sha256=hashlib.sha256(PARQUET.read_bytes()).hexdigest(),
                   source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   assumptions=['Fixed historical trade paths and dollar risk; not a per-start strategy rerun.',
                                'Promotion checked at flat closes only; actual equity-target promotion can occur earlier intratrade.',
                                'Fresh $50k funded balance from next bar after promotion; evaluation profit is not paid.',
                                'Withdraw all eligible gross profit at every flat checkpoint; gross debit includes firm share.',
                                'Intrabar modeled lows checked before flat pass/payout; exact ticks are unavailable.',
                                'At account starts, wait until inherited historical position is flat.',
                                'Same $300 personal strategy daily gate in both risk scenarios.',
                                'No KYC/activation delay; evaluation fees, taxes, network charges excluded.',
                                'Monthly starts overlap, are correlated, and use already selected historical data.',
                                'Observed frequencies are not estimates of independent future success probabilities.'],
                   sources=['https://www.breakoutprop.com/program-rules/',
                            'https://intercom.help/breakoutprop/en/articles/11647189-what-is-the-maximum-daily-loss-in-a-funded-account',
                            'https://intercom.help/breakoutprop/en/articles/11647224-when-can-i-request-a-payout-from-my-funded-account',
                            'https://intercom.help/breakoutprop/en/articles/11647212-do-payouts-affect-my-maximum-daily-loss-limit'],
                   summary=summary, reference=reference)
    (directory/'results.json').write_text(json.dumps(payload, indent=2, default=str, allow_nan=False), encoding='utf-8')
    pd.DataFrame([{k: v for k, v in row.items() if k != 'payouts'} for row in rows]).to_csv(directory/'monthly_starts.csv', index=False)
    lines = ['# ETH v1.11: Breakout $50k Classic, 90/10 historical account replay', '',
             'Period: January 1, 2023 to October 28, 2026 exclusive. Current rules applied retrospectively; this does not claim these plans existed throughout the period.', '',
             'Assumed Classic plan: $5,000 target, $47,000 static equity floor, 3% daily loss from balance at 00:30 UTC. Minimum trader payout $50 after the 90% split. Other Breakout plans have different targets/floors.', '',
             'Each row tests a new account at each calendar-month start with a COMPLETE observation horizon. No timeout is imposed by the firm: unfinished below means this research horizon ended. Median days to pass includes successful starts only.', '',
             '| Planned risk | Horizon | Starts | Passed eval | Eval breached | Still in eval | Passed AND later paid | Median days to pass | Median trader payout, all starts |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in summary:
        if row['already_funded']:
            continue
        n = row['trials']
        duration = f"{row['median_days_to_pass']:.0f}" if row['median_days_to_pass'] is not None else '-'
        lines.append(f"| ${row['risk_usd']:g} | {row['days']} days | {n} | {row['passes']} ({row['passes']/n:.1%}) | {row['evaluation_breaches']} | {row['unfinished']} | {row['accounts_with_payout']} ({row['accounts_with_payout']/n:.1%}) | {duration} | ${row['median_payout_all_starts']:,.2f} |")
    lines += ['', '## Starting already funded (no evaluation)', '',
              '| Risk | Horizon | Starts | At least one payout | Funded breaches | Median payout count | Median total trader payout |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in summary:
        if row['already_funded']:
            n = row['trials']
            lines.append(f"| ${row['risk_usd']:g} | {row['days']} days | {n} | {row['accounts_with_payout']} ({row['accounts_with_payout']/n:.1%}) | {row['funded_breaches']} | {row['median_payout_count_all_starts']:g} | ${row['median_payout_all_starts']:,.2f} |")
    lines += ['', '## Assumptions and limits', '']+[f'- {x}' for x in payload['assumptions']]
    lines += ['', 'Execution: next-open entries; 4bp fee each side; two ticks plus 2bp adverse market/stop slippage; 3.3bp/day financing. All historical data participated in strategy selection. No strategy parameters were optimized here. Frozen profiles and future validation window remain unchanged.', '',
              '## Rules checked November 3, 2026', '']+[f'- {url}' for url in payload['sources']]
    text = '\n'.join(lines)+'\n'
    (directory/'report.md').write_text(text, encoding='utf-8')
    (ROOT/'reports/v1_11_breakout_50k_pass_payout.md').write_text(text, encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
