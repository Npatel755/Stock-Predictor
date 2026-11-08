"""Session-based metrics and dependence-aware uncertainty, with explicit assumptions."""
import numpy as np
import pandas as pd
from scipy.stats import norm, skew, kurtosis


def block_bootstrap(values, draws=499, block=5, seed=20261106):
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not np.isfinite(x).all() or draws < 1 or block < 1:
        raise ValueError("Finite one-dimensional observations and positive budget required")
    n = len(x)
    if not n:
        return dict(observations=0, insufficient_evidence=True, mean_ci=[None, None], pvalue=1.0)
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(draws):
        starts = rng.integers(0, n, int(np.ceil(n/block)))
        ids = ((starts[:, None]+np.arange(block)) % n).ravel()[:n]
        means.append(x[ids].mean())
    means = np.asarray(means)
    return dict(observations=n, insufficient_evidence=n < max(30, block*4), draws=draws, block_sessions=block,
        mean=float(x.mean()), mean_ci=list(np.quantile(means, [.025, .975])),
        pvalue=float((1+np.count_nonzero(means-x.mean() >= x.mean()))/(draws+1)),
        method="Circular session block bootstrap; weak stationarity assumed; not future probability")


def probabilistic_sharpe(returns, reference=0):
    x = np.asarray(returns, dtype=float)
    if len(x) < 10 or np.std(x, ddof=1) <= 0:
        return None
    sr = x.mean()/x.std(ddof=1)
    denominator = np.sqrt(max(1e-12, 1-skew(x)*sr+(kurtosis(x, fisher=False)-1)*sr*sr/4))
    return float(norm.cdf((sr-reference)*np.sqrt(len(x)-1)/denominator))


def summarize(result, initial=50000, trials=1, seed=20261106):
    curve, trades = result["curve"], result["trades"]
    if curve.empty:
        return dict(net_pnl=0, trades=0)
    eq = curve.equity.to_numpy()
    peaks = np.maximum.accumulate(np.r_[initial, eq])[1:]
    daily = curve.groupby("session_id", sort=False).equity.last()
    pnl = daily.diff()
    pnl.iloc[0] = daily.iloc[0]-initial
    returns = pnl/initial  # Constant research capital; no reinvestment assumption.
    std = returns.std(ddof=1)
    downside = np.sqrt(np.mean(np.minimum(returns, 0)**2))
    net = trades.net_pnl if len(trades) else pd.Series(dtype=float)
    wins, losses = net[net > 0], net[net < 0]
    dd = float(np.max(peaks-eq))
    worst = curve.intrabar_worst_bound.to_numpy()
    intraday_dd = float(np.max(peaks-worst))
    sharpe = float(np.sqrt(252)*returns.mean()/std) if len(returns) > 1 and std > 0 else None
    streak = longest = 0
    for loss in net < 0:
        streak = streak+1 if loss else 0
        longest = max(longest, streak)
    monthly = pnl.groupby(pd.to_datetime(pnl.index).to_period("M")).sum()
    annual = pnl.groupby(pd.to_datetime(pnl.index).year).sum()
    ci = block_bootstrap(returns, seed=seed)
    # Conservative Bonferroni diagnostic is reported without claiming DSR or Reality Check.
    ci["multiple_testing_pvalue_upper"] = min(1, ci["pvalue"]*trials)
    gross = float(trades.gross_pnl.sum()) if len(trades) else 0.0
    fees = float(trades.fees.sum()) if len(trades) else 0.0
    return dict(net_pnl=float(eq[-1]-initial), gross_pnl=gross, fees=fees, trades=len(net),
        profit_factor=float(wins.sum()/abs(losses.sum())) if len(losses) else None,
        average_trade=float(net.mean()) if len(net) else None, median_trade=float(net.median()) if len(net) else None,
        expected_value_per_trade=float(net.mean()) if len(net) else None,
        win_rate=float((net > 0).mean()) if len(net) else None,
        average_win=float(wins.mean()) if len(wins) else None, average_loss=float(losses.mean()) if len(losses) else None,
        payoff_ratio=float(wins.mean()/abs(losses.mean())) if len(wins) and len(losses) else None,
        max_drawdown=dd, max_intraday_drawdown_bound=intraday_dd, worst_day=float(pnl.min()),
        tail_loss_5pct=float(pnl[pnl <= pnl.quantile(.05)].mean()), longest_losing_streak=longest,
        sharpe=sharpe, sortino=float(np.sqrt(252)*returns.mean()/downside) if downside > 0 else None,
        calmar=float(returns.mean()*252/(dd/initial)) if dd > 0 else None,
        return_to_drawdown=float((eq[-1]-initial)/dd) if dd > 0 else None,
        exposed_fraction=float((curve.quantity != 0).mean()),
        exposure_adjusted_volatility=float(std*np.sqrt(252)/np.sqrt(max(1e-12, (curve.quantity != 0).mean()))) if len(returns) > 1 else None,
        profitable_months=int((monthly > 0).sum()), profitable_years=int((annual > 0).sum()),
        session_days=len(daily), daily_pnl={str(k): float(v) for k, v in pnl.items()},
        monthly_pnl={str(k): float(v) for k, v in monthly.items()}, annual_pnl={str(k): float(v) for k, v in annual.items()},
        psr_iid_diagnostic=probabilistic_sharpe(returns), uncertainty=ci,
        annualization="252 trading sessions; fixed initial capital; short samples not reliable")


