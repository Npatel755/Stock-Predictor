"""Local read-only dashboard. Run with streamlit, no broker controls exposed."""
from pathlib import Path
import json
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="MES / MNQ Research", layout="wide")
st.title("MES / MNQ Research")
st.caption("Historical simulation and paper trading · Live execution is disabled")
latest_file = ROOT/"reports/post_final_research_summary.json"
risk_file = ROOT/"reports/latest_risk_expansion_study.json"
refinement_file = ROOT/"reports/latest_pareto_refinement.json"
if refinement_file.exists():
    risk_file = refinement_file
followup_file = ROOT/"reports/latest_profit_drawdown_followup.json"
if followup_file.exists():
    risk_file = followup_file
risk_study = json.loads(risk_file.read_text()) if risk_file.exists() else None
baseline_label = "Previous $4,451 benchmark" if risk_study and risk_study.get("pareto_refinement") else "Original one-contract baseline"
if risk_study and risk_study.get("profit_drawdown_followup"):
    baseline_label = "Saved $5,779.50 result (risk stopped)"
latest = json.loads(latest_file.read_text()) if latest_file.exists() else None
if risk_study:
    latest = dict(studies=[risk_study["path"]], leading_observed_candidate=dict(transfer="NQ->MNQ", **risk_study["best_selected"]))
if latest:
    leading = latest["leading_observed_candidate"]
    metrics = leading["metrics"]
    instrument = leading["transfer"].split("->")[-1]
    title = leading["candidate"]["name"].replace("_", " ").title()
    st.subheader(f"Latest research · {instrument} {title}")
    st.warning("Development result: the 2024–2025 validation results were reused to choose these parameters. These figures are not independent validation. Future parameter selection must use training data only.")
    if risk_study:
        screening = (f"{risk_study['reused_screen_cases']} original reference screens reused" if "reused_screen_cases" in risk_study
                     else f"{risk_study['selected_replays']} continuous reference replays" if risk_study.get("profit_drawdown_followup")
                     else f"{risk_study['screen_attempts']} reference screens")
        st.caption(f"2024–2025 reused selection period · risk/exit study: {screening} / {risk_study['selected_replays']} selected micro replays")
    else:
        st.caption("2024–2025 reused selection period · latest batch: 16 new rule families / 128 reference screens")
    panels = st.columns(5)
    panels[0].metric("Latest strategy net P&L", f"${metrics['net_pnl']:,.2f}")
    panels[1].metric("Latest strategy max drawdown", f"${metrics['max_drawdown']:,.2f}")
    panels[2].metric("Latest strategy intrabar drawdown", f"${metrics['max_intraday_drawdown_bound']:,.2f}")
    panels[3].metric("Latest strategy trades", metrics["trades"])
    stress_factor = "2" if risk_study else "3"
    panels[4].metric(f"Net at {stress_factor}× modeled costs", f"${leading['stress'][stress_factor]['net_pnl']:,.2f}")
    if risk_study:
        params = leading["candidate"]
        st.caption(f"Sizing: {params['sizing'].replace('_', ' ')} · maximum {params['contracts']} contracts · {params['stop_points']}-point stop · {params['payoff']}:1 target · exit {params['exit_minute']//60:02d}:{params['exit_minute']%60:02d} ET. Net improvement over {baseline_label.lower()}: ${risk_study['pnl_improvement']:,.2f}.")
        if risk_study.get("pareto_refinement"):
            report_name = "PROFIT_DRAWDOWN_FOLLOWUP.md" if risk_study.get("profit_drawdown_followup") else "PARETO_REFINEMENT.md"
            st.caption(f"Refinement goal met: {risk_study['goal_met']}. See reports/{report_name} for all results.")
        st.caption(f"Adverse intrabar drawdown: ${metrics['max_intraday_drawdown_bound']:,.2f}; at 2× costs: ${leading['stress']['2']['max_intraday_drawdown_bound']:,.2f}. Base permanent shutdown: {metrics['permanent_risk_lock']}; 2×-cost shutdown: {leading['stress']['2']['permanent_risk_lock']}.")
        unresolved = [name.replace('_', ' ') for name, passed in leading["evidence_checks"].items() if not passed]
        st.caption("Research candidate · unresolved evidence checks: "+(", ".join(unresolved) if unresolved else "new independent forward confirmation")+". Separate from the frozen 2026 final test below.")
        if leading["stress"]["3"]["permanent_risk_lock"]:
            st.caption("The 3×-cost stress case triggered a permanent risk shutdown and failed; its positive terminal P&L does not count as a full-period pass.")
    else:
        st.caption("Research candidate: older-history and confidence checks failed. This is separate from the frozen 2026 final test shown below.")
    for directory in map(Path, latest["studies"]):
        curve_path = directory/f"{instrument}_{leading['candidate_id']}_validation_equity.parquet"
        if not curve_path.exists():
            continue
        curve = pd.read_parquet(curve_path)
        drawdown = curve.equity.cummax().clip(lower=50000)-curve.equity
        indexes = np.unique(np.linspace(0, len(curve)-1, min(2500, len(curve))).astype(int))
        chart = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.65, .35], vertical_spacing=.09)
        chart.add_scatter(x=curve.timestamp_utc.iloc[indexes], y=curve.equity.iloc[indexes]-50000,
            name="Cumulative net P&L", mode="lines", line=dict(color="#36b99a"), row=1, col=1)
        if risk_study:
            baseline_path = directory/f"MNQ_{risk_study['baseline']['candidate_id']}_validation_equity.parquet"
            baseline_curve = pd.read_parquet(baseline_path)
            base_indexes = np.unique(np.linspace(0, len(baseline_curve)-1, min(2500, len(baseline_curve))).astype(int))
            chart.add_scatter(x=baseline_curve.timestamp_utc.iloc[base_indexes], y=baseline_curve.equity.iloc[base_indexes]-50000,
                name=baseline_label, mode="lines", line=dict(color="#a3aab8", dash="dot"), row=1, col=1)
        chart.add_scatter(x=curve.timestamp_utc.iloc[indexes], y=-drawdown.iloc[indexes],
            name="Drawdown", mode="lines", fill="tozeroy", line=dict(color="#c65767"), row=2, col=1)
        chart.add_hline(y=-2000, line_dash="dash", annotation_text="$2,000 drawdown limit", row=2, col=1)
        chart.update_layout(title="Latest strategy · 2024–2025 equity and drawdown", height=480)
        chart.update_yaxes(title_text="Net P&L (USD)", row=1, col=1)
        chart.update_yaxes(title_text="Drawdown (USD)", row=2, col=1)
        st.plotly_chart(chart, width="stretch", key="latest_strategy_equity")
        break
