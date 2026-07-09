import json
from pathlib import Path
from scripts.kg_health_check import analyze, write_report


def test_analyze_returns_required_keys():
    stats = {
        "total_nodes": 100, "total_relationships": 200,
        "entities_by_type": {"PERSON": 50, "TECHNOLOGY": 30},
        "entities_by_subtype": {"SCIENTIST": 10}
    }
    result = analyze(stats, articles_in_kg=10)
    assert "summary" in result
    assert "entity_type_distribution" in result
    assert "recommendations" in result
    assert result["summary"]["total_nodes"] == 100
    assert "PERSON" in result["entity_type_distribution"]


def test_write_report_creates_file(tmp_path):
    report = {"summary": {"total_nodes": 1}}
    out = tmp_path / "report.json"
    write_report(report, out)
    assert out.exists()
    assert json.loads(out.read_text())["summary"]["total_nodes"] == 1
