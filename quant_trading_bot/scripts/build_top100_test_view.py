"""Display rankings of already-recorded tests. No market access or replay."""
import csv
from html import escape
import json
from pathlib import Path
from quant_futures.config import file_hash

ROOT=Path(__file__).resolve().parents[1]
CSV_FIELDS=('display_rank','config_id','instrument','family','net','cash_dd','closing_dd','intrabar_dd','worst_dd',
    'net_to_dd','trades','profit_factor','expectancy','training_net','training_dd','full_training_qualified','full_test_scenario_pass','parameters')


def ordered(rows,mode):
    ratio=lambda r:r['net']/r['worst_dd'] if r['worst_dd']>0 else float('inf')
    if mode=='lowest_drawdown': key=lambda r:(r['worst_dd'],-r['net'],r['config_id'])
    elif mode=='profit_to_drawdown': key=lambda r:(-ratio(r),-r['net'],r['worst_dd'],r['config_id'])
    else: key=lambda r:(-r['net'],r['worst_dd'],r['config_id'])
    return sorted(rows,key=key)[:100]


def main():
    summary=json.loads((ROOT/'reports/positive_cohort_test_summary.json').read_text(encoding='utf-8'))
    folder=Path(summary['run_path']).resolve()
    if not folder.is_relative_to((ROOT/'runs').resolve()): raise ValueError('Invalid artifacts folder')
    source=folder/'test_results.csv'
    if file_hash(source)!=summary['results_csv_sha256']: raise ValueError('Recorded test results changed')
    freeze=json.loads((folder/'frozen_cohort.json').read_text(encoding='utf-8'))
    parameters={r['config_id']:r['parameters'] for r in freeze['candidate']['cohort']}
    rows=[]
    with source.open(encoding='utf-8',newline='') as stream:
        for r in csv.DictReader(stream):
            if r['user_test_checks_pass']!='True': continue
            row=dict(config_id=r['config_id'],instrument=r['instrument'],family=r['family'],net=float(r['test_net']),
                cash_dd=float(r['test_cash_dd']),closing_dd=float(r['test_closing_dd']),intrabar_dd=float(r['test_intrabar_dd']),
                trades=int(r['test_trades']),profit_factor=float(r['test_profit_factor']) if r['test_profit_factor'] else None,
                expectancy=float(r['test_expectancy']) if r['test_expectancy'] else None,training_net=float(r['training_net']),
                training_dd=max(float(r[k]) for k in ('training_cash_dd','training_closing_dd','training_intrabar_dd')),
                full_training_qualified=r['full_training_qualified']=='True',full_test_scenario_pass=r['full_test_scenario_checks_pass']=='True',
                parameters=parameters[r['config_id']])
            row['worst_dd']=max(row[k] for k in ('cash_dd','closing_dd','intrabar_dd'))
            row['net_to_dd']=row['net']/row['worst_dd'] if row['worst_dd']>0 else None
            rows.append(row)
    for mode in ('net','lowest_drawdown','profit_to_drawdown'):
        with (folder/('top100_by_'+mode+'.csv')).open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=CSV_FIELDS);writer.writeheader()
            for i,r in enumerate(ordered(rows,mode),1):
                writer.writerow(dict(r,display_rank=i,parameters=json.dumps(r['parameters'],sort_keys=True)))
    def money(v): return f'${v:,.2f}'
    initial=[]
    for i,r in enumerate(ordered(rows,'net'),1):
        cells=[i,r['config_id'],r['instrument'],r['family'],money(r['net']),money(r['cash_dd']),money(r['closing_dd']),money(r['intrabar_dd']),
            f"{r['net_to_dd']:.2f}" if r['net_to_dd'] is not None else 'infinite',r['trades'],
            'yes' if r['full_training_qualified'] else 'no','yes' if r['full_test_scenario_pass'] else 'no']
        initial.append('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in cells)+'</tr>')
    payload=json.dumps(rows,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Top 100 recorded strategy tests</title>
<style>
:root{font-family:system-ui,Segoe UI,sans-serif;color-scheme:dark;background:#101621;color:#e3eaf6}body{margin:0;padding:24px}main{max-width:1600px;margin:auto}h1{margin:0 0 8px;font-size:30px}p{line-height:1.55;color:#b9c7db}.notice{padding:14px;border-left:4px solid #d4a74c;background:#302b20;color:#e7d2a1;border-radius:5px}.controls{display:flex;gap:18px;flex-wrap:wrap;align-items:end;background:#172130;padding:20px;border-radius:10px;margin:20px 0}label{display:grid;gap:7px;font-size:13px;color:#b9c7db}select,input,button{font:inherit;background:#1e2b3d;color:#edf4ff;border:1px solid #50667e;border-radius:5px;padding:9px}input[type=number]{width:80px}button{cursor:pointer}a{color:#9dcdf2}.table{overflow:auto;border:1px solid #314159;border-radius:8px;max-height:76vh}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:11px 10px;border-bottom:1px solid #2a394d;text-align:left;white-space:nowrap}th{position:sticky;top:0;background:#1d2c40;z-index:1}tbody tr:nth-child(even){background:#172130}.positive{color:#8bd6b3}.small{font-size:12px;color:#91a4be}.flag{color:#edc985}pre{white-space:pre-wrap;max-width:400px;font-size:11px}summary{cursor:pointer}#status{font-weight:600}.links{display:flex;flex-wrap:wrap;gap:18px;margin:16px 0}@media(max-width:700px){body{padding:15px}.controls{padding:14px}h1{font-size:24px}}
</style></head><body><main>
<h1>Top 100 recorded strategy tests</h1>
<p>From 3,243 frozen training-selected configurations,1,181 had positive test net P&amp;L and all drawdowns below $2,000. No strategy was rerun or tuned to build this view.</p>
<div class="notice">These are already-observed 2026 test results. Display sorting is exploratory reporting, not independent validation or selection of a deployable winner. No candidate passed every original training gate and every recorded test gate. Modeled costs are included; actual account eligibility remains unverified.</div>
<div class="controls">
<label>Rank by<select id="mode"><option value="net">Highest net P&amp;L</option><option value="profit_to_drawdown">Highest profit / drawdown</option><option value="lowest_drawdown">Lowest drawdown</option></select></label>
<label>Market<select id="market"><option value="all">All markets</option><option>MNQ</option><option>MES</option></select></label>
<label>Minimum trades<input id="mintrades" type="number" min="0" step="1" value="0"></label>
<label>Checks<select id="gates"><option value="all">All positive / sub-$2,000 cases</option><option value="test">Pass recorded test scenario checks</option><option value="both">Pass full training and test checks</option></select></label>
<label>Find candidate / family<input id="find" type="search" placeholder="ID or family"></label>
<button id="download">Download displayed 100 as CSV</button></div>
<p id="status">Showing 100 by highest net P&amp;L.</p>
<p class="small">All figures below use one continuous $50,000 test account per strategy. Drawdown sorting uses the largest of closing, realized-cash and intrabar drawdown. Profit / DD uses that same maximum. Trade counts below 30 are flagged; no minimum is imposed by default. Expand a candidate to see its unchanged configuration.</p>
<div class="table"><table><thead><tr><th>Display rank</th><th>Candidate / configuration</th><th>Market</th><th>Family</th><th>Test net P&amp;L</th><th>Cash DD</th><th>Closing DD</th><th>Intrabar DD</th><th>Net / max DD</th><th>Trades</th><th>Full training gates</th><th>Test scenario gates</th></tr></thead><tbody id="rows">{{INITIAL}}</tbody></table></div>
<p class="links"><a href="/">Dashboard</a><a href="/reports/POSITIVE_TRAINING_COHORT_TEST.md">Full cohort report</a><a href="/cohort-test/test_results.csv">All 3,243 results CSV</a><a href="/cohort-test/top100_by_net.csv">Top 100 by P&amp;L CSV</a><a href="/cohort-test/top100_by_lowest_drawdown.csv">Lowest DD 100 CSV</a><a href="/cohort-test/top100_by_profit_to_drawdown.csv">Profit / DD100 CSV</a></p>
<script id="data" type="application/json">{{DATA}}</script>
<script>
const all=JSON.parse(document.getElementById('data').textContent), el=id=>document.getElementById(id);
const money=x=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(x);
const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ratio=r=>r.worst_dd>0?r.net/r.worst_dd:Infinity;let displayed=[];
function render(){
 const mode=el('mode').value, market=el('market').value, min=Math.max(0,Number(el('mintrades').value)||0), gates=el('gates').value, find=el('find').value.toLowerCase();
 const matches=all.filter(r=>(market==='all'||r.instrument===market)&&r.trades>=min&&(gates==='all'||r.full_test_scenario_pass&&(gates!=='both'||r.full_training_qualified))&&(!find||(r.config_id+' '+r.family).toLowerCase().includes(find)));
 matches.sort((a,b)=>(mode==='net'?b.net-a.net:mode==='lowest_drawdown'?a.worst_dd-b.worst_dd:(ratio(b)===ratio(a)?0:ratio(b)-ratio(a)))||(mode==='lowest_drawdown'||mode==='profit_to_drawdown'?b.net-a.net:a.worst_dd-b.worst_dd)||a.worst_dd-b.worst_dd||a.config_id.localeCompare(b.config_id));
 displayed=matches.slice(0,100);el('status').textContent=`Showing ${displayed.length} of ${matches.length} matching recorded tests. Ranking: ${el('mode').selectedOptions[0].textContent}.`;
 el('rows').innerHTML=displayed.map((r,i)=>`<tr><td>${i+1}</td><td><details><summary>${esc(r.config_id)}</summary><pre>${esc(JSON.stringify(r.parameters,null,2))}</pre><span class="small">Training net ${money(r.training_net)}; worst fold DD ${money(r.training_dd)}</span></details></td><td>${r.instrument}</td><td>${esc(r.family)}</td><td class="positive">${money(r.net)}</td><td>${money(r.cash_dd)}</td><td>${money(r.closing_dd)}</td><td>${money(r.intrabar_dd)}</td><td>${Number.isFinite(ratio(r))?ratio(r).toFixed(2):'∞ (zero observed DD)'}</td><td class="${r.trades<30?'flag':''}">${r.trades}${r.trades<30?' · small sample':''}</td><td>${r.full_training_qualified?'PASS':'FAIL'}</td><td>${r.full_test_scenario_pass?'PASS':'FAIL'}</td></tr>`).join('')||'<tr><td colspan="12">No recorded cases match these filters.</td></tr>';
}
for(const id of ['mode','market','mintrades','gates','find'])el(id).addEventListener('input',render);
el('download').addEventListener('click',()=>{const fields=['display_rank','config_id','instrument','family','net','cash_dd','closing_dd','intrabar_dd','worst_dd','trades','full_training_qualified','full_test_scenario_pass','parameters'];const q=v=>'"'+String(v??'').replaceAll('"','""')+'"';const csv=[fields.join(','),...displayed.map((r,i)=>fields.map(k=>q(k==='display_rank'?i+1:k==='parameters'?JSON.stringify(r.parameters):r[k])).join(','))].join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='top100_'+el('mode').value+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);});render();
</script></main></body></html>'''
    html=template.replace('{{INITIAL}}',''.join(initial)).replace('{{DATA}}',payload)
    (ROOT/'reports/TOP100_TEST_RESULTS.html').write_text(html,encoding='utf-8')
    receipt=dict(display_only=True,strategy_replays=0,parameter_changes=0,positive_low_dd_cases=len(rows),
        displayed_per_ranking=min(100,len(rows)),source_results_sha256=summary['results_csv_sha256'],
        ranking_modes=['net','lowest_drawdown','profit_to_drawdown'],html_bytes=len(html.encode('utf-8')))
    (ROOT/'reports/top100_test_view_verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt))


if __name__=='__main__': main()
