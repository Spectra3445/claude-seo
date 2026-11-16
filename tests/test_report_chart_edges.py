import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/seo-audit/report-template/render_report.py"
spec = importlib.util.spec_from_file_location("audit_render_report", SCRIPT)
render_report = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(render_report)


def test_charts_handle_single_point_flat_range_and_zero_bars():
    chart = render_report.line_chart({
        "points": [["today", 0]], "ticks": [0], "format": "int", "aria": "trend",
    })
    assert "nan" not in chart.lower()
    assert "<polyline points=" in chart

    bars = render_report.card_bars({
        "rows": [{"name": str(i), "value": 0} for i in range(3)],
        "title": "Sources", "label": "Count", "caption": "All zero",
    }, [])
    assert bars.count("width:0.0%") == 3
