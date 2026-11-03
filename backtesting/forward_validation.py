"""One fixed prospective evaluation, after the complete locked window exists."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .alternative_strategies import simulate
from .exit_research import freeze
from .generalization_policy import digest,frozen_profile
from .independent_visuals import equity_curve
from .market_data import BAR,clean_candles,utc
from .optimize import pnl,write_json
from .paths import ROOT
from .post_selection_checks import paired_interval
from .regime_filters import RegimeFilter,prepare_features,apply_filter


def evaluate(path,root=ROOT,now=None):
    p,rule,cfg,meta=frozen_profile(root)
    now=utc(now) if now is not None else pd.Timestamp.now(tz='UTC')
    start,end=utc(p['future_start_utc']),utc(p['future_end_exclusive_utc'])
    if now<end:
        return dict(status='awaiting_future_window',earliest_final_evaluation_utc=str(end),passed=False,
                    prospective_validation_complete=False,ready_for_funded_trading=False)
    # No prices or returns are read before the fixed evaluation date.
    source_bytes=Path(path).read_bytes()
    raw=pd.read_parquet(io.BytesIO(source_bytes))
    warmup_start=start-pd.Timedelta(hours=rule.slow*5)
    times=pd.to_datetime(raw.timestamp,utc=True)
    raw=raw[(times>=warmup_start)&(times<end)].copy()
    bars,quality=clean_candles(raw,start=warmup_start,end=end)
    if quality['missing_bars']:raise ValueError('Forward data has gaps; no fills or fabricated candles are allowed')
    if bars.timestamp.min()>start-pd.Timedelta(hours=rule.slow*5):
        raise ValueError('Forward data needs a full five-EMA-length historical warm-up')
    if bars.available_at.max()<end:raise ValueError('The entire locked future period is required')
    frame=apply_filter(prepare_features(bars,rule),RegimeFilter(**meta['entry_filters']))
    mask=(bars.timestamp>=start)&(bars.available_at<=end)
    future=bars.loc[mask].reset_index(drop=True);signals=frame.loc[mask].reset_index(drop=True)
    expected=int((end-start)/BAR)
    if len(future)!=expected or future.timestamp.iloc[0]!=start or future.available_at.iloc[-1]!=end:
        raise ValueError('Incomplete locked future period')
    results={};curve=None
    for bps in p['required_cost_scenarios_bps']:
        metrics,trades,events=simulate(future,rule,replace(cfg,slippage_bps=bps),signals=signals)
        results[str(bps)]=metrics
        if bps==2.:
            curve=equity_curve(future,events,cfg)
            main_trades=trades;main_events=events
    daily=curve.set_index('timestamp').equity.resample('1D').last()
    changes=daily.diff();changes.iloc[0]=daily.iloc[0]-cfg.initial_capital
    interval=paired_interval(changes.to_numpy(),seed=20261104,draws=10000,block_days=7)
    main=results['2.0']
    checks=dict(minimum_closed_trades=main['closed_trade_legs']>=p['minimum_closed_trades'],
                positive_main_and_stressed_net=all(pnl(m)>0 for m in results.values()),
                drawdown_limit=all(m['max_intrabar_drawdown']<=p['maximum_intrabar_drawdown'] for m in results.values()),
                no_margin_calls=all(m['margin_call_events']==0 for m in results.values()),
                positive_lower_block_interval=interval['interval_95'][0]>0)
    certificate=dict(evaluation_type='locked_forward',protocol_sha256=digest(p),
                     configuration_sha256=p['frozen_configuration_sha256'],
                     frozen_version=p['frozen_version'],data_sha256=hashlib.sha256(source_bytes).hexdigest(),
                     period=[str(start),str(end)],checks=checks,metrics=results,block_interval=interval,
                     passed=all(checks.values()),prospective_validation_complete=True,
                     ready_for_funded_trading=False,
                     qualification='A single frozen forward test cannot guarantee future profits or certify broker parity/account rules.')
    out=root/'artifacts/generalization/forward';out.mkdir(parents=True,exist_ok=True)
    # A revealed test is consumed. Never overwrite its outcome with a new feed
    # revision or a different set of parameters after inspecting the result.
    freeze(out/'forward_certificate.json',certificate)
    curve.to_parquet(out/'equity.parquet',index=False)
    future.to_parquet(out/'bars.parquet',index=False)
    main_trades.to_csv(out/'trades.csv',index=False);main_events.to_csv(out/'events.csv',index=False)
    return certificate


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bars',type=Path,required=True)
    print(json.dumps(evaluate(parser.parse_args().bars),indent=2,default=str))