saved_test_file = ROOT/"reports/saved_version_reused_test.json"
if saved_test_file.exists():
    saved_test = json.loads(saved_test_file.read_text(encoding="utf-8"))
    tm = saved_test["metrics"]
    st.subheader("Saved $6,622 version · frozen 2026 reused-test evaluation")
    st.caption("One fixed version and one base-cost replay. No tuning against this test outcome. The period was previously used by an earlier strategy, so this is not independent confirmation.")
    panels = st.columns(4)
    panels[0].metric("Frozen-version test net P&L", f"${tm['net_pnl']:,.2f}")
    panels[1].metric("Frozen-version test closing drawdown", f"${tm['max_drawdown']:,.2f}")
    panels[2].metric("Frozen-version test intrabar drawdown", f"${tm['max_intraday_drawdown_bound']:,.2f}")
    panels[3].metric("Frozen-version test trades", tm["trades"])
    if tm["net_pnl"] <= 0:
        st.warning("The frozen strategy lost money in this evaluation. It stayed below the $2,000 drawdown limit but failed the profitability check. Its parameters will not be retuned from this result.")
    tc = pd.read_parquet(Path(saved_test["path"])/"test_equity.parquet")
    ti = np.unique(np.linspace(0,len(tc)-1,min(2500,len(tc))).astype(int))
    td = tc.equity.cummax().clip(lower=50000)-tc.equity
    fig = make_subplots(rows=2,cols=1,shared_xaxes=True,vertical_spacing=.09)
    fig.add_scatter(x=tc.timestamp_utc.iloc[ti],y=tc.equity.iloc[ti]-50000,name="Frozen-version test net P&L",row=1,col=1)
    fig.add_scatter(x=tc.timestamp_utc.iloc[ti],y=-td.iloc[ti],name="Test drawdown",fill="tozeroy",row=2,col=1)
    fig.add_hline(y=-2000,line_dash="dash",row=2,col=1)
    fig.update_layout(title="Frozen saved version · 2026 reused-test outcome",height=470)
    st.plotly_chart(fig,width="stretch",key="saved_version_reused_test")
