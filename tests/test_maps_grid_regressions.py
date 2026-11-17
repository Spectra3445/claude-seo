import importlib.util
import json
import stat
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

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
    outbox.write_text(json.dumps({
        "client": "aristral", "keyword": "before", "run_at": "2026-11-17T00:00:00Z",
        "center_lat": 51.4, "center_lng": -2.6, "grid_size": 1,
        "cells": [{"row": 0, "col": 0, "lat": 51.4, "lng": -2.6, "rank": 1}],
    }) + "\n")
    monkeypatch.setattr(db, "OUTBOX", outbox)

    def upload(_runs):
        with outbox.open("a", encoding="utf-8") as f:
            f.write('{"keyword":"during"}\n')

    monkeypatch.setattr(db, "push", upload)
    assert db.cmd_flush() == 0
    assert [json.loads(line)["keyword"] for line in outbox.read_text(encoding="utf-8").splitlines()] == ["during"]


def test_flush_replays_multiple_runs_and_leftover_drain(tmp_path, monkeypatch):
    db = _load("maps_grid_db_recovery", ROOT / "skills/seo-maps/scripts/maps_grid_db.py")
    outbox = tmp_path / "maps-outbox.jsonl"
    drain = tmp_path / "maps-outbox.drain-crashed.jsonl"
    def run(keyword):
        return {"client": "aristral", "keyword": keyword, "run_at": "2026-11-16T00:00:00Z",
                "center_lat": 51.4, "center_lng": -2.6, "grid_size": 1,
                "cells": [{"row": 0, "col": 0, "lat": 51.4, "lng": -2.6, "rank": None}]}

    outbox.write_text("".join(json.dumps(run(k)) + "\n" for k in ("new-1", "new-2")))
    drain.write_text("".join(json.dumps(run(k)) + "\n" for k in ("old-1", "old-2")))
    monkeypatch.setattr(db, "OUTBOX", outbox)
    uploaded = []
    monkeypatch.setattr(db, "push", lambda runs: uploaded.extend(runs))

    assert db.cmd_flush() == 0

    assert [run["keyword"] for run in uploaded] == ["old-1", "old-2", "new-1", "new-2"]
    assert not drain.exists()
    assert not list(tmp_path.glob("maps-outbox.drain-*.jsonl"))


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


def test_partial_grid_records_coverage_but_cannot_publish_a_score(tmp_path, monkeypatch, capsys):
    geogrid = _load("geogrid_partial", ROOT / "skills/seo-maps/scripts/geogrid.py")
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps([[{"items": [{"type": "maps_search", "cid": "123", "rank_group": 1}]}],
                               None, None, None]))
    writes = []
    monkeypatch.setattr(geogrid.maps_grid_db, "write_run", writes.append)
    args = SimpleNamespace(center="51.4,-2.6", grid=2, spacing_km=1, keyword=["seo"],
                           zoom="14z", device="mobile", depth=20, lang="en", dry_run=False,
                           from_raw=str(raw), client="aristral", context=None, yes=False,
                           cid="123", place_id=None, business=None, out=str(tmp_path))
    assert geogrid.cmd_run(args) == 0
    run = writes[0]
    assert (run["expected_cells"], run["received_cells"]) == (4, 1)
    assert geogrid.maps_grid_db.metrics(run["cells"], 4) == (None, None)
    assert geogrid.maps_grid_db.validate(run) == "partial grid: 1/4 cells"
    with pytest.raises(ValueError, match="partial grid"):
        geogrid.maps_grid_db.push([run], env={"SEODB_URL": "https://current-project.supabase.co",
                                              "SEODB_SERVICE_KEY": "fake", "SEODB_SCHEMA": "seo"})
    assert "SoLV partial" in capsys.readouterr().out
    assert json.loads(next(tmp_path.glob("grid-*.json")).read_text(encoding="utf-8"))["runs"][0]["received_cells"] == 1


