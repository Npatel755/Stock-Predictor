"""Audit of Antigravity's scale-out free-roll sprint (scripts/research_scaleout_freeroll_runner_train.py) on 1-min NQ, TRAINING 2010-23 only.

Step 0 reproduces their simulator exactly (same data, same rules, same friction). Then each fill/look-ahead fix is applied cumulatively:
  F1 stop fills at the bar open when the bar opens beyond the stop (gap-through), not exactly at the stop
  F2 stop checked before target when one 1-min bar touches both (their code books the target first)
  F3 the entry bar itself is checked for the stop (their code skips exits on the entry bar)
  F4 breakout entry fills at the bar open when the bar opens beyond the range edge (their code fills at the edge)
  F5 VIX >= 15 gate uses the PRIOR session's VIX close (their code uses the same day's close, published at 16:15 ET = look-ahead)
  F6 engine-standard friction: 2 ticks adverse per side + $0.61/side commission = 1.61 pts round trip (theirs 1.30)
Reports net, worst day, $150+ days per year (the payout metric), days <= -$1,000, by era.
"""
import json
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
t = pq.read_table(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet",
                  columns=["timestamp_utc", "open", "high", "low", "close"]).to_pandas()
et = t.timestamp_utc.dt.tz_convert("America/New_York")
t["date"] = et.dt.date; t["sod"] = (et.dt.hour * 60 + et.dt.minute).astype(int)
rth = t[(t.sod >= 570) & (t.sod <= 960)].sort_values(["date", "sod"])
assert rth.timestamp_utc.max() < pd.Timestamp("2024-01-01", tz="UTC")
dates = sorted(rth["date"].unique())
eod = rth[rth.sod == 960].groupby("date")["close"].last(); sod0 = rth[rth.sod == 570].groupby("date")["open"].first()
gap = (sod0 - eod.shift(1)).dropna().to_dict()
v = pd.read_csv(ROOT / "data/external/VIX_History.csv"); v["date"] = pd.to_datetime(v["DATE"]).dt.date
vix_same = dict(zip(v["date"], v["CLOSE"]))
vix_prior = dict(zip(v["date"], v["CLOSE"].shift(1)))           # value on date d = the close of the previous CBOE session
G = {d: {k: g[k].to_numpy() for k in ("sod", "open", "high", "low", "close")} for d, g in rth.groupby("date")}
PT = 2.0


def sim(n, stop=16.0, t1=28.0, tp2=120.0, fix=0, friction=1.30):
    """fix = number of cumulative fixes applied (0 = Antigravity's code exactly)."""
    half = n // 2; out = {}
    vixd = vix_prior if fix >= 5 else vix_same
    for d in dates:
        vx = vixd.get(d, 18.0)
        if vx is None or (isinstance(vx, float) and np.isnan(vx)): vx = 18.0
        if vx < 15.0 or d not in G:
            out[d] = 0.0; continue
        b = G[d]; s = b["sod"]; m15 = s < 585
        if not m15.any(): out[d] = 0.0; continue
        hi, lo = b["high"][m15].max(), b["low"][m15].min()
        if hi - lo < 15.0: out[d] = 0.0; continue
        idx = np.where((s >= 585) & (s <= 955))[0]
        if len(idx) == 0: out[d] = 0.0; continue
        g = gap.get(d, 0.0); pnl = 0.0; inpos = False; leg1 = False; dirn = 0; e = sl1 = sl2 = tp1 = tp_2 = 0.0
        for i in idx:
            o, h, l = b["open"][i], b["high"][i], b["low"][i]
            entered_now = False
            if not inpos:
                if g >= 0 and h > hi:
                    dirn, e = 1, (max(hi, o) if fix >= 4 else hi)
                elif g <= 0 and l < lo:
                    dirn, e = -1, (min(lo, o) if fix >= 4 else lo)
                else:
                    continue
                inpos, leg1 = True, False
                sl1 = sl2 = e - dirn * stop; tp1 = e + dirn * t1; tp_2 = e + dirn * tp2
                entered_now = True
                if fix < 3:
                    continue                                          # their code: no exit checks on the entry bar
            fav = h if dirn > 0 else l; adv = l if dirn > 0 else h
            hit = lambda lvl, px: (px <= lvl) if dirn > 0 else (px >= lvl)
            hit_fav = lambda lvl, px: (px >= lvl) if dirn > 0 else (px <= lvl)

            def fill(lvl):                                            # stop fill
                if fix >= 1 and not entered_now and hit(lvl, o):      # bar opened through the stop
                    return o
                return lvl
            if not leg1:
                t_hit, s_hit = hit_fav(tp1, fav), hit(sl1, adv)
                if fix >= 2 and s_hit:
                    px = fill(sl1); pnl += (dirn * (px - e) - friction) * PT * n; inpos = False; break
                if t_hit:
                    pnl += (t1 - friction) * PT * half; leg1 = True; sl2 = e + dirn * 1.0
                elif s_hit:
                    px = fill(sl1); pnl += (dirn * (px - e) - friction) * PT * n; inpos = False; break
            else:
                t_hit, s_hit = hit_fav(tp_2, fav), hit(sl2, adv)
                if fix >= 2 and s_hit:
                    px = fill(sl2); pnl += (dirn * (px - e) - friction) * PT * half; inpos = False; break
                if t_hit:
                    pnl += (tp2 - friction) * PT * half; inpos = False; break
                elif s_hit:
                    px = fill(sl2); pnl += (dirn * (px - e) - friction) * PT * half; inpos = False; break
            if pnl >= 1750.0 or pnl <= -400.0:
                break
        if inpos:
            c = b["close"][idx[-1]]; q = half if leg1 else n
            pnl += (dirn * (c - e) - friction) * PT * q
        out[d] = pnl
    return pd.Series(out)


