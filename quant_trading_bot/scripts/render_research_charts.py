"""Self-contained interactive charts from measured, registered validation runs."""
from pathlib import Path
import json
import html
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from plotly.offline import get_plotlyjs
from quant_futures.research import json_write
from research_inventory import inventory

ROOT = Path(__file__).resolve().parents[1]
counts = inventory(ROOT)
json_write(ROOT/"reports/strategy_counts.json", counts)
sections = []
latest_path = ROOT/"reports/post_final_research_summary.json"
latest = json.loads(latest_path.read_text()) if latest_path.exists() else None
risk_path = ROOT/"reports/latest_risk_expansion_study.json"
risk_study = json.loads(risk_path.read_text()) if risk_path.exists() else None
refinement_path = ROOT/"reports/latest_pareto_refinement.json"
if refinement_path.exists():
    risk_study = json.loads(refinement_path.read_text())
followup_path = ROOT/"reports/latest_profit_drawdown_followup.json"
if followup_path.exists():
    risk_study = json.loads(followup_path.read_text())
baseline_label = "Previous $4,451 benchmark" if risk_study and risk_study.get("pareto_refinement") else "Original one-contract baseline"
if risk_study and risk_study.get("profit_drawdown_followup"):
    baseline_label = "Saved $5,779.50 result (risk stopped)"
if risk_study:
    latest = dict(studies=[risk_study["path"]], leading_observed_candidate=dict(transfer="NQ->MNQ", **risk_study["best_selected"]))
latest_curve_html = None
include_library = True
catalog = json.loads((ROOT/"data/catalog.json").read_text())
coverage = go.Figure()
colors = {"train": "#416ca8", "validation": "#b68424", "test": "#8060ad"}
for role in ("train", "validation", "test"):
    for index, instrument in enumerate(("ES", "NQ", "MES", "MNQ")):
        part = catalog["instruments"][instrument]["splits"][role]
        row = instrument+(" · mini reference" if instrument in ("ES", "NQ") else " · target micro")
        coverage.add_scatter(x=[part["coverage"]["start"], part["coverage"]["end"]], y=[row, row],
            mode="lines", line=dict(color=colors[role], width=17), name=role.title(), legendgroup=role,
            showlegend=index == 0, text=[f"{instrument} {role}: {part['coverage']['rows']:,} bars"]*2,
            hovertemplate="%{text}<br>%{x}<extra></extra>")
coverage.update_layout(template="plotly_white", title="Available history and fixed split boundaries", height=360,
    xaxis_title="UTC · ES/NQ history is distinct from MES/MNQ", yaxis_title=None,
    legend=dict(orientation="h", y=1.15), margin=dict(l=170))
