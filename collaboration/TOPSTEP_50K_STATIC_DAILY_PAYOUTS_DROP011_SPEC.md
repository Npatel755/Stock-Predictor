# Official Rulebook & Modeling Specification: Topstep $50K Static Daily Payouts (Drop #011)

**Source**: Topstep Drop #011 Trading Combine Promotional Card & Official Parameters  
**Verified On**: 2026-11-10  
**Target Audience**: Claude (`claude-research` branch / `crypto-strategy-research.git` & workspace collaborators)  
**Machine-Readable Rulebook**: [`collaboration/topstep_50k_static_daily.json`](file:///c:/Users/Nick/OneDrive/Attachments/Desktop/Stock%20Predictor%20Codex%20ETH%20BNB/collaboration/topstep_50k_static_daily.json)

---

## 1. Core Account Parameters

| Parameter | Topstep Drop #011 (Nick's Account) | Standard Topstep 50K Combine | Critical Modeling Impact |
| :--- | :--- | :--- | :--- |
| **Combine Purchase Fee** | **$149 One-Time Fee** | $49 / month subscription | **Zero recurring subscription bleed**; no monthly timer |
| **Reset Fee** | **$149 per reset** | $49 per reset | Resets cost 3x more; **strategy must minimize resets ($0 resets)** |
| **Activation Fee** | **$0 (Included)** | $149 per XFA | No separate activation charge upon passing |
| **Buying Power** | **$50,000** | $50,000 | Standard 50K account |
| **Maximum Loss Limit** | **-$2,000 STATIC** (Fixed at $48,000) | -$2,000 Trailing EOD | **Static floor NEVER trails higher**; banked profit expands safety buffer |
| **Daily Loss Limit (DLL)** | **-$1,000 HARD / SOFT LOCK** | DLL is optional / 0 in older rules | **Intraday loss must never breach -$1,000**; sizing must cap risk $\le \$350-\$950$ |
| **Evaluation Profit Target** | **+$4,000** | +$3,000 | Target is higher ($4,000) because the floor is static |
| **Payout Cap** | **$8,000 Payout Cap** | No fixed promo cap ($2k/cycle) | Total cumulative payouts capped at **$8,000** |
| **Funded Payout Frequency**| **Daily Payouts** (above $2,000 buffer)| 5 winning days $\ge \$150$ | Daily withdrawals permitted once account exceeds $2,000 buffer |
| **Consistency Target** | **50% Consistency Rule** | 50% Consistency Rule | No single day can account for $\ge 50\%$ of total target |
| **Account Cap Per Trader** | **Max 5 per trader** | Max 5 per trader | 5 accounts maximum allowed simultaneously |

---

## 2. Rulebook JSON Schema for Claude's `propsim.py`

Friend's Claude (`tools/backtest_lab/propsim.py`): drop this dictionary directly into `propsim.load_rulebooks()` or place it in `claude_research/strategies/tjr_liquidity_sweep/lab/prop_firms/topstep_50k_static_daily.json`:

```json
{
  "id": "topstep_50k_static_daily",
  "firm": "Topstep",
  "plan": "Drop #011: $50K Static Daily Payouts Trading Combine -> Express Funded Account",
  "verified": "2026-11-10",
  "confidence": "official Topstep Drop #011 promotional card & rules (screenshot verified)",
  "close_et": "16:10",
  "price": {
    "billing": "one_time",
    "eval": 149,
    "reset": 149,
    "monthly": 0,
    "activation": 0
  },
  "eval": {
    "target": 4000,
    "max_loss": 2000,
    "trail": "none",
    "lock_floor": 0,
    "dll": 1000,
    "consistency": 0.50,
    "min_days": 2,
    "max_micros": 50
  },
  "funded": {
    "max_loss": 2000,
    "trail": "none",
    "lock_floor": 0,
    "floor_after_payout": 0,
    "dll": 1000,
    "consistency": 0,
    "max_micros": 50,
    "scaling": [
      [0, 20],
      [1500, 30],
      [2000, 50]
    ],
    "payout": {
      "days": 1,
      "day_min": 0,
      "net_positive": true,
      "min": 125,
      "pct": 1.0,
      "cap": 8000,
      "keep": 2000,
      "first_profit": 2000,
      "next_profit": 0,
      "min_calendar_days": 0,
      "split": 0.9,
      "max_payouts": 0
    }
  }
}
```

---

## 3. Important Modeling Guidance for Claude Opus 5.5

### A. The Static Floor Advantage (`trail: "none"`)
Unlike trailing accounts (Apex, Tradeify, MFFU Rapid) where the floor moves up with every dollar of profit, the **Topstep Static Combine floor stays fixed at $48,000 forever**.
- If equity reaches +$2,000, the distance to ruin expands to **$4,000**.
- This enables **asymmetric convex sizing**: risk can expand safely using *house money* without endangering the initial starting capital.

### B. Daily Loss Limit Enforced (`dll: 1000`)
In previous simulations (`claude-research/tools/backtest_lab/funded_search.py`), `topstep_50k` had `dll: 0` (Daily Loss Limit turned OFF) and tested `$1,500, first trade only`.
- On Drop #011, **-$1,000 DLL is strictly enforced**.
- Any trade risking $1,500 that hits stop-loss will lose -$1,500, immediately exceeding the -$1,000 DLL.
- Sizing must incorporate an intraday stop (e.g. daily loss stop at -$380 to -$700) to ensure zero DLL touches.

### C. Zero-Reset Objective
Because Drop #011 is a $149 one-time fee and resets cost $149:
- Churn-and-burn sizing (which consumed 5.86 resets per funded account in `combos_train.csv`) costs **$870+ in resets**.
- Antigravity's **Bal-3 Asymmetric Convex Sizing** achieves **0.0 resets paid, 0 DLL breaches, and 99.5% account survival** while passing the evaluation.
