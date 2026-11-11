# CLAUDE.md — Multi-Agent Collaboration Protocol (Claude <-> Antigravity <-> Nick)

Welcome Claude! You are pair programming with **Nick** (User) and working in direct coordination with **Antigravity** (Google DeepMind's advanced agentic coding assistant).

---

## 🧰 BEFORE EVERY TASK: CHECK SKILLS & TOOLS FIRST

Whenever Nick sends you anything (a request, a file, a link, a zip, a pasted message), do this **first**, before planning or writing code:

1. **Match skills.** Go through the available skills and pick every one whose description fits the task. Load each with the Skill tool and follow it. Skills live in:
   * `~/.claude/skills/`: your personal skills. This includes the 43 quant research skills plus `news-trading-intelligence` (e.g. `walk-forward-validation`, `overfitting-defense`, `statistical-evidence-auditor`, `risk-of-ruin-monte-carlo`, `quantconnect-strategy-forensics`) and the general pack (`strategy-backtest-lab`, `trade-risk-sizing`, `stock-research-scan`, ...).
   * `.agents/skills/` in this repo: Devin/Codex copies of the same quant skills. Claude Code does not load these; if you edit a quant skill, mirror the change to the other copy.
2. **Match tools.** Work out which tools the task needs, including deferred tools (load them with ToolSearch). Before writing a new script, check for existing ones in `quant_trading_bot/scripts/`, `quant_trading_bot/src/` and `collaboration/claude_bridge.py`.
3. **Say what you picked.** Start your reply with one line naming the skills and tools you're using, or "No matching skill" if none fit.

---

## 🔍 CLAUDE'S ROLE: REVIEW ANTIGRAVITY + CO-DEVELOP STRATEGIES

Set by Nick on 2026-11-09. Reviewing Antigravity used to be Devin's job; it's now yours.

1. **Check Antigravity's work every session.** Read its latest turns (`python collaboration/claude_bridge.py --read-antigravity --tail 5`) and any new scripts or results. For each claim, check that it is feasible under the real account rules and not inflated:
   * Does the number trace to a results file, and to the code that produced it?
   * Does the code do what the variant's label says?
   * Was it run on the training split only?
   * Are the friction costs applied?
2. **Critique only what the evidence supports.** Don't invent objections just to have something to say. If a claim checks out, say so in one line. When something is wrong, cite the file, line and number, and send Antigravity a note through the bridge (`--msg-to-antigravity`).
3. **Develop strategies alongside Antigravity**, not only review its work.

**Current goal (Claude's job): a funded-account payout strategy that gets 12 payouts a year (one a month)** on a **Topstep 50K funded account** (static $2,000 drawdown, $1,000 daily loss limit). A payout needs 5 trading days (not necessarily consecutive) with **net P&L ≥ $150** after friction, so the target is about **60 qualifying days a year, with real profit to withdraw each cycle**. Qualifying days without edge are worthless (see payout_2 in `research/strategy_memory/lessons.md`). Survival comes first, because a blown account produces no more payouts. Antigravity's separate job is passing the $4,000 evaluation as fast as possible.

**Official Rulebook File (Topstep Drop #011 - $50K Static Daily Payouts Combine):**
- Drop-in JSON for `propsim.py` / `load_rulebooks()`: [`collaboration/topstep_50k_static_daily.json`](collaboration/topstep_50k_static_daily.json)
- Full Modeling Spec: [`collaboration/TOPSTEP_50K_STATIC_DAILY_PAYOUTS_DROP011_SPEC.md`](collaboration/TOPSTEP_50K_STATIC_DAILY_PAYOUTS_DROP011_SPEC.md)
- Parameters: **$149 one-time purchase**, **$0 monthly**, **$0 activation**, **+$4,000 target**, **-$2,000 STATIC floor (never trails)**, **-$1,000 DLL (strictly active)**, **$8,000 payout cap**, daily payouts above $2,000 buffer. Resets cost $149 each; **target is 0.0 resets paid**.

**Status (2026-11-10, overnight):** best measured per 50K account at today's prices is v5.2 + the stopped overnight leg (night leg on above ~$500): ~6.2 payouts/yr, 0.7% 12-month breach, ~11% if volatility stays 1.5x for a year. 12/yr = two accounts. Details and caveats: `quant_trading_bot/reports/PAYOUT_OVERNIGHT_2026-11-10.md`. All price-level results assume training's % behaviour repeats at NQ ~28k; forward paper decides. **Update (2026-11-10, later):** those figures used a floor that never moves. On Topstep's funded accounts any payout sets the floor to $0. On the **$50K Static Daily Payouts+** account (static -$2,000 until the first payout, daily payouts of profit above a $2,000 buffer), the same book withdrawing daily while keeping $4,000 gives ~9.9 payouts in year 1 (7.1 for 2010-16 starts), 0.7% closed (3.3% / 7.3% stressed), and ~17.7 payouts / ~$10.4k in year 2. On the standard XFA (floor trails, then $0) it gives ~5 payouts with 5% closed. **Adopted (payout_24):** on that account, trade 1 micro below a $4,000 balance and 2x from $4,000, withdrawing daily only above $6,000: ~$25.3k withdrawn per 24 months (+57% vs 1x), 9.5 payouts in year 1 and 19.7 in year 2, 0.7% closed (S3 3.6%, S4 6.5%). Holdout (one-shot, frozen, 2024-26, now spent): validation 16 payouts / $12.9k, test +$7.4k book, account not closed but came within ~$400 of the floor twice. **Evaluation:** the same book at 3x passes the $4k static Combine within 90 days in ~53% (training) / 39% (2024-25) / 59% (2026) of starts. Challenger on paper since 2026-11-10 (eval_8, chosen post hoc on training): v5.3 + MNQ_BRK_E_2c + MES_MOM_3c, 3x / 2x at -$500 / 1x at -$1,000 / 5x from day 60 if > $1,000 short = 60.0% training; eval_9-11 (DP sizing, risk plumbing, calendar legs, sleeve weights) found nothing better, so ~60% per attempt is this book's ceiling. Promotion triggers are in the replay docstring. Paper replay of both tracks: `scripts/paper_account_static_daily.py` (runs after every paper run), now on **v5.3** (= v5.2 without the TRD30PM afternoon sleeve; Nick's choice 2026-11-10 as a safety trade: -4% dollars, near-misses 2.9% -> 0.7%; `reports/V53_IMPROVE_TRAINING.json`). Funded rule on paper since 2026-11-10: **Fortress 4X** (1x <$4k, 2x from $4k, 3x from $4.8k, 4x from $6.5k, size trimmed to $900 risk, daily payouts above $8.5k): training $35.2k per 24 months vs $25.9k, same closures, conservative S4 9.4%, but year-1 payouts 8.3 and median first payout ~257 days (`reports/CHECK_FORTRESS_4X_TRAINING.json`). See `research/strategy_memory/lessons.md` (payout_20-24, eval_1).

---

## 🌉 THE BI-DIRECTIONAL AGENT BRIDGE

A real-time bridge is active in this workspace between **You (Claude)** and **Antigravity**. You can view each other's complete conversation histories, research findings, code modifications, and strategic decisions.

### 1. How You Read Antigravity's & Devin's Chat History
Everything discussed, proved, and implemented is mirrored live in the repository:
* **Antigravity Complete Transcript (148 turns)**: [`collaboration/ANTIGRAVITY_CHAT_HISTORY.md`](collaboration/ANTIGRAVITY_CHAT_HISTORY.md)
* **Devin Complete Transcript (756 messages)**: [`collaboration/DEVIN_CHAT_HISTORY.md`](collaboration/DEVIN_CHAT_HISTORY.md)
* **Unified Chronological Stream (1,026+ events)**: [`collaboration/UNIFIED_COLLABORATION_STREAM.md`](collaboration/UNIFIED_COLLABORATION_STREAM.md)
* **Executive Catch-Up Memo for You**: [`collaboration/ANTIGRAVITY_TO_CLAUDE.md`](collaboration/ANTIGRAVITY_TO_CLAUDE.md)
* **Machine-Readable JSONL Logs**:
  - `collaboration/ANTIGRAVITY_FULL_CHAT_HISTORY.jsonl`
  - `collaboration/DEVIN_FULL_CHAT_HISTORY.jsonl`

👉 **Start by reading [`collaboration/ANTIGRAVITY_TO_CLAUDE.md`](collaboration/ANTIGRAVITY_TO_CLAUDE.md)** for a structured executive summary of all 148 Antigravity turns and 756 Devin messages.

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
   * **Static Drawdown**: the account fails if equity ever touches -$2,000 from the starting balance ($48,000). The floor does **not** trail. Nick uses Topstep's static drawdown option, which is why the target is $4,000. *(Older simulators model a trailing floor. For the Book D+ baseline the difference is small: 33.6% pass static vs 33.2% trailing.)*
   * **Daily Loss Limit (DLL)**: -$1,000 max loss in a single session.
   * **50% Consistency Rule**: No single day may account for $\ge 50\%$ of total banked profit (enforced by a daily profit cap of +$1,750).

4. **Best evaluation result so far: Book D+ at fixed 6 MNQ** (training split 2010–2023, $4k target):
   * Sleeves in `research_evaluation_supercharged_train.py`: AG_CRABEL15 (15m momentum), AG_MES_TRD30 (30m trend), AG_TRD60 (60m trend). Crabel continuation trades at 6 contracts, everything else at 3.
   * **~33% pass, ~4.5–4.9% ruin**. The other ~62% of starts are still open at the end of the window (neither passed nor blown).
   * **⚠ "Days" in these results are days with a trade, not trading days.** Book D+ trades on only 1,098 of the 3,397 sessions in the split (32%), and the evaluation scripts step only through trade days. So the "90-day window" is really about 280 trading days (~13 months), and "median 27 days to pass" is about 84 trading days (~4 months), not ~5 weeks. Affected: `research_evaluation_supercharged_train.py`, `research_pass_rate_above_50_train.py`, `research_arch_d_plus_pass_rate.py`, `research_multi_sleeve_time_to_pass_train.py`, `generate_cushion_staged_chart.py`, `simulate_optimal_eval_strategy_train.py`. `audit_evaluation_horizons_train.py` steps through real sessions and is correct. New simulators must step through every trading session.
   * **Baseline for the $150-day goal** (Claude, 2026-11-09; funded, static $2k drawdown, no target): about **1.1 days per month with net ≥ $150** (mean; median ~0.7), with **11.3% of accounts blown** within ~13 months. Stopping for the day at +$150 barely changes this, because most trade days have only one trade.
   * **Cushion-staged scaling (6 → 10–12 MNQ after +$1,000–1,200) made things worse** in every variant tested: 8–22% pass, 12.6–22.7% ruin.
   * No tested configuration has reached 50% pass, and none has 0% ruin.
   * Sources: `quant_trading_bot/reports/RESEARCH_PASS_RATE_ABOVE_50.json`, `quant_trading_bot/reports/EVALUATION_SUPERCHARGED_RESULTS.json`.
   * *Corrected 2026-11-09 by Claude: this section used to claim ">50% pass rate with 0.0% ruin" for 6 → 10–12 MNQ staging. No results file supports that; Antigravity's own run of that config gave 14.6% pass / 19.6% ruin.*

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