coverage.add_vline(x="2024-01-01", line_dash="dot")
coverage.add_vline(x="2026-01-01", line_dash="dot")
sections.append(pio.to_html(coverage, full_html=False, include_plotlyjs=False))
include_library = False
for protocol in sorted((ROOT/"reports").glob("final_market_campaign_*m.json")):
    study = json.loads(protocol.read_text())
    for instrument, run in study["runs"].items():
        directory = Path(run["path"])
        data = pd.DataFrame(json.loads((directory/"leaderboard.json").read_text())).sort_values("net_pnl")
        title = f"{instrument} · {study['timeframe_minutes']}-minute validation"
        figure = go.Figure(go.Bar(y=data.candidate_id, x=data.net_pnl, orientation="h",
            marker_color=["#21846b" if value > 0 else "#b64d59" if value < 0 else "#8d97a7" for value in data.net_pnl],
            text=data.trades.map(lambda count: "No trades" if count == 0 else ""), textposition="outside",
            customdata=data[["max_drawdown", "trades", "positive_fold_fraction"]].to_numpy(),
            hovertemplate="%{y}<br>Validation net $%{x:,.2f}<br>Max drawdown $%{customdata[0]:,.2f}<br>Trades %{customdata[1]}<br>Positive folds %{customdata[2]:.0%}<extra></extra>"))
        figure.add_vline(x=0, line_color="#aab2bd")
        figure.update_layout(template="plotly_white", title=title, height=750, margin=dict(l=220, r=70), xaxis_title="Validation net P&L (simulated USD)")
        sections.append(pio.to_html(figure, full_html=False, include_plotlyjs=include_library))
        include_library = False
        scatter = go.Figure()
        for family, group in data.groupby("family"):
            scatter.add_scatter(x=group.max_drawdown, y=group.net_pnl, mode="markers", name=family,
                text=group.candidate_id, marker=dict(size=8+group.trades.pow(.5).clip(upper=24)),
                hovertemplate="%{text}<br>Drawdown $%{x:,.2f}<br>Validation net $%{y:,.2f}<extra>%{fullData.name}</extra>")
        scatter.add_hline(y=0, line_dash="dot")
        scatter.update_layout(template="plotly_white", title=title+" · return versus drawdown", height=440,
            xaxis_title="Maximum drawdown (USD)", yaxis_title="Validation net P&L (USD)")
        sections.append(pio.to_html(scatter, full_html=False, include_plotlyjs=False))
        summary = json.loads((directory/"summary.json").read_text())
        selected = summary["selected_for_research_only"]
        curve = pd.read_parquet(directory/f"{selected}_equity.parquet")
        # Plot at most 3000 evenly spaced observations; metrics always use the
        # complete series. Full curves remain beside each registered experiment.
        sample = curve.iloc[np.unique(np.linspace(0, len(curve)-1, min(3000, len(curve))).astype(int))]
        equity = go.Figure()
        equity.add_scatter(x=sample.timestamp_utc, y=sample.equity, mode="lines", name="Simulated equity")
        equity.add_scatter(x=sample.timestamp_utc, y=[50000]*len(sample), mode="lines", name="Flat cash", line=dict(dash="dot"))
        equity.update_layout(template="plotly_white", title=title+" · research-selected "+selected, height=400,
            xaxis_title="UTC", yaxis_title="Simulated USD equity")
        sections.append(pio.to_html(equity, full_html=False, include_plotlyjs=False))
extended_path = ROOT/"reports/latest_extended_study.json"
if extended_path.exists():
    extended = json.loads(extended_path.read_text())
    for instrument in ("MES", "MNQ"):
        rows = [dict(study=row["name"], **row["result"]["metrics"]) for row in extended["attempts"]
            if row["instrument"] == instrument and "metrics" in row.get("result", {})]
        data = pd.DataFrame(rows).sort_values("net_pnl")
        figure = go.Figure(go.Bar(x=data.net_pnl, y=data.study, orientation="h",
            marker_color=["#21846b" if value > 0 else "#b64d59" if value < 0 else "#8d97a7" for value in data.net_pnl],
            text=data.trades.map(lambda count: "No trades" if count == 0 else ""), textposition="outside"))
        figure.update_layout(template="plotly_white", title=f"{instrument} · extended 15-minute studies", height=660,
            margin=dict(l=220), xaxis_title="Validation net P&L (simulated USD)")
        sections.append(pio.to_html(figure, full_html=False, include_plotlyjs=False))
