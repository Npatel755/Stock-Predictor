"""Export saved training-only finalist curves, ledgers, and explanatory notes.

Reads completed experiment artifacts only; never loads protected market prices.
"""
import os
os.environ['MPLBACKEND']='Agg'
from pathlib import Path
import csv
import json
import hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]


def read(path): return json.loads(path.read_text(encoding='utf-8'))


def export(result,folder):
    outputs=[]
    for rank,row in enumerate(result['top10'],1):
        cid=row['config_id']
        fig,axes=plt.subplots(4,2,figsize=(13,10),layout='constrained')
        logs=[]
        for i,fold in enumerate(row['fold_metrics']):
            stem=cid+'_'+fold['label']
            curve=pd.read_parquet(folder/(stem+'_equity.parquet'))
            trades=pd.read_parquet(folder/(stem+'_trades.parquet'))
            trades.insert(0,'fold',fold['label']);logs.append(trades)
            equity=curve.equity.to_numpy()
            peaks=np.maximum.accumulate(np.r_[50000,equity])[1:]
            dd=peaks-equity
            adverse=peaks-curve.intrabar_worst_bound.to_numpy()
            # Decimation affects display only; retain exact DD extrema.
            ids=np.unique(np.r_[np.linspace(0,len(curve)-1,min(600,len(curve)),dtype=int),dd.argmax(),adverse.argmax()])
            x=curve.timestamp_utc.iloc[ids]
            axes[i,0].plot(x,equity[ids]-50000,color='#276da8',linewidth=.8)
            axes[i,0].axhline(0,color='gray',linewidth=.5)
            axes[i,1].plot(x,-dd[ids],label='Closing',linewidth=.8)
            axes[i,1].plot(x,-adverse[ids],label='Intrabar bound',linewidth=.6,alpha=.7)
            axes[i,1].axhline(-2000,color='#b33a3a',linestyle='--',linewidth=.8)
            for ax in axes[i]:
                ax.set_title(fold['label']);ax.grid(alpha=.15);ax.set_ylabel('USD');ax.tick_params(axis='x',labelsize=7)
            if i==0: axes[i,1].legend(fontsize=8)
        axes[0,0].set_title(row['fold_metrics'][0]['label']+' | Net equity')
        axes[0,1].set_title(row['fold_metrics'][0]['label']+' | Drawdown')
        fig.suptitle(f"Training rank {rank}: {row['instrument']} {row['family']} | {cid}\nFour separate $50k accounts; capital resets by fold; display sampled")
        target=folder/(cid+'_curves.png')
        fig.savefig(target,dpi=130)
        if rank==1:
            plt.rcParams['svg.fonttype']='none'
            fig.savefig(ROOT/'dashboard/assets/mass-training.svg',format='svg')
        plt.close(fig)
        ledger=folder/(cid+'_trades.csv')
        pd.concat(logs,ignore_index=True).to_csv(ledger,index=False)
        outputs.append(dict(config_id=cid,plot=target.name,ledger=ledger.name,trades=sum(len(log) for log in logs)))
    return outputs


