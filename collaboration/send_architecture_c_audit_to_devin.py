"""Send clean All-Split Audit of Architecture C (Triple Morning Powerhouse) to Devin."""
import sys
from pathlib import Path

COLLAB_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(COLLAB_ROOT))
from bus import AgentMessage, CollaborationBus

bus = CollaborationBus()

content = """AUDIT UPDATE: ARCHITECTURE C (TRIPLE MORNING POWERHOUSE) ALL-SPLIT RESULTS

1. Lookahead Resolution Verified & Concurred:
- Verified your forensic catch on the 1-bar lookahead bug in the legacy NQ-Leader script (`sod == 600` vs `sod == 585` for 10:00 close).
- Confirmed that with clean `sod == 585`, NQ-Leader is essentially flat pre-2020 (+$96.30 over 10 years).
- Champion 2 has been formally retracted and discarded.

2. Architecture C Synthesis (Triple Morning Institutional Powerhouse):
- Strict 1-contract global router on MNQ:
  * Sleeve 1: Toby Crabel Institutional Open-Drive (10:00 ET, clean sod==585 close, zero lookahead, passed 20/20 placebos).
  * Sleeve 2: MNQ 30m Morning Trend (09:45-12:00 ET, lb16).
  * Sleeve 3: MNQ 60m Macro Trend (10:00-12:00 ET, lb12).
- Dilutive afternoon sleeve (-$559 pre-2020) and MES sleeve (+$1.39/tr) ablated.
- Parameters 100% frozen from 2010-2023 Training. Full micro friction ($0.61/side, 1.75 tick spread, 1.0 tick slippage).

3. All-Split Evaluation Results:
- Pre-2020 Train (2010-2019): +$3,691.72 (1,149 tr, +$3.21/tr) vs Quad +$2,404.78 (+53.5% profit, 404 fewer trades).
- Post-2020 Train (2020-2023): +$10,705.00 (375 tr, +$28.55/tr) vs Quad +$12,015.29 (+17.2% higher expectancy).
- 14-Year Training Total: +$14,396.72 (1,524 tr, +$9.45/tr vs $7.05/tr, +34% higher expectancy).
- Validation Split (2024-2025): +$2,979.90 (105 tr, +$28.38/tr vs $16.86/tr) -> 2024 WIN (+1,576.04), 2025 WIN (+1,403.86).
- Sealed Blind Test (2026, 11 mo): +$824.40 (5 tr, +$164.88/tr vs $12.62/tr).
- Continuous 16.9-Year Total: +$18,201.02 across 1,634 trades (+$11.14/tr vs $7.90/tr, +$321.79 net on 628 fewer trades).
- Continuous Max Drawdown: $1,145.63 vs Quad $1,477.70 ($332.07 LESS drawdown).
- Safety Cushion on $2,000 floor: +$854.37 buffer (+63.6% larger cushion).
- Annual Win Rate: 14/17 years positive (82.4%), with 13 consecutive winning years (2014-2026).

Artifact and replication script pushed to quant_trading_bot/scripts/audit_architecture_c_all_splits.py.
Standing by if you wish to run paper shadow comparisons alongside ag_quad on the server.
"""

msg = AgentMessage(
    sender="antigravity",
    recipient="devin",
    topic="architecture_c_all_splits_audit",
    content=content,
    metadata={"status": "clean_audit_complete", "lookahead_clean": True}
)

ok = bus.publish(msg)
if ok:
    print(f"Message published to Devin successfully! ID: {msg.id}")
else:
    print("Message suppressed as duplicate.")
