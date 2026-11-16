import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_flush_preserves_entries_appended_during_upload(tmp_path, monkeypatch):
    db = _load("maps_grid_db_regression", ROOT / "skills/seo-maps/scripts/maps_grid_db.py")
    outbox = tmp_path / "maps-outbox.jsonl"
    outbox.write_text('{"keyword":"before"}\n')
    monkeypatch.setattr(db, "OUTBOX", outbox)

    def upload(_runs):
        with outbox.open("a") as f:
            f.write('{"keyword":"during"}\n')

    monkeypatch.setattr(db, "push", upload)
    assert db.cmd_flush() == 0
    assert [json.loads(line)["keyword"] for line in outbox.read_text().splitlines()] == ["during"]


def test_geogrid_run_writes_unique_timestamped_filename(tmp_path, monkeypatch):
    geogrid = _load("geogrid_regression", ROOT / "skills/seo-maps/scripts/geogrid.py")
    raw = tmp_path / "raw.json"
    raw.write_text('[[{"items": []}]]')
    monkeypatch.setattr(geogrid.maps_grid_db, "write_run", lambda _run: None)
    args = type("Args", (), {
        "center": "51.4,-2.6", "grid": 1, "spacing_km": 1, "keyword": ["seo"],
        "zoom": "14z", "device": "mobile", "depth": 20, "lang": "en", "dry_run": False,
        "from_raw": str(raw), "client": "aristral", "context": None, "yes": False,
        "cid": None, "place_id": None, "business": "Aristral", "out": str(tmp_path),
    })()

    assert geogrid.cmd_run(args) == 0
    paths = list(tmp_path.glob("grid-aristral-*.json"))
    assert len(paths) == 1
    assert len(paths[0].stem.rsplit("-", 1)[1]) == 8
    assert "T" in paths[0].stem