def describe(result,folder,outputs):
    rows=list(csv.DictReader((folder/'ranked.csv').open(encoding='utf-8',newline='')))
    best=result['top10'][0]
    c=best['parameters']
    formulas={
        'trend':'EMA(L/2) minus EMA(L), divided by trailing ATR14; follow its sign above the threshold.',
        'momentum':'Price change over L completed bars divided by ATR14 times sqrt(L); follow its sign above the threshold.',
        'mean_reversion':'Fade the rolling L-bar close z-score when its magnitude exceeds the threshold.',
        'breakout':'Trade beyond the preceding L-bar high/low plus threshold times ATR14.',
        'vwap':'Fade session cumulative volume-weighted typical price when the ATR-normalized deviation exceeds threshold, only while absolute L-bar normalized momentum is at most1.',
        'opening_range':'Trade beyond the completed L-minute regular opening range plus threshold times ATR14.',
        'regime':'Follow L-bar normalized momentum when path efficiency exceeds threshold/3 and short/long volatility ratio is below1.5.',
        'volatility':'Follow L-bar normalized momentum when short/long return-volatility ratio exceeds threshold.',
        'volume':'Follow L-bar normalized momentum when volume divided by preceding L-bar average volume exceeds threshold.',
        'hybrid':'Follow EMA trend when its sign agrees with the 2L-bar price change and absolute normalized momentum exceeds threshold.'}
    lines=['# Frozen training research details','',
        f"Completed **{len(rows):,}** configurations across four markets and ten families. **{result['qualified_count']}** met all training gates.",'',
        'All configurations were selected retrospectively within training. The four chronological blocks assess fixed-rule stability; they are not an independently selected external walk-forward record. There is no fitted predictive model or evaluation-block recalibration.', '',
        'The ranking treats Sharpe as a mean of fold daily Sharpes; profit factor pools winning and losing net trade P&L. Net profit sums four disjoint fold accounts. Closing, cash, and intrabar drawdowns are the worst separate fold, not a continuous account drawdown.', '',
        '## Highest ranked training configuration','',
        ('**Training-qualified only; external evidence remains unavailable.**' if best['qualified'] else '**Diagnostic candidate only: this configuration failed at least one training gate. There is no qualifying strategy to recommend.**'),'',
        f"`{best['config_id']}` — {c['instrument']} / {c['family']}. {formulas[c['family']]}",'',
        '```json',json.dumps(c,indent=2),'```','',
        f"Signal lookback is {c['lookback']} {'minutes of opening range' if c['family']=='opening_range' else 'completed 15-minute bars'}. Decision times are ET minutes {c['session_start']} through {c['session_end']} exclusive. Entries execute at the following open, with the last entry open no later than15 minutes before the configured session end. Flat by ET minute {min(c['session_end'],955)}. Weekdays only.",'',
        f"Initial stop is {c['stop_atr']} × ATR14, rounded upward to full ticks; target is {c['target_r']} × stop distance. Maximum hold {c['hold_bars']} bars; trailing stop distance {c['trailing_atr']} × preceding completed ATR14 (zero disables it). Signals are HOLD while a position is open; no reversal exits.",'',
        f"Maximum {c['max_contracts']} contracts, further limited by $150 stop risk including round-trip fees/slippage reserve and 1% of prior-bar volume. Daily loss scenario $300; hard drawdown lock $1,800; provisional EOD funded floor $2,000 below peak completed cash, capped at $50,100. Five consecutive losses lock the session. These are scenario assumptions, not verified account eligibility.",'',
        '## Fold results','',
        '| Fold | Net USD | Closing DD | Cash DD | Intrabar DD | Trades | Consistency | Lock |','|---|---:|---:|---:|---:|---:|---:|---|']
    for m in best['fold_metrics']:
        ratio=m['consistency']
        lines.append(f"| {m['label']} | {m['net_pnl']:.2f} | {m['max_drawdown']:.2f} | {m['realized_drawdown']:.2f} | {m['intrabar_drawdown']:.2f} | {m['trades']} | {ratio if ratio is not None else 'undefined'} | {m['lock']} |")
    failures=dict(nonpositive_fold=0,insufficient_trades=0,drawdown_limit=0,risk_lock=0,funded_floor_breach=0,consistency=0)
    for row in rows:
        fm=json.loads(row['fold_metrics'])
        failures['nonpositive_fold']+=any(m['net_pnl']<=0 for m in fm)
        failures['insufficient_trades']+=any(m['trades']<30 for m in fm)
        failures['drawdown_limit']+=any(max(m['max_drawdown'],m['realized_drawdown'],m['intrabar_drawdown'])>=2000 for m in fm)
        failures['risk_lock']+=any(m['killed'] for m in fm)
        failures['funded_floor_breach']+=any(m['funded_failed'] for m in fm)
        failures['consistency']+=any(m['consistency'] is None or m['consistency']>.5 for m in fm)
    lines+=['','## Failed training gates','',
        'Counts overlap: a configuration may fail several gates. No gate was relaxed after the search.','',
        '| Gate failure | Configurations |','|---|---:|']
    lines += [f'| {name} | {count:,} |' for name,count in failures.items()]
    lines+=['','## Training data provenance','',
        '| Market | Source minute rows | Accepted complete15m bars | Source minutes retained |','|---|---:|---:|---:|']
    for symbol in ('ES','NQ','MES','MNQ'):
        meta=read(folder/'cache'/(symbol+'_15m.json'))
        lines.append(f"| {symbol} | {meta['source_rows']:,} | {meta['bars']:,} | {15*meta['bars']/meta['source_rows']:.1%} |")
    lines+=['','## Selection uncertainty and data limits','',
        'The no-trade baseline is $0 net with no losses or exposure. Ten thousand correlated configurations create substantial selection bias; the ranking is not a multiple-testing-adjusted significance test. No Deflated Sharpe or PBO confidence claim is made. Even a training-qualified result remains RESEARCH-ONLY. Negative candidates and the full universe remain in the CSV.', '',
        f"Behavior groups after identical signal-path/exit/sizing comparison: {sum(r['behaviorally_unique']=='True' for r in rows):,}. Distinct active parameter configurations do not imply independent trading edges.",'',
        'Only exact contiguous complete 15-minute source windows are used. Missing bars are not interpolated. Indicators reset at raw contract changes or gaps over20 minutes. This conservative treatment can leave little eligible history, especially for long lookbacks. Authoritative historical holiday schedules and current fee/account-rule versions remain unresolved.', '',
        'All regime tags use the previous completed candle and are available before entry. The two regimes are a fixed ATR-normalized EMA-trend magnitude threshold of0.5. They are descriptive diagnostics, not an adaptively fitted filter.', '',
        '## Preserved artifacts','']
    for output in outputs:
        lines.append(f"- `{output['config_id']}`: [{output['plot']}]({output['plot']}), [{output['ledger']}]({output['ledger']}); {output['trades']} base-cost trades across all folds. Full-resolution equity and 2×-cost paths remain in Parquet files.")
    lines+=['','## Reproduction','',
        'Run from the quant_trading_bot project with its existing immutable training catalog and Python environment:','',
        '```powershell','.\\.venv\\Scripts\\python.exe scripts\\mass_research.py --run runs/mass_training_v2',
        '.\\.venv\\Scripts\\python.exe scripts\\publish_mass_research.py',
        '.\\.venv\\Scripts\\python.exe scripts\\render_mass_research.py','```','',
        'The run rejects changed source hashes, assumptions, or configuration universe. Completed configurations resume by unique SQLite primary key. Frozen code is in code/, runtime versions in code/runtime_versions.json, source manifests and fold boundaries beside protocol.json. Earlier partial mass_training_v1 was retired to correct regime-report timing; it is not counted as additional completed unique experiments.','']
    (folder/'RESEARCH_DETAILS.md').write_text('\n'.join(lines),encoding='utf-8')
    (ROOT/'reports/MASS_RESEARCH_DETAILS.md').write_text('\n'.join(lines).replace('](','](../runs/'+folder.name+'/'),encoding='utf-8')


def main():
    result=read(ROOT/'reports/mass_research_result.json')
    folder=Path(result['run_path']).resolve()
    if not folder.is_relative_to((ROOT/'runs').resolve()) or result['completed']!=10000:
        raise ValueError('Require a completed project run')
    outputs=export(result,folder)
    describe(result,folder,outputs)
    receipt=dict(training_artifacts_only=True,protected_market_prices_read=False,outputs=outputs)
    (ROOT/'reports/mass_research_chart_verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(dict(plots=len(outputs),ledgers=len(outputs))))


if __name__=='__main__': main()
