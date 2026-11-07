"""Read-only, local dashboard with no numerical or chart-library imports."""
import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/"dashboard/assets"


def read_report(name):
    path = ROOT/"reports"/name
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (json.JSONDecodeError,FileNotFoundError,PermissionError):
        # A checkpoint replacement may overlap this request. Keep the page
        # usable and let the next refresh pick up the complete saved record.
        return {}


def summary():
    development = read_report("latest_profit_drawdown_followup.json").get("best_selected",{})
    test = read_report("saved_version_reused_test.json")
    return dict(development=development,test=test,cohort_test_progress=read_report('positive_cohort_test_progress.json'),cohort_test_result=read_report('positive_cohort_test_summary.json'),continuation_progress=read_report('mass_continuation_progress.json'),continuation_result=read_report('mass_continuation_result.json'),mass_best_test=read_report('mass_best_reused_test.json'),mass_progress=read_report("mass_research_progress.json"),mass_result=read_report("mass_research_result.json"),training_afternoon_research=read_report("training_afternoon_research.json"),training_session_research=read_report("training_session_research.json"),training_selection=read_report("training_only_selection.json"),
        training_selected_validation=read_report("training_selected_validation.json"),training_selected_test=read_report("training_selected_test.json"),counts={key:value for key,value in read_report("strategy_counts.json").items()
        if key in ("distinct_strategy_definitions","unique_parameter_configurations","completed_run_attempts")},
        policy="Training data only for parameter selection. No tuning against validation or test data.")


def money(value):
    return f"−${abs(value):,.2f}" if value < 0 else f"${value:,.2f}"


def metrics(row, prefix=""):
    m = row.get("metrics",{})
    fields = [("Net P&L",money(m.get("net_pnl",0))),
        ("Closing drawdown",money(m.get("max_drawdown",0))),
        ("Intrabar drawdown",money(m.get("max_intraday_drawdown_bound",0))),
        ("Trades",str(m.get("trades",0)))]
    return '<div class="metrics">'+"".join(f'<div><span>{escape(prefix+label)}</span><strong>{escape(value)}</strong></div>' for label,value in fields)+"</div>"


def saved_rows():
    rows = []
    for path in sorted((ROOT/"reports/saved_candidates").glob("*/candidate.json")):
        candidate = json.loads(path.read_text(encoding="utf-8"))["candidate"]
        m = candidate["metrics"]
        rows.append("<tr>"+"".join(f"<td>{escape(str(value))}</td>" for value in (
            candidate["candidate_id"],money(m["net_pnl"]),money(m["max_drawdown"]),money(m["max_intraday_drawdown_bound"]),
            m["trades"],"Risk stopped" if m["permanent_risk_lock"] else "Completed"))+"</tr>")
    return "".join(rows)


def coverage_rows():
    catalog_path = ROOT/"data/catalog.json"
    if not catalog_path.exists():
        return ""
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    rows = []
    for symbol,item in catalog["instruments"].items():
        for role,part in item.get("splits",{}).items():
            coverage = part["coverage"]
            values = (symbol,role,coverage["start"][:10],coverage["end"][:10],f"{coverage['rows']:,}")
            rows.append("<tr>"+"".join(f"<td>{escape(value)}</td>" for value in values)+"</tr>")
    return "".join(rows)