def test_service_key_is_sent_only_to_the_configured_https_supabase_origin(monkeypatch, capsys):
    db = _load("maps_grid_db_origin", ROOT / "skills/seo-maps/scripts/maps_grid_db.py")
    monkeypatch.delenv("SEODB_EXPECTED_HOST", raising=False)
    sent = []
    class Response:
        status_code = 200
    monkeypatch.setattr("requests.post", lambda url, **kwargs: (sent.append((url, kwargs)), Response())[1])
    host = "current-project.supabase.co"
    env = {"SEODB_URL": f"https://{host}", "SEODB_SERVICE_KEY": "secret", "SEODB_SCHEMA": "seo"}
    db._post(env, "maps_grid_runs", [], "id")
    assert sent[0][0].startswith(f"https://{host}/rest/v1/")
    assert sent[0][1]["allow_redirects"] is False
    db._post(dict(env, SEODB_URL="https://another-project.supabase.co"), "maps_grid_runs", [], "id")
    assert sent[1][0].startswith("https://another-project.supabase.co/rest/v1/")
    for bad in (f"http://{host}", "https://attacker.example", f"https://{host}.evil.example",
                f"https://{host}/rest/v1", f"https://user:pass@{host}", f"https://{host}?key=secret"):
        with pytest.raises(ValueError):
            db._post(dict(env, SEODB_URL=bad), "maps_grid_runs", [], "id")
    assert len(sent) == 2
    monkeypatch.setenv("SEODB_EXPECTED_HOST", host)
    with pytest.raises(ValueError):
        db._post(dict(env, SEODB_URL="https://another-project.supabase.co"), "maps_grid_runs", [], "id")
    db.push([], env=env)
    assert not capsys.readouterr().err
    Response.status_code = 400
    Response.text = "rejected secret"
    with pytest.raises(RuntimeError, match="HTTP 400") as error:
        db._post(env, "maps_grid_runs", [], "id")
    assert "secret" not in str(error.value)
    import requests
    monkeypatch.setattr(requests, "post", lambda *_a, **_kw: (_ for _ in ()).throw(
        requests.exceptions.ConnectionError("secret current-project.supabase.co")))
    with pytest.raises(RuntimeError, match="Supabase request failed") as error:
        db._post(env, "maps_grid_runs", [], "id")
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("suffix", ("/rest/v1", "/rest/v1/", "/"))
def test_load_env_normalizes_supabase_rest_path_and_trailing_slash(tmp_path, monkeypatch, suffix):
    db = _load("maps_grid_db_url_normalization", ROOT / "skills/seo-maps/scripts/maps_grid_db.py")
    config = tmp_path / "seodb.env"
    config.write_text(f"SEODB_URL=https://current-project.supabase.co{suffix}\n"
                      "SEODB_SERVICE_KEY=secret\n")
    monkeypatch.setattr(db, "ENV_FILE", config)
    monkeypatch.delenv("SEODB_EXPECTED_HOST", raising=False)
    sent = []
    monkeypatch.setattr("requests.post", lambda url, **_kwargs: (sent.append(url),
                        SimpleNamespace(status_code=201))[1])
    env = db.load_env()
    assert env["SEODB_URL"] == "https://current-project.supabase.co"
    db._post(env, "maps_grid_runs", [], "id")
    assert sent == ["https://current-project.supabase.co/rest/v1/maps_grid_runs?on_conflict=id"]


def test_db_writer_never_logs_config_file_values(tmp_path, monkeypatch, capsys):
    db = _load("maps_grid_db_no_config_logging", ROOT / "skills/seo-maps/scripts/maps_grid_db.py")
    config = tmp_path / "seodb.env"
    config.write_text("SEODB_URL=https://current-project.supabase.co\n"
                      "SEODB_SERVICE_KEY=private-service-key\nSEODB_SCHEMA=private-schema\n")
    monkeypatch.setattr(db, "ENV_FILE", config)
    monkeypatch.setattr(db, "OUTBOX", tmp_path / "seodb/maps-outbox.jsonl")
    monkeypatch.delenv("SEODB_EXPECTED_HOST", raising=False)
    assert db.push([]) == []
    run = {"client": "aristral", "keyword": "seo", "run_at": "2026-11-17T00:00:00Z",
           "center_lat": 51.4, "center_lng": -2.6, "grid_size": 1,
           "cells": [{"row": 0, "col": 0, "lat": 51.4, "lng": -2.6, "rank": 1}]}
    monkeypatch.setattr(db, "push", lambda _runs: (_ for _ in ()).throw(
        RuntimeError("private-service-key current-project.supabase.co private-schema")))
    assert db.write_run(run) is None
    printed = capsys.readouterr()
    assert all(value not in printed.out + printed.err for value in
               ("private-service-key", "current-project.supabase.co", "private-schema"))
    assert json.loads(db.OUTBOX.read_text(encoding="utf-8")) == run


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits are unavailable on Windows")
def test_private_backfill_and_outbox_modes(tmp_path, monkeypatch):
    db = _load("maps_grid_db_modes", ROOT / "skills/seo-maps/scripts/maps_grid_db.py")
    outbox = tmp_path / "seodb/maps-outbox.jsonl"
    monkeypatch.setattr(db, "OUTBOX", outbox)
    monkeypatch.setattr(db, "push", lambda _runs: (_ for _ in ()).throw(RuntimeError("offline")))
    run = {"client": "aristral", "keyword": "seo", "run_at": "2026-11-17T00:00:00Z",
           "center_lat": 51.4, "center_lng": -2.6, "grid_size": 1, "spacing_km": 1,
           "cells": [{"row": 0, "col": 0, "lat": 51.4, "lng": -2.6, "rank": 1}]}
    assert db.write_run(run) is None
    db.write_private(outbox.parent / "maps-backfill.jsonl", "private\n")
    assert stat.S_IMODE(outbox.parent.stat().st_mode) == 0o700
    for path in (outbox, outbox.with_name(outbox.name + ".lock"), outbox.parent / "maps-backfill.jsonl"):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_private_writer_works_without_fchmod(tmp_path, monkeypatch):
    db = _load("maps_grid_db_no_fchmod", ROOT / "skills/seo-maps/scripts/maps_grid_db.py")
    monkeypatch.delattr(db.os, "fchmod", raising=False)
    path = tmp_path / "private/file.jsonl"
    db.write_private(path, "test\n")
    assert path.read_text(encoding="utf-8") == "test\n"
    monkeypatch.setattr(db, "OUTBOX", tmp_path / "private/maps-outbox.jsonl")
    monkeypatch.setattr(db, "push", lambda _runs: (_ for _ in ()).throw(RuntimeError("offline")))
    run = {"client": "aristral", "keyword": "queued", "run_at": "2026-11-17T00:00:00Z",
           "center_lat": 51.4, "center_lng": -2.6, "grid_size": 1,
           "cells": [{"row": 0, "col": 0, "lat": 51.4, "lng": -2.6, "rank": 1}]}
    assert db.write_run(run) is None
    assert json.loads(db.OUTBOX.read_text(encoding="utf-8").strip()) == run


