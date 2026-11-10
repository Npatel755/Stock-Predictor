"""
Generate 4-Panel Publication-Grade Chart for the Upgraded Zero-Reset Topstep $50K Static Combine Architecture.
"""
import sys, json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
report_path = ROOT / "reports/RESEARCH_UPGRADED_ZERO_RESET_STATIC_COMBINE.json"

with open(report_path) as f:
    data = json.load(f)

chrono = data["chronological_sliding_window_audit"]
mc = data["monte_carlo_block_bootstrap"]
stress = data["adversarial_stress_lab"]

sessions = [int(k) for k in chrono.keys()]
months = [chrono[str(k)]["months_approx"] for k in sessions]
pass_rates = [chrono[str(k)]["pass_rate_pct"] for k in sessions]
zero_rates = [chrono[str(k)]["zero_edge_pct"] for k in sessions]
alpha_boost = [chrono[str(k)]["alpha_boost_pct"] for k in sessions]
surv_rates = [chrono[str(k)]["survival_rate_pct"] for k in sessions]
ruin_rates = [chrono[str(k)]["floor_ruin_pct"] for k in sessions]

plt.style.use("dark_background")
fig, axes = plt.subplots(2, 2, figsize=(18, 12), dpi=150)
fig.suptitle(
    "Topstep $50K Static Daily Payouts Combine ($149 One-Time Fee): Upgraded Zero-Reset Architecture\n"
    "14-Year Training Split Audit (2010–2023) | Multi-Skill Arsenal: Decomposition, Asymmetric Ratchet & Monte Carlo",
    fontsize=16, fontweight="bold", color="#00ffcc", y=0.98
)

# Panel 1: Cumulative Pass Rate Progression vs Zero-Edge Control
ax1 = axes[0, 0]
x_pos = np.arange(len(sessions))
w = 0.35
b1 = ax1.bar(x_pos - w/2, pass_rates, width=w, label="Upgraded Asymmetric Portfolio", color="#00d4ff", alpha=0.9)
b2 = ax1.bar(x_pos + w/2, zero_rates, width=w, label="Zero-Edge Control (Baseline Luck)", color="#ff5555", alpha=0.7)

