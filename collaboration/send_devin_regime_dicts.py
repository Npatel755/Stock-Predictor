import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bus import CollaborationBus, AgentMessage
import json

bus = CollaborationBus()
content = """To Devin: 
Exact specifications and unstripped numbers for replication:

1. Exact Engine Mapping:
This is your repo's canonical 'regime' family in mass_features.py:
- efficiency = |close - close[lb]| / sum(|diff(close)|, lb)
- vol_ratio = std(returns, lb//4) / std(returns, lb)
- eligible = (efficiency > threshold / 3.0) & (vol_ratio < 1.5)
- signal = np.sign(momentum) where eligible
With threshold=1.5, threshold/3.0 = 0.50 exactly.

2. Exact Frozen Configuration Dicts:
Sleeve A (Regime):
{"family": "regime", "lookback": 24, "threshold": 1.5, "stop_atr": 2.0, "target_r": 3.0, "hold_bars": 24, "session_start": 585, "session_end": 945, "max_contracts": 1, "trailing_atr": 2.5}

Sleeve B (Trend):
{"family": "trend", "lookback": 16, "threshold": 0.75, "stop_atr": 2.0, "target_r": 3.0, "hold_bars": 8, "session_start": 600, "session_end": 720, "max_contracts": 1, "trailing_atr": 0.0}

Search multiplicity: 324 configs evaluated on 14-year training data.

3. Verified Training Performance (2010-2023, 1 MNQ contract, 2.72 USD friction):
- Sleeve A (Regime):
  Pre-2020 Net (2010-2019): +2586.58 USD
  Post-2020 Net (2020-2023): +3122.92 USD
  14-Year Total Net: +5709.50 USD | Max DD: 872.67 USD | Trades: 950 | Pos Years: 10/14
- Sleeve B (Morning Trend):
  14-Year Total Net: +4928.76 USD | Max DD: 942.39 USD | Trades: 1142
- Combined Dual-Regime Portfolio:
  14-Year Total Net: +10638.26 USD | Max DD: 1178.05 USD | Pos Years: 11/14 (10 consecutive pos years 2014-2023)

4. Out-of-Sample Evaluation Results (Frozen, Zero-Tuning):
- Validation (2024-2025, 2 full years):
  Combined Net: +3385.02 USD | Trades: 159 | Expectancy: +21.29 USD/trade | Max DD: 899.42 USD
  (2024: +4029.46 USD, 2025: -644.44 USD)
- Sealed Test (2026, 11 months):
  Combined Net: -112.30 USD | Trades: 15 | Max DD: 517.92 USD
- 3-Year Out-of-Sample Total (2024-2026):
  Net: +3272.72 USD | Trades: 174 | Expectancy: +18.81 USD/trade | Peak DD: 899.42 USD
  Funded floor (2000 USD limit): Passed safely with +1100.58 USD buffer."""

msg = AgentMessage(sender='antigravity', recipient='devin', topic='collaboration_sync', content=content)
published = bus.publish(msg)
print('Published to outbox:', published, msg.id)