def sim_path(n, stop=16.0, t1=28.0, tp2=120.0, prior_vix=True, friction=1.30):
    """Fair version: every 1-min bar is walked along the standard OHLC path (up bar O-L-H-C, down bar O-H-L-C), so the entry bar is
    handled by when the breakout and the stop actually occur along that path (neither 'never stopped' nor 'always stopped').
    Gap-through stops fill at the bar open (F1); a breakout bar opening beyond the range fills at its open (F4)."""
    half = n // 2; out = {}; vixd = vix_prior if prior_vix else vix_same
    for d in dates:
        vx = vixd.get(d, 18.0)
        if vx is None or (isinstance(vx, float) and np.isnan(vx)): vx = 18.0
        if vx < 15.0 or d not in G: out[d] = 0.0; continue
        b = G[d]; s = b["sod"]; m15 = s < 585
        if not m15.any(): out[d] = 0.0; continue
        hi, lo = b["high"][m15].max(), b["low"][m15].min()
        if hi - lo < 15.0: out[d] = 0.0; continue
        idx = np.where((s >= 585) & (s <= 955))[0]
        if len(idx) == 0: out[d] = 0.0; continue
        g = gap.get(d, 0.0); st = dict(inpos=False, done=False, leg1=False, dirn=0, e=0.0, pnl=0.0)

        def open_pos(dirn, px):
            st.update(inpos=True, leg1=False, dirn=dirn, e=px, sl1=px - dirn * stop, sl2=px - dirn * stop, tp1=px + dirn * t1, tp2=px + dirn * tp2)

        def close_all(px, q):
            st["pnl"] += (st["dirn"] * (px - st["e"]) - friction) * PT * q; st["inpos"] = False; st["done"] = True

        def walk(a, z):                       # monotone segment a -> z
            if st["done"]: return
            up = z > a
            if not st["inpos"]:
                if g >= 0 and up and a <= hi < z: open_pos(1, hi); a = hi
                elif g <= 0 and not up and a >= lo > z: open_pos(-1, lo); a = lo
                else: return
            dn = st["dirn"]; favourable = (up and dn > 0) or ((not up) and dn < 0)
            if favourable:
                if not st["leg1"] and (z >= st["tp1"] if dn > 0 else z <= st["tp1"]):
                    st["pnl"] += (t1 - friction) * PT * half; st["leg1"] = True; st["sl2"] = st["e"] + dn * 1.0
                if st["leg1"] and (z >= st["tp2"] if dn > 0 else z <= st["tp2"]):
                    close_all(st["tp2"], half)
            else:
                lvl, q = (st["sl2"], half) if st["leg1"] else (st["sl1"], n)
                if (z <= lvl if dn > 0 else z >= lvl):
                    close_all(lvl, q)

        for i in idx:
            if st["done"]: break
            o, h, l, c = b["open"][i], b["high"][i], b["low"][i], b["close"][i]
            if st["inpos"]:                                         # gap-through at the bar open
                dn = st["dirn"]; lvl, q = (st["sl2"], half) if st["leg1"] else (st["sl1"], n)
                if (o <= lvl if dn > 0 else o >= lvl): close_all(o, q); break
            elif (g >= 0 and o > hi) or (g <= 0 and o < lo):         # bar opens beyond the range edge: fill at the open
                open_pos(1 if (g >= 0 and o > hi) else -1, o)
            pts = [o, l, h, c] if c >= o else [o, h, l, c]
            for a, z in zip(pts[:-1], pts[1:]):
                walk(a, z)
            if st["pnl"] >= 1750.0 or st["pnl"] <= -400.0: break
        if st["inpos"] and not st["done"]:
            close_all(b["close"][idx[-1]], half if st["leg1"] else n)
        out[d] = st["pnl"]
    return pd.Series(out)


