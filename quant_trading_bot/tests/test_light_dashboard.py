import importlib.util
import csv
import json
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("light_dashboard",ROOT/"dashboard/light_server.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


def test_light_dashboard_http_has_saved_results_and_bounded_payload():
    server = dashboard.ThreadingHTTPServer(("127.0.0.1",0),dashboard.Handler)
    worker = Thread(target=server.serve_forever,daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base+"/health") as response:
            assert response.read() == b"ok"
        with urlopen(base+"/") as response:
            page = response.read()
            assert len(page) < 30000
            text = page.decode("utf-8")
            assert "$6,622.00" in text and "−$356.00" in text
            assert "not independent validation" in text
            assert "No fitting, parameter changes" in text
            assert "plotly" not in text.lower() and "vega" not in text.lower()
            assert 'id="equity-chart"' in text
            assert 'src=' not in text.split('id="equity-chart"',1)[1].split('>',1)[0]
            if (ROOT/"reports/training_selected_validation.json").exists():
                assert "$5,071.00" in text
                assert "No retuning follows this result" in text
                assert "Training qualification: False" in text
                assert "not fresh independent confirmation" in text
            if (ROOT/"reports/training_selected_test.json").exists():
                assert "−$126.00" in text
                assert "The test lost money" in text
                assert "chart-training-test" in text
        with urlopen(base+"/charts/test.svg") as response:
            assert response.headers["Content-Type"] == "image/svg+xml"
            assert len(response.read()) < 30000
        with pytest.raises(HTTPError) as error:
            urlopen(base+"/reports/../../AGENTS.md")
        assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def test_prepared_charts_preserve_reported_values_and_limit_points():
    for name in ("development","test"):
        path = ROOT/"dashboard/assets"/(name+".svg")
        image = ET.fromstring(path.read_text(encoding="utf-8"))
        polylines = image.findall(".//{http://www.w3.org/2000/svg}polyline")
        assert len(polylines) == 2
        assert all(len(line.attrib["points"].split()) <= 600 for line in polylines)
        assert image.find("{http://www.w3.org/2000/svg}desc") is not None


def test_mass_checkpoint_can_be_partial_and_html_cannot_inject(monkeypatch,tmp_path):
    monkeypatch.setattr(dashboard,"ROOT",tmp_path)
    reports = tmp_path/"reports"
    reports.mkdir()
    checkpoint = reports/"mass_research_progress.json"
    checkpoint.write_text('{"completed":',encoding="utf-8")
    assert dashboard.read_report(checkpoint.name) == {}
    card = dashboard.mass_research_card(dict(mass_progress=dict(target=10000,completed=523,unique_configs=523,
        phase='<script>alert("bad")</script>',per_market=dict(ES=123,NQ=400),validation_accessed=False,test_accessed=False)))
    assert "523 / 10,000" in card
    assert '<script>' not in card and "&lt;script&gt;" in card
    assert "validation and test prices remain closed" in card
    assert "Training search complete" not in card
    unverified = dashboard.mass_research_card(dict(mass_result=dict(target=10000,completed=9000,unique_configs=9000,qualified_count=0)))
    assert "Training search complete" not in unverified
    assert "Price-access status is not verified" in unverified


def test_mass_downloads_are_active_run_allowlisted_and_streamable(monkeypatch,tmp_path):
    monkeypatch.setattr(dashboard,"ROOT",tmp_path)
    (tmp_path/"reports").mkdir()
    run = tmp_path/"runs/research"
    run.mkdir(parents=True)
    csv_path = run/"ranked.csv"
    csv_path.write_text("config_id,net_pnl\na,10\n",encoding="utf-8")
    checkpoint = tmp_path/"reports/mass_research_progress.json"
    checkpoint.write_text(json.dumps(dict(run_path="runs/research")),encoding="utf-8")
    assert dashboard.mass_artifact("ranked.csv") == csv_path
    assert dashboard.mass_artifact("../../reports/research_policy.json") is None
    server = dashboard.ThreadingHTTPServer(("127.0.0.1",0),dashboard.Handler)
    worker = Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/mass/ranked.csv") as response:
            assert response.read() == csv_path.read_bytes()
            assert "attachment" in response.headers["Content-Disposition"]
        checkpoint.write_text(json.dumps(dict(run_path=str(tmp_path))),encoding="utf-8")
        assert dashboard.mass_artifact("ranked.csv") is None
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def test_mass_publisher_checks_all_records_before_claiming_completion(monkeypatch,tmp_path):
    publisher_spec = importlib.util.spec_from_file_location("mass_publisher",ROOT/"scripts/publish_mass_research.py")
    publisher = importlib.util.module_from_spec(publisher_spec)
    publisher_spec.loader.exec_module(publisher)
    monkeypatch.setattr(publisher,"ROOT",tmp_path)
    monkeypatch.setattr(publisher,"REPORTS",tmp_path/"reports")
    (tmp_path/"reports").mkdir()
    run = tmp_path/"runs/mass"
    run.mkdir(parents=True)
    with (run/"ranked.csv").open("w",encoding="utf-8",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=["config_id","net_pnl"])
        writer.writeheader()
        writer.writerows(dict(config_id=f"cfg_{i}",net_pnl=i-5000) for i in range(10000))
    with (run/"configurations.jsonl").open("w",encoding="utf-8") as stream:
        for i in range(10000):
            stream.write(json.dumps(dict(config_id=f"cfg_{i}",lookback=i+1))+"\n")
    result = dict(run_path="runs/mass",target=10000,completed=10000,unique_configs=10000,qualified_count=0,
        top10=[],validation_accessed=False,test_accessed=False,fresh_holdout_available=False,
        validation_status="blocked_previously_observed",test_status="blocked_previously_observed")
    assert publisher.run_directory(result) == run
    receipt = publisher.verify_records(result,run)
    assert receipt["csv_rows"] == receipt["manifest_rows"] == 10000
    publisher.render_reports(result,run,receipt)
    validation = (tmp_path/"reports/MASS_VALIDATION_REPORT.md").read_text(encoding="utf-8")
    assert "BLOCKED" in validation and "No new price evaluation" in validation
    assert "No top-10 candidate list" in (tmp_path/"reports/MASS_RESEARCH_REPORT.md").read_text(encoding="utf-8")
    with pytest.raises(ValueError,match="incomplete"):
        publisher.verify_records(dict(result,completed=9999),run)
    with (run/"configurations.jsonl").open("a",encoding="utf-8") as stream:
        stream.write(json.dumps(dict(config_id="cfg_0"))+"\n")
    with pytest.raises(ValueError,match="manifest count"):
        publisher.verify_records(result,run)