final_file = ROOT/"reports/final_candidate_test.json"
final_test = json.loads(final_file.read_text()) if final_file.exists() else None
if final_test:
    st.subheader("Frozen candidate · one-time 2026 MNQ final test")
    metrics = final_test["metrics"]
    panels = st.columns(4)
    panels[0].metric("Final-test net P&L", f"${metrics['net_pnl']:,.2f}")
    panels[1].metric("Max drawdown", f"${metrics['max_drawdown']:,.2f}")
    panels[2].metric("Adverse intrabar DD bound", f"${metrics['max_intraday_drawdown_bound']:,.2f}")
    panels[3].metric("Final-test trades", metrics["trades"])
    st.warning("2026 MNQ was evaluated once after freezing the candidate. Its thin positive result and confidence interval do not establish a dependable trading edge. The 2026 market period is consumed for model-selection purposes; it will not be reused as untouched test data.")
count_file = ROOT/"reports/strategy_counts.json"
if count_file.exists():
    counts = json.loads(count_file.read_text())
    columns = st.columns(4)
    columns[0].metric("Strategy / model definitions", counts["distinct_strategy_definitions"])
    columns[1].metric("Unique configurations", counts["unique_parameter_configurations"])
    columns[2].metric("Market / configuration cases", counts["unique_market_configuration_cases"])
    columns[3].metric("Completed attempts incl. reruns", counts["completed_run_attempts"])
    st.caption("Reruns do not increase the distinct-strategy count. Approximate training screens, full event backtests and inner optimization are recorded separately in STRATEGY_COUNTS.md.")
catalog_path = ROOT/"data/catalog.json"
if catalog_path.exists():
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    st.subheader("Active market data")
    st.caption("Databento job "+catalog["active_job"]+" · raw contract prices · one-minute OHLCV")
    st.dataframe(pd.DataFrame([dict(instrument=name, **item["coverage"], role=item["role"])
        for name, item in catalog["instruments"].items()]), width="stretch")
    if catalog.get("split_protocol"):
        st.caption("Chronological split: training through 2023; validation 2024–2025; test 2026. "+("One frozen MNQ final evaluation has consumed the 2026 market period; ES/NQ/MES test prices remain unread." if final_test else "Test data is reserved for frozen final evaluation."))
        st.dataframe(pd.DataFrame([dict(instrument=name, partition=role, **part["coverage"])
            for name, item in catalog["instruments"].items() for role, part in item.get("splits", {}).items()]), width="stretch")
        coverage = go.Figure()
        for role, color in (("train", "#416ca8"), ("validation", "#b68424"), ("test", "#8060ad")):
            for index, name in enumerate(("ES", "NQ", "MES", "MNQ")):
                part = catalog["instruments"][name]["splits"][role]
                label = name+(" · mini reference" if name in ("ES", "NQ") else " · target micro")
                coverage.add_scatter(x=[part["coverage"]["start"], part["coverage"]["end"]], y=[label, label],
                    mode="lines", line=dict(width=16, color=color), name=role.title(), legendgroup=role,
                    showlegend=index == 0, hovertemplate=label+" · "+role+"<br>%{x}<extra></extra>")
        coverage.update_layout(title="Available history", height=330, xaxis_title="UTC", legend=dict(orientation="h"))
        st.plotly_chart(coverage, width="stretch")
        st.caption("2010 history belongs to ES/NQ. MES/MNQ start in May 2019. Earlier micro-trained comparison runs used a 100,000-observation fitting cap. ES/NQ have not been relabeled as unavailable early micro contracts.")
        if list((ROOT/"runs").glob("reference_transfer_*/protocol.json")):
            st.info("Transfer protocol: ES/NQ 2010–2023 training and actual MES/MNQ 2024–2025 validation. "+("The frozen 2026 MNQ test is now recorded separately." if final_test else "Actual micro 2026 remains reserved for final test.")+" The transfer fits use all eligible reference rows; the 100,000-row cap applies only to earlier micro-trained comparison runs. Earlier micro history is feature warmup, not fitting in the transfer study.")