def ambiguity(n=6, stop=16.0, t1=28.0, tp2=120.0):
    """Days whose entry bar contains BOTH the breakout level and the 16-pt stop (1-min data cannot order them) and their share of the
    path-walk P&L (6c, runner 120, prior-day VIX, 1.30 pts)."""
    fair = sim_path(n, stop, t1, tp2); amb = set()
    for d in dates:
        vx = vix_prior.get(d, 18.0); vx = 18.0 if (vx is None or (isinstance(vx, float) and np.isnan(vx))) else vx
        if vx < 15.0 or d not in G: continue
        b = G[d]; s = b["sod"]; m15 = s < 585
        if not m15.any(): continue
        hi, lo = b["high"][m15].max(), b["low"][m15].min()
        if hi - lo < 15.0: continue
        g = gap.get(d, 0.0)
        for i in np.where((s >= 585) & (s <= 955))[0]:
            h, l = b["high"][i], b["low"][i]
            if g >= 0 and h > hi:
                if l <= max(hi, b["open"][i]) - stop: amb.add(d)
                break
            if g <= 0 and l < lo:
                if h >= min(lo, b["open"][i]) + stop: amb.add(d)
                break
    traded = fair[fair != 0]
    a = traded[[d in amb for d in traded.index]]
    return dict(traded_days=int(len(traded)), ambiguous_entry_bar_days=int(len(a)), ambiguous_share_of_days=round(len(a) / max(1, len(traded)), 3),
                path_walk_net_on_ambiguous_days=round(float(a.sum()), 2), path_walk_net_other_days=round(float(traded.sum() - a.sum()), 2))


def sim_confirm(n, stop=16.0, t1=28.0, tp2=120.0, friction=1.61):
    """Execution variant without entry-bar ambiguity: enter at the NEXT bar's open after a 1-min CLOSE beyond the opening range (gap-aligned),
    then the same stop / bank / free-roll / runner rules, path-walked bar by bar, prior-day VIX, engine friction."""
    half = n // 2; out = {}
    for d in dates:
        vx = vix_prior.get(d, 18.0); vx = 18.0 if (vx is None or (isinstance(vx, float) and np.isnan(vx))) else vx
        if vx < 15.0 or d not in G: out[d] = 0.0; continue
        b = G[d]; s = b["sod"]; m15 = s < 585
        if not m15.any(): out[d] = 0.0; continue
        hi, lo = b["high"][m15].max(), b["low"][m15].min()
        if hi - lo < 15.0: out[d] = 0.0; continue
        idx = np.where((s >= 585) & (s <= 955))[0]
        g = gap.get(d, 0.0); sig = None
        for k, i in enumerate(idx[:-1]):
            c = b["close"][i]
            if (g >= 0 and c > hi) or (g <= 0 and c < lo):
                sig = (k + 1, 1 if (g >= 0 and c > hi) else -1); break
        if sig is None: out[d] = 0.0; continue
        k0, dn = sig; e = b["open"][idx[k0]]; sl = e - dn * stop; tp1_ = e + dn * t1; tp2_ = e + dn * tp2; leg1 = False; pnl = 0.0; done = False
        for i in idx[k0:]:
            o, h, l, c = b["open"][i], b["high"][i], b["low"][i], b["close"][i]
            if i != idx[k0] and (o <= sl if dn > 0 else o >= sl):
                pnl += (dn * (o - e) - friction) * PT * (half if leg1 else n); done = True; break
            pts = [o, l, h, c] if c >= o else [o, h, l, c]
            for a, z in zip(pts[:-1], pts[1:]):
                fav = (z > a and dn > 0) or (z < a and dn < 0)
                if fav:
                    if not leg1 and (z >= tp1_ if dn > 0 else z <= tp1_):
                        pnl += (t1 - friction) * PT * half; leg1 = True; sl = e + dn * 1.0
                    if leg1 and (z >= tp2_ if dn > 0 else z <= tp2_):
                        pnl += (tp2 - friction) * PT * half; done = True; break
                elif (z <= sl if dn > 0 else z >= sl):
                    pnl += (dn * (sl - e) - friction) * PT * (half if leg1 else n); done = True; break
            if done or pnl >= 1750.0 or pnl <= -400.0: break
        if not done:
            pnl += (dn * (b["close"][idx[-1]] - e) - friction) * PT * (half if leg1 else n)
        out[d] = pnl
    return pd.Series(out)


