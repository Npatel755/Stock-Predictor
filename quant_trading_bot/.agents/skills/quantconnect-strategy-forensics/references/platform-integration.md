# QuantConnect access paths — avoid assuming permissions

## Free/public investigation
- Browse official Strategy Library, public research articles, QuantConnect docs, forums and GitHub notebooks/code. Respect licenses and attribution.
- The public LEAN engine GitHub repository is code, not a licensed futures historical data package.
- Research notebooks can contain demonstrations dependent on cloud-only or licensed datasets.

## Authorized QuantConnect Research / LEAN CLI
- QuantBook is available in the Research Environment for historical-data exploration; verify account, data access and chosen local/cloud environment.
- LEAN CLI supports local research and backtests when installed/configured; commands can need Docker and an eligible paid organization tier. Run `lean backtest "Project"` only after checking current official docs, project state, data entitlements and any costs.
- Prefer the user's existing data and research code if available. Do not duplicate large datasets or silently change engine versions.

## QuantConnect MCP
- Official docs: https://www.quantconnect.com/docs/v2/ai-assistance/mcp-server
- Key concepts: https://www.quantconnect.com/docs/v2/ai-assistance/mcp-server/key-concepts
- The QuantConnect MCP connects approved agent clients to the QuantConnect API; official listing includes Devin Desktop, but this does not establish that every Devin agent session supports or has configured it.
- A paid eligible agent node is required for the remote MCP according to current QuantConnect docs; the free A-MICRO agent node does not support the remote connection.
- Discover actual available MCP tools and their schemas at runtime. Avoid assuming `backtest`/`project`/`research` actions exist if not exposed.
- Never store credentials/tokens in repo, logs, skill text or chat output. Ask for user-approved secure setup in a supported client.
- Creating paid backtests, deploying live algorithms, modifying organizations, purchasing data, or touching brokerage accounts requires explicit prior approval. No live trading is authorized by installation of this skill.

## Source integrity
- Always distinguish direct quote / original code / own paraphrase / derived hypothesis / independently reproduced result.
- Keep a dated visited source log and a code provenance record. Do not claim a complete QuantConnect audit without a coverage ledger.