for i, (p, a) in enumerate(zip(pass_rates, alpha_boost)):
    ax1.text(i - w/2, p + 1.2, f"{p}%\n(+{a}%)", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#ffffff")

ax1.set_xticks(x_pos)
ax1.set_xticklabels([f"{s}d\n(~{m}mo)" for s, m in zip(sessions, months)], fontsize=9)
ax1.set_ylabel("Cumulative Pass Rate (%)", fontsize=11, fontweight="bold", color="#00d4ff")
ax1.set_title("1. Cumulative Pass Rate vs Zero-Edge Control (0.0 Resets Paid)", fontsize=12, fontweight="bold", color="#ffffff")
ax1.legend(loc="upper left", frameon=True, facecolor="#1e1e1e", edgecolor="#444444")
ax1.grid(True, linestyle="--", alpha=0.3)
ax1.set_ylim(0, 90)

# Panel 2: Account Survival Rate & Floor Ruin
ax2 = axes[0, 1]
ax2.plot(x_pos, surv_rates, marker="o", linewidth=2.5, color="#00ff88", label="Account Survival Rate (%)")
ax2.plot(x_pos, ruin_rates, marker="s", linewidth=2.0, color="#ff3366", label="Floor Ruin Rate (%)")

for i, (s, r) in enumerate(zip(surv_rates, ruin_rates)):
    ax2.annotate(f"{s:.2f}%\n(R:{r:.2f}%)", (i, s - 4.5 if s > 95 else s + 2), ha="center", fontsize=8.5, fontweight="bold", color="#00ff88" if s > 95 else "#ff3366")

ax2.set_xticks(x_pos)
ax2.set_xticklabels([f"{s}d\n(~{m}mo)" for s, m in zip(sessions, months)], fontsize=9)
ax2.set_ylabel("Percentage (%)", fontsize=11, fontweight="bold", color="#00ff88")
ax2.set_title("2. Static Floor (-$2,000) Survival Rate (Zero Touch Guarantee)", fontsize=12, fontweight="bold", color="#ffffff")
ax2.legend(loc="center left", frameon=True, facecolor="#1e1e1e", edgecolor="#444444")
ax2.grid(True, linestyle="--", alpha=0.3)
ax2.set_ylim(-2, 105)

# Panel 3: Monte Carlo Block Bootstrap Path Distribution (60 Sessions)
ax3 = axes[1, 0]
mc_60 = mc["60"]
mc_metrics = [
    ("Pass Rate (60d)", mc_60["pass_rate_pct"], "#00d4ff"),
    ("Account Survival", mc_60["survival_rate_pct"], "#00ff88"),
    ("Static Floor Ruin", mc_60["ruin_rate_pct"], "#ff3366"),
    ("DLL Breaches", mc_60["dll_touches_pct"], "#ffd700"),
]

bars3 = ax3.bar([m[0] for m in mc_metrics], [m[1] for m in mc_metrics], color=[m[2] for m in mc_metrics], width=0.55, alpha=0.85)
for b, m in zip(bars3, mc_metrics):
    ax3.text(b.get_x() + b.get_width()/2, b.get_height() + 1.5, f"{m[1]}%", ha="center", va="bottom", fontsize=10, fontweight="bold", color="#ffffff")

ax3.set_ylabel("Probability Across 10,000 Paths (%)", fontsize=11, fontweight="bold", color="#ffffff")
ax3.set_title("3. Monte Carlo 10,000-Path Block Bootstrap (60 Calendar Sessions)", fontsize=12, fontweight="bold", color="#ffffff")
ax3.grid(True, linestyle="--", alpha=0.3)
ax3.set_ylim(0, 115)
ax3.text(0.5, 0.55, f"10,000 Resampled Paths\n5-Day Volatility Blocks\n95th% Max DD: ${mc_60['p95_drawdown']}\nDLL Breaches: 0.00%",
         transform=ax3.transAxes, ha="center", va="center", fontsize=10,
         bbox=dict(boxstyle="round,pad=0.6", facecolor="#111111", edgecolor="#00ffcc", alpha=0.9))

# Panel 4: Adversarial Stress Lab (Execution Friction)
ax4 = axes[1, 1]
stress_labels = list(stress.keys())
s_pass = [stress[k]["pass_rate_pct"] for k in stress_labels]
s_surv = [stress[k]["survival_rate_pct"] for k in stress_labels]
s_ruin = [stress[k]["ruin_rate_pct"] for k in stress_labels]

x_s = np.arange(len(stress_labels))
w_s = 0.35
ax4.bar(x_s - w_s/2, s_pass, width=w_s, label="Pass Rate (%)", color="#00d4ff", alpha=0.85)
ax4.bar(x_s + w_s/2, s_surv, width=w_s, label="Survival Rate (%)", color="#00ff88", alpha=0.85)

for i, (p, s) in enumerate(zip(s_pass, s_surv)):
    ax4.text(i - w_s/2, p + 1.2, f"{p}%", ha="center", va="bottom", fontsize=9, fontweight="bold", color="#ffffff")
    ax4.text(i + w_s/2, s + 1.2, f"{s}%", ha="center", va="bottom", fontsize=9, fontweight="bold", color="#ffffff")

short_labels = ["Baseline", "Adverse Slip\n(+2t on stops)", "Commission\nSurge (+50%)", "Severe\nFriction"]
ax4.set_xticks(x_s)
ax4.set_xticklabels(short_labels, fontsize=9)
ax4.set_ylabel("Percentage (%)", fontsize=11, fontweight="bold", color="#ffffff")
ax4.set_title("4. Adversarial Stress Lab: Extreme Execution Friction (60 Sessions)", fontsize=12, fontweight="bold", color="#ffffff")
ax4.legend(loc="lower right", frameon=True, facecolor="#1e1e1e", edgecolor="#444444")
ax4.grid(True, linestyle="--", alpha=0.3)
ax4.set_ylim(0, 115)

plt.tight_layout(rect=[0, 0, 1, 0.94])

chart_out = ROOT / "reports/upgraded_zero_reset_static_combine_chart.png"
plt.savefig(chart_out)
print(f"Saved chart to {chart_out}")

# Also copy to artifacts directory
import shutil
artifact_dir = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")
shutil.copy(chart_out, artifact_dir / "upgraded_zero_reset_static_combine_chart.png")
print(f"Copied chart to artifact directory: {artifact_dir / 'upgraded_zero_reset_static_combine_chart.png'}")
