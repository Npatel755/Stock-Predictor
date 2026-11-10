import json

with open('quant_trading_bot/reports/RESEARCH_UPGRADED_ZERO_RESET_STATIC_COMBINE.json', 'r') as f:
    rep = json.load(f)

print('=== 14-Year Chronological Sliding Window Audit (Nick $149 Static Combine Drop #011) ===')
print(f"{'Horizon':<12} | {'Months':<8} | {'Pass Rate':<10} | {'Survival':<10} | {'Ruin %':<8} | {'DLL Breaches':<12} | {'Resets':<8} | {'Median Days':<12}")
print('-' * 95)
for h, d in rep['chronological_sliding_window_audit'].items():
    s = d['sessions']
    mo = d['months_approx']
    pr = d['pass_rate_pct']
    srv = d['survival_rate_pct']
    rn = d['floor_ruin_pct']
    dll = d['dll_breaches']
    rst = d['resets_paid']
    md = d.get('median_days_to_pass', 'N/A')
    print(f"{s:<12} | {mo:<8.1f} | {pr:<9.1f}% | {srv:<9.1f}% | {rn:<7.2f}% | {dll:<12} | {rst:<8.1f} | {md}")