transfer_studies = sorted(list((ROOT/"runs").glob("reference_transfer_*/protocol.json"))+
    list((ROOT/"runs").glob("minute_reference_transfer_*/protocol.json"))+
    list((ROOT/"runs").glob("opening_range_minutes_*/protocol.json"))+
    list((ROOT/"runs").glob("overnight_minutes_*/protocol.json"))+
    list((ROOT/"runs").glob("adaptive_opening_minutes_*/protocol.json"))+
    list((ROOT/"runs").glob("session_window_minutes_*/protocol.json"))+
    list((ROOT/"runs").glob("gap_structure_minutes_*/protocol.json"))+
    list((ROOT/"runs").glob("risk_expansion_*/protocol.json"))+
    list((ROOT/"runs").glob("pareto_refinement_*/protocol.json"))+
    list((ROOT/"runs").glob("profit_drawdown_followup_*/protocol.json")), key=lambda path: path.stat().st_mtime, reverse=True)
if transfer_studies:
    st.subheader("ES/NQ training → later micro validation")
    observed_positive = []
    for study_file in transfer_studies:
        for instrument in ("MES", "MNQ"):
            result_file = study_file.parent/f"{instrument}_validation_results.json"
            if result_file.exists():
                for row in json.loads(result_file.read_text()):
                    metrics = row.get("metrics", {})
                    if metrics.get("net_pnl", 0) > 0:
                        observed_positive.append(dict(study=study_file.parent.name, instrument=instrument,
                            candidate=row["candidate_id"], net_pnl=metrics["net_pnl"],
                            max_drawdown=metrics["max_drawdown"], trades=metrics["trades"],
                            qualified=row.get("economic_research_qualified", False)))
    if observed_positive:
        st.write("Positive observed validation results")
        st.dataframe(pd.DataFrame(observed_positive).sort_values("net_pnl", ascending=False), width="stretch")
        st.warning("A positive backtest is a research candidate. Review training checks, confidence, cost stress and year-to-year stability; these results do not guarantee profitability or a future $2,000 drawdown cap.")
    study = st.selectbox("Transfer study", transfer_studies, format_func=lambda path: path.parent.name)
    protocol = json.loads(study.read_text())
    if protocol.get("post_final_test_research"):
        st.warning("Post-final-test exploratory research: 2024–2025 is a reused selection period. Independent confirmation requires new forward data; 2026 is excluded from this search.")
    st.caption("15-minute resampled control" if study.parent.name.startswith("reference_transfer_") else "Original one-minute bars")
    progress_rows, result_rows = [], []
    for reference, micro in (("ES", "MES"), ("NQ", "MNQ")):
        shards = study.parent/(reference+"_one_minute_training_shards")/"manifest.json"
        if shards.exists():
            manifest = json.loads(shards.read_text())
            progress_rows.append(dict(reference=reference, processed_source_rows=manifest["input_rows"],
                eligible_training_rows=manifest["eligible_rows"], contract_shards=len(manifest["shards"])))
        outcomes = study.parent/f"{micro}_validation_results.json"
        if outcomes.exists():
            for row in json.loads(outcomes.read_text()):
                if "metrics" in row:
                    result_rows.append(dict(transfer=reference+"→"+micro, candidate=row["candidate_id"],
                        net_pnl=row["metrics"]["net_pnl"], max_drawdown=row["metrics"]["max_drawdown"], trades=row["metrics"]["trades"],
                        research_qualified=row.get("economic_research_qualified", False)))
    if progress_rows:
        st.dataframe(pd.DataFrame(progress_rows), width="stretch")
    if result_rows:
        st.dataframe(pd.DataFrame(result_rows), width="stretch")
        figure = go.Figure()
        for pair in sorted(set(row["transfer"] for row in result_rows)):
            rows = [row for row in result_rows if row["transfer"] == pair]
            figure.add_bar(x=[row["candidate"] for row in rows], y=[row["net_pnl"] for row in rows], name=pair,
                customdata=[[row["max_drawdown"], row["trades"]] for row in rows],
                hovertemplate="%{x}<br>Net $%{y:,.2f}<br>DD $%{customdata[0]:,.2f}<br>Trades %{customdata[1]}<extra>%{fullData.name}</extra>")
        figure.update_layout(title="Actual micro validation · selected inside reference training", yaxis_title="Simulated USD net P&L")
        st.plotly_chart(figure, width="stretch")
    st.caption("Training and calibration use ES/NQ before 2024. These micro results are 2024–2025 validation. Final-test results are reported separately. A $1,800 risk stop does not guarantee future drawdown remains below $2,000.")
