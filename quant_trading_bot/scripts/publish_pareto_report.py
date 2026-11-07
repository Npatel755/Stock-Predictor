"""Describe the completed refinement without changing the earlier study record."""
import json


def publish(root, study):
    best = study["best_selected"]
    metrics = best["metrics"]
    followup = study.get("profit_drawdown_followup", False)
    filename = "PROFIT_DRAWDOWN_FOLLOWUP.md" if followup else "PARETO_REFINEMENT.md"
    counter = (f"{study['selected_replays']} continuous reference replays and {study['selected_replays']} MNQ replays"
               if followup else f"{study['screen_attempts']} reference settings screened, {study['selected_replays']} selected MNQ replays")
    summary = (
        f"MNQ {'profit/drawdown follow-up' if followup else 'entry-filter/protective-stop refinement'}: **{counter}**. "
        f"The higher-profit/no-worse-drawdown goal was **{'met' if study['goal_met'] else 'not met'}**. "
        f"Retained selection: **${metrics['net_pnl']:,.2f} net / ${metrics['max_drawdown']:,.2f} closing drawdown / "
        f"${metrics['max_intraday_drawdown_bound']:,.2f} adverse-intrabar bound**. "
        "These are reused 2024–2025 selection results; no 2026 test prices were accessed."
    )
    lines = ["# MNQ profit and drawdown research", "", summary, "",
        ("The user saved the $5,779.50 net / $1,920 drawdown candidate and accepted drawdown below $2,000. "
        "That anchor triggered the original $1,900 risk stop and ceased trading early; its result is retained as observed. "
        f"The follow-up freezes {study['selected_replays']} settings. {study['design']} "
        "The aim is higher profit and lower drawdown than the saved anchor, completing the period without a base-case shutdown. "
        "[Saved high-profit candidate](saved_candidates/refine_41d93a46b7/candidate.json) · "
        "[Saved lower-drawdown candidate](saved_candidates/refine_1ea7bbf061/candidate.json)."
        if followup else
        "The benchmark is the previously selected two-contract strategy: $4,451 net, $1,638 closing-equity drawdown and $1,649 adverse-intrabar drawdown bound. "
        "The fixed grid varies opening-gap bounds, minimum opening momentum, five protective-stop policies, 3:1/4:1 targets and two/three contracts. "
        "Stop changes use prior completed closes and never loosen a stop. Execution retains integer fills, volume participation, fees, adverse price adjustments and continuous account risk gates."), "",
        ("These settings are explicitly selected after examining reused 2024–2025 results. Each receives a continuous NQ 2022–2023 reference replay. "
        "Earlier 2010–2021 screens from the parent study are retained as context; new sizing rules do not have complete continuous-account verification over that earlier period. "
        "Sizes use only preceding completed equity and peak; existing positions are not resized retroactively. "
        "Stops use only prior completed closes and never loosen. Integer fills, costs and risk gates are replayed. "
        "No 2026 prices were loaded, and this is not independent confirmation."
        if followup else
        "Reference screening uses original NQ 2010–2023 history; 2022–2023 supplies internal ranking. "
        "The top eight settings plus predeclared protective anchors were frozen before actual MNQ 2024–2025 replays. "
        "Independent-trade screens are approximate; selected settings also receive full continuous 2022–2023 reference replay. "
        "Older 2010–2021 evidence remains an approximate screen, not a continuous account verification. "
        "Every additional selection on these years increases overfitting risk. The consumed 2026 final test is unchanged."), "",
        ("The user goal requires profit above $5,779.50, both closing and adverse-intrabar drawdown below $1,920 (and the user's $2,000 ceiling), and no base-case permanent shutdown. "
        "Cost/evidence qualification additionally requires positive years, at least 100 trades, positive 2×-cost profit and both 2× drawdowns below $2,000 without shutdown. "
        "A base-case improvement can meet the user goal while failing these additional checks."
        if followup else
        "Passing requires net profit above $4,451, closing drawdown at most $1,638, intrabar drawdown at most $1,649, "
        "no permanent shutdown, positive results in both selection years, at least 100 trades, and positive 2×-cost profit with both drawdowns below $2,000 and no shutdown. "
        "Long-history and confidence evidence are separate checks. No result has independent forward confirmation or deployment eligibility."), "",
        "| Candidate | Gap range | Min momentum | Protection | Sizing | Contracts | Stop | Target | Exit ET | Net | Close DD | Intrabar DD | Trades | 2× net | Base goal | All checks |",
        "|---|---|---:|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|"]
    fresh = [row for row in study["validation_results"] if not row.get("reused_parent_result")]
    for row in sorted(fresh, key=lambda item: item["metrics"]["net_pnl"], reverse=True):
        p, m = row["candidate"], row["metrics"]
        sizing = p['sizing'] + (" " + str(p['taper_thresholds']) if 'taper_thresholds' in p else "")
        lines.append(f"| {row['candidate_id']} | {p['gap_low']}–{p['gap_high']} | {p['momentum_min']} | {p['protection']} | {sizing} | {p['contracts']} | {p['stop_points']} | {p['payoff']} | {p['exit_minute']//60:02d}:{p['exit_minute']%60:02d} | ${m['net_pnl']:,.2f} | ${m['max_drawdown']:,.2f} | ${m['max_intraday_drawdown_bound']:,.2f} | {m['trades']} | ${row['stress']['2']['net_pnl']:,.2f} | {row.get('base_goal_met', row['selection_qualified'])} | {row['selection_qualified']} |")
    lines += ["", "## Selection failures", ""]
    for row in fresh:
        failed = ", ".join(key for key, passed in row["checks"].items() if not passed) or "none"
        evidence = ", ".join(key for key, passed in row["evidence_checks"].items() if not passed) or "none"
        lines.append(f"- `{row['candidate_id']}` — selection failures: {failed}; unresolved evidence: {evidence}.")
    lines += ["", "## Retained result", "",
        f"Candidate: `{best['candidate_id']}`. Parameters: `{json.dumps(best['candidate'], sort_keys=True)}`.", "",
        f"Annual net: `{json.dumps(best['annual_pnl'], sort_keys=True)}`. Evidence checks: `{json.dumps(best['evidence_checks'], sort_keys=True)}`.", "",
        "| Cost multiplier | Net | Close DD | Intrabar DD | Permanent shutdown |",
        "|---|---:|---:|---:|---|"]
    for factor, m in best["stress"].items():
        lines.append(f"| {factor}× | ${m['net_pnl']:,.2f} | ${m['max_drawdown']:,.2f} | ${m['max_intraday_drawdown_bound']:,.2f} | {m['permanent_risk_lock']} |")
    lines += ["", f"Run artifacts: `{study['path']}`. The carried benchmark is a prior result and is excluded from new-trial counts.", "",
        f"[Interactive charts](research_charts.html) · [Machine-readable results]({'latest_profit_drawdown_followup.json' if followup else 'latest_pareto_refinement.json'})", ""]
    (root/"reports"/filename).write_text("\n".join(lines), encoding="utf-8")
    return summary