def page():
    data = summary()
    development,test = data["development"],data["test"]
    params = development.get("candidate",{})
    description = (f"{params.get('contracts',0)} MNQ contracts · {params.get('stop_points',0)}-point stop · "
        f"{params.get('payoff',0)}R target · {params.get('exit_minute',0)//60:02d}:{params.get('exit_minute',0)%60:02d} ET exit")
    stress = development.get("stress",{}).get("2",{})
    counts = data["counts"]
    template = (ROOT/"dashboard/light_dashboard.html").read_text(encoding="utf-8")
    replacements = {
        "{{TRAINING_SESSION_RESEARCH}}":training_100k_card()+saved_50k_results_card()+training_50k_card()+top5_chart_card()+top1_validation_card()+cohort_test_card(data)+continuation_card(data)+mass_research_card(data)+mass_test_card(data)+session_research_card(data),
        "{{TRAINING_SELECTED_RESULT}}":training_selected_card(data),
        "{{TRAINING_CHART_BUTTON}}":('<button id="chart-training-selected" aria-pressed="false">Training-selected validation</button>'
            if data.get("training_selected_validation") else "")+('<button id="chart-training-test" aria-pressed="false">Training-selected test</button>'
            if data.get("training_selected_test") else ""),
        "{{DEVELOPMENT_METRICS}}":metrics(development),
        "{{TEST_METRICS}}":metrics(test),
        "{{PARAMETERS}}":escape(description),
        "{{COST_STRESS}}":escape(money(stress.get("net_pnl",0))),
        "{{SAVED_ROWS}}":saved_rows(),"{{COVERAGE_ROWS}}":coverage_rows(),
        "{{COUNTS}}":escape(f"{counts.get('distinct_strategy_definitions',0)} definitions · {counts.get('unique_parameter_configurations',0)} configurations · {counts.get('completed_run_attempts',0)} recorded attempts"),
        "{{TEST_STATUS}}":("The frozen strategy lost money. It stayed below the $2,000 drawdown ceiling but failed profitability and positive-confidence checks."
            if test.get("metrics",{}).get("net_pnl",0) <= 0 else "See the frozen evaluation report for the full checks."),
    }
    for key,value in replacements.items():
        template = template.replace(key,value)
    return template.encode("utf-8")


def integer(value,default=0):
    try:
        return max(0,int(value))
    except (ValueError,TypeError,OverflowError):
        return default


def training_100k_card():
    p=read_report('training_search_100k_progress.json');r=read_report('training_search_100k_result.json')
    if not p and not r: return ''
    record=r or p;n=integer(record.get('completed'));target=integer(record.get('target'),100000)
    card=f'<article class="card" id="training-100k"><h2>100,000 additional training configurations</h2><p><strong>{n:,} / {target:,}</strong> completed. Objective: highest training net with every drawdown strictly below $2,000.</p><progress value="{n}" max="{target}" style="width:100%">{n} of {target}</progress>'
    card+='<p class="muted">Training only; validation/test prices and outcomes stay closed. The user-provided 50% consistency rule is an evaluation-account-phase diagnostic. Research ranking also requires positive yearly folds, sufficient trades, no permanent risk lock, and doubled-cost survival.</p>'
    if r:
        w=r.get('winner')
        if w:
            b=w['base'];s=w['stress_2x']
            card+=f'<p><code>{escape(b["config_id"])}</code> · {escape(b["instrument"])} {escape(b["family"])}. Training net {money(b["net_pnl"])}; worst annual intrabar DD {money(b["intrabar_drawdown"])}. Doubled-cost net {money(s["net_pnl"])}.</p>'
            card+=f'<p>Evaluation-phase gates: base {bool(b["evaluation_phase_qualified"])}; doubled costs {bool(s["evaluation_phase_qualified"])}. Training improvement over the saved benchmark: {bool(r["improved_vs_benchmark"])}.</p>'
        else: card+='<p>No candidate passed the predeclared base and doubled-cost research gates.</p>'
    card+='<p class="links"><a href="/reports/TRAINING_SEARCH_100K.md" target="_blank" rel="noopener">Training report</a><a href="/training-100k/ranked.csv">Ranked CSV</a><a href="/training-100k/configurations.jsonl">Frozen configurations</a><a href="/charts/training-100k.svg" target="_blank" rel="noopener">Training curves</a></p></article>'
    return card


def training_100k_artifact(name):
    if name not in ('ranked.csv','configurations.jsonl','protocol.json','selected_training_candidate.json'): return None
    result=read_report('training_search_100k_result.json')
    record=result or read_report('training_search_100k_progress.json')
    if not record.get('run_path') or name=='ranked.csv' and not result: return None
    folder=Path(record['run_path']).resolve()
    if not folder.is_relative_to((ROOT/'runs').resolve()): return None
    path=(folder/name).resolve()
    return path if path.is_relative_to(folder) and path.is_file() else None


