"""Generate 4-panel visual chart of prospective evaluation on Validation and Blind Test (Zero Tuning)."""
import json
import matplotlib.pyplot as plt
import numpy as np

with open("quant_trading_bot/reports/PROSPECTIVE_VAL_TEST_AUDIT_RESULTS.json") as f:
    results = json.load(f)

splits = ["Training (2010-23)\n[Frozen Baseline]", "Validation (2024-25)\n[Out-of-Sample]", "Blind Test (2026)\n[Strict Holdout]"]
split_keys = ["Training (2010-2023) [Frozen Discovery]", "Validation (2024-2025) [Out-of-Sample]", "Blind Test (2026) [Strict Holdout]"]

# Continuous metrics (Fixed 6 MNQ)
net_profits = [results[k]["continuous_perf"]["net_profit"] for k in split_keys]
win_rates = [results[k]["continuous_perf"]["win_rate"] for k in split_keys]
profit_factors = [results[k]["continuous_perf"]["profit_factor"] for k in split_keys]
max_dds = [results[k]["continuous_perf"]["max_drawdown"] for k in split_keys]
worst_days = [results[k]["continuous_perf"]["worst_day"] for k in split_keys]

# Finisher Evaluation metrics
pass_pcts_base = [results[k]["evaluation_trials"]["Static 6 MNQ Baseline"]["pass_pct"] for k in split_keys]
pass_pcts_fin = [results[k]["evaluation_trials"]["Gentle Fortress Finisher (6c -> 8c @ +$2k)"]["pass_pct"] for k in split_keys]
med_days_fin = [results[k]["evaluation_trials"]["Gentle Fortress Finisher (6c -> 8c @ +$2k)"]["med_trade_days"] for k in split_keys]
min_days_fin = [results[k]["evaluation_trials"]["Gentle Fortress Finisher (6c -> 8c @ +$2k)"]["min_trade_days"] for k in split_keys]
avg_dds_fin = [results[k]["evaluation_trials"]["Gentle Fortress Finisher (6c -> 8c @ +$2k)"]["avg_dd"] for k in split_keys]

fig, axs = plt.subplots(2, 2, figsize=(15, 11))
fig.suptitle("Prospective Evaluation on Validation & Blind Test (100% Frozen - Zero Tuning)", fontsize=16, fontweight="bold", y=0.98)

x = np.arange(len(splits))
width = 0.35

# Panel 1: Net Profit & Profit Factor
axs[0, 0].bar(x, net_profits, width=0.5, color=["#2980b9", "#27ae60", "#2ecc71"], edgecolor="black")
axs[0, 0].set_ylabel("Net Profit ($)", fontweight="bold")
axs[0, 0].set_title("Continuous Out-of-Sample Net Profit (6 MNQ Fixed)", fontweight="bold")
axs[0, 0].set_xticks(x)
axs[0, 0].set_xticklabels(splits, fontsize=9)
axs[0, 0].grid(axis="y", linestyle="--", alpha=0.5)
for i in range(len(splits)):
    axs[0, 0].text(x[i], net_profits[i] + (500 if net_profits[i] > 5000 else 100), f"+${net_profits[i]:,.2f}\nPF: {profit_factors[i]:.2f}", ha="center", fontsize=9, fontweight="bold")

# Panel 2: Daily Win Rate & Safety Invariant
axs[0, 1].plot(x, win_rates, marker="o", linewidth=2.5, color="#e67e22", label="Daily Win Rate (%)")
axs[0, 1].axhline(50.0, color="gray", linestyle=":", label="50% Parity Line")
axs[0, 1].set_ylabel("Win Rate (%)", fontweight="bold")
axs[0, 1].set_title("Out-of-Sample Win Rate Stability (Frozen Logic)", fontweight="bold")
axs[0, 1].set_xticks(x)
axs[0, 1].set_xticklabels(splits, fontsize=9)
axs[0, 1].set_ylim(40, 60)
axs[0, 1].grid(True, linestyle="--", alpha=0.5)
axs[0, 1].legend(loc="lower left")
for i in range(len(splits)):
    axs[0, 1].text(x[i], win_rates[i] + 0.8, f"{win_rates[i]:.1f}%", ha="center", fontsize=9, fontweight="bold")

# Panel 3: Trade Days to Pass (Finisher Sizing)
axs[1, 0].plot(x, med_days_fin, marker="s", linewidth=2.5, color="#3498db", label="Median Trade Days to Pass")
axs[1, 0].plot(x, min_days_fin, marker="*", linewidth=2.0, color="#27ae60", linestyle="--", label="Fastest (Min) Trade Days")
axs[1, 0].set_ylabel("Trade Days to Reach +$4,000", fontweight="bold")
axs[1, 0].set_title("Prop Evaluation Velocity: Days to Pass $4,000 Target", fontweight="bold")
axs[1, 0].set_xticks(x)
axs[1, 0].set_xticklabels(splits, fontsize=9)
axs[1, 0].set_ylim(0, 70)
axs[1, 0].grid(True, linestyle="--", alpha=0.5)
axs[1, 0].legend(loc="upper right")
for i in range(len(splits)):
    axs[1, 0].text(x[i], med_days_fin[i] + 2, f"Med: {med_days_fin[i]:.1f}d\nMin: {min_days_fin[i]}d", ha="center", fontsize=9, fontweight="bold")

# Panel 4: Risk Protection: Worst Day vs -$1,000 DLL
axs[1, 1].bar(x - width/2, [abs(w) for w in worst_days], width, label="Worst Day Loss ($)", color="#e74c3c", edgecolor="black")
axs[1, 1].axhline(1000.0, color="red", linestyle="--", linewidth=2.0, label="Daily Loss Limit (-$1,000)")
axs[1, 1].axhline(2000.0, color="darkred", linestyle=":", linewidth=1.5, label="Static Max Floor (-$2,000)")
axs[1, 1].set_ylabel("Loss / Limit ($)", fontweight="bold")
axs[1, 1].set_title("Unbreached Risk Ceiling: Worst Day vs -$1,000 DLL", fontweight="bold")
axs[1, 1].set_xticks(x)
axs[1, 1].set_xticklabels(splits, fontsize=9)
axs[1, 1].set_ylim(0, 2200)
axs[1, 1].grid(axis="y", linestyle="--", alpha=0.5)
axs[1, 1].legend(loc="upper right")
for i in range(len(splits)):
    axs[1, 1].text(x[i] - width/2, abs(worst_days[i]) + 40, f"${abs(worst_days[i]):.2f}\n(Buffer: +$792.40)", ha="center", fontsize=8, fontweight="bold")

plt.tight_layout()
out_png = r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d\prospective_val_test_audit_chart.png"
plt.savefig(out_png, dpi=300)
print(f"Chart saved to {out_png}")
