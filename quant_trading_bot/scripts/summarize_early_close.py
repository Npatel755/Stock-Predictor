import check_early_close_effect as ce

for name, cfg, bars in [
    ('MES MOM 3c (Portfolio E leg)', ce.mes_mom_3c, ce.bars_mes),
    ('MNQ BRK 2c (Portfolio E leg)', ce.mnq_brk_2c, ce.bars_mnq),
    ('MES HYB 3c (10M Rank 6)', ce.mes_hyb_3c, ce.bars_mes),
    ('MNQ TRD 1c (10M Rank 5)', ce.mnq_trd_1c, ce.bars_mnq),
]:
    r_no = ce.run(cfg, bars, False)
    r_yes = ce.run(cfg, bars, True)
    print(f"=== {name} ===")
    print(f"  WITHOUT fix : Net={r_no['net_pnl']:>8.2f} | DD={r_no['intrabar_drawdown']:>8.2f} | Trades={r_no['trades']:>3} | Lock={r_no.get('lock')} | Failed={r_no.get('funded_failed')}")
    print(f"  WITH fix    : Net={r_yes['net_pnl']:>8.2f} | DD={r_yes['intrabar_drawdown']:>8.2f} | Trades={r_yes['trades']:>3} | Lock={r_yes.get('lock')} | Failed={r_yes.get('funded_failed')}")
