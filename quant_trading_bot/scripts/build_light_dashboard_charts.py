"""Prepare small SVG displays from saved curves; never replay a strategy."""
import os
for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[key] = "1"
from html import escape
import json
import math
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/"dashboard/assets"


def sampled_ids(equity,limit=600):
    if len(equity) <= limit:
        return list(range(len(equity)))
    groups = (limit-4)//2
    width = math.ceil(len(equity)/groups)
    chosen = {0,len(equity)-1}
    drawdown = equity.cummax().clip(lower=50000)-equity
    chosen.add(int(drawdown.to_numpy().argmax()))
    for start in range(0,len(equity),width):
        values = equity.iloc[start:start+width].to_numpy()
        chosen.add(start+int(values.argmin()))
        chosen.add(start+int(values.argmax()))
    return sorted(chosen)


def svg(curve,metrics,title):
    ids = sampled_ids(curve.equity)
    equity = curve.equity.to_numpy()-50000
    dd = (curve.equity.cummax().clip(lower=50000)-curve.equity).to_numpy()
    n = max(1,len(curve)-1)
    left,right,width = 92,970,1000
    def x(index): return left+(right-left)*index/n
    top = max(100,float(equity.max()))
    bottom = min(-100,float(equity.min()))
    pad = (top-bottom)*.08
    top,bottom = top+pad,bottom-pad
    def y(value): return 100+(top-value)/(top-bottom)*240
    max_dd = max(2000,float(dd.max())*1.05)
    def yd(value): return 430+value/max_dd*130
    bits = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 625" role="img" aria-labelledby="title description">',
        f'<title id="title">{escape(title)}</title><desc id="description">Net {metrics["net_pnl"]:.2f} dollars; closing drawdown {metrics["max_drawdown"]:.2f}; intrabar drawdown {metrics["max_intraday_drawdown_bound"]:.2f}. Display sampled from the saved full curve.</desc>',
        '<rect width="1000" height="625" fill="#111b29"/>',
        '<g font-family="system-ui,sans-serif" fill="#b8c5da" font-size="13">',
        f'<text x="30" y="36" fill="#eef4ff" font-size="20">{escape(title)}</text>',
        f'<text x="30" y="64">Net ${metrics["net_pnl"]:,.2f} · Closing DD ${metrics["max_drawdown"]:,.2f} · Intrabar DD ${metrics["max_intraday_drawdown_bound"]:,.2f}</text>']
    for i in range(5):
        value = bottom+(top-bottom)*i/4
        py = y(value)
        bits += [f'<line x1="{left}" y1="{py:.1f}" x2="{right}" y2="{py:.1f}" stroke="#28364a"/>',
            f'<text x="{left-12}" y="{py+5:.1f}" text-anchor="end">${value:,.0f}</text>']
    bits += [f'<line x1="{left}" y1="{y(0):.1f}" x2="{right}" y2="{y(0):.1f}" stroke="#65748a" stroke-dasharray="4 4"/>',
        '<text x="30" y="400" fill="#eef4ff" font-size="16">Closing drawdown</text>']
    for value in (0,1000,2000):
        bits += [f'<line x1="{left}" y1="{yd(value):.1f}" x2="{right}" y2="{yd(value):.1f}" stroke="#384154" stroke-dasharray="4 4"/>',
            f'<text x="{left-12}" y="{yd(value)+5:.1f}" text-anchor="end">−${value:,}</text>']
    net_points = ' '.join(f'{x(i):.1f},{y(equity[i]):.1f}' for i in ids)
    dd_points = ' '.join(f'{x(i):.1f},{yd(dd[i]):.1f}' for i in ids)
    bits += [f'<polyline fill="none" stroke="#58c5aa" stroke-width="2.2" points="{net_points}"/>',
        f'<polygon fill="#cd788d" opacity=".15" points="{left},430 {dd_points} {right},430"/>',
        f'<polyline fill="none" stroke="#df8a9e" stroke-width="1.7" points="{dd_points}"/>']
    for i in range(5):
        index = round((len(curve)-1)*i/4)
        bits.append(f'<text x="{x(index):.1f}" y="592" text-anchor="middle">{curve.timestamp_utc.iloc[index].strftime("%b %Y")}</text>')
    bits.append('</g></svg>')
    return ''.join(bits),len(ids)


def main():
    ASSETS.mkdir(exist_ok=True)
    development = json.loads((ROOT/"reports/latest_profit_drawdown_followup.json").read_text())
    test = json.loads((ROOT/"reports/saved_version_reused_test.json").read_text())
    cases = [("development",ROOT/"reports/saved_candidates"/development["best_selected"]["candidate_id"]/f"MNQ_{development['best_selected']['candidate_id']}_validation_equity.parquet",development["best_selected"]["metrics"],"Saved development version · reused 2024–2025"),
        ("test",ROOT/Path(test["path"])/"test_equity.parquet",test["metrics"],"Frozen saved version · reused 2026 test")]
    selected_path = ROOT/"reports/training_selected_validation.json"
    if selected_path.exists():
        selected = json.loads(selected_path.read_text(encoding="utf-8"))
        cases.append(("training-selected",ROOT/Path(selected["path"])/"validation_equity.parquet",selected["metrics"],
            "Training-selected candidate · one validation evaluation"))
    selected_test_path = ROOT/"reports/training_selected_test.json"
    if selected_test_path.exists():
        selected_test = json.loads(selected_test_path.read_text(encoding="utf-8"))
        cases.append(("training-test",ROOT/Path(selected_test["path"])/"test_equity.parquet",selected_test["metrics"],
            "Training-selected candidate · frozen reused-test evaluation"))
    receipt = {}
    for name,path,metrics,title in cases:
        curve = pd.read_parquet(path,columns=["timestamp_utc","equity"])
        assert abs(float(curve.equity.iloc[-1])-50000-metrics["net_pnl"]) < 1e-8
        image,points = svg(curve,metrics,title)
        target = ASSETS/(name+".svg")
        target.write_text(image,encoding="utf-8")
        receipt[name] = dict(source_rows=len(curve),display_points=points,bytes=target.stat().st_size)
    receipt["strategy_replayed"] = False
    (ROOT/"reports/light_dashboard_charts.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