def test_private_writer_closes_fd_when_permission_change_fails(tmp_path, monkeypatch):
    db = _load("maps_grid_db_close_fd", ROOT / "skills/seo-maps/scripts/maps_grid_db.py")
    path = tmp_path / "private/file.jsonl"
    monkeypatch.delattr(db.os, "fchmod", raising=False)
    real_chmod, real_close = db.os.chmod, db.os.close
    closed = []
    def chmod(target, mode, **kwargs):
        if Path(target) == path:
            raise OSError("permission change failed")
        return real_chmod(target, mode, **kwargs)
    def close(fd):
        closed.append(fd)
        real_close(fd)
    monkeypatch.setattr(db.os, "chmod", chmod)
    monkeypatch.setattr(db.os, "close", close)
    with pytest.raises(OSError, match="permission change failed"):
        db.write_private(path, "private\n")
    assert len(closed) == 1


def test_flush_quarantines_partial_runs_without_losing_them(tmp_path, monkeypatch, capsys):
    db = _load("maps_grid_db_quarantine", ROOT / "skills/seo-maps/scripts/maps_grid_db.py")
    outbox = tmp_path / "seodb/maps-outbox.jsonl"
    valid = {"client": "aristral", "keyword": "complete", "run_at": "2026-11-17T00:00:00Z",
             "center_lat": 51.4, "center_lng": -2.6, "grid_size": 1,
             "cells": [{"row": 0, "col": 0, "lat": 51.4, "lng": -2.6, "rank": 1}]}
    partial = dict(valid, keyword="partial", grid_size=2, expected_cells=4, received_cells=1)
    db.write_private(outbox, "".join(json.dumps(run) + "\n" for run in (partial, valid)))
    monkeypatch.setattr(db, "OUTBOX", outbox)
    uploaded = []
    monkeypatch.setattr(db, "push", lambda runs: uploaded.extend(runs))
    assert db.cmd_flush() == 0
    assert uploaded == [valid]
    quarantine = outbox.with_name("maps-outbox.rejected.jsonl")
    assert [json.loads(line) for line in quarantine.read_text(encoding="utf-8").splitlines()] == [partial]
    assert not outbox.exists()
    assert not list(outbox.parent.glob("maps-outbox.drain-*.jsonl"))
    assert "quarantined 1 rejected runs" in capsys.readouterr().err
    if sys.platform != "win32":
        assert stat.S_IMODE(quarantine.stat().st_mode) == 0o600
        assert stat.S_IMODE(quarantine.parent.stat().st_mode) == 0o700


def test_flush_lock_keeps_a_concurrent_writer_out_of_the_drained_file(tmp_path, monkeypatch):
    db = _load("maps_grid_db_lock", ROOT / "skills/seo-maps/scripts/maps_grid_db.py")
    outbox = tmp_path / "seodb/maps-outbox.jsonl"
    monkeypatch.setattr(db, "OUTBOX", outbox)
    def run(keyword):
        return {"client": "aristral", "keyword": keyword, "run_at": "2026-11-17T00:00:00Z",
                "center_lat": 51.4, "center_lng": -2.6, "grid_size": 1, "spacing_km": 1,
                "cells": [{"row": 0, "col": 0, "lat": 51.4, "lng": -2.6, "rank": 1}]}
    db.write_private(outbox, json.dumps(run("before")) + "\n")
    uploading = threading.Event()
    wrote = threading.Event()

    def push(_runs):
        if threading.current_thread() is threading.main_thread():
            uploading.set()
            assert not wrote.wait(0.05)
        else:
            raise RuntimeError("offline")

    monkeypatch.setattr(db, "push", push)
    writer = threading.Thread(target=lambda: (uploading.wait(), db.write_run(run("during")), wrote.set()))
    writer.start()
    assert db.cmd_flush() == 0
    writer.join(timeout=2)
    assert wrote.is_set()
    assert [json.loads(line)["keyword"] for line in outbox.read_text(encoding="utf-8").splitlines()] == ["during"]
