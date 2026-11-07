"""Synchronized MES/MNQ replay with one cash balance and one hard risk state."""
import numpy as np
import pandas as pd
from .backtest import Simulator
from .data import validate
from .risk import RiskManager, portfolio_exposure


def run_portfolio(datasets, signals, configs, account=None):
    names = sorted(datasets)
    if not names or set(names) != set(signals) or set(names) != set(configs):
        raise ValueError("Matching data, signal and config instruments required")
    first = configs[names[0]]
    shared = RiskManager(first.risk, first.initial_balance)
    sleeves, records = {}, {}
    reference = None
    for name in names:
        cfg = configs[name]
        if cfg.instrument != name or cfg.initial_balance != first.initial_balance or cfg.risk != first.risk or cfg.timeframe_minutes != first.timeframe_minutes:
            raise ValueError("Portfolio sleeves require identical account, risk and timeframe settings")
        bars, quality = validate(datasets[name], cfg.timeframe_minutes)
        if quality["fatal"] or bars.timestamp_utc.duplicated().any() or not bars.instrument.eq(name).all():
            raise ValueError("Invalid selected portfolio data")
        if reference is not None and not bars.timestamp_utc.equals(reference):
            raise ValueError("Synchronized timestamps required; no implicit price filling or intersection")
        reference = bars.timestamp_utc
        if len(bars) != len(signals[name]) or not len(bars):
            raise ValueError("Nonempty aligned signals required")
        sim = Simulator(cfg)
        sim.risk, sim.external_risk = shared, True
        sleeves[name], records[name] = sim, list(bars.itertuples(index=False))
    initial = first.initial_balance
    def cash():
        return initial+sum(sim.cash-initial for sim in sleeves.values())
    reserved = {}
    def per_contract_risk(sim):
        return sim.cfg.execution.stop_ticks*sim.spec.tick*sim.spec.multiplier+2*sim.cfg.costs.fee+sim.spec.tick*sim.spec.multiplier*(2*sim.cfg.costs.slippage_ticks+sim.cfg.costs.spread_ticks+2*sim.cfg.costs.impact_ticks+1)
    def other_exposure(name):
        risk = quantity = 0
        for other, sim in sleeves.items():
            q = reserved.get(other, 0)
            if other != name and q:
                # Gross stop distance plus adverse round-trip costs; no hedge credit.
                risk += q*per_contract_risk(sim)
                quantity += q
        return dict(open_risk=risk, correlated_contracts=quantity)
    curve = []
    for index, timestamp in enumerate(reference):
        session = records[names[0]][index].session_id
        shared.begin_session(session, cash())
        # Reserve beginning-of-bar exposure for the whole bar. A different
        # sleeve cannot use an intrabar stop/target (unknown at the open) to
        # free capacity for an order executed at this bar's open.
        reserved = {name: sim.position.quantity if sim.position else 0 for name, sim in sleeves.items()}
        states = {}
        for name in names:
            sim = sleeves[name]
            sim.portfolio_context = other_exposure(name)
            existing = sum(reserved.values())
            # Prevent pending entries after a funded lockout. The conservative
            # portfolio cap is also enforced by the common correlated-risk gate.
            if account is not None and not account.permit_position(existing+1):
                if sim.pending and sim.pending[1] in (-1, 1) and not sim.position:
                    sim.pending = None
            prior_sequence = sim.order_sequence
            states[name] = sim.step(records[name][index], signals[name].iloc[index] if hasattr(signals[name], "iloc") else signals[name][index])
            new_entries = sum(order.filled for oid, order in sim.broker.orders.items()
                if oid.startswith("entry-") and int(oid.split("-")[-1]) > prior_sequence)
            reserved[name] = max(reserved[name], new_entries)
        equity = initial+sum(state["equity"]-initial for state in states.values())
        worst = initial+sum(state["intrabar_worst_bound"]-initial for state in states.values())
        why = shared.observe(worst) or shared.observe(equity)
        if account is not None:
            account.mark(worst, session=session, closing_balance=cash())
            if account.failed or account.day_locked:
                why = "funded_account_limit"
                shared.kill(why) if account.failed else setattr(shared, "day_locked", True)
        if why or shared.killed:
            for name, sim in sleeves.items():
                sim.pending = None
                if sim.position:
                    bar = records[name][index]
                    sim._close(bar.low if sim.position.side > 0 else bar.high, timestamp, "portfolio_risk_exit")
                    sim.curve[-1].update(cash=sim.cash, equity=sim.cash, quantity=0)
            equity = cash()
        positions = [dict(instrument=name, quantity=sim.position.side*sim.position.quantity,
                          price=records[name][index].close) for name, sim in sleeves.items() if sim.position]
        curve.append(dict(timestamp_utc=timestamp, session_id=session, cash=cash(), equity=equity,
            intrabar_worst_bound=min(worst, equity), quantity=sum(abs(p["quantity"]) for p in positions),
            gross_notional=portfolio_exposure(positions, {n: s.spec.multiplier for n, s in sleeves.items()}),
            risk_locked=shared.killed or shared.day_locked, risk_reason=shared.reason))
    trades, events = [], []
    for name, sim in sleeves.items():
        result = sim.finish()
        if len(result["trades"]):
            trades.append(result["trades"].assign(instrument=name))
        events.extend(dict(instrument=name, **event) for event in result["events"])
    curve[-1].update(equity=cash(), cash=cash(), quantity=0, gross_notional=0)
    if account:
        account.end_session(cash())
    return dict(curve=pd.DataFrame(curve), trades=pd.concat(trades, ignore_index=True) if trades else pd.DataFrame(),
        events=sorted(events, key=lambda e: pd.Timestamp(e["timestamp"])),
        execution_priority=names, risk=shared, account=account)
