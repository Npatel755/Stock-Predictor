# QuantConnect Research Map — official/public sources

Updated 2026-11-06. Verify API and licensing details again before implementation. The entries below are research starting points, not evidence of a positive trading edge.

## A. Primary research content
- Strategy Library: https://www.quantconnect.com/docs/v2/writing-algorithms/strategy-library
- Research articles: https://www.quantconnect.com/docs/v2/cloud-platform/community/research
- Community forum documentation: https://www.quantconnect.com/docs/v2/cloud-platform/community/forum
- QuantConnect Research notebooks (GitHub): https://github.com/QuantConnect/Research
- Research Engine / QuantBook: https://www.quantconnect.com/docs/v2/research-environment/key-concepts/research-engine
- Research Pipeline: https://www.quantconnect.com/docs/v2/cloud-platform/research-pipeline

## B. LEAN code and reproducibility
- LEAN engine source: https://github.com/QuantConnect/Lean
- LEAN CLI source: https://github.com/QuantConnect/lean-cli
- LEAN CLI setup: https://www.quantconnect.com/docs/v2/lean-cli/key-concepts/getting-started
- LEAN backtest command: https://www.quantconnect.com/docs/v2/lean-cli/api-reference/lean-backtest
- LEAN local backtest deployment: https://www.quantconnect.com/docs/v2/lean-cli/backtesting/deployment
- LEAN reality models: https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/key-concepts
- LEAN slippage model reference: https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/slippage/supported-models
- LEAN transaction fees: https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/transaction-fees/supported-models

## C. Index futures audit essentials
- Futures requesting data: https://www.quantconnect.com/docs/v2/writing-algorithms/securities/asset-classes/futures/requesting-data
- Futures universe and continuous/mapped distinction: https://www.quantconnect.com/docs/v2/writing-algorithms/securities/asset-classes/futures/requesting-data/universes
- Futures rollover handling: https://www.quantconnect.com/docs/v2/writing-algorithms/securities/asset-classes/futures/handling-data

## D. Tooling integration and permissions
- QuantConnect MCP server overview: https://www.quantconnect.com/docs/v2/ai-assistance/mcp-server
- QuantConnect MCP key concepts & entitlement: https://www.quantconnect.com/docs/v2/ai-assistance/mcp-server/key-concepts
- QuantConnect research agent: https://www.quantconnect.com/docs/v2/ai-assistance/predefined-agents/research-agent
- QuantConnect Research Validation Agent: https://www.quantconnect.com/docs/v2/ai-assistance/predefined-agents/research-validation-agent
- Dataset licensing: https://www.quantconnect.com/docs/v2/cloud-platform/datasets/licensing

## E. Targeted discovery queries
- `site:quantconnect.com/research "dual thrust"`
- `site:quantconnect.com/research "intraday" "breakout"`
- `site:quantconnect.com/docs/v2/writing-algorithms/strategy-library "futures"`
- `site:quantconnect.com/docs/v2/writing-algorithms/strategy-library "momentum"`
- `site:quantconnect.com/forum "NQ" backtest`
- `site:github.com/QuantConnect/Research "Kalman"`
- `site:github.com/QuantConnect/Lean "DataMappingMode"`
- `site:quantconnect.com/research "short term reversal" futures`

## F. Source quality and tooling boundaries
1. Article/paper claims are leads, not independent validation. Reproduction code and valid trade data carry more weight than screenshots.
2. Date-stamp source discoveries, attribute original author, and capture code commit SHA/license when relevant.
3. Publications themselves disclose many historical samples; assume the disclosed dates are already observed, not a pristine test set.
4. Local LEAN CLI backtests may require paid organization tier, Docker and legitimately obtained local data. Check the current official requirements instead of assuming access.
5. QuantConnect MCP remote server requires an eligible paid agent node; the free A-MICRO node cannot connect according to current docs. Do not ask for or log secrets in repository files.
6. Continuous futures are not directly tradable. The continuous series can be an adjusted analytical feed while the mapped individual contract holds raw executable prices.
7. Validate default fee and slippage models against the user's actual brokerage and funded-evaluation rules; defaults are not a guarantee of realistic fills.

## G. Example research starting points (not endorsements)
- Dual Thrust Trading Algorithm: https://www.quantconnect.com/research/15258/dual-thrust-trading-algorithm/
- Strategy Library entries: Dynamic Breakout II, Short Term Reversal with Futures, Commodities Futures Trend Following, Intraday ETF Momentum, asset-class momentum, volatility-aware strategies. Use their source pages for exact rules and references before any implementation.
- Open notebook repository contains historical notebooks on mean reversion, pairs trading, Kalman filters, hidden Markov models, and more; many are demonstrations rather than verified live strategies.
