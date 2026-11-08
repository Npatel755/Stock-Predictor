import check_early_close_effect as ce

for name, cfg, bars in [
    ('MES MOM 1c', {**ce.mes_mom_3c, 'max_contracts': 1}, ce.bars_mes),
    ('MNQ BRK 1c', {**ce.mnq_brk_2c, 'max_contracts': 1}, ce.bars_mnq),
    ('MES HYB 1c', {**ce.mes_hyb_3c, 'max_contracts': 1}, ce.bars_mes),
    ('MNQ TRD 1c', {**ce.mnq_trd_1c, 'max_contracts': 1}, ce.bars_mnq),
]:
    r = ce.run(cfg, bars, True)
    print(f"{name:<15}: Net={r['net_pnl']:>8.2f} | DD={r['intrabar_drawdown']:>8.2f} | Trades={r['trades']:>3} | Lock={r.get('lock')} | Failed={r.get('funded_failed')}")
