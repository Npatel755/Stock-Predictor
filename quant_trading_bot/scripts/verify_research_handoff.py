"""Verify published latest-chart values and preserved candidate artifacts."""
import base64
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ChartParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "div" and "plotly-graph-div" in attributes.get("class", "").split():
            self.ids.append(attributes["id"])


def last_value(values):
    if isinstance(values, list):
        return values[-1]
    raw = base64.b64decode(values["bdata"])
    if values["dtype"] != "f8":
        raise ValueError("Unexpected equity-array encoding")
    return struct.unpack("<d", raw[-8:])[0]


def main():
    study = json.loads((ROOT/"reports/latest_profit_drawdown_followup.json").read_text())
    document = (ROOT/"reports/research_charts.html").read_text(encoding="utf-8")
    parsed = ChartParser()
    parsed.feed(document)
    assert len(parsed.ids) == len(set(parsed.ids))
    latest = document.split("<section id='latest-strategy'>", 1)[1]
    invocation = re.search(r'Plotly\.newPlot\(\s*"([^\"]+)"\s*,\s*', latest)
    assert invocation and invocation.group(1) == parsed.ids[0]
    traces, _ = json.JSONDecoder().raw_decode(latest[invocation.end():])
    equity = next(trace for trace in traces if trace["name"] == "Simulated equity")
    assert last_value(equity["y"]) == 50000+study["best_selected"]["metrics"]["net_pnl"]
    baseline = next(trace for trace in traces if trace["name"].startswith("Saved $5,779.50"))
    assert last_value(baseline["y"]) == 50000+study["baseline"]["metrics"]["net_pnl"]
    verified = []
    for manifest in sorted((ROOT/"reports/saved_candidates").glob("*/candidate.json")):
        saved = json.loads(manifest.read_text(encoding="utf-8"))
        for artifact in saved["artifacts"].values():
            assert sha(ROOT/artifact["path"]) == artifact["sha256"]
        verified.append(saved["candidate"]["candidate_id"])
    for name in ("latest_pareto_refinement.json", "sizing_profit_drawdown_followup.json", "latest_profit_drawdown_followup.json"):
        report = json.loads((ROOT/"reports"/name).read_text())
        assert report["final_test_accessed"] is False
        for filename, expected in report["script_hashes"].items():
            assert sha(Path(report["path"])/filename) == expected
    receipt = json.loads((ROOT/"reports/test_receipt.json").read_text())
    assert receipt["passed"] and receipt["source_hash"] == study["source_hash"]
    result = dict(passed=True, completed_at=datetime.now(timezone.utc).isoformat(),
        plot_containers=len(parsed.ids), latest_equity=last_value(equity["y"]),
        saved_candidates_verified=verified, source_snapshots_verified=True,
        test_accessed_by_prior_development_studies=False,
        chart_sha256=sha(ROOT/"reports/research_charts.html"), test_receipt=receipt)
    (ROOT/"reports/research_resume_verification.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
