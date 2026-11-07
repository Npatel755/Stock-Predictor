from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import neighborhood_refinement_study as study
from quant_futures.data import canonical
from quant_futures.execution import Action, PaperBroker
from quant_futures.transfer import morning_indexes


def parameters():
    return dict(name=study.execution.engine.NAME,stop_points=30,payoff=4,contracts=2,
        sizing="fixed",risk_stop=1900,gap_low=.1,gap_high=.6,momentum_min=.05,
        protection="entry_075",exit_minute=720)


def sessions(bars):
    prior = bars.iloc[:390].copy()
    prior["timestamp_utc"] = pd.date_range("2023-01-03T14:30Z",periods=390,freq="min")
    prior[["open","close"]] = 20000.
    prior["high"],prior["low"] = 20050.,19950.
    current = prior.copy()
    current["timestamp_utc"] += pd.Timedelta(days=1)
    current["open"] = 20020.
    current["close"] = 20030.
    current["high"],current["low"] = 20031.,20019.
    prior["instrument"],prior["contract"] = "NQ","NQH23"
    current["instrument"],current["contract"] = "NQ","NQH23"
    return canonical(prior),canonical(current)


def test_session_cache_matches_complete_history_signals(bars):
    prior,current = sessions(bars)
    history = []
    chunks = []
    for frame in (prior,current):
        features = study.execution.engine.entry(study.BASE.gap.context(frame,history))
        chunks.append(study.retain_session(frame,features))
        history.append(study.BASE.gap.history_value(frame))
    retained = pd.concat(chunks,ignore_index=True)
    complete = canonical(pd.concat([prior,current],ignore_index=True))
    for clock in (690,705,720):
        candidate = dict(parameters(),exit_minute=clock)
        expected = study.execution.signals_for(complete,candidate).iloc[morning_indexes(complete)].reset_index(drop=True)
        pd.testing.assert_series_equal(study.cached_signals(retained,candidate),expected)
    assert study.cached_signals(retained,parameters()).eq(Action.LONG).sum() == 1


def test_configurable_screen_matches_original_and_uses_declared_exit(bars):
    prior,current = sessions(bars)
    current.loc[121:149,["open","high","low","close"]] += 10
    context = study.BASE.gap.context(current,[study.BASE.gap.history_value(prior)])
    features = study.execution.engine.entry(context)
    candidate = dict(parameters(),exit_minute=690,protection="none",payoff=10)
    cfg = study.BASE.configuration("NQ",candidate)
    broker = PaperBroker(cfg.costs)
    assert study.screen(context,features,candidate,cfg,broker) == study.execution.engine.screen(context,features,candidate,cfg,broker)
    later = study.screen(context,features,dict(candidate,exit_minute=705),cfg,broker)
    earlier = study.screen(context,features,candidate,cfg,broker)
    assert later["net_pnl"] > earlier["net_pnl"]


def test_discarding_unused_events_preserves_equity_trades_and_risk(bars):
    data = canonical(bars.iloc[:180].copy())
    data["instrument"],data["contract"] = "MNQ","MNQH26"
    signal = pd.Series([Action.LONG]+[Action.HOLD]*150+[Action.EXIT]+[Action.HOLD]*28)
    full = study.execution.replay(data,signal,parameters(),"MNQ")
    bounded = study.execution.replay(data,signal,parameters(),"MNQ",retain_events=False)
    for key in ("curve","trades"):
        pd.testing.assert_frame_equal(full[key],bounded[key])
    assert full["permanent_risk_lock"] == bounded["permanent_risk_lock"]
    assert len(bounded["events"]) < len(full["events"])
