"""Plot the five displayed test leaders from saved artifacts; no replay."""
import os
os.environ['MPLBACKEND']='Agg'
import csv
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter
from build_light_dashboard_charts import sampled_ids
from quant_futures.config import file_hash

ROOT=Path(__file__).resolve().parents[1]


def main():
    summary=json.loads((ROOT/'reports/positive_cohort_test_summary.json').read_text(encoding='utf-8'))
    folder=Path(summary['run_path']).resolve()
    source=folder/'test_results.csv'
    if file_hash(source)!=summary['results_csv_sha256']: raise ValueError('Saved results changed')
    with source.open(encoding='utf-8',newline='') as stream:
        rows=[r for r in csv.DictReader(stream) if r['user_test_checks_pass']=='True']
    rows.sort(key=lambda r:(-float(r['test_net']),max(float(r[k]) for k in ('test_cash_dd','test_closing_dd','test_intrabar_dd')),r['config_id']))
    plt.rcParams.update({'svg.fonttype':'none','font.size':10,'figure.facecolor':'#111b29','axes.facecolor':'#111b29',
        'text.color':'#e3eaf6','axes.labelcolor':'#b8c5da','xtick.color':'#b8c5da','ytick.color':'#b8c5da','axes.edgecolor':'#3a4b62'})
    fig,(net_ax,dd_ax)=plt.subplots(2,1,figsize=(13,8),sharex=True,gridspec_kw={'height_ratios':[1.5,1]})
    colors=['#64d9b1','#73b4ff','#f3c773','#c79aff','#f18e9d'];records=[]
    for rank,(r,color) in enumerate(zip(rows[:5],colors),1):
        curve_path=folder/'curves'/(r['config_id']+'.parquet')
        curve=pd.read_parquet(curve_path)
        peaks=np.maximum.accumulate(np.r_[50000.,curve.equity.to_numpy()])[1:]
        dd=peaks-curve.intrabar_worst_bound.to_numpy()
        assert abs(curve.equity.iloc[-1]-50000-float(r['test_net']))<1e-7
        assert abs(dd.max()-float(r['test_intrabar_dd']))<1e-7
        ids=np.unique(np.r_[sampled_ids(curve.equity,limit=390),dd.argmax()])
        label=f"#{rank} {r['instrument']} {r['family']} · {r['config_id'][-6:]}"
        net_line,=net_ax.plot(curve.timestamp_utc.iloc[ids],curve.equity.iloc[ids]-50000,color=color,linewidth=1.4,label=label)
        dd_line,=dd_ax.plot(curve.timestamp_utc.iloc[ids],-dd[ids],color=color,linewidth=1.1)
        net_line.set_gid(f'top5-net-{rank}')
        dd_line.set_gid(f'top5-dd-{rank}')
        records.append(dict(rank=rank,config_id=r['config_id'],instrument=r['instrument'],family=r['family'],
            net_pnl=float(r['test_net']),realized_drawdown=float(r['test_cash_dd']),intrabar_drawdown=float(r['test_intrabar_dd']),
            trades=int(r['test_trades']),display_points=len(ids),source_rows=len(curve),source_sha256=file_hash(curve_path),color=color))
    net_ax.axhline(0,color='#8090a5',linewidth=.7,linestyle='--');net_ax.set_ylabel('Net P&L after modeled costs')
    dd_ax.axhline(-2000,color='#ef6d76',linewidth=1,linestyle='--',label='$2,000 drawdown threshold')
    dd_ax.set_ylabel('Intrabar drawdown bound');dd_ax.set_ylim(-2100,75)
    for ax in (net_ax,dd_ax):
        ax.yaxis.set_major_formatter(StrMethodFormatter('${x:,.0f}'));ax.grid(alpha=.14,color='#8ca0bc')
    legend=net_ax.legend(loc='upper left',ncol=2,fontsize=9,facecolor='#172130',edgecolor='#3a4b62',labelcolor='#e3eaf6')
    for rank,(handle,label) in enumerate(zip(legend.get_lines(),legend.get_texts()),1):
        handle.set_gid(f'top5-legend-line-{rank}')
        label.set_gid(f'top5-legend-label-{rank}')
    fig.suptitle('Top 5 by recorded test net P&L',fontsize=18,x=.08,ha='left')
    fig.text(.08,.925,'Separate $50,000 accounts · Reused 2026 test results · No reruns or tuning',color='#b8c5da',fontsize=10)
    dd_ax.set_xlabel('Recorded test dates (UTC)')
    fig.subplots_adjust(left=.09,right=.98,top=.88,bottom=.09,hspace=.12)
    assets=ROOT/'dashboard/assets';fig.savefig(assets/'top5-test.svg',format='svg')
    fig.savefig(assets/'top5-test.png',dpi=150);plt.close(fig)
    receipt=dict(strategy_replayed=False,market_prices_loaded=False,parameters_changed=False,
        ranking='Same highest test-net ranking as the top100 display; DD ascending tie-break',
        source_results_sha256=summary['results_csv_sha256'],records=records,
        svg_bytes=(assets/'top5-test.svg').stat().st_size)
    (ROOT/'reports/top5_test_charts.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(dict(prepared=5,svg_bytes=receipt['svg_bytes'],strategy_replayed=False)))


if __name__=='__main__': main()
