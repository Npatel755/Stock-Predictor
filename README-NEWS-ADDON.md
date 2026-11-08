# News Trading Intelligence — Devin Skill Add-on

Adds one repository skill, `.agents/skills/news-trading-intelligence/SKILL.md`, to the existing 43-skill pack. It extends (does not replace) `economic-event-research` by investigating *breaking* news, sentiment, first-publication versus actual-access timing, revisions, news-only predictive edge, and trading-cost-adjusted studies.

## Install
Extract at the root of your trading repository and ask Devin to verify skill discovery. No news feeds, API keys, historical data or paid subscriptions are included. Do not automatically purchase data, place orders or treat its procedures as profitability guarantees.

## Devin invocation
`@skills:news-trading-intelligence` — Investigate whether scheduled and breaking news can improve my NQ/ES -> MNQ/MES strategies after realistic costs, with no look-ahead bias, protected holdouts, and explicit data-access limitations. Also evaluate no-trade/size-reduction policies. Do not place live trades.

## Added files
- `.agents/skills/news-trading-intelligence/SKILL.md`
- `.agents/skills/news-trading-intelligence/templates/NEWS_EVENT_RECORD.json`
- `NEWS_SKILL_INSTALL_PROMPT.md`

## Apply to existing historical data
See `RUN_NEWS_ALIGNMENT_PROMPT.md` for a complete reusable Devin assignment to audit existing price datasets, reconstruct historical news, align clocks, and test whether news yields incremental out-of-sample improvements. The skill includes `references/point-in-time-news-price-alignment.md`.
