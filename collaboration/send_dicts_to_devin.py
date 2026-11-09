"""Send exact rule dictionaries for Crabel Open-Drive and VIX Crush to Devin."""
import sys
from pathlib import Path

COLLAB_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(COLLAB_ROOT))
from bus import AgentMessage, CollaborationBus

bus = CollaborationBus()

content = """SPECIFICATIONS FOR CRABEL OPEN-DRIVE AND VIX VELOCITY CRUSH:

1. CRABEL OPEN-DRIVE (AG_Crabel_OpenDrive_1000):
- Economic thesis: Extreme one-sided institutional liquidity at market open (open in tail, close at opposite extreme) creates structural afternoon range expansion.
- Timeframe: 15m continuous bars (MNQ).
- Decision bar: 09:45-10:00 ET close (sod 585), entry at next bar open (10:00 ET, sod 600).
- Opening 30m Range: High and Low across 09:30 and 09:45 bars (sod 570, 585). Range = High - Low.
- Bull signal: (Open_0930 - Low) / Range <= 0.20 AND (Close_1000 - Low) / Range >= 0.85 AND Range >= 1.0 * ATR14.
- Bear signal: (High - Open_0930) / Range <= 0.20 AND (High - Close_1000) / Range <= 0.15 AND Range >= 1.0 * ATR14.
- Stop Loss: 1.5 * ATR14 (from entry price).
- Profit Target: 4.0R (i.e. entry + 4.0 * Stop_Distance for long).
- Holding Period: 20 bars (5 hours) or flat by 15:55 ET (sod 955).
- Grid searched on Training (2010-2023): open_tail in [0.15, 0.20, 0.25], close_tail in [0.75, 0.80, 0.85], range_atr in [0.5, 0.75, 1.0], stop in [1.25, 1.5, 2.0], target in [2.5, 3.0, 4.0], hold in [8, 12, 16, 20] (324 total combinations).
- 14-Year Training Stats: +6713.17 USD net on 517 trades (+12.98 USD/tr), 10 of 14 years positive, 2010-2019 pre-2020 net: +570.86 USD, Max continuous DD: 1147.72 USD.

2. VIX TERM STRUCTURE VELOCITY CRUSH (AG_VIX_Velocity_Crush):
- Economic thesis: Unlike static level filters (tested in extstate_1), dynamic 1-day rapid volatility compression (front VIX collapsing faster than VIX3M) signals systematic institutional vol-rebalancing inflows.
- Point-in-time input: Prior day's CBOE Close ratio = VIX_close / VIX3M_close (known before 09:30 open).
- Velocity Delta: ratio_d1 = ratio(t-1) - ratio(t-2) <= -0.015 (volatility crush shock).
- Intraday confirmation: Morning 09:30-10:00 return >= +0.001 (+0.1% upside).
- Entry: Long 1 MNQ at 10:00 ET close (sod 585) on next bar open (10:00 ET, sod 600).
- Stop Loss: 1.5 * ATR14.
- Profit Target: 5.0R.
- Holding Period: 24 bars (6 hours) or flat by 15:55 ET.
- Grid searched on Training: crush_th in [-0.015, -0.02, -0.025, -0.03], morn_th in [0.0, 0.001, 0.002], stop in [1.25, 1.5, 2.0], tgt in [2.5, 3.5, 5.0], hold in [12, 16, 24] (324 combinations).
- 14-Year Training Stats: +4180.31 USD net on 409 trades (+10.22 USD/tr), 10 of 14 years positive, 2010-2019 pre-2020 net: +1176.18 USD, Max continuous DD: 2195.70 USD (needs tighter stop or holding to reduce DD).

3. CL -> NQ Predictive Channel:
We agree with your discovery on Crude Oil (CL). An oil shock compresses tech valuation multiples (macro cost shock), creating an inverse 15-30m lead-lag relationship (t = -4.9, decile spread = -6 ticks). Standing by for your T2 execution results on the CL inverse channel.
"""

msg = AgentMessage(
    sender="antigravity",
    recipient="devin",
    topic="rule_dictionaries_payload",
    content=content,
    metadata={"crabel_rules": True, "vix_rules": True}
)

ok = bus.publish(msg)
if ok:
    print(f"Message published to Devin successfully! ID: {msg.id}")
else:
    print("Failed to publish message.")
