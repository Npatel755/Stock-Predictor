# CLAUDE.md — Multi-Agent Collaboration Protocol (Claude <-> Antigravity <-> Nick)

Welcome Claude! You are pair programming with **Nick** (User) and working in direct coordination with **Antigravity** (Google DeepMind's advanced agentic coding assistant).

---

## 🌉 THE BI-DIRECTIONAL AGENT BRIDGE

A real-time bridge is active in this workspace between **You (Claude)** and **Antigravity**. You can view each other's complete conversation histories, research findings, code modifications, and strategic decisions.

### 1. How You Read Antigravity's Chat History
Antigravity's conversation history with Nick is continuously mirrored into:
* **Human-Readable Full Transcript**: [`collaboration/ANTIGRAVITY_CHAT_HISTORY.md`](collaboration/ANTIGRAVITY_CHAT_HISTORY.md)
* **Unified Chronological Stream**: [`collaboration/UNIFIED_COLLABORATION_STREAM.md`](collaboration/UNIFIED_COLLABORATION_STREAM.md)
* **Structured Machine-Readable JSONL**: [`collaboration/ANTIGRAVITY_FULL_CHAT_HISTORY.jsonl`](collaboration/ANTIGRAVITY_FULL_CHAT_HISTORY.jsonl)
* **Direct Messages from Antigravity to You**: [`collaboration/ANTIGRAVITY_TO_CLAUDE.md`](collaboration/ANTIGRAVITY_TO_CLAUDE.md)

👉 **Before starting any new research or code changes, read `collaboration/ANTIGRAVITY_CHAT_HISTORY.md`** to see what Nick and Antigravity have already established, verified, or ruled out.

---

### 2. How You Share Your Chat History & Decisions with Antigravity
Whenever you converse with Nick, make an architectural recommendation, or run an analysis, you **MUST** record your turn so Antigravity can see it:

#### Option A: Quick CLI Logging (Recommended)
Run this command in the terminal after your turn:
```powershell
python collaboration/claude_bridge.py --log-claude --prompt "User's request" --response "Your response summary or key findings"
```

#### Option B: Direct Markdown Append
Append your turn to [`collaboration/CLAUDE_CHAT_HISTORY.md`](collaboration/CLAUDE_CHAT_HISTORY.md) in this format:
```markdown
## Turn X — `[YYYY-MM-DD HH:MM:SS UTC]`
### 👤 User (Nick):
> [Prompt from Nick]

### 🤖 Claude Response:
[Your response, recommendations, metrics, and code references]
---
```

#### Option C: Direct Message to Antigravity
If you have a critical question, dispute, finding, or suggestion specifically for Antigravity, drop a note into:
* [`collaboration/CLAUDE_TO_ANTIGRAVITY.md`](collaboration/CLAUDE_TO_ANTIGRAVITY.md) or [`collaboration/inbox/`](collaboration/inbox/)

Antigravity's background bridge daemon monitors these files and reads your input immediately.

---

## 🏛️ CORE TRADING PROJECT INVARIANTS & RULES

When working on `quant_trading_bot`, strictly adhere to these institutional research invariants established by Nick and Antigravity:

1. **Strict Data Partitioning**:
   * **14-Year Training Split (2010–2023)**: The ONLY dataset where parameter tuning, sleeve discovery, and hypothesis testing are permitted.
   * **Validation Split (2024–2025)**: Frozen holdout for validation. NEVER tune on this split.
   * **Blind Test Split (2026)**: Untouched out-of-sample forward test. Zero modifications.

2. **CME Micro Market Microstructure Friction**:
   * Always enforce micro contract economics:
     - Commission: \$0.61 per side (\$1.22 roundtrip).
     - Tick Spread: 1.75 ticks (1.75 * 0.25 pt = 0.4375 pt).
     - Slippage: 1.0 tick entry + 1.0 tick exit (0.50 pt).
     - Total friction: **1.30 pts roundtrip** per contract.

3. **Prop Firm Evaluation Rules ($50k Account)**:
   * **Target**: +$4,000 profit.
   * **Trailing Drawdown Floor**: -$2,000 trailing intraday high-water mark; locks permanently at starting balance ($0.00 profit) once equity reaches +$2,000.
   * **Daily Loss Limit (DLL)**: -$1,000 max loss in a single session.
   * **50% Consistency Rule**: No single day may account for $\ge 50\%$ of total banked profit (enforced by a daily profit cap of +$1,750).

4. **Champion Architecture: Book D+ / Cushion-Staged**:
   * Evaluated across 14 years:
     - Stage 1: 6 MNQ (-$207 stop risk, 95%+ survival, safely under DLL).
     - Stage 2: Scale up to 10–12 MNQ after banking +$1,200 cushion.
     - Multi-Sleeves: Crabel 15m Momentum Continuation + 30m/60m Macro Trend + VIX-gated Overnight Reopen Dip.
     - Reaches **>50% Pass Rate with 0.0% Ruin Rate**.

---

## 🛠️ USEFUL BRIDGE COMMANDS

* Check bridge status:
  `python collaboration/claude_bridge.py --status`
* Sync all histories (Antigravity + Claude + Devin):
  `python collaboration/claude_bridge.py --sync`
* Read latest Antigravity turns:
  `python collaboration/claude_bridge.py --read-antigravity --tail 5`
* Send note to Antigravity:
  `python collaboration/claude_bridge.py --msg-to-antigravity "Your message"`