def summ(s):
    s = s.astype(float); idx = pd.to_datetime(pd.Series(s.index).astype(str)).to_numpy(); yrs = pd.DatetimeIndex(idx).year
    traded = s != 0; d150 = pd.Series((s >= 150).to_numpy(), index=yrs).groupby(level=0).sum()
    early = yrs < 2020
    return dict(net=round(float(s.sum()), 2), traded_days=int(traded.sum()), win_rate=round(float((s[traded] > 0).mean()), 3),
                worst_day=round(float(s.min()), 2), days_le_minus_400=int((s <= -400).sum()), days_le_minus_1000=int((s <= -1000).sum()),
                days150_per_year=round(float(d150.mean()), 1), net_2010_19=round(float(s[early].sum()), 2), net_2020_23=round(float(s[~early].sum()), 2),
                pos_years=f"{int((pd.Series(s.to_numpy(), index=yrs).groupby(level=0).sum() > 0).sum())}/{len(set(yrs))}")


res = {}
labels = ["0 Antigravity code as written", "F1 gap-through stop fills", "F2 stop before target in a bar", "F3 check the entry bar",
          "F4 realistic breakout entry fill", "F5 prior-day VIX (no look-ahead)"]
for n, tp2, tag in ((6, 100.0, "6c_runner100"), (12, 120.0, "12c_runner120"), (6, 120.0, "6c_runner120")):
    for k, lab in enumerate(labels):
        res[f"{tag} | {lab}"] = summ(sim(n, tp2=tp2, fix=k))
    res[f"{tag} | F6 engine friction 1.61 pts"] = summ(sim(n, tp2=tp2, fix=5, friction=1.61))
    res[f"{tag} | FAIR path-walk, all fixes, 1.30 pts"] = summ(sim_path(n, tp2=tp2, friction=1.30))
    res[f"{tag} | FAIR path-walk, all fixes, 1.61 pts"] = summ(sim_path(n, tp2=tp2, friction=1.61))
    res[f"{tag} | FAIR path-walk, same-day VIX (theirs), 1.30"] = summ(sim_path(n, tp2=tp2, prior_vix=False, friction=1.30))
    res[f"{tag} | CONFIRM entry (next open after 1m close), 1.61"] = summ(sim_confirm(n, tp2=tp2, friction=1.61))
res["ambiguity_6c_runner120"] = ambiguity()
print("ambiguity:", res["ambiguity_6c_runner120"], flush=True)
res = {k: v for k, v in res.items()}
for k, r in [(k, r) for k, r in res.items() if k != "ambiguity_6c_runner120"]:
    print(f"{k:60s} net {r['net']:>11,.2f} | worst {r['worst_day']:>9,.2f} | $150+ d/yr {r['days150_per_year']:>5} | "
          f"2010-19 {r['net_2010_19']:>10,.0f} | 2020-23 {r['net_2020_23']:>10,.0f} | yrs+ {r['pos_years']}", flush=True)
(ROOT / "reports/AUDIT_FREEROLL_SPRINT_1M_TRAINING.json").write_text(json.dumps(res, indent=1))