for pattern, label in (("reference_transfer_*", "15-minute control"), ("minute_reference_transfer_*", "Original one-minute training"),
    ("opening_range_minutes_*", "One-attempt opening range"), ("overnight_minutes_*", "Overnight"),
    ("adaptive_opening_minutes_*", "Volatility-scaled opening range"),
    ("session_window_minutes_*", "Session/calendar rules — post-final exploratory selection"),
    ("gap_structure_minutes_*", "Opening gaps/price structure — post-final exploratory selection"),
    ("risk_expansion_*", "Higher-risk sizing and exits — reused-period selection"),
    ("pareto_refinement_*", "Entry filters and protective stops — reused-period selection"),
    ("profit_drawdown_followup_*", "Higher profit / lower drawdown — reused-period follow-up")):
    directories = sorted((ROOT/"runs").glob(pattern), key=lambda path:path.stat().st_mtime)
    if not directories:
        continue
    directory = directories[-1]
    rows = []
    for reference, micro in (("ES", "MES"), ("NQ", "MNQ")):
        outcomes = directory/f"{micro}_validation_results.json"
        if outcomes.exists():
            rows.extend(dict(transfer=reference+"→"+micro, **row) for row in json.loads(outcomes.read_text()) if "metrics" in row)
    if rows:
        figure = go.Figure()
        for pair in sorted(set(row["transfer"] for row in rows)):
            selected = [row for row in rows if row["transfer"] == pair]
            figure.add_bar(x=[row["candidate_id"] for row in selected], y=[row["metrics"]["net_pnl"] for row in selected], name=pair,
                customdata=[[row["metrics"]["max_drawdown"], row["metrics"]["trades"]] for row in selected],
                hovertemplate="%{x}<br>Validation net $%{y:,.2f}<br>Max DD $%{customdata[0]:,.2f}<br>Trades %{customdata[1]}<extra>%{fullData.name}</extra>")
        figure.update_layout(template="plotly_white", title=label+" · reference-trained → actual micro validation", height=440,
            yaxis_title="Validation net P&L (simulated USD)")
        sections.append(pio.to_html(figure, full_html=False, include_plotlyjs=False))
        if pattern.startswith(("session_window", "gap_structure", "risk_expansion", "pareto_refinement", "profit_drawdown_followup")):
            risk_return = go.Figure()
            for pair in sorted(set(row["transfer"] for row in rows)):
                selected = [row for row in rows if row["transfer"] == pair]
                risk_return.add_scatter(x=[row["metrics"]["max_drawdown"] for row in selected],
                    y=[row["metrics"]["net_pnl"] for row in selected], mode="markers", name=pair,
                    text=[row["candidate_id"] for row in selected],
                    marker=dict(size=[10+min(18, row["metrics"]["trades"]**.5) for row in selected]),
                    hovertemplate="%{text}<br>Max DD $%{x:,.2f}<br>Selection-period net $%{y:,.2f}<extra>%{fullData.name}</extra>")
            risk_return.add_vline(x=2000, line_dash="dash", annotation_text="$2,000 DD limit")
            risk_return.add_hline(y=0, line_dash="dot")
            risk_return.update_layout(template="plotly_white", title=label+" · return versus drawdown",
                xaxis_title="Measured maximum drawdown (USD)", yaxis_title="Reused 2024–2025 selection-period net P&L (USD)", height=430)
            sections.append(pio.to_html(risk_return, full_html=False, include_plotlyjs=False))
        profitable = [row for row in rows if row["metrics"]["net_pnl"] > 0]
        for row in profitable:
            micro = row["transfer"].split("→")[-1]
            path = directory/f"{micro}_{row['candidate_id']}_validation_equity.parquet"
            if not path.exists():
                continue
            curve = pd.read_parquet(path)
            drawdown = curve.equity.cummax().clip(lower=50000)-curve.equity
            indexes = np.unique(np.linspace(0, len(curve)-1, min(3000, len(curve))).astype(int))
            figure = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.66, .34], vertical_spacing=.07)
            figure.add_scatter(x=curve.timestamp_utc.iloc[indexes], y=curve.equity.iloc[indexes], name="Simulated equity", mode="lines", row=1, col=1)
            if risk_study and row["candidate_id"] == risk_study["best_selected"]["candidate_id"] and str(directory) == risk_study["path"]:
                base_curve = pd.read_parquet(directory/f"MNQ_{risk_study['baseline']['candidate_id']}_validation_equity.parquet")
                base_ids = np.unique(np.linspace(0, len(base_curve)-1, min(3000, len(base_curve))).astype(int))
                figure.add_scatter(x=base_curve.timestamp_utc.iloc[base_ids], y=base_curve.equity.iloc[base_ids],
                    name=baseline_label, mode="lines", line=dict(color="#8892a2", dash="dot"), row=1, col=1)
            figure.add_scatter(x=curve.timestamp_utc.iloc[indexes], y=[50000]*len(indexes), name="Flat cash", mode="lines", line=dict(dash="dot"), row=1, col=1)
            figure.add_scatter(x=curve.timestamp_utc.iloc[indexes], y=-drawdown.iloc[indexes], name="Drawdown", mode="lines", fill="tozeroy", line=dict(color="#b64d59"), row=2, col=1)
            figure.add_hline(y=-2000, line_dash="dash", line_color="#922e36", annotation_text="$2,000 drawdown rejection limit", row=2, col=1)
            metrics = row["metrics"]
            figure.update_layout(template="plotly_white", title=f"{label} · {row['transfer']} · net ${metrics['net_pnl']:,.2f} / max DD ${metrics['max_drawdown']:,.2f}", height=620)
            figure.update_yaxes(title_text="Simulated equity (USD)", row=1, col=1)
            figure.update_yaxes(title_text="Drawdown (USD)", row=2, col=1)
            sections.append(pio.to_html(figure, full_html=False, include_plotlyjs=False))
            if latest and row["candidate_id"] == latest["leading_observed_candidate"]["candidate_id"] and str(directory) in latest["studies"]:
                latest_curve_html = sections[-1]
            months = metrics.get("monthly_pnl", {})
            if months:
                monthly = go.Figure(go.Bar(x=list(months), y=list(months.values()),
                    marker_color=["#21846b" if value > 0 else "#b64d59" for value in months.values()]))
                monthly.update_layout(template="plotly_white", title=label+" · "+micro+" monthly validation P&L",
                    height=360, yaxis_title="Simulated USD net P&L", xaxis_title="Month")
                sections.append(pio.to_html(monthly, full_html=False, include_plotlyjs=False))
