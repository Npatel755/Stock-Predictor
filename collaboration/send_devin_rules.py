import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from bus import CollaborationBus, AgentMessage

bus = CollaborationBus()

rules_payload = {
    "info": "Exact frozen rule dicts for replication on fixed engine with early-close handling (applied in src/quant_futures/session_calendar.py)",
    "rules": {
        "MNQ_Trend_1c": {
            "instrument": "MNQ", "family": "trend", "lookback": 6, "threshold": 1.0,
            "stop_atr": 1.75, "target_r": 2.25, "hold_bars": 6, "session_start": 585,
            "session_end": 945, "max_contracts": 1, "trailing_atr": 0.0
        },
        "MES_Mom_1c": {
            "instrument": "MES", "family": "momentum", "lookback": 6, "threshold": 2.0,
            "stop_atr": 1.5, "target_r": 2.25, "hold_bars": 20, "session_start": 585,
            "session_end": 945, "max_contracts": 1, "trailing_atr": 0.0
        },
        "MES_Trend_1c": {
            "instrument": "MES", "family": "trend", "lookback": 6, "threshold": 1.0,
            "stop_atr": 1.5, "target_r": 1.75, "hold_bars": 6, "session_start": 585,
            "session_end": 945, "max_contracts": 1, "trailing_atr": 0.0
        },
        "MNQ_MornBrk_1c": {
            "instrument": "MNQ", "family": "breakout", "lookback": 20, "threshold": 1.25,
            "stop_atr": 1.5, "target_r": 2.5, "hold_bars": 8, "session_start": 600,
            "session_end": 720, "max_contracts": 1, "trailing_atr": 0.0
        }
    },
    "numbers_unstripped": {
        "MNQ_Trend_1c": {
            "train_14y_net_dollars": 6944.42, "train_14y_dd_dollars": 641.04,
            "val_24_25_net_dollars": 1404.64, "val_24_25_dd_dollars": 577.84,
            "val_2024_net_dollars": 1063.60, "val_2025_net_dollars": 341.04
        },
        "Portfolio_Duo_Momentum": {
            "train_net_dollars": 8579.79, "train_dd_dollars": 620.68,
            "val_24_25_net_dollars": 1587.81, "val_24_25_dd_dollars": 895.18,
            "val_cushion_dollars": 1104.82,
            "val_2024_net_dollars": 1554.71, "val_2025_net_dollars": 33.10
        },
        "Portfolio_Tri_Alpha": {
            "train_net_dollars": 14631.90, "train_dd_dollars": 693.50,
            "val_24_25_net_dollars": 2292.68, "val_24_25_dd_dollars": 1369.73,
            "val_2024_net_dollars": 1414.88, "val_2025_net_dollars": 877.80
        }
    },
    "current_direction": "Exploring 30m and 60m higher-timeframe swing rules to decrease scalping, capture 50-150 point moves ($100-$300/tr), and make transaction friction < 1% of trade value. Awaiting your 1m counter-trend results."
}

msg = AgentMessage(
    sender="antigravity",
    recipient="devin",
    topic="rule_replication_payload",
    content=json.dumps(rules_payload, indent=2)
)
ok = bus.publish(msg)
print(f"Dispatched rule payload to Devin. Message ID: {msg.id} (Status: {ok})")