run_root = ROOT/"runs"
runs = sorted([p for p in run_root.glob("*") if p.is_dir() and (p/"experiment.json").exists()],
              key=lambda p: (p/"experiment.json").stat().st_mtime, reverse=True)
if not runs:
    st.info("No research results are currently active. Data import and validation do not establish strategy profitability.")
    st.stop()
st.sidebar.caption("The latest strategy and its chart appear at the top of the page. This selector opens earlier comparison runs.")
selected = st.sidebar.selectbox("Historical comparison experiment", runs, format_func=lambda p: p.name)
st.subheader("Historical comparison experiment")
def read(name, default=None):
    path = selected/name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
experiment = read("experiment.json", {})
if experiment.get("synthetic"):
    st.warning("SYNTHETIC FUNCTIONAL TEST — these values provide no evidence of trading profitability.")
summary = read("summary.json", {})
st.write("Candidate status: no deployable candidate" if summary.get("no_deployable_candidate", True) else "Research review pending")
attempts = read("attempts.json", [])
if not attempts and (selected/"attempts.jsonl").exists():
    for line in (selected/"attempts.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            attempts.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # A writer may be in the middle of its latest append.
budget = experiment.get("config", {}).get("maximum_trials", 1)
st.progress(min(1.0, len(attempts)/max(1, budget)), text=f"Recorded candidate attempts: {len(attempts)}")
tabs = st.tabs(["Data", "Leaderboard", "Equity", "Models", "Funded scenarios", "Paper"])
with tabs[0]:
    st.json(read("data_quality.json", {}))
    st.json({k: experiment.get(k) for k in ("dataset_version", "instrument", "timeframe", "created_at", "train_period", "final_test_period")})
with tabs[1]:
    rows = read("leaderboard.json", [])
    table = pd.DataFrame(rows)
    if not table.empty:
        columns = [c for c in ["candidate_id", "net_pnl", "max_drawdown", "sharpe", "profit_factor", "trades", "positive_fold_fraction", "research_eligible"] if c in table]
        st.dataframe(table[columns], width="stretch")
        metric = st.selectbox("Comparison metric", ["net_pnl", "max_drawdown", "trades"],
            format_func=lambda value: {"net_pnl": "Validation net P&L", "max_drawdown": "Maximum drawdown", "trades": "Number of trades"}[value])
        plotted = table.sort_values(metric)
        colors = ["#2b8a6e" if value > 0 else "#b94b55" if value < 0 else "#8b95a6" for value in plotted.net_pnl] if metric == "net_pnl" else "#526eb5"
        figure = go.Figure(go.Bar(x=plotted[metric], y=plotted.candidate_id, orientation="h", marker_color=colors,
            text=plotted.trades.map(lambda value: "No trades" if value == 0 else ""), textposition="outside",
            customdata=plotted[["net_pnl", "max_drawdown", "trades"]].to_numpy(),
            hovertemplate="%{y}<br>Net P&L $%{customdata[0]:,.2f}<br>Drawdown $%{customdata[1]:,.2f}<br>Trades %{customdata[2]}<extra></extra>"))
        figure.add_vline(x=0, line_color="#aab0bb", line_width=1)
        figure.update_layout(title=f"{experiment.get('instrument', '')} · {experiment.get('timeframe', '')}-minute validation",
            height=max(430, len(plotted)*25), margin=dict(l=210), xaxis_title="Trades" if metric == "trades" else "Simulated USD")
        st.plotly_chart(figure, width="stretch")
        risk_figure = go.Figure()
        for family, group in table.groupby("family"):
            risk_figure.add_scatter(x=group.max_drawdown, y=group.net_pnl, mode="markers", name=family,
                text=group.candidate_id, marker=dict(size=(8+group.trades.pow(.5).clip(upper=24))),
                hovertemplate="%{text}<br>Drawdown $%{x:,.2f}<br>Net P&L $%{y:,.2f}<extra>%{fullData.name}</extra>")
        risk_figure.add_hline(y=0, line_dash="dot")
        risk_figure.update_layout(title="Validation return versus drawdown", xaxis_title="Maximum drawdown (USD)", yaxis_title="Net P&L (USD)")
        st.plotly_chart(risk_figure, width="stretch")
        st.caption("Bubble size reflects trade count. Gray zero-trade bars are abstention benchmarks. Fold resets and bar-close exposure estimates limit comparisons; these charts do not establish deployment eligibility.")
    st.subheader("Failed and skipped attempts")
    st.dataframe(pd.DataFrame([dict(candidate=a.get("candidate_id"), status=a.get("status"), error=a.get("error")) for a in attempts if a.get("status") != "completed"]))
with tabs[2]:
    files = sorted(selected.glob("*_equity.parquet"))
    if files:
        curve_file = st.selectbox("Curve", files, format_func=lambda p: p.stem)
        curve = pd.read_parquet(curve_file).set_index("timestamp_utc")
        figure = go.Figure()
        figure.add_scatter(x=curve.index, y=curve.equity, name="Simulated equity", mode="lines")
        figure.add_scatter(x=curve.index, y=[50000]*len(curve), name="Flat cash benchmark", mode="lines", line=dict(dash="dot"))
        st.line_chart((curve.equity.cummax().clip(lower=50000)-curve.equity).rename("drawdown"))
        trade_file = Path(str(curve_file).replace("_equity.parquet", "_trades.parquet"))
        if trade_file.exists():
            trades = pd.read_parquet(trade_file)
            if not trades.empty:
                for field, label, symbol in (("entry_time", "Entry", "triangle-up"), ("exit_time", "Exit", "x")):
                    times = pd.to_datetime(trades[field], utc=True)
                    positions = curve.index.get_indexer(times, method="pad")
                    valid = positions >= 0
                    figure.add_scatter(x=times[valid], y=curve.equity.iloc[positions[valid]], mode="markers", name=label,
                        marker=dict(symbol=symbol, size=7), text=trades.net_pnl[valid].map(lambda value: f"Trade net P&L ${value:,.2f}"),
                        hovertemplate="%{x}<br>%{text}<extra>%{fullData.name}</extra>")
            st.dataframe(trades)
        figure.update_layout(xaxis_title="UTC", yaxis_title="Simulated USD equity", height=430)
        st.plotly_chart(figure, width="stretch")
        st.caption("Flat cash benchmark: $50,000. Fold simulations restart risk state; combined equity is an attribution curve.")
with tabs[3]:
    rows = read("leaderboard.json", [])
    calibrated = [r for r in rows if r.get("calibration")]
    for row in calibrated:
        st.write(row["candidate_id"])
        st.json({k: v for k, v in row["calibration"].items() if k != "reliability"})
        st.dataframe(pd.DataFrame(row["calibration"].get("reliability", [])))
    st.json(read("attribution.json", {}))
    st.json(read("model_analysis.json", {}))
    extended_file = ROOT/"reports/latest_extended_study.json"
    if extended_file.exists():
        extended = json.loads(extended_file.read_text())
        st.subheader("Registered extended studies")
        st.dataframe(pd.DataFrame([dict(instrument=row["instrument"], study=row["name"], status=row["status"],
            net_pnl=row.get("result", {}).get("metrics", {}).get("net_pnl"), error=row.get("error")) for row in extended["attempts"]]), width="stretch")
    st.caption("Importance, drift and ablation artifacts appear when those experiments have been run; absence is not a favorable result.")
with tabs[4]:
    st.info("Scenarios remain unverified for operational eligibility until purchased account settings and holidays are confirmed.")
    st.json(read("funded_account.json", {}))
with tabs[5]:
    states = sorted((ROOT/"runs").glob("*/state.json"))
    if states:
        state = st.selectbox("Paper session", states, format_func=lambda p: p.parent.name)
        st.json(json.loads(state.read_text(encoding="utf-8")))
        shutdown = state.parent/"shutdown.json"
        if shutdown.exists():
            st.json(json.loads(shutdown.read_text(encoding="utf-8")))
    else:
        st.info("No paper session available. Passing tests and a version-matched artifact are required.")
