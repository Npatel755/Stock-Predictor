"""Generate comprehensive 4-panel publication-grade audit chart for Super Champion Fast Passer with Win Lock.
TRAINING SPLIT (2010-2023) ONLY.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
ARTIFACTS = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")

# Load multi-sleeve trades
trades = pd.read_parquet(ROOT / "data/processed/multi_sleeve_trades_train.parquet")
CORE_SLEEVES = ["AG_CRABEL15_D_1c", "OVERNIGHT_DIP", "AG_MES_TRD30_D_1c"]
trades = trades[trades.sleeve.isin(CORE_SLEEVES)].copy()
trades["tout"] = pd.to_datetime(trades.tout_str, utc=True)
trades["tin"] = pd.to_datetime(trades.tin_str, utc=True)
trades["date"] = trades.tout.dt.tz_convert("America/New_York").dt.date
trades = trades.sort_values("tin").reset_index(drop=True)

# Load ZN daily bond data for bond regime filter
zn = pd.read_parquet(ROOT / "data/market/crossasset_train/ZN_c_0_ohlcv1h_2010_2023.parquet")
zet = zn.index.tz_convert("America/New_York")
sel = zet.hour == 15
c = pd.Series(zn.close.to_numpy()[sel], index=pd.to_datetime(zet[sel].date)).groupby(level=0).last()
zn_ret = (c / c.shift(1) - 1).dropna()

tin_dates = pd.to_datetime(trades.tin.dt.tz_convert("America/New_York").dt.date)
unique_dates = pd.DatetimeIndex(sorted(tin_dates.unique()))
zn_mapped_daily = zn_ret.reindex(zn_ret.index.union(unique_dates)).ffill(limit=3).reindex(unique_dates)
trades["zn_down"] = tin_dates.map(zn_mapped_daily).to_numpy() < 0

# Apply bond filter to overnight
trades_opt = trades[~((trades.sleeve == "OVERNIGHT_DIP") & trades.zn_down)].copy()

daily_sleeve_pnl = trades_opt.groupby(["date", "sleeve"])["net_today"].sum().unstack(fill_value=0.0)
daily_sleeve_cum = daily_sleeve_pnl.cumsum()
total_portfolio_cum = daily_sleeve_pnl.sum(axis=1).cumsum()

# Set up figure
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
plt.subplots_adjust(hspace=0.32, wspace=0.25)

# -------------------------------------------------------------
# Panel 1: Single Account Evaluation Pass Probability (Progression to 57.5%)
# -------------------------------------------------------------
ax1 = axes[0, 0]
categories = ["2 Weeks (10 sess)", "3 Weeks (15 sess)", "1 Month (21 sess)"]
x = np.arange(len(categories))
width = 0.20

single_sleeve = [1.5, 3.7, 6.6]
baseline_4sleeve = [13.6, 26.6, 43.0]
super_champion = [21.1, 38.5, 57.5]
zero_control = [7.9, 14.3, 21.7]

rects1 = ax1.bar(x - 1.5*width, single_sleeve, width, label="Single-Sleeve (Crabel 15m)", color="#94a3b8")
rects2 = ax1.bar(x - 0.5*width, baseline_4sleeve, width, label="Baseline 4-Sleeve", color="#3b82f6")
rects3 = ax1.bar(x + 0.5*width, super_champion, width, label="Super Champion (Win-Locked)", color="#10b981")
rects4 = ax1.bar(x + 1.5*width, zero_control, width, label="Matched Zero-Edge Control", color="#ef4444", alpha=0.7)

ax1.set_title("Topstep Evaluation Pass Probability: Evolution to Super Champion", fontsize=12, fontweight="bold")
ax1.set_ylabel("Probability of Passing (%)", fontsize=11)
ax1.set_xticks(x)
ax1.set_xticklabels(categories, fontsize=10, fontweight="bold")
ax1.set_ylim(0, 68)
ax1.grid(axis="y", linestyle="--", alpha=0.5)
ax1.legend(loc="upper left", fontsize=9)

for rects in [rects1, rects2, rects3, rects4]:
    for r in rects:
        h = r.get_height()
        ax1.annotate(f"{h:.1f}%", xy=(r.get_x() + r.get_width()/2, h),
                     xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8)

# -------------------------------------------------------------
# Panel 2: Multi-Account Probability to Pass (1, 2, or 3 Accounts)
# -------------------------------------------------------------
ax2 = axes[0, 1]
x2 = np.arange(len(categories))
width2 = 0.25

p_1acc = [21.1, 38.5, 57.5]
p_2acc = [37.8, 62.2, 81.9]
p_3acc = [50.9, 76.7, 92.3]

b2_1 = ax2.bar(x2 - width2, p_1acc, width2, label="1 Account (Solo)", color="#3b82f6")
b2_2 = ax2.bar(x2, p_2acc, width2, label="2 Accounts Simultaneous", color="#10b981")
b2_3 = ax2.bar(x2 + width2, p_3acc, width2, label="3 Accounts Simultaneous", color="#f59e0b")

ax2.set_title("Multi-Account Scaling: P(At Least 1 Account Passes)", fontsize=12, fontweight="bold")
ax2.set_ylabel("Probability of At Least 1 Pass (%)", fontsize=11)
ax2.set_xticks(x2)
ax2.set_xticklabels(categories, fontsize=10, fontweight="bold")
ax2.set_ylim(0, 105)
ax2.grid(axis="y", linestyle="--", alpha=0.5)
ax2.legend(loc="upper left", fontsize=9)

for rects in [b2_1, b2_2, b2_3]:
    for r in rects:
        h = r.get_height()
        ax2.annotate(f"{h:.1f}%", xy=(r.get_x() + r.get_width()/2, h),
                     xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")

# -------------------------------------------------------------
# Panel 3: Cumulative 14-Year Equity of Super Champion Core
# -------------------------------------------------------------
ax3 = axes[1, 0]
ax3.plot(daily_sleeve_cum.index, daily_sleeve_cum["AG_CRABEL15_D_1c"] / 1000, label="Crabel 15m Breakout (+$51.0k, 52.4% win)", color="#3b82f6", lw=1.5)
ax3.plot(daily_sleeve_cum.index, daily_sleeve_cum["OVERNIGHT_DIP"] / 1000, label="Bond-Filtered Overnight (+$26.4k, 55.5% win)", color="#10b981", lw=1.5)
ax3.plot(daily_sleeve_cum.index, daily_sleeve_cum["AG_MES_TRD30_D_1c"] / 1000, label="MES 30m Trend (+$10.2k, 45.7% win)", color="#8b5cf6", lw=1.5)
ax3.plot(total_portfolio_cum.index, total_portfolio_cum / 1000, label="Super Champion Combined (+$87.6k)", color="#0f172a", lw=2.5)

ax3.set_title("14-Year Cumulative Equity: Quality-Curated Sleeves", fontsize=12, fontweight="bold")
ax3.set_ylabel("Cumulative P&L ($k)", fontsize=11)
ax3.grid(True, linestyle="--", alpha=0.5)
ax3.legend(loc="upper left", fontsize=9)

# -------------------------------------------------------------
# Panel 4: Final Comprehensive Scorecard
# -------------------------------------------------------------
ax4 = axes[1, 1]
ax4.axis("off")
table_data = [
    ["Metric", "Single Sleeve", "Champion 3-Sleeve", "Super Champion (Win-Lock)"],
    ["Pass Rate in 2 Weeks (10d)", "1.5%", "21.0%", "21.1% (37.8% across 2 acc)"],
    ["Pass Rate in 3 Weeks (15d)", "3.7%", "37.6%", "38.5% (62.2% across 2 acc)"],
    ["Pass Rate in 1 Month (21d)", "6.6%", "54.5%", "57.5% (81.9% across 2 acc)"],
    ["Pass Rate in 1 Mo (3 acc)", "N/A", "90.6%", "92.3% (9 out of 10 pass)"],
    ["Zero-Edge Random Control", "4.6%", "21.8%", "21.7%"],
    ["Genuine Alpha Boost", "+2.0%", "+32.7%", "+35.8% (Highest Edge)"],
    ["Average Resets Paid", "4.6 resets", "0.9 resets", "0.8 resets (Lowest)"],
    ["Estimated Cash Cost", "$274 total", "$93 total", "$88 total (Save $186)"],
    ["Intraday Win Lock", "None", "None", "$750 - $1,000 lock"],
    ["DLL Breach Risk (-$1,000)", "0.0% (guarded)", "0.0% (guarded)", "0.0% (guarded)"]
]

table = ax4.table(cellText=table_data, loc="center", cellLoc="center", colWidths=[0.32, 0.20, 0.24, 0.24])
table.auto_set_font_size(False)
table.set_fontsize(9.0)
table.scale(1.0, 1.8)

for i in range(4):
    cell = table[(0, i)]
    cell.set_facecolor("#1e293b")
    cell.set_text_props(color="white", fontweight="bold")

for r in range(1, len(table_data)):
    bg = "#f8fafc" if r % 2 == 0 else "#ffffff"
    if r in (1, 2, 3, 4, 6):
        bg = "#f0fdf4"
    for c in range(4):
        table[(r, c)].set_facecolor(bg)

ax4.set_title("Super Champion Final Scorecard", fontsize=12, fontweight="bold", pad=20)

out_path = ARTIFACTS / "multi_sleeve_fast_passer_chart.png"
plt.savefig(out_path, dpi=300, bbox_inches="tight")
print(f"Chart updated at {out_path}")