def saved_50k_results_card():
    r=read_report('saved_50k_candidate_summary.json')
    if not r: return ''
    parts=['<article class="card" id="saved-50k-results"><h2>Saved $9,972.50 training candidate: validation then test</h2>',
        '<p>MNQ trend · identical frozen parameters · one base-cost evaluation per split · no tuning.</p>',
        '<div class="table-wrap"><table><thead><tr><th>Period</th><th>Net P&amp;L</th><th>Cash DD</th><th>Intrabar DD</th><th>Trades</th><th>Permanent lock</th></tr></thead><tbody>']
    for phase in ('validation','test'):
        d=r[phase];m=d['metrics']
        values=[phase.title(),money(m['net_pnl']),money(m['realized_drawdown']),money(m['intrabar_drawdown']),m['trades'],d['lock_reason'] or 'none']
        parts.append('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in values)+'</tr>')
    parts.append('</tbody></table></div><div class="notice negative">Validation lost money and triggered the existing maximum-drawdown safety lock. Test was evaluated afterward unchanged and was profitable. The validation failure is preserved.</div>'
        '<p>The 50% consistency gate is recorded as evaluation-account-phase only per your instruction; this does not change trading rules. These previously observed periods are not independent confirmation.</p>'
        '<p class="links"><a href="/saved50k/frozen_candidate.json">Saved strategy and parameters</a><a href="/reports/SAVED_50K_CANDIDATE_SPLITS.md" target="_blank" rel="noopener">Full split report</a>'
        '<a href="/charts/saved-50k-validation.svg" target="_blank" rel="noopener">Validation curve</a><a href="/charts/saved-50k-test.svg" target="_blank" rel="noopener">Test curve</a></p></article>')
    return ''.join(parts)


def saved_50k_artifact(name):
    if name not in ('frozen_candidate.json','validation_trades.csv','test_trades.csv'): return None
    record=read_report('saved_50k_candidate_summary.json')
    if not record.get('path'): return None
    folder=Path(record['path']).resolve()
    if not folder.is_relative_to((ROOT/'runs').resolve()): return None
    path=(folder/name).resolve()
    return path if path.is_relative_to(folder) and path.is_file() else None


def training_50k_card():
    p=read_report('training_search_50k_progress.json');r=read_report('training_search_50k_result.json')
    if not p and not r: return ''
    record=r or p;completed=integer(record.get('completed'));target=integer(record.get('target'),50000)
    card=f'<article class="card" id="training-50k"><h2>50,000 new configurations: maximize training profit</h2><p><strong>{completed:,} / {target:,}</strong> completed. Cash, closing and intrabar drawdowns must each remain strictly below $2,000.</p>'
    card+=f'<progress value="{completed}" max="{target}" style="width:100%">{completed} of {target}</progress>'
    card+='<p class="muted">Training data only, 2020–2023 yearly accounts. Validation and test data remain closed for this search. Profit-first ranking with the original robustness gates and doubled-cost verification.</p>'
    if r:
        winner=r.get('winner')
        peak=r.get('top10',[{}])[0]
        if peak:
            card+=f'<p>Highest base-qualified training net: {money(peak["net_pnl"])}; worst annual intrabar DD {money(peak["intrabar_drawdown"])}.</p>'
        if winner:
            m=winner['base'];s=winner['stress_2x']
            card+=f'<p>Best new candidate passing base and doubled-cost gates: <code>{escape(m["config_id"])}</code> · {escape(m["instrument"])} {escape(m["family"])}. Training net {money(m["net_pnl"])}; worst annual intrabar DD {money(m["intrabar_drawdown"])}. Net at doubled costs: {money(s["net_pnl"])}.</p>'
            if not r.get('improved_vs_benchmark'):
                card+=f'<div class="notice">No higher-profit fully qualified replacement was found. Earlier training benchmark: {money(r["benchmark"]["net_pnl"])}. The highest base-profit new candidate failed the doubled-cost consistency gate.</div>'
        else: card+='<p>No candidate passed both base and doubled-cost gates.</p>'
    card+='<p class="links"><a href="/reports/TRAINING_SEARCH_50K.md" target="_blank" rel="noopener">Full training report</a><a href="/training-50k/ranked.csv">Ranked CSV</a><a href="/training-50k/configurations.jsonl">Frozen configurations</a><a href="/charts/training-50k.svg" target="_blank" rel="noopener">Saved training curves</a></p></article>'
    return card


def training_50k_artifact(name):
    if name not in ('ranked.csv','configurations.jsonl','protocol.json','selected_training_candidate.json','highest_base_profit_candidate.json'): return None
    record=read_report('training_search_50k_result.json') or read_report('training_search_50k_progress.json')
    if not record.get('run_path'): return None
    folder=Path(record['run_path']).resolve()
    if not folder.is_relative_to((ROOT/'runs').resolve()): return None
    path=(folder/name).resolve()
    return path if path.is_relative_to(folder) and path.is_file() else None


def top1_validation_card():
    result=read_report('top1_validation_dashboard.json')
    if not result: return ''
    m=result['metrics']
    return ('<article class="card" id="top1-validation"><h2>#1 test-ranked strategy: requested validation result</h2>'
        '<p>MNQ breakout · one unchanged base-cost evaluation · existing 2024–2025 validation split. No tuning and no test replay.</p>'
        +metrics(result)+f'<p>Realized-cash drawdown: {money(m["realized_drawdown"])}.</p>'
        '<div class="notice negative">'+escape(result['limitation'])+'</div>'
        '<p class="muted">Selected from test outcomes; validation was previously observed. This is a diagnostic, not independent confirmation.</p>'
        '<details><summary>Show saved validation equity and closing drawdown</summary><img class="chart" src="/charts/top1-validation.svg" loading="lazy" alt="Saved number1 strategy validation equity and closing drawdown"></details>'
        '<p><a href="/reports/TOP_TEST_NUMBER1_VALIDATION.md" target="_blank" rel="noopener">Full validation report and saved-test comparison</a></p></article>')


def top5_chart_card():
    if not (ASSETS/'top5-test.svg').is_file(): return ''
    records=read_report('top5_test_charts.json').get('records',[])
    controls=[]
    for row in records:
        rank=integer(row.get('rank'))
        label=f'#{rank} {row.get("instrument","")} {row.get("family","")} · {str(row.get("config_id",""))[-6:]}'
        color=row.get('color','#b8c5da')
        controls.append(f'<div class="top5-option"><label><input type="checkbox" data-top5-toggle="{rank}" checked>'
            f'<span style="color:{escape(color,quote=True)}">{escape(label)}</span></label>'
            f'<button type="button" data-top5-only="{rank}" aria-label="Show only {escape(label,quote=True)}">Show only</button></div>')
    return ('<article class="card" id="top5"><h2>Top 5 by recorded test P&amp;L</h2>'
        '<p>Net equity and intrabar drawdown for the five strategies in the top-100 list. Each starts with a separate $50,000 account. Reused 2026 test results; no reruns or tuning.</p>'
        '<div id="top5-controls"><p><button type="button" id="top5-show-all">Show all</button> '
        '<button type="button" id="top5-hide-all">Hide all</button></p>'
        +''.join(controls)+'</div><p class="muted" id="top5-status" aria-live="polite">Showing all five strategies.</p>'
        '<object id="top5-chart" class="chart" type="image/svg+xml" data="/charts/top5-test.svg" aria-label="Five strategy equity and drawdown chart" style="aspect-ratio:13/8;width:100%">'
        '<a href="/charts/top5-test.svg">Open the saved top-five chart</a></object>'
        '<p class="links"><a href="/charts/top5-test.png" target="_blank" rel="noopener">PNG (all five)</a>'
        '<a href="/charts/top5-test.svg" target="_blank" rel="noopener">SVG (all five)</a><a href="/top100-test">Top 100 details</a></p></article>')


def cohort_test_card(data):
    result=data.get('cohort_test_result',{});p=result or data.get('cohort_test_progress',{})
    if not p: return ''
    completed,target=integer(p.get('completed')),integer(p.get('target'))
    parts=['<article class="card" id="positive-cohort-test"><h2>All positive, low-drawdown training cases: requested test</h2>',
        f'<p><strong>{completed:,} / {target:,}</strong> results recorded. One unchanged base-cost case per configuration; no validation access or tuning.</p>']
    if result:
        parts.append(f'<p>{integer(result.get("positive_and_dd_under_2000")):,} had positive test P&amp;L and all drawdowns below $2,000. '
            f'{integer(result.get("full_test_scenario_pass")):,} also passed the recorded minimum-trade, consistency and risk scenario checks. '
            f'{integer(result.get("zero_trade_cases")):,} produced no trades. Full CSV includes every outcome.</p>')
        parts.append(f'<p>Of the10 candidates that passed every original training gate, '
            f'<strong>{integer(result.get("full_training_and_full_test_pass"))}</strong> passed all recorded test scenario checks.</p>')
        parts.append('<div class="table-wrap"><table><thead><tr><th>Original training-gate candidate</th><th>Family</th><th>Test net</th><th>Cash DD</th><th>Intrabar DD</th><th>Trades</th></tr></thead><tbody>')
        for r in result.get('full_training_gate_cases',[]):
            values=[r.get('config_id',''),r.get('family',''),money(r['test_net']) if 'test_net' in r else 'unavailable',
                money(r['test_cash_dd']) if 'test_cash_dd' in r else 'unavailable',money(r['test_intrabar_dd']) if 'test_intrabar_dd' in r else 'unavailable',r.get('test_trades','unavailable')]
            parts.append('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in values)+'</tr>')
        parts.append('</tbody></table></div>')
    parts.append('<div class="notice">This is a broad comparison on the previously observed2026 test period. It is not independent confirmation or a basis to select or deploy a winner. Results retain frozen training order; prior completed tests were reused without rerunning.</div>'
        '<p class="links"><a href="/top100-test" target="_blank" rel="noopener">Top100 P&amp;L / drawdown explorer</a><a href="/reports/POSITIVE_TRAINING_COHORT_TEST.md" target="_blank" rel="noopener">Full report</a>'
        '<a href="/cohort-test/test_results.csv">All results CSV</a><a href="/cohort-test/test_trades.csv">All trade logs CSV</a>'
        '<a href="/cohort-test/frozen_cohort.json">Frozen cohort and configurations</a></p></article>')
    return ''.join(parts)


def cohort_test_artifact(name):
    if name not in ('test_results.csv','test_trades.csv','frozen_cohort.json','top100_by_net.csv','top100_by_lowest_drawdown.csv','top100_by_profit_to_drawdown.csv'): return None
    record=read_report('positive_cohort_test_summary.json') or read_report('positive_cohort_test_progress.json')
    if not record.get('run_path'): return None
    folder=Path(record['run_path']).resolve()
    if not folder.is_relative_to((ROOT/'runs').resolve()): return None
    path=(folder/name).resolve()
    return path if path.is_relative_to(folder) and path.is_file() else None


def continuation_card(data):
    card=mass_research_card(dict(mass_progress=data.get('continuation_progress',{}),mass_result=data.get('continuation_result',{})))
    if not card: return ''
    card=card.replace('id="mass-research"','id="mass-continuation"').replace('10,000-configuration research engine','Additional10,000 training configurations')
    card=card.replace('/mass/','/continuation/').replace('/charts/mass-training.svg','/charts/mass-continuation.svg')
    for old,new in [('MASS_RESEARCH_REPORT.md','MASS_CONTINUATION_REPORT.md'),('MASS_RESEARCH_DETAILS.md','MASS_CONTINUATION_DETAILS.md'),
                    ('MASS_VALIDATION_REPORT.md','MASS_CONTINUATION_VALIDATION_REPORT.md'),('MASS_TEST_REPORT.md','MASS_CONTINUATION_TEST_REPORT.md')]:
        card=card.replace(old,new)
    return card.replace('</h2>','</h2><p class="muted">Original search domains and gates; next fixed seed20261107. Original10,000 configurations excluded. No selection from validation or test outcomes.</p>',1)


def mass_test_card(data):
    record=data.get('mass_best_test',{})
    if not record: return ''
    m=record.get('metrics',{})
    outcome='Passed the recorded scenario checks.' if record.get('scenario_checks_pass') else 'Failed the recorded scenario checks.'
    return ('<article class="card" id="mass-test"><h2>Frozen top MNQ strategy · requested test evaluation</h2>'
        '<p>One unchanged training-selected candidate; one base-cost test case. No fitting, tuning, alternate finalists or validation replay.</p>'
        +metrics(record)+f'<p>Realized-cash drawdown: {money(m.get("realized_drawdown",0))}. '
        +escape(outcome)+'</p><div class="notice">The2026 period was previously observed. This is a reused-test diagnostic, not independent confirmation. The original training research and prior test records are preserved.</div>'
        '<p class="links"><a href="/reports/MASS_BEST_REUSED_TEST.md" target="_blank" rel="noopener">Full frozen test result</a>'
        '<a href="/charts/mass-test.svg" target="_blank" rel="noopener">Saved test equity and drawdown</a></p></article>')


def mass_research_card(data):
    progress = data.get("mass_progress",{})
    result = data.get("mass_result",{})
    if not progress and not result:
        return ""
    record = result or progress
    completed = integer(record.get("completed"))
    target = max(10000,integer(record.get("target"),10000))
    unique = integer(record.get("unique_configs"))
    finished = bool(result) and completed >= target and unique >= target
    phase = "Training search complete" if finished else str(progress.get("phase","Training research running"))
    percent = min(100,100*completed/target)
    parts = ['<article class="card" id="mass-research"><h2>10,000-configuration research engine</h2>',
        f'<p>{escape(phase)} · <strong>{completed:,} / {target:,}</strong> completed · {unique:,} unique configurations.</p>',
        f'<progress aria-label="Completed training configurations" value="{min(completed,target)}" max="{target}" style="width:100%;height:18px">{percent:.1f}%</progress>']
    markets = progress.get("per_market",{})
    if isinstance(markets,dict) and markets:
        parts.append('<p class="muted">'+escape(' · '.join(f'{symbol}: {integer(markets.get(symbol)):,}' for symbol in ("ES","NQ","MES","MNQ")))+'</p>')
    explicit_closed = (record.get("validation_accessed",record.get("validation_prices_accessed")) is False
        and record.get("test_accessed",record.get("test_prices_accessed")) is False)
    parts.append('<div class="notice">'+('Training-only search: validation and test prices remain closed for this batch. '
        if explicit_closed else 'Price-access status is not verified by the current checkpoint. ')+
        'Existing split dates stay unchanged. Later periods were previously observed; fresh validation and an untouched final test are unavailable.</div>')
    if result:
        qualified = integer(result.get("qualified_count"))
        parts.append(f'<p><strong>Training-qualified configurations: {qualified:,}.</strong> This is not a profitability pass on unseen data or approval for live trading.</p>')
        rows = result.get("top10",[])
        if isinstance(rows,list) and rows:
            parts.append('<p class="muted">Net sums four separate training accounts; drawdowns are worst separate folds.</p><div class="table-wrap"><table><thead><tr><th>Training candidate</th><th>Market</th><th>Family</th><th>Net P&amp;L</th><th>Cash DD</th><th>Intrabar DD</th><th>Training qualified</th></tr></thead><tbody>')
            for row in rows[:10]:
                if not isinstance(row,dict):
                    continue
                metrics_ = row.get("metrics",{}) if isinstance(row.get("metrics",{}),dict) else {}
                try:
                    net = money(float(row.get("net_pnl",metrics_.get("net_pnl",0))))
                    drawdown = money(float(row.get("realized_drawdown",metrics_.get("max_drawdown",0))))
                    intrabar = money(float(row.get('intrabar_drawdown',metrics_.get('intrabar_drawdown',0))))
                except (ValueError,TypeError,OverflowError):
                    net,drawdown,intrabar = "Unavailable","Unavailable","Unavailable"
                values = (row.get("config_id",row.get("candidate_id","—")),row.get("instrument","—"),
                    row.get("family","—"),net,drawdown,intrabar,bool(row.get("qualified",False)))
                parts.append('<tr>'+''.join('<td>'+escape(str(value))+'</td>' for value in values)+'</tr>')
            parts.append('</tbody></table></div>')
    parts.append('<p class="links"><a href="/reports/MASS_RESEARCH_REPORT.md" target="_blank" rel="noopener">Full training research</a>'
        '<a href="/mass/ranked.csv">Ranked CSV</a><a href="/mass/configurations.jsonl">Configuration manifest</a>'
        '<a href="/reports/MASS_VALIDATION_REPORT.md" target="_blank" rel="noopener">Validation status</a>'
        '<a href="/reports/MASS_TEST_REPORT.md" target="_blank" rel="noopener">Final test status</a>'
        '<a href="/charts/mass-training.svg" target="_blank" rel="noopener">Saved training curves</a>'
        '<a href="/reports/MASS_RESEARCH_DETAILS.md" target="_blank" rel="noopener">Strategy rules and fold details</a></p></article>')
    return ''.join(parts)


def mass_artifact(name,continuation=False):
    if name not in ("ranked.csv","configurations.jsonl","protocol.json"):
        return None
    record = (read_report('mass_continuation_result.json') or read_report('mass_continuation_progress.json')) if continuation else (read_report("mass_research_result.json") or read_report("mass_research_progress.json"))
    if not record.get("run_path"):
        return None
    directory = Path(record["run_path"])
    if not directory.is_absolute():
        directory = ROOT/directory
    directory = directory.resolve()
    if not directory.is_relative_to((ROOT/"runs").resolve()):
        return None
    path = (directory/name).resolve()
    if not path.is_relative_to(directory) or not path.is_file():
        return None
    return path


def session_research_card(data):
    afternoon = bool(data.get("training_afternoon_research"))
    report = data.get("training_afternoon_research",{}) if afternoon else data.get("training_session_research",{})
    if not report:
        return ""
    count = report["qualified_candidates"]
    selected = report.get("selected")
    families = "midday trend, midday reversal and afternoon trend" if afternoon else "opening-range, failed-breakout and opening-momentum"
    result = (f'<article class="card"><h2>Latest research · training splits only</h2>'
        f'<p>24 fixed {families} cases. '
        'Three chronological NQ training blocks from 2010–2023. Top four cases replayed at doubled costs. '
        'No validation or test prices opened in this batch.</p>')
    result += f'<div class="notice">Training-qualified candidates: {count}. '
    result += ('Frozen candidate: '+escape(selected["candidate_id"])+'.' if selected else 'No candidate passed every check; no candidate was promoted.')
    report_link = "TRAINING_AFTERNOON_RESEARCH.md" if afternoon else "TRAINING_SESSION_RESEARCH.md"
    result += ('</div><p class="muted">Training-only findings use actual NQ mini-contract economics. '
        'They do not establish profitable MNQ trading or independent confirmation.</p>'
        f'<p><a href="/reports/{report_link}" target="_blank" rel="noopener">Latest training cases and cost checks</a></p>')
    if afternoon:
        result += '<p><a href="/reports/TRAINING_SESSION_RESEARCH.md" target="_blank" rel="noopener">Earlier 24 opening-session cases: no qualified candidate</a></p>'
    result += '</article>'
    return result


def training_selected_card(data):
    selection = data.get("training_selection",{})
    if not selection:
        return ""
    selected = selection["selected"]
    candidate = escape(selected["candidate_id"])
    result = data.get("training_selected_validation",{})
    description = (f'<article class="card"><h2>New candidate · training-only parameter selection</h2>'
        f'<p>Candidate <code>{candidate}</code> was chosen using NQ training history, then frozen before this validation evaluation. '
        'Neither validation nor test metrics entered this run’s ranking.</p>')
    if result:
        description += '<h3>Single frozen validation evaluation · actual MNQ 2024–2025</h3>'+metrics(result)
        passed = all(result["checks"].values())
        description += f'<div class="notice{ "" if passed else " negative"}">All declared validation checks passed: {passed}. Training qualification: {selected["training_qualified"]}. No retuning follows this result.</div>'
    else:
        description += '<p>Training selection is frozen. The one validation evaluation has not been published.</p>'
    test = data.get("training_selected_test",{})
    if test:
        description += '<h3>Same frozen candidate · testing split 2026</h3>'+metrics(test)
        description += ('<div class="notice negative">The test lost money and failed profitability and positive-confidence checks. '
            'It stayed below the $2,000 drawdown ceiling. One version, one base-cost test; no tuning. '
            'The earlier validation result was preserved without replay.</div>'
            '<p><a href="/reports/TRAINING_SELECTED_SPLITS.md" target="_blank" rel="noopener">Validation and test comparison</a></p>')
    description += ('<p class="muted">The inherited design was influenced by earlier validation-guided research. '
        'The validation period has already been observed; this is not fresh independent confirmation. '
        'NQ training profits use actual mini-contract economics and are not relabeled as MNQ profits.</p>'
        '<p><a href="/reports/TRAINING_SELECTED_VALIDATION.md" target="_blank" rel="noopener">Selection audit and outcome</a></p></article>')
    return description


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith(('/mass/','/continuation/','/cohort-test/','/training-50k/','/training-100k/','/saved50k/')):
            name=path.split('/',2)[2]
            if path.startswith('/training-100k/'): artifact=training_100k_artifact(name)
            elif path.startswith('/saved50k/'): artifact=saved_50k_artifact(name)
            elif path.startswith('/training-50k/'): artifact=training_50k_artifact(name)
            elif path.startswith('/cohort-test/'): artifact=cohort_test_artifact(name)
            else: artifact=mass_artifact(name,continuation=path.startswith('/continuation/'))
            if artifact is None:
                self.send_error(404,"Research artifact is unavailable")
                return
            self.send_response(200)
            self.send_header("Content-Type","text/csv; charset=utf-8" if artifact.suffix == ".csv" else "application/json; charset=utf-8" if artifact.suffix == ".json" else "application/x-ndjson; charset=utf-8")
            self.send_header("Content-Length",str(artifact.stat().st_size))
            self.send_header("Content-Disposition",f'attachment; filename="{artifact.name}"')
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.end_headers()
            with artifact.open("rb") as stream:
                shutil.copyfileobj(stream,self.wfile,length=65536)
            return
        if path in ("/health","/_stcore/health"):
            body,kind = b"ok","text/plain; charset=utf-8"
        elif path == "/":
            body,kind = page(),"text/html; charset=utf-8"
        elif path == "/api/summary":
            body,kind = json.dumps(summary(),ensure_ascii=False).encode("utf-8"),"application/json; charset=utf-8"
        elif path == '/api/training-50k':
            body,kind=json.dumps(dict(progress=read_report('training_search_50k_progress.json'),result=read_report('training_search_50k_result.json'))).encode('utf-8'),'application/json; charset=utf-8'
        elif path == '/api/training-100k':
            body,kind=json.dumps(dict(progress=read_report('training_search_100k_progress.json'),result=read_report('training_search_100k_result.json'))).encode('utf-8'),'application/json; charset=utf-8'
        elif path == '/top100-test':
            report_path=ROOT/'reports/TOP100_TEST_RESULTS.html'
            if not report_path.is_file():
                self.send_error(404,'Top100 view is not yet published')
                return
            body,kind=report_path.read_bytes(),'text/html; charset=utf-8'
        elif path == '/assets/top5_chart_controls.js':
            body,kind=(ROOT/'dashboard/top5_chart_controls.js').read_bytes(),'text/javascript; charset=utf-8'
        elif path in ("/charts/development.svg","/charts/test.svg","/charts/training-selected.svg","/charts/training-test.svg","/charts/mass-training.svg","/charts/mass-test.svg","/charts/mass-continuation.svg","/charts/top5-test.svg","/charts/top5-test.png","/charts/top1-validation.svg","/charts/training-50k.svg","/charts/saved-50k-validation.svg","/charts/saved-50k-test.svg","/charts/training-100k.svg"):
            file = ASSETS/path.rsplit("/",1)[1]
            if not file.exists():
                self.send_error(404,"Chart has not been prepared")
                return
            body,kind = file.read_bytes(),"image/png" if file.suffix=='.png' else "image/svg+xml"
        elif path in ("/reports/SAVED_VERSION_TEST.md","/reports/SAVED_CANDIDATES.md","/reports/PROFIT_DRAWDOWN_FOLLOWUP.md","/reports/TRAINING_SELECTED_VALIDATION.md","/reports/TRAINING_SELECTED_SPLITS.md","/reports/TRAINING_SESSION_RESEARCH.md","/reports/TRAINING_AFTERNOON_RESEARCH.md","/reports/MASS_RESEARCH_REPORT.md","/reports/MASS_VALIDATION_REPORT.md","/reports/MASS_TEST_REPORT.md","/reports/MASS_RESEARCH_DETAILS.md","/reports/MASS_BEST_REUSED_TEST.md","/reports/MASS_CONTINUATION_REPORT.md","/reports/MASS_CONTINUATION_DETAILS.md","/reports/MASS_CONTINUATION_VALIDATION_REPORT.md","/reports/MASS_CONTINUATION_TEST_REPORT.md","/reports/POSITIVE_TRAINING_COHORT_TEST.md","/reports/TOP_TEST_NUMBER1_VALIDATION.md","/reports/TRAINING_SEARCH_50K.md","/reports/SAVED_50K_CANDIDATE_SPLITS.md","/reports/TRAINING_SEARCH_100K.md"):
            report_path = ROOT/path.lstrip("/")
            if not report_path.is_file():
                self.send_error(404,"Report has not yet been published")
                return
            body,kind = report_path.read_bytes(),"text/plain; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type",kind)
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=8511)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1",args.port),Handler)
    print(f"Dashboard: http://127.0.0.1:{args.port}",flush=True)
    server.serve_forever()
