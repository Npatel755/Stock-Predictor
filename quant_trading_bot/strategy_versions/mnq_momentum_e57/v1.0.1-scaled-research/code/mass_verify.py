"""Independent ledger arithmetic and bounded shared-simulator trade replay.

No file access. Sampling is fixed evenly spaced chronology, never P&L selected.
Shared replays isolate trades: account-path risk is verified by dedicated engine
fixtures, not claimed equivalent to the older simulator's adverse-bound logic.
"""
import math
from typing import Literal
import numpy as np
from quant_futures.backtest import Simulator
from quant_futures.config import ResearchConfig,Costs,Execution,RiskLimits
from quant_futures.execution import Action,PaperBroker
from quant_futures.contracts import SPECS
from quant_futures.risk import fixed_dollar_size


class VerificationConfig(ResearchConfig):
    instrument: Literal['ES','NQ','MES','MNQ'] = 'MNQ'


def verify_execution(bars,data,signal,atr,c,cfg,result,max_replays=25):
    symbol=c['instrument']
    spec=SPECS[symbol]
    costs=Costs(**{k:cfg[k] for k in ('commission_per_side','exchange_per_side','regulatory_per_side','spread_ticks','slippage_ticks','impact_ticks')})
    broker=PaperBroker(costs)
    count=len(result['trade_net'])
    net=result['trade_side']*result['trade_qty']*(result['trade_exitprice']-result['trade_entryprice'])*spec.multiplier-result['trade_fees']
    np.testing.assert_allclose(net,result['trade_net'],rtol=0,atol=1e-7)
    np.testing.assert_allclose(net.sum(),result['equity'][-1]-cfg['initial_balance'],rtol=0,atol=1e-7)
    for j in range(count):
        entry=int(result['trade_entry'][j])
        side=int(result['trade_side'][j])
        if entry < 1 or signal[entry-1] != side:
            raise AssertionError('Entry lacks a preceding directional decision')
        expected=broker.market_price(data['open'][entry],side,symbol)
        np.testing.assert_allclose(result['trade_entryprice'][j],expected,rtol=0,atol=1e-8)
        distance=math.ceil(atr[entry-1]*cfg['stop_atr']/spec.tick)*spec.tick
        adverse=spec.tick*(costs.slippage_ticks+costs.spread_ticks/2+costs.impact_ticks)
        request=fixed_dollar_size(cfg['risk_per_trade'],distance,spec.multiplier,
            roundtrip_cost=2*costs.fee+(2*adverse+spec.tick)*spec.multiplier,maximum=cfg['maxqty'])
        expected_qty=min(request,int(data['volume'][entry-1]*cfg['participation']))
        if expected_qty != result['trade_qty'][j]:
            raise AssertionError('Independent stop-risk/participation sizing differs')
    samples=np.unique(np.linspace(0,count-1,min(count,max_replays),dtype=int)) if count else []
    for j in samples:
        entry,exit_=int(result['trade_entry'][j]),int(result['trade_exit'][j])
        side,qty=int(result['trade_side'][j]),int(result['trade_qty'][j])
        ticks=max(1,math.ceil(atr[entry-1]*cfg['stop_atr']/spec.tick))
        target=round((result['trade_entryprice'][j]+side*ticks*spec.tick*cfg['target_ratio'])/spec.tick)*spec.tick
        target_ticks=int(round(abs(target-result['trade_entryprice'][j])/spec.tick))
        config=VerificationConfig(instrument=symbol,timeframe_minutes=15,costs=costs,
            execution=Execution(stop_ticks=ticks,target_ticks=target_ticks,max_hold_bars=cfg['hold_bars'],
                max_gap_minutes=cfg['max_gap_minutes'],session_flat_minute_et=cfg['flat_minute'],
                participation=cfg['participation'],use_observed_quotes=False),
            risk=RiskLimits(max_contracts=qty,max_correlated_contracts=qty,max_trade_risk=1e9,max_open_risk=1e9,
                max_daily_loss=1e9,max_drawdown=1e9,max_slippage_ticks=1e6))
        sim=Simulator(config)
        for index,bar in zip(range(entry-1,exit_+1),bars.iloc[entry-1:exit_+1].itertuples(index=False)):
            if sim.position is not None and cfg['trailing_atr'] > 0 and np.isfinite(atr[index-1]):
                proposed=round((data['close'][index-1]-side*cfg['trailing_atr']*atr[index-1])/spec.tick)*spec.tick
                sim.position.stop=max(sim.position.stop,proposed) if side>0 else min(sim.position.stop,proposed)
            sim.step(bar,Action.LONG if index==entry-1 and side>0 else Action.SHORT if index==entry-1 else Action.HOLD)
            if index==exit_ and int(result['trade_reason'][j])==6 and sim.position is not None:
                sim._close(bar.low if side>0 else bar.high,bar.timestamp_utc,'risk_exit')
        actual=sim.finish()['trades']
        if len(actual)!=1:
            raise AssertionError('Shared trade replay did not produce one closed trade')
        for key,expected in [('entry_price',result['trade_entryprice'][j]),('exit_price',result['trade_exitprice'][j]),
                             ('quantity',qty),('net_pnl',result['trade_net'][j]),('fees',result['trade_fees'][j])]:
            np.testing.assert_allclose(actual.iloc[0][key],expected,rtol=0,atol=1e-7,err_msg=key)
    return dict(passed=True,ledger_trades=count,shared_simulator_replayed=len(samples),
        replay_sampling='up to25 evenly spaced chronological trades per fold, fixed before research',
        account_path_equivalence=False,
        limitation='Older simulator omits exit-bar adverse excursion and exit-cost reserves. Isolated trade replays verify fills; full risk-path equivalence is not claimed.')
