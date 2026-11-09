# multimarket_1 — the frozen MNQ trend/breakout sleeves applied to crude as a micro (MCL), pre-registered 2026-11-09 before any run

Thesis: the only rules whose moves exceed micro costs are the trend/breakout sleeves; the institutional edge in trend following is the same rule across
uncorrelated markets, not a better rule on one market. Data already owned: CL.c.0 1-min 2010-2025 (Databento). Trade as MCL: tick 0.01 = $1.00,
spread 2 ticks (MCL book is thinner than CL's 1 tick), slippage 1 tick/side, commission $0.61/side, 1 contract. Session: CL pit 09:00-14:30 ET; entries on
completed bars 09:30-13:30 ET, flat 14:25 ET. Rules (frozen, no parameter search): AG morning EWMA trend lb16 th0.75 (30m, stop 1.5 ATR, 3.5R, hold 8);
AG 30m Donchian breakout lb8 th1.5 (stop 1.25, 5R, hold 8); fixed 15m momentum lb24 (stop 2 ATR, 3R, 24 bars). Training 2010-2023 by year; validation
2024-2025 only for passers; gates as prior rounds (net > 0, >= 10/14 years, largest year <= 40%, >= 95% of 20 random-direction placebos, >= 100 trades).
Also reported: daily P&L correlation of each CL sleeve with the corresponding MNQ sleeve (diversification value), and the combined MNQ+MCL drawdown
against the $2k lock. Prediction written now: CL intraday trend rules are flat-to-negative after 2 ticks of spread (crude is choppier intraday than NQ);
the diversification correlation will be near zero. No spend.
