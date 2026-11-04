"""Render complete research evidence without opening nominal final returns."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

from .data_pipeline import HERE


def read(name, default=None):
    path = HERE/name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def money(value):
    return '-' if value is None else f'${value:,.0f}'


def pct(value):
    return '-' if value is None else f'{value:.1%}'


def put(name, lines):
    (HERE/name).write_text('\n'.join(lines)+'\n', encoding='utf-8')


def report():
    data, funding = read('data_manifest.json', {}), read('funding_manifest.json', {})
    split = read('split_manifest.json', {})
    train = read('training_results.json', [])
    valid = read('validation_results.json', {}).get('candidates', [])
    baselines = read('validation_results.json', {}).get('baselines', [])
    robust = read('robustness_results.json', [])
    conditional = read('conditional_results.json', [])
    combined = read('combined_validation_results.json', {})
    legacy = read('legacy_comparisons.json', [])
    registry = pd.read_csv(HERE/'experiment_registry.csv') if (HERE/'experiment_registry.csv').exists() else pd.DataFrame()
    accepted = [r for r in valid if r['accepted']]
    conclusion = 'NO STRATEGY approved: development evidence did not meet every frozen acceptance gate.' if not accepted else 'Some candidates passed retrospective development gates; PAPER ONLY pending genuinely new observations.'
    lines = ['# ETH/BNB isolated research results', '', conclusion, '',
             '## Evidence status', '',
             f'- TRAIN: {split.get("train")}; three chronological forward folds; already inspected historical development data.',
             f'- VALIDATION: {split.get("validation_eval_start")} to {split.get("validation", [None,None])[1]}; one frozen shortlist, no failure replacements.',
             f'- FINAL: {split.get("nominal_final")}; contaminated by earlier ETH and BNB searches. No performance evaluation performed in this project.',
             f'- PAPER: {split.get("new_prospective_reservation")}; pending, no live orders or scheduled collection.', '',
             '## Experiment accounting', '',
             f'Primary hypotheses:96 (48 specifications×2 assets); baselines24; conditional model2 and ensemble2 slots. Holm family size124. Training strategy rows completed:{len(train)}. Append-only executed replay records:{len(registry)}.',
             'Stress/ablation runs are diagnostics, never replacements or new accepted winners. Prior848 ETH search slots plus repeated BNB rounds remain additional selection exposure.', '',
             '## TRAIN shortlist evidence', '',
             '| Asset | Candidate | Positive folds | Trades | Worst intrabar bound | Sum of reset-fold P&L | Holm p |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    shortlist = read('validation_shortlist.json', {}).get('selected', [])
    selected_ids = {(r['symbol'],r['id']) for r in shortlist}
    for r in train:
        if (r['symbol'], r['id']) in selected_ids:
            lines.append(f'| {r["symbol"]} | {r["id"]} | {r["train_positive_folds"]}/3 | {r["train_trades"]} | {pct(r["train_worst_drawdown"])} | {money(r["train_sum_reset_account_pnl"])} | {r["train_holm_p"]:.4f} |')
    lines += ['', '## VALIDATION scoreboard', '',
              '| Asset | Candidate | Net | Return | Adverse-cost net | Intrabar bound | Trades | Accepted | Failed gates |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |']
    for r in valid:
        m = r['metrics']
        lines.append(f'| {r["symbol"]} | {r["id"]} | {money(m["net_pnl"])} | {pct(m["net_return"])} | {money(r["adverse_metrics"]["net_pnl"])} | {pct(m["max_intrabar_drawdown"])} | {m["trades"]} | {r["accepted"]} | {", ".join(k for k,v in r["gates"].items() if not v)} |')
    lines += ['', '## VALIDATION baselines', '', '| Asset | Baseline | Net | Return | Intrabar bound | Trades |', '| --- | --- | ---: | ---: | ---: | ---: |']
    for r in baselines:
        m = r['metrics']
        lines.append(f'| {r["symbol"]} | {r["id"]} | {money(m["net_pnl"])} | {pct(m["net_return"])} | {pct(m["max_intrabar_drawdown"])} | {m["trades"]} |')
    lines += ['', '## Fitted components and ensemble', '']
    for r in conditional:
        m = r.get('metrics', r)
        lines.append(f'- {r["symbol"]} {r["kind"]}, {r["phase"]}: {r.get("reason", money(m.get("net_pnl")))}. {r.get("note", "")}')
    if combined:
        m = combined['metrics']
        lines += ['', '## Combined ETH/BNB VALIDATION portfolio', '',
                  f'Frozen first training selection per asset, $25,000 sleeve each: {money(m.get("net_pnl"))} net, {pct(m.get("net_return"))} return, {pct(m.get("max_drawdown"))} close drawdown. Two correlated crypto sleeves do not establish diversification.',
                  f'Observed return correlation: `{combined["correlation"]}`.',
                  'A causal5% per-sleeve entry halt is a stress diagnostic; exits remain enabled. This differs from a single optimized portfolio circuit breaker.']
    lines += ['', '## Original strategy comparisons (separate economics)', '']
    for r in legacy:
        m = r['metrics']
        lines.append(f'- {r["name"]}: marked net {money(m["final_equity"]-m["initial_capital"])}. {r["caveat"]}')
    lines += ['', '## Reproducibility and limits', '',
              '63+ deterministic tests cover next-open order timing, future-data poisoning, higher-timeframe availability, funding, partial exits, data gaps, fitted scalers and frozen paper hashes. See verification.json for the final executed count.',
              'Primary exposure is capped at1x on entry. Signals use completed bars and fill next open; previous completed volume caps fills at0.1%, with partial exits/residual risk. Adverse spread/slippage applies to all market/triggered orders. Historical Binance taker schedules, precision changes, order-book depth and mark-price maintenance tiers are unavailable; costs and filters are explicit scenarios.',
              'Trade and full-resolution equity Parquet, daily return CSV, configs, code/data hashes and attribution JSON are stored per registry trial under outputs/. Terminal forced closes may bypass volume capacity and are flagged. Calendar daily Sharpe annualizes at365.25; bootstrap uses4,999 circular7-day blocks and Holm124. Intervals assume dependent-return stationarity and cannot reverse historical selection contamination.',
              'Signals are computed at each horizon and execution also uses that horizon’s OHLC. Intrabar timing is unresolved; stop-first and conservative adverse equity bounds are approximations. Native5m data supports complete aggregates but is not a tick path.',
              'No fresh final holdout, prospective profit, exchange-specific execution validation or guaranteed future edge is claimed.']
    put('research_summary.md', lines)
    audit = ['# Data audit', '', 'Market: Binance USD-M linear USDT perpetual futures. Spot economics are not mixed into this project.', '',
             '| Asset | Five-minute bars | Missing | Zero-volume | Snapshot SHA256 |', '| --- | ---: | ---: | ---: | --- |']
    for symbol, m in data.get('assets', {}).items():
        audit.append(f'| {symbol} | {m["rows"]:,} | {m["missing_candles"]} | {m["zero_volume_bars"]} | {m["snapshot_sha256"]} |')
    audit += ['', f'Exchange ZIP/checksum pairs validated:{len(data.get("raw_archives", []))}. Original raw ZIPs are read-only external provenance, local clean snapshots remain in isolated data/. Funding raw ZIP/checksum copies are retained locally.', '',
              'UTC candle alignment, unique/conflicting duplicates, OHLC ordering, finite/nonnegative volume, complete history and aggregation counts are checked. No prices are forward-filled. Local hashes show identity, not independent correctness of the exchange.', '',
              '## Funding and missing sources', '']
    for s, m in funding.items():
        audit.append(f'- {s}: {m["rows"]} signed settlement records, SHA256 {m["snapshot_sha256"]}.')
    audit += ['', 'Observed settlement timestamps contain up to47ms processing jitter after nominal8h boundaries. Raw timestamps remain unchanged; settlement eligibility is approximated at the nominal boundary before new entries. Funding signals use the EXACT timestamp plus1hour delay. Payment notional uses candle-open trade prices, not unobserved mark prices. Complete coverage/interval checks run before use.',
              'Open interest excluded: no complete point-in-time source. Historical maintenance/filter/fee schedules absent. Corporate stock splits do not apply to these linear perpetual contracts; contract/exchange convention changes remain a feed-specific limitation.', '',
              'Primary source: https://github.com/binance/binance-public-data ; funding: https://www.binance.com/en/support/faq/detail/360033525031 .']
    put('data_audit.md', audit)
    put('final_holdout_report.md', ['# Final holdout status', '', '**NOT EVALUATED: CONTAMINATED.**', '',
                                    f'Nominal final20%: {split.get("nominal_final")}. Earlier repository ETH/BNB experiments inspected these dates before this research began.',
                                    'The split manifest records contamination before search; the runner forbids performance access at/after the final boundary. Reusing this period would not create an independent final result.', '',
                                    f'Original sealed future window:{split.get("existing_sealed_future")}. It is untouched.',
                                    f'New reserved paper-only window:{split.get("new_prospective_reservation")}. No results are available. Eligibility gates/hashes must remain frozen until its end.', '',
                                    f'Frozen retrospective gate passers:{len(accepted)}. If none pass, the appropriate recommendation is no strategy; failed history is not fixed by relabeling it.'])
    stress = ['# Robustness diagnostics', '', 'Every diagnostic is predeclared and does not choose a replacement after validation.', '',
              '| Asset | Frozen candidate | Scenario | Net | Return | Intrabar bound | Trades |', '| --- | --- | --- | ---: | ---: | ---: | ---: |']
    for r in robust:
        stress.append(f'| {r["symbol"]} | {r["id"]} | {r["scenario"]} | {money(r["net_pnl"])} | {pct(r["net_return"])} | {pct(r["max_intrabar_drawdown"])} | {r["trades"]} |')
    stress += ['', 'Includes increased risk, adverse/crisis costs, delayed orders, entry outages, lower capacity, trailing stops, parameter neighbors, regime ablation,24h lag, seeded randomized daily-sign control, long/short isolation and cross-asset no-refit transfer. The randomized control is a falsification diagnostic, not a tradable rule. Conditional2x is tested only after positive base/adverse results; liquidation remains a last-price proxy.',
               'Repeated timeframes/parameters are correlated; multiplicity adjustment is not a proof of generalization. CPCV/PBO and Deflated Sharpe are not reported because the inherited adaptive trial history is incomplete. All candidate failures remain in strategy_comparison.csv.']
    put('robustness_report.md', stress)
    put('integration_notes_for_devin.md', ['# Integration notes for Devin', '',
         'Everything authored for this task is under research/codex_eth_bnb in branch research/codex-eth-bnb. Original checkout remains outside the write boundary. No production integration is performed.', '',
         'Interfaces: data_pipeline.snapshot/funding/load/resample; strategies.library/build_features/build_signal; execution.simulate(frame,config)->metrics/trades/equity; analytics; runner.Lab; paper.emit_paper_signal. OHLCV timestamps denote UTC candle open. Signal information exists only at candle close; execution consumes previous signal.', '',
         'Reproduction from the dedicated worktree:', '',
         '```powershell',
         "& '../Stock Predictor/.ethvenv/Scripts/python.exe' -m pytest research/codex_eth_bnb/tests -q -p no:cacheprovider",
         "& '../Stock Predictor/.ethvenv/Scripts/python.exe' -m research.codex_eth_bnb.data_pipeline --funding",
         "& '../Stock Predictor/.ethvenv/Scripts/python.exe' -m research.codex_eth_bnb.runner",
         '```', '',
         'Read research_plan.md, candidate_manifest.json, split_manifest.json and code_freeze.json before reproducing. The registry append-only replay key includes config/code/data identity. Repeated identical trials load saved artifacts; frozen manifests reject changes. data/ and outputs/ are git-ignored local artifacts; persist them with checksum manifests when handing off. Source raw archive paths point to the original machine and must be supplied read-only on another machine.', '',
         'Paper interface is local-file only: `python -m research.codex_eth_bnb.paper --config CONFIG.json --bars CANDLES.parquet --asof UTC_TIMESTAMP --output stdout`. It emits desired exposure, not orders. Context input can supply local BTC/peer files. A valid frozen candidate envelope and unchanged code/data manifests are required; no candidate exists if gates fail. Never promote an illustrative/rejected configuration.', '',
         'No API keys, live execution, production imports, unattended jobs or deployment are added. Any future integration requires explicit review and authorization.'])
    scoreboard = [{k: v for k, v in row.items() if k not in ['metrics','adverse_metrics','bootstrap','gates']} |
                  dict(net_pnl=row['metrics']['net_pnl'], net_return=row['metrics']['net_return'],
                       adverse_net=row['adverse_metrics']['net_pnl'], failed_gates=','.join(k for k,v in row['gates'].items() if not v)) for row in valid]
    pd.DataFrame(scoreboard).to_csv(HERE/'validation_scoreboard.csv', index=False)
    print(conclusion, flush=True)


if __name__ == '__main__':
    report()
