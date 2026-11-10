"""Generate 4-panel visual chart comparing strategies to achieve ~2-week average pass time."""
import json
import matplotlib.pyplot as plt
import numpy as np

with open("quant_trading_bot/reports/GENTLE_FORTRESS_RESULTS.json") as f:
    results = json.load(f)

# Select key strategies to display
keys = [0, 1, 2, 4, 5]
labels = [
    "1. Static 6 MNQ\n(Baseline)",
    "2. Gentle 7c Finisher\n(6c -> 7c @ +$2k)",
    "3. Gentle 8c Finisher\n(6c -> 8c @ +$2k)",
    "4. Active VIX >= 16\n(6c -> 8c @ +$2k)",
    "5. High-Vol VIX >= 18\n(6c -> 8c @ +$2k)"
]

pass_pcts = [results[i]["pass_pct"] for i in keys]
ruin_pcts = [results[i]["ruin_pct"] for i in keys]
mean_days = [results[i]["mean_trade_days"] for i in keys]
med_days = [results[i]["med_trade_days"] for i in keys]
p25_days = [results[i]["p25_trade_days"] for i in keys]
min_days = [results[i]["min_trade_days"] for i in keys]
avg_dds = [results[i]["avg_dd"] for i in keys]

fig, axs = plt.subplots(2, 2, figsize=(15, 11))
fig.suptitle("Path to ~2-Week (10-14 Days) Average Evaluation Pass Time", fontsize=16, fontweight="bold", y=0.98)

# Panel 1: Pass Rate vs Ruin Rate
x = np.arange(len(labels))
width = 0.35
axs[0, 0].bar(x - width/2, pass_pcts, width, label="Pass Rate (%)", color="#2ecc71", edgecolor="black")
axs[0, 0].bar(x + width/2, ruin_pcts, width, label="Ruin Rate (%)", color="#e74c3c", edgecolor="black")
axs[0, 0].set_ylabel("Probability (%)", fontweight="bold")
axs[0, 0].set_title("Evaluation Outcome Probability (Topstep $50k Account)", fontweight="bold")
axs[0, 0].set_xticks(x)
axs[0, 0].set_xticklabels(labels, fontsize=9)
axs[0, 0].set_ylim(0, 110)
axs[0, 0].grid(axis="y", linestyle="--", alpha=0.5)
axs[0, 0].legend(loc="upper right")
for i in range(len(labels)):
    axs[0, 0].text(x[i] - width/2, pass_pcts[i] + 2, f"{pass_pcts[i]:.1f}%", ha="center", fontsize=8, fontweight="bold")
    axs[0, 0].text(x[i] + width/2, ruin_pcts[i] + 2, f"{ruin_pcts[i]:.1f}%", ha="center", fontsize=8, fontweight="bold")

# Panel 2: Mean vs Median vs P25 Pass Time
axs[0, 1].plot(x, mean_days, marker="o", linewidth=2.5, color="#e67e22", label="Mean (Average) Days")
axs[0, 1].plot(x, med_days, marker="s", linewidth=2.5, color="#3498db", label="Median (50th %) Days")
axs[0, 1].plot(x, p25_days, marker="^", linewidth=2.0, color="#9b59b6", linestyle="--", label="Top 25% (P25) Days")
axs[0, 1].plot(x, min_days, marker="*", linewidth=1.5, color="#27ae60", linestyle=":", label="Fastest (Min) Days")
axs[0, 1].axhline(10.0, color="red", linestyle="--", alpha=0.7, label="2-Week Target (10 Trading Days)")
axs[0, 1].set_ylabel("Trading Days to Pass", fontweight="bold")
axs[0, 1].set_title("Pass Time Distribution: Compressing Toward 2 Weeks", fontweight="bold")
axs[0, 1].set_xticks(x)
axs[0, 1].set_xticklabels(labels, fontsize=9)
axs[0, 1].set_ylim(0, 30)
axs[0, 1].grid(True, linestyle="--", alpha=0.5)
axs[0, 1].legend(loc="upper right", fontsize=8)
for i in range(len(labels)):
    axs[0, 1].text(x[i], mean_days[i] + 0.8, f"Avg:{mean_days[i]:.1f}d", ha="center", fontsize=8, color="#d35400", fontweight="bold")

# Panel 3: Maximum Drawdown on Pass
colors = ["#34495e", "#2980b9", "#16a085", "#27ae60", "#2ecc71"]
bars_dd = axs[1, 0].bar(labels, avg_dds, color=colors, edgecolor="black", width=0.55)
axs[1, 0].axhline(2000.0, color="red", linestyle="--", linewidth=1.5, label="Max Static Floor (-$2,000)")
axs[1, 0].axhline(1000.0, color="orange", linestyle=":", linewidth=1.5, label="Daily Loss Limit (-$1,000)")
axs[1, 0].set_ylabel("Average Peak Drawdown ($)", fontweight="bold")
axs[1, 0].set_title("Peak Drawdown During Passing Trials (Safety Buffer)", fontweight="bold")
axs[1, 0].set_ylim(0, 2200)
axs[1, 0].grid(axis="y", linestyle="--", alpha=0.5)
axs[1, 0].legend(loc="upper right")
for bar in bars_dd:
    yval = bar.get_height()
    axs[1, 0].text(bar.get_x() + bar.get_width()/2.0, yval + 40, f"${yval:,.2f}", ha="center", fontsize=8, fontweight="bold")

# Panel 4: Trading Days vs Calendar Velocity Comparison
cal_days_approx = [m * 1.4 for m in mean_days]
axs[1, 1].bar(x - width/2, mean_days, width, label="Mean Trading Sessions", color="#3498db", edgecolor="black")
axs[1, 1].bar(x + width/2, cal_days_approx, width, label="Approx Calendar Days (~1.4x)", color="#9b59b6", edgecolor="black")
axs[1, 1].axhline(14.0, color="red", linestyle="--", linewidth=1.5, label="2 Calendar Weeks (14 Days)")
axs[1, 1].set_ylabel("Days", fontweight="bold")
axs[1, 1].set_title("Calendar Velocity: Translating Sessions to Real Weeks", fontweight="bold")
axs[1, 1].set_xticks(x)
axs[1, 1].set_xticklabels(labels, fontsize=9)
axs[1, 1].set_ylim(0, 40)
axs[1, 1].grid(axis="y", linestyle="--", alpha=0.5)
axs[1, 1].legend(loc="upper right")
for i in range(len(labels)):
    axs[1, 1].text(x[i] - width/2, mean_days[i] + 0.8, f"{mean_days[i]:.1f}d", ha="center", fontsize=8, fontweight="bold")
    axs[1, 1].text(x[i] + width/2, cal_days_approx[i] + 0.8, f"{cal_days_approx[i]:.1f}d", ha="center", fontsize=8, fontweight="bold")

plt.tight_layout()
chart_path = r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d\two_week_average_passer_chart.png"
plt.savefig(chart_path, dpi=300)
print(f"Chart saved to {chart_path}")