def account_monte_carlo(daily_pnl, rules, draws=200, block=5, seed=20261106, worst_excursions=None):
    from .funded import FundedAccount
    x = np.asarray(daily_pnl, dtype=float)
    if not len(x) or not np.isfinite(x).all():
        return dict(insufficient_evidence=True, draws=0)
    rng = np.random.default_rng(seed)
    failures, targets, days, drawdowns, profits = [], [], [], [], []
    excursions = np.minimum(x, 0) if worst_excursions is None else np.asarray(worst_excursions)
    for _ in range(draws):
        starts = rng.integers(0, len(x), int(np.ceil(len(x)/block)))
        ids = ((starts[:, None]+np.arange(block)) % len(x)).ravel()[:len(x)]
        account = FundedAccount(rules)
        balance, peak, maxdd = rules.nominal, rules.nominal, 0.0
        first_target = None
        for day, idx in enumerate(ids):
            account.mark(balance+excursions[idx], session=str(day), closing_balance=balance)
            balance += x[idx]
            account.mark(balance, session=str(day), closing_balance=balance)
            account.end_session(balance)
            # Prevent end_session being called twice by the next mark.
            account.session = None
            peak = max(peak, balance)
            maxdd = max(maxdd, peak-(balance+min(0, excursions[idx]-x[idx])))
            if account.failed:
                break
            summary = account.summary()
            # Unknown minimum days means this is target+consistency probability,
            # never presented as official evaluation-pass probability.
            if summary["target_reached"] and summary["consistency_pass"]:
                first_target = day+1
                break
        failures.append(account.failed)
        targets.append(first_target is not None)
        if first_target is not None:
            days.append(first_target)
        drawdowns.append(maxdd)
        profits.append(balance-rules.nominal)
    return dict(draws=draws, sample_sessions=len(x), insufficient_evidence=len(x) < 60,
        scenario_failure_frequency=float(np.mean(failures)), target_and_consistency_frequency=float(np.mean(targets)),
        days_to_target_quantiles=list(np.quantile(days, [.1, .5, .9])) if days else None,
        drawdown_quantiles=list(np.quantile(drawdowns, [.1, .5, .9])), net_profit_quantiles=list(np.quantile(profits, [.1, .5, .9])),
        method="Circular session blocks with intraday worst-equity bounds; historical scenario frequencies only")
