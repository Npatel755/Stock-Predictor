import sys, pandas as pd, numpy as np

ROOT = Path = sys.path.insert(0, 'quant_trading_bot/scripts')
from research_composite_symmetric_and_regime_train import *

sig_regime = np.zeros(len(rth_mnq), dtype=np.int8)
sig_regime[(net_sig_arr > 0) & sma_gate_arr] = 1
sig_regime[(net_sig_arr < 0) & (~sma_gate_arr)] = -1

pnl_reg, ntr_reg = sim_two_sided(o, h, l, c, atr, sig_regime, day, sod, 1.5, 3.5, 12, 955, COMM, SLIP, spec['pv'], spec['tick'])
s_reg = pd.Series(pnl_reg)
tot_reg = float(s_reg.sum())
pre_reg = float(s_reg[year < 2020].sum())
post_reg = float(s_reg[year >= 2020].sum())
yearly_reg = s_reg.groupby(year).sum()
pos_reg = int((yearly_reg > 0).sum())
cum_reg = s_reg.cumsum()
mdd_reg = float((cum_reg.cummax() - cum_reg).max())

print('=== 200-SMA REGIME ASYMMETRIC COMPOSITE (Long above, Short below) ===')
print('Total Net: USD', tot_reg, '| Trades:', ntr_reg, f'({ntr_reg/14:.1f} tr/yr) | Exp: USD', tot_reg/ntr_reg)
print('Pre-2020: USD', pre_reg, '| Post-2020: USD', post_reg, '| +Yrs:', pos_reg, '/ 14')
print('Max DD: USD', mdd_reg, '| Safety Buffer: USD', 2000 - mdd_reg)
print('Yearly:')
for yr, val in yearly_reg.items():
    print(f'  {yr}: USD {val:+.2f}')
