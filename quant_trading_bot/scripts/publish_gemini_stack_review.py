"""Readable report from completed frozen research artifacts; no simulations."""
import html
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/gemini_stack_continuation_v1'


def main():
    r=json.loads((RUN/'results.json').read_text());audit=json.loads((RUN/'calendar_router_attribution.json').read_text())
    rows=[]
    for period in ('discovery','confirmation'):
        for name,key in [('Causal triple baseline','baseline'),('Frozen earlier-TRAIN choice','frozen_choice')]:
            m=r[period][key]
            rows.append({'Period':period,'Configuration':name,'24-month withdrawals':m['S0']['mean_withdrawals'],
              'Windows':m['S0']['windows'],'S0 closure %':m['S0']['closed_fraction']*100,
              'S3 risk-flag %':m['S3']['conservative_stoprisk_flag_fraction']*100,'S4 risk-flag %':m['S4']['conservative_stoprisk_flag_fraction']*100})
    table=pd.DataFrame(rows).to_html(index=False,border=0,float_format=lambda v:f'{v:,.2f}')
    legacy=audit['legacy_original_calendar']['S0']['mean_withdrawals'];full=audit['legacy_same_books_full_calendar']['S0']['mean_withdrawals'];causal=audit['causal_gapfilled_full_calendar']['S0']['mean_withdrawals']
    early=r['discovery']['lift_fraction']*100;late=r['confirmation']['lift_fraction']*100
    style='body{font:16px/1.65 system-ui;background:#111820;color:#e8edf2;max-width:1250px;padding:34px;margin:auto}h1{font-size:34px;line-height:1.2}h2{margin-top:32px}a{color:#91d6ff}.cards{display:flex;gap:14px;flex-wrap:wrap}.card{background:#1c2835;padding:18px;border:1px solid #43546a;border-radius:8px;flex:1;min-width:180px}.value{font-size:29px;color:#a4dbff;font-weight:700}.notice{padding:18px;border-left:4px solid #e1ad54;background:#322a1d}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:12px;border-bottom:1px solid #405064;white-space:nowrap;text-align:left}img{width:100%}pre{white-space:pre-wrap;font:14px/1.7 monospace}'
    page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Gemini triple-stack continuation</title><style>{style}</style>
<h1>Gemini triple-stack continuation</h1>
<p>BRK30 + MORN30 + TRD30PM · Funded payout research · TRAIN only</p>
<p class="notice"><strong>No qualifying replacement.</strong> The 31-cell continuation selected K $8,400 with both deep-cushion gates at $9,000 on earlier TRAIN. It improved mean base-scenario withdrawals by {early:.2f}% on earlier TRAIN and {late:.2f}% on later TRAIN. The frozen acceptance gate required at least 5% on both. No deployed or paper settings changed.</p>
<div class="cards"><div class="card"><div class="value">${legacy:,.0f}</div>Original model reproduced</div><div class="card"><div class="value">${full:,.0f}</div>Same inputs, all portfolio dates</div><div class="card"><div class="value">${causal:,.0f}</div>Causal router, filled TRAIN gap, all dates</div></div>
<p>These amounts are mean hypothetical withdrawals over 139 overlapping 24-month TRAIN windows. They are neither evaluation-pass profit nor verified live account payouts.</p>
<h2>What the audit found</h2>
<ol><li><strong>Rounded gate:</strong> the original S3 conservative risk flag occurred in 7 of 139 windows (5.03597%). Rounding it to 5.0% made a strict 5% limit appear to pass. This continuation uses the exact fraction.</li>
<li><strong>Omitted dates:</strong> the original account loop used only dates where the base book traded, omitting dates belonging only to added sleeves. Keeping the original trades and router but using the whole portfolio calendar changes the reproduced base-scenario mean from $52,016 to $44,654.</li>
<li><strong>Routing and history:</strong> the original router ordered signals by their bar-start labels, which can prioritize information before it was available. New selection uses entry availability and fixed priority. It also fills the already identified January–May 2019 TRAIN splice gap using the existing E-mini history. Applying those two changes jointly gives the $29,082 mean. Their individual effects are not separately identified here.</li></ol>
<h2>Frozen chronological comparison</h2>
<p>Discovery: 55 monthly starts from July 2010 through January 2015; each 24-month window ends by January 2017. Confirmation: 61 starts from January 2017 through January 2022, all ending within TRAIN. The intervening windows were purged from selection to prevent overlap across that boundary. One configuration was frozen before later-TRAIN confirmation, and no substitute was chosen afterward.</p>
<div class="scroll">{table}</div>
<img src="GEMINI_STACK_CONTINUATION_TRAIN.png" alt="Earlier TRAIN discovery and later TRAIN confirmation mean withdrawal comparison">
<p>On later TRAIN, the base-scenario mean rose from $39,757 to $40,816. Under S3 stress it fell from $29,443 to $28,162. The candidate remains a rejected research result despite its small base-scenario gain.</p>
<h2>Exact frozen choice</h2><pre>{html.escape(json.dumps(r['frozen_configuration'],indent=2))}</pre>
<p>The search covered the triple stack and the TRD60Q quad stack across the predefined keep/gate grid, plus separate MES 30-minute, E57, and MES momentum additions. It did not complete every possible penta-stack combination.</p>
<h2>Limits that remain</h2>
<p>The account model still clips daily P&amp;L at a $1,000 loss and checks end-of-day closure. Its conservative risk flag is a largest-position stop-risk proxy, not an observed intrabar floor breach. It can include a planned trade that a daily stop would skip. This audit does not establish exact DLL/floor execution or compliance with any current funded-account agreement.</p>
<p>The original payout schedule, floor assumptions, and fixed reference-price normalization were retained for comparability. Actual account terms were not independently verified. Overlapping windows are dependent; years of previous TRAIN optimization remain part of the selection history. Neither external validation/test data nor forward paper ledgers were used for selection. There is no independent unseen confirmation.</p>
<p>The optimized replay reconciles withdrawals plus ending balance to trading P&amp;L. It matches an independent Python account reference on 1,017 scenario/window paths, and the targeted fixture suite passed. The complete original scripts and rejected candidates are preserved.</p>
<p><a href="../runs/gemini_stack_continuation_v1/protocol.json">Frozen protocol</a> · <a href="../runs/gemini_stack_continuation_v1/all_earlier_training_candidates.csv">All 31 discovery cases</a> · <a href="../runs/gemini_stack_continuation_v1/frozen_earlier_train_choice.json">Choice frozen before later TRAIN</a> · <a href="../runs/gemini_stack_continuation_v1/calendar_router_attribution.json">Calendar reconciliation</a> · <a href="GEMINI_STACK_CONTINUATION_TRAIN.json">Full result</a> · <a href="GEMINI_STACK_CONTINUATION_TRAIN_verification.json">Verification</a></p></html>'''
    (ROOT/'reports/GEMINI_STACK_CONTINUATION_TRAIN.html').write_text(page,encoding='utf-8')
    print('Report rendered from saved artifacts; no simulations or holdout access.')


if __name__=='__main__':main()
