from pathlib import Path
import importlib.util
import pytest
import platform


@pytest.mark.skipif(importlib.util.find_spec("streamlit") is None, reason="Optional Streamlit unavailable")
def test_dashboard_renders_without_exception():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/"dashboard/app.py"))
    # WSL imports and first Plotly render traverse the Windows-mounted project.
    # This is a functional check, not a dashboard latency benchmark.
    app.run(timeout=60 if platform.system() == "Linux" else 30)
    assert not app.exception
    latest = Path(__file__).resolve().parents[1]/"reports/post_final_research_summary.json"
    if latest.exists():
        import json
        risk = latest.parent/"latest_risk_expansion_study.json"
        expected = (json.loads(risk.read_text())["best_selected"] if risk.exists() else json.loads(latest.read_text())["leading_observed_candidate"])["metrics"]["net_pnl"]
        assert app.subheader[0].value.startswith("Latest research")
        assert app.metric[0].label == "Latest strategy net P&L"
        assert app.metric[0].value == f"${expected:,.2f}"