final_file = ROOT/"reports/final_candidate_test.json"
final = json.loads(final_file.read_text()) if final_file.exists() else None
if final:
    curve = pd.read_parquet(Path(final["path"])/"test_equity.parquet")
    ids = np.unique(np.linspace(0, len(curve)-1, min(3000, len(curve))).astype(int))
    drawdown = curve.equity.cummax().clip(lower=50000)-curve.equity
    figure = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.66, .34], vertical_spacing=.08)
    figure.add_scatter(x=curve.timestamp_utc.iloc[ids], y=curve.equity.iloc[ids], name="2026 final-test equity", line=dict(color="#8054a4"), row=1, col=1)
    figure.add_scatter(x=curve.timestamp_utc.iloc[ids], y=[50000]*len(ids), name="Flat cash", line=dict(dash="dot"), row=1, col=1)
    figure.add_scatter(x=curve.timestamp_utc.iloc[ids], y=-drawdown.iloc[ids], name="2026 drawdown", fill="tozeroy", line=dict(color="#b64d59"), row=2, col=1)
    figure.add_hline(y=-2000, line_dash="dash", annotation_text="$2,000 historical drawdown limit", row=2, col=1)
    figure.update_layout(template="plotly_white", height=620, title=f"One-time 2026 MNQ FINAL TEST · net ${final['metrics']['net_pnl']:,.2f} / max DD ${final['metrics']['max_drawdown']:,.2f}")
    figure.update_yaxes(title_text="Simulated equity (USD)", row=1, col=1)
    figure.update_yaxes(title_text="Drawdown (USD)", row=2, col=1)
    sections.insert(1, pio.to_html(figure, full_html=False, include_plotlyjs=False))
