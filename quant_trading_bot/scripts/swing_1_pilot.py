"""swing_1: multi-day mean-reversion holds on MNQ/MES, training 2010-23 only (research/swing_1/PROTOCOL.md)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1

ECON = {"MNQ": dict(mult=2.0, tick=0.25, spread=1.75), "MES": dict(mult=5.0, tick=0.25, spread=1.0)}
FEE = 0.61
rng = np.random.default_rng(20261109)


def daily(inst):
    b = m1.load_bars(inst, 1, "2009-06-01", "2024-01-01", "train").reset_index(drop=True)
    assert b.timestamp_utc.max() < pd.Timestamp("2024-01-01", tz="UTC")
    loc = b.timestamp_utc.dt.tz_convert("America/New_York")
    sod = loc.dt.hour * 60 + loc.dt.minute
    d = loc.dt.date
    # trade date: bars from 18:00 belong to the next calendar day's session
    tdate = pd.to_datetime(pd.Series(np.where(sod >= 1080, (loc + pd.Timedelta(days=1)).dt.date, d)))
    f = pd.DataFrame(dict(tdate=tdate.to_numpy(), sod=sod.to_numpy(), open=b.open.to_numpy(), close=b.close.to_numpy(), low=b.low.to_numpy()))
    rth = f[(f.sod >= 570) & (f.sod < 960)]
    close = rth.groupby("tdate").close.last()            # 15:59 close
    reopen = f[(f.sod >= 1085) & (f.sod < 1090)].groupby("tdate").open.first()  # 18:05 open of the session that starts the evening before tdate
    slow = f.groupby("tdate").low.min()
    out = pd.DataFrame(dict(close=close, reopen=reopen, slow=slow)).dropna(subset=["close"])
    out = out[(out.index >= "2010-01-01") & (out.index < "2024-01-01")]
    return out


def rsi2(c):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def signals(df):
    c = df.close
    s = {}
    s["S1_2down"] = (c < c.shift(1)) & (c.shift(1) < c.shift(2))
    s["S2_3down"] = s["S1_2down"] & (c.shift(2) < c.shift(3))
    s["S3_rsi2"] = rsi2(c) < 10
    s["S4_5dlow"] = c <= c.rolling(5).min()
    return {k: v.fillna(False).to_numpy() for k, v in s.items()}, (c > c.rolling(200).mean()).fillna(False).to_numpy()


def simulate(df, entries, exit_rule, side, econ):
    """entries: bool array on day index D (signal at D close). Fill at reopen of D+1 session; exits at RTH close."""
    c, r, lo = df.close.to_numpy(), df.reopen.to_numpy(), df.slow.to_numpy()
    idx = df.index
    mult, half, tick = econ["mult"], econ["spread"] * econ["tick"] / 2, econ["tick"]
    n = len(df); trades = []; i = 0
    while i < n - 1:
        if not entries[i] or np.isnan(r[i + 1]):
            i += 1; continue
        e = r[i + 1] + side * (half + tick)
        j = i + 1; worst = 0.0
        while True:
            # marked worst while holding (session low for longs; for shorts use close as a conservative proxy of highs not stored)
            mark = (lo[j] - e) * mult if side > 0 else (e - c[j]) * mult
            worst = min(worst, mark - 2 * FEE)
            done = (j - i >= 5) or (exit_rule == "X1" and c[j] > c[j - 1]) or (exit_rule == "X2" and j - i >= 3) or (exit_rule == "X3" and j - i >= 5) or j == n - 1
            if done: break
            j += 1
        x = c[j] - side * (half + tick)
        net = side * (x - e) * mult - 2 * FEE
        trades.append(dict(entry=idx[i + 1], exit=idx[j], net=net, worst=worst, hold=j - i))
        i = j + 1
    return pd.DataFrame(trades)


def stats(tr, df):
    if tr.empty: return dict(net=0.0, n=0)
    yr = tr.set_index("exit").net.groupby(lambda d: d.year).sum()
    # marked trailing DD: closed equity before each trade + worst mark within it
    eq = tr.net.cumsum().to_numpy(); prev = np.concatenate([[0.0], eq[:-1]])
    marked = np.minimum(eq, prev + tr.worst.to_numpy())
    hwm = np.maximum.accumulate(np.concatenate([[0.0], eq]))[:-1]
    dd_marked = float(np.max(hwm - marked)); dd_closed = float(np.max(hwm - eq))
    return dict(net=round(float(tr.net.sum()), 2), n=int(len(tr)), per=round(float(tr.net.mean()), 2), pos_years=int((yr > 0).sum()),
                max_year_share=round(float(yr.max() / tr.net.sum()), 3) if tr.net.sum() > 0 else None,
                net_2010_19=round(float(yr[yr.index <= 2019].sum()), 2), dd_closed=round(dd_closed, 2), dd_marked=round(dd_marked, 2),
                med_hold=int(tr.hold.median()), years={int(k): round(float(v), 2) for k, v in yr.items()})


def placebo(df, entries, exit_rule, side, econ, n_sets=200):
    years = pd.DatetimeIndex(df.index).year
    cnt = pd.Series(entries).groupby(years).sum()
    nets = []
    for _ in range(n_sets):
        e = np.zeros(len(df), bool)
        for y, k in cnt.items():
            pool = np.where(years == y)[0]
            if k > 0: e[rng.choice(pool, size=min(int(k), len(pool)), replace=False)] = True
        nets.append(simulate(df, e, exit_rule, side, econ).net.sum())
    return np.array(nets)


def main():
    out = {}
    for inst in ("MNQ", "MES"):
        df = daily(inst); econ = ECON[inst]
        sig, trend = signals(df)
        print(inst, "days", len(df), df.index.min().date(), df.index.max().date(), flush=True)
        for sname, s in sig.items():
            for tf in ("none", "sma200"):
                ent = s & trend if tf == "sma200" else s
                for xr in ("X1", "X2", "X3"):
                    for side, lab in ((1, "long"), (-1, "short")):
                        tr = simulate(df, ent, xr, side, econ); st = stats(tr, df)
                        if side > 0 and st["n"] >= 50:
                            pl = placebo(df, ent, xr, side, econ); st["beats"] = int((st["net"] > pl).sum()); st["plc_med"] = round(float(np.median(pl)), 2)
                        key = f"{inst}|{sname}|{tf}|{xr}|{lab}"; out[key] = st
                        print(key, {k: st.get(k) for k in ("net", "n", "per", "pos_years", "max_year_share", "net_2010_19", "dd_marked", "beats")}, flush=True)
    Path(ROOT / "reports/SWING_1_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
