"""Post-run artifact accounting; does not alter strategies, selection or registry."""
from __future__ import annotations

import json
import math
import numpy as np
import pandas as pd

from ..analytics import daily_returns, metric_extras
from ..data_pipeline import HERE, sha


def audit():
    limit = pd.Timestamp(json.loads((HERE/'split_manifest.json').read_text())['nominal_final'][0])
    registry = pd.read_csv(HERE/'experiment_registry.csv')
    if registry.trial_key.duplicated().any():
        raise ValueError('Registry contains duplicate replay identities')
    rows, calendar = [], []
    for trial in registry.itertuples(index=False):
        folder = HERE/'outputs'/trial.trial_key
        payload = json.loads((folder/'result.json').read_text())
        metrics = payload['metrics']
        curve = pd.read_parquet(folder/'equity.parquet')
        trades = pd.read_parquet(folder/'trades.parquet')
        if curve.timestamp.max() > limit or pd.Timestamp(trial.end) > limit:
            raise ValueError('Contaminated final observation entered an experiment')
        initial = metrics['initial_capital']
        if metrics['open_position'] is None and abs(trades.net_pnl.sum()-(curve.equity.iloc[-1]-initial)) > 1e-6:
            raise ValueError('Trade ledger failed independent cash reconciliation')
        if (curve.intrabar_worst_equity-curve.equity > 1e-6).any():
            raise ValueError('Intrabar equity bound exceeds close equity')
        extra = metric_extras(dict(metrics=metrics, equity=curve, trades=trades))
        for frequency in ['monthly', 'quarterly', 'yearly']:
            for record in extra[frequency]:
                calendar.append(dict(trial_key=trial.trial_key, phase=trial.phase, symbol=trial.symbol,
                                     strategy_id=trial.strategy_id, frequency=frequency, **record))
        returns = daily_returns(curve, initial)
        std = returns.std(ddof=1)
        downside = np.sqrt(np.mean(np.minimum(returns,0.)**2))
        corrected = dict(annualized_volatility=float(std*np.sqrt(365.25)) if pd.notna(std) else None,
                         sharpe=float(returns.mean()/std*np.sqrt(365.25)) if std > 0 else None,
                         sortino=float(returns.mean()/downside*np.sqrt(365.25)) if downside > 0 else None,
                         sampling='365.25 calendar days; midnight-ending candle belongs to bar-open date')
        # Original engine's volatility/Sortino used close-date ownership; this
        # companion is the calendar-correct attribution, without changing frozen
        # search metrics. Runner already used corrected daily Sharpe for ranking.
        extra['calendar_correct_metrics'] = corrected
        extra.pop('daily', None)  # Full daily series is already daily_returns.csv.
        (folder/'attribution.json').write_text(json.dumps(extra, indent=2, default=str, allow_nan=False)+'\n', encoding='utf-8')
        rows.append(dict(trial_key=trial.trial_key, phase=trial.phase, symbol=trial.symbol,
                         strategy_id=trial.strategy_id, timeframe=trial.timeframe, **corrected,
                         final_equity=metrics['final_equity'], net_pnl=metrics['net_pnl'],
                         ledger_reconciled=True, contaminated_final_access=False))
    pd.DataFrame(rows).to_csv(HERE/'accounting_audit.csv', index=False)
    pd.DataFrame(calendar).to_csv(HERE/'calendar_performance.csv', index=False)
    payload = dict(audited_replays=len(rows), ledger_failures=0, final_period_access=False,
                   postprocess_sha256=sha(__file__), registry_sha256=sha(HERE/'experiment_registry.csv'),
                   note='Calendar-correct volatility/Sortino companion; frozen ranking used correct calendar Sharpe already. No selection changes.')
    (HERE/'accounting_audit.json').write_text(json.dumps(payload, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(payload, indent=2), flush=True)


if __name__ == '__main__':
    audit()