saved_test_path = ROOT/"reports/saved_version_reused_test.json"
saved_test = json.loads(saved_test_path.read_text()) if saved_test_path.exists() else None
saved_test_html = None
if saved_test:
    tc = pd.read_parquet(Path(saved_test["path"])/"test_equity.parquet")
    ti = np.unique(np.linspace(0,len(tc)-1,min(3000,len(tc))).astype(int))
    td = tc.equity.cummax().clip(lower=50000)-tc.equity
    tf = make_subplots(rows=2,cols=1,shared_xaxes=True,vertical_spacing=.09)
    tf.add_scatter(x=tc.timestamp_utc.iloc[ti],y=tc.equity.iloc[ti]-50000,name="Frozen-version test net P&L",row=1,col=1)
    tf.add_scatter(x=tc.timestamp_utc.iloc[ti],y=-td.iloc[ti],name="Frozen-version test drawdown",fill="tozeroy",row=2,col=1)
    tf.add_hline(y=-2000,line_dash="dash",row=2,col=1)
    tm = saved_test["metrics"]
    tf.update_layout(template="plotly_white",height=600,title=f"Frozen $6,622 development version · reused 2026 test · net ${tm['net_pnl']:,.2f} / close DD ${tm['max_drawdown']:,.2f}")
    saved_test_html = pio.to_html(tf,full_html=False,include_plotlyjs=False)
    sections.insert(0,saved_test_html)

document = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>MES / MNQ validation charts</title>
<style>body{font:16px system-ui,sans-serif;background:#f3f5f9;color:#18243a;margin:0}main{max-width:1450px;margin:auto;padding:32px}header,section{background:white;border-radius:14px;padding:22px;margin-bottom:22px}p{max-width:1000px;line-height:1.6}h1{margin-top:0}a{color:#315c9d}</style></head><body><main><header>
<h1>MES / MNQ validation research</h1><p>ES/NQ archive history begins in 2010. Actual MES/MNQ history begins in May 2019. Training ends in 2023 · validation 2024–2025 · 2026 test reserved.</p>
<p>The coverage chart shows available data, not a claim that every row was fitted. The current original one-minute transfer study trains ES/NQ from 2010 through 2023 using all eligible reference rows, with internal selection in 2022–2023. The 15-minute transfer experiment is a separately labeled control. Actual MES/MNQ 2024–2025 is validation, and 2026 is reserved test. Earlier micro history is feature warmup only. Prior micro-trained comparison charts below used a 100000-observation fitting cap; their historical results remain visible. ES/NQ P&L is never relabeled as pre-2019 micro performance.</p>
<p>Hover for values and use the Plotly controls to zoom. Gray zero-trade results represent abstention. These historical curves reset risk and capital between folds; they are attribution views. Bubble size represents trade count. Equity displays sample at most 3000 observations, while reported metrics use all observations. No deployable strategy has been established.</p></header>"""
document = document.replace("<h1>MES / MNQ validation research</h1>",
    f"<h1>MES / MNQ validation research</h1><p><strong>{counts['distinct_strategy_definitions']} strategy/model definitions · {counts['unique_parameter_configurations']} unique configurations · {counts['unique_market_configuration_cases']} market/configuration cases · {counts['completed_run_attempts']} completed attempts including reruns.</strong> Reruns do not count as new strategies. Approximate training screens are separately identified in STRATEGY_COUNTS.md.</p>")
if final:
    document = document.replace("2026 test reserved.", "2026 MNQ final test evaluated once.").replace("2026 is reserved test", "2026 MNQ final test has now been consumed")
    document = document.replace("</h1>", f"</h1><p><strong>Frozen 2026 MNQ test: ${final['metrics']['net_pnl']:,.2f} net / ${final['metrics']['max_drawdown']:,.2f} max drawdown / {final['metrics']['trades']} trades.</strong> This thin positive result does not establish a dependable edge. The 2026 market period will not be reused as untouched test data.</p>", 1)
document = document.replace("These historical curves reset risk and capital between folds; they are attribution views.",
    "Earlier micro comparison curves reset risk and capital between folds; the transfer studies use continuous one-account validation curves. New session/calendar and gap/structure studies reuse 2024–2025 for exploratory selection after the final test; they have no independent final confirmation.")
document = document.replace("</h1>","</h1><p><strong>Research policy: no tuning against validation or test data.</strong> The 2024–2025 figures below were reused to choose parameters and are development results, not independent validation. Future parameter selection uses training history only.</p>",1)
if saved_test:
    tm = saved_test["metrics"]
    test_card = f"<div style='border-left:5px solid #b64d59;padding:12px 20px;background:#fff1f2'><h2>Frozen saved version · 2026 reused-test evaluation</h2><p><strong>Net ${tm['net_pnl']:,.2f} · Closing drawdown ${tm['max_drawdown']:,.2f} · Intrabar drawdown ${tm['max_intraday_drawdown_bound']:,.2f} · {tm['trades']} trades.</strong> One fixed version and one base-cost case; no tuning. This period was previously consumed, so this is not independent confirmation. <a href='#frozen-version-test'>Test equity chart</a> · <a href='SAVED_VERSION_TEST.md'>Full outcome</a>.</p></div>"
    document = document.replace("</h1>","</h1>"+test_card,1)
if latest:
    leading = latest["leading_observed_candidate"]
    m = leading["metrics"]
    name = html.escape(leading["candidate"]["name"].replace("_", " ").title())
    extra = ""
    if risk_study:
        params = leading["candidate"]
        extra = f"<p>Maximum {params['contracts']} contracts · {html.escape(params['sizing'])} sizing · {params['stop_points']}-point stop · {params['payoff']}:1 target. Net improvement over baseline: ${risk_study['pnl_improvement']:,.2f}. Permanent-lock and cost-stress checks are included in selection.</p>"
        if risk_study.get("pareto_refinement"):
            report_link = "PROFIT_DRAWDOWN_FOLLOWUP.md" if risk_study.get("profit_drawdown_followup") else "PARETO_REFINEMENT.md"
            extra += f"<p>Refinement goal met: {risk_study['goal_met']}. {risk_study['selected_replays']} micro replays. <a href='{report_link}'>Full refinement results</a>.</p>"
        extra += f"<p>Base-case permanent risk shutdown: {m['permanent_risk_lock']}; 2×-cost shutdown: {leading['stress']['2']['permanent_risk_lock']}. Cost-stress qualification is separate from the base profit/drawdown goal.</p>"
        if leading["stress"]["3"]["permanent_risk_lock"]:
            extra += "<p>3×-cost stress triggered permanent risk shutdown and failed; positive terminal profit in a stopped case is not a full-period pass.</p>"
    cost_factor = "2" if risk_study else "3"
    card = f"<div style='border-left:5px solid #21846b;padding:12px 20px;background:#edf8f4'><h2>Latest research · {html.escape(leading['transfer'])} · {name}</h2><p><strong>Net ${m['net_pnl']:,.2f} · Max drawdown ${m['max_drawdown']:,.2f} · {m['trades']} trades · {cost_factor}× costs net ${leading['stress'][cost_factor]['net_pnl']:,.2f}</strong></p>{extra}<p>2024–2025 reused selection period. Long-history and confidence qualification still matter; independent confirmation remains unavailable. <a href='#latest-strategy'>Jump to the latest equity and drawdown chart</a>.</p></div>"
    document = document.replace("</h1>", "</h1>"+card, 1)
if latest_curve_html:
    sections.remove(latest_curve_html)
    sections.insert(0, latest_curve_html)
# Load the library before every chart so reordering cannot break first-chart rendering.
document = document.replace("</head>", "<script>"+get_plotlyjs()+"</script></head>", 1)
document += "".join(("<section id='latest-strategy'>" if index == 0 and latest_curve_html else "<section id='frozen-version-test'>" if section == saved_test_html else "<section>")+section+"</section>" for index, section in enumerate(sections))
document += "</main></body></html>"
path = ROOT/"reports/research_charts.html"
path.write_text(document, encoding="utf-8")
json_write(ROOT/"reports/chart_artifact_verification.json", dict(passed=True, interactive=True,
    self_contained=True, plot_containers=len(sections), bytes=path.stat().st_size))
print(json.dumps(dict(path=str(path), charts=len(sections), bytes=path.stat().st_size)))
