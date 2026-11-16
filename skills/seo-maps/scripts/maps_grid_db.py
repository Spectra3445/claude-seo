#!/usr/bin/env python3
"""Write geo-grid runs to the SEO data layer (Supabase `hunnkrkyrkhibsfzahub`, schema `seo`:
seo.maps_grid_runs + seo.maps_grid_points) over PostgREST (Content-Profile: $SEODB_SCHEMA).

  maps_grid_db.py load RUN.json [RUN.jsonl ...] [--dry-run]   # canonical runs -> DB (idempotent)
  maps_grid_db.py flush                                        # retry the outbox
  maps_grid_db.py selftest                                     # maths + id stability, no network

Canonical run (what geogrid.py saves and backfill_vault.py emits):
  {client, keyword, business_name, place_id, cid, center_lat, center_lng, grid_size,
   spacing_km, zoom, device, cost_usd, source, run_context, run_at (ISO),
   cells: [{row, col, lat, lng, rank|null, top3: [{rank,title,cid,rating,reviews}]|null}]}
row 0 = north, col 0 = west. avg_rank / solv are always recomputed from cells:
  solv = top-3 cells / all cells * 100 ; avg_rank = mean rank over ranked cells (null if none).

Idempotent: run id = uuid5(client|keyword|run_at|centre|grid|spacing|zoom), upserted on PK,
points upserted on (run_id,row_idx,col_idx). Re-loading the same file changes nothing.
place_id column holds the Google place_id when known, else "cid:<CID>".

Credentials: ~/.config/aristral/seodb.env (SEODB_URL, SEODB_SERVICE_KEY, SEODB_SCHEMA); never
printed (the DB host is echoed before writes, per the contract). SEODB_OFF=1 disables writes.
A DB failure never raises out of write_run(): it warns on stderr and appends the run to
~/.local/share/aristral/seodb/maps-outbox.jsonl for `flush`.
"""
import json
import os
import re
import sys
import uuid
from pathlib import Path

ENV_FILE = Path.home() / ".config/aristral/seodb.env"
OUTBOX = Path.home() / ".local/share/aristral/seodb/maps-outbox.jsonl"
NS = uuid.UUID("6f1d2a5e-3c4b-4e8a-9b7c-0d1e2f3a4b5c")
CLIENTS = {"bmny", "floapparels", "aristral", "cartcourier", "chdevelopment", "cookingit", "kebabishgrill", "lumavir",
           "natapmu", "novaio", "premierconstruction", "saeedlawfirm", "shahlawyers",
           "skinandbeautybox", "smartdms", "soielle", "trettrain"}


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip().removeprefix("export ").strip()] = v.strip().strip("'\"")
    for k in ("SEODB_URL", "SEODB_SERVICE_KEY"):
        env.setdefault(k, os.environ.get(k, ""))
    env.setdefault("SEODB_SCHEMA", os.environ.get("SEODB_SCHEMA") or "seo")
    env["SEODB_URL"] = re.sub(r"/rest/v1/?$", "", env["SEODB_URL"].rstrip("/"))
    return env


def metrics(cells):
    ranks = [c["rank"] for c in cells if c.get("rank")]
    solv = round(100 * sum(1 for r in ranks if r <= 3) / len(cells), 1) if cells else None
    avg = round(sum(ranks) / len(ranks), 2) if ranks else None
    return avg, solv


def run_id(r):
    key = "|".join(str(x) for x in (r["client"], r["keyword"].strip().lower(), r["run_at"],
                                     round(r["center_lat"], 5), round(r["center_lng"], 5),
                                     r["grid_size"], r["spacing_km"], r.get("zoom") or ""))
    return str(uuid.uuid5(NS, key))


def to_rows(r):
    rid = run_id(r)
    avg, solv = metrics(r["cells"])
    pid = r.get("place_id") or (f"cid:{r['cid']}" if r.get("cid") else None)
    run = {"id": rid, "client": r["client"], "keyword": r["keyword"], "business_name": r.get("business_name"),
           "place_id": pid, "center_lat": r["center_lat"], "center_lng": r["center_lng"],
           "grid_size": r["grid_size"], "spacing_km": r["spacing_km"], "avg_rank": avg, "solv": solv,
           "cost_usd": round(float(r.get("cost_usd") or 0), 4), "source": r.get("source") or "seo-maps",
           "run_context": r.get("run_context"), "run_at": r["run_at"]}
    pts = [{"run_id": rid, "row_idx": c["row"], "col_idx": c["col"], "lat": c["lat"], "lng": c["lng"],
            "rank": c.get("rank"), "top3": c.get("top3")} for c in r["cells"]]
    return run, pts


def validate(r):
    if r.get("client") not in CLIENTS:
        return f"unknown client {r.get('client')!r}"
    n = r.get("grid_size")
    cells = r.get("cells") or []
    if not cells:
        return "no cells"
    if len({(c["row"], c["col"]) for c in cells}) != len(cells):
        return "duplicate cell coordinates"
    if any(not (0 <= c["row"] < n and 0 <= c["col"] < n) for c in cells):
        return "cell index outside grid"
    return None


def _post(env, table, rows, conflict):
    import requests
    url = env["SEODB_URL"] + f"/rest/v1/{table}?on_conflict={conflict}"
    key = env["SEODB_SERVICE_KEY"]
    resp = requests.post(url, json=rows, timeout=60, headers={
        "apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "Content-Profile": env["SEODB_SCHEMA"], "Prefer": "resolution=merge-duplicates,return=minimal"})
    if resp.status_code >= 300:
        raise RuntimeError(f"{table}: HTTP {resp.status_code} {resp.text[:300]}")


def push(runs, env=None):
    """Upsert canonical runs. Raises on failure (callers that must not fail use write_run)."""
    env = env or load_env()
    if not env.get("SEODB_URL") or not env.get("SEODB_SERVICE_KEY"):
        raise RuntimeError(f"SEODB_URL / SEODB_SERVICE_KEY missing in {ENV_FILE}")
    print(f"# seodb maps: host {re.sub(r'^https?://', '', env['SEODB_URL'])} schema {env['SEODB_SCHEMA']}",
          file=sys.stderr)
    run_rows, pt_rows = [], []
    for r in runs:
        a, b = to_rows(r)
        run_rows.append(a)
        pt_rows.extend(b)
    for i in range(0, len(run_rows), 500):  # authenticator statement_timeout=8s: <= 500 rows/batch
        _post(env, "maps_grid_runs", run_rows[i:i + 500], "id")
    for i in range(0, len(pt_rows), 500):
        _post(env, "maps_grid_points", pt_rows[i:i + 500], "run_id,row_idx,col_idx")
    return [a["id"] for a in run_rows]


def write_run(r):
    """Never raises. Returns run id on success, None if queued to the outbox or invalid."""
    if os.environ.get("SEODB_OFF", "").strip() not in ("", "0", "false"):
        return None
    try:
        err = validate(r)
        if err:
            print(f"# seodb maps: skipped ({err}): {r.get('client')} / {r.get('keyword')}", file=sys.stderr)
            return None
        return push([r])[0]
    except Exception as e:  # DB trouble must never fail the grid run
        print(f"# seodb maps: write failed, queued to outbox ({str(e)[:200]})", file=sys.stderr)
        try:
            OUTBOX.parent.mkdir(parents=True, exist_ok=True)
            with OUTBOX.open("a") as f:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        except Exception as e2:
            print(f"# seodb maps: outbox write failed too ({e2})", file=sys.stderr)
        return None


def read_runs(path):
    text = Path(path).read_text()
    if path.endswith(".jsonl"):
        return [json.loads(x) for x in text.splitlines() if x.strip()]
    d = json.loads(text)
    return d if isinstance(d, list) else d.get("runs", [d])


def cmd_load(paths, dry):
    runs = [r for p in paths for r in read_runs(p)]
    ok, bad = [], []
    for r in runs:
        err = validate(r)
        (bad if err else ok).append((r, err))
    for r, err in bad:
        print(f"# skip ({err}): {r.get('client')} / {r.get('keyword')} / {r.get('run_at')}", file=sys.stderr)
    good = [r for r, _ in ok]
    ids = {run_id(r) for r in good}
    print(f"# {len(good)} valid runs ({len(ids)} distinct ids), {sum(len(r['cells']) for r in good)} points, "
          f"{len(bad)} skipped", file=sys.stderr)
    if dry:
        return 0
    push(good)
    print(f"# loaded {len(good)} runs into maps_grid_runs/maps_grid_points", file=sys.stderr)
    return 0


def cmd_flush():
    if not OUTBOX.exists() or not OUTBOX.read_text().strip():
        print("# outbox empty", file=sys.stderr)
        return 0
    runs = read_runs(str(OUTBOX))
    push([r for r in runs if not validate(r)])
    OUTBOX.write_text("")
    print(f"# flushed {len(runs)} runs", file=sys.stderr)
    return 0


def selftest():
    cells = [{"row": i, "col": j, "lat": 0, "lng": 0, "rank": r}
             for (i, j), r in zip([(0, 0), (0, 1), (1, 0), (1, 1)], [1, 5, None, 3])]
    assert metrics(cells) == (3.0, 50.0), metrics(cells)
    r = {"client": "aristral", "keyword": "SEO agency", "run_at": "2026-10-20T12:00:00Z", "center_lat": 51.4,
         "center_lng": -2.6, "grid_size": 2, "spacing_km": 1, "zoom": "14z", "cells": cells}
    assert run_id(r) == run_id(dict(r, keyword="seo agency ")), "id must ignore case/whitespace"
    assert validate(r) is None and validate(dict(r, client="nope"))
    print("selftest ok")
    return 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "load":
        dry = "--dry-run" in argv
        return cmd_load([a for a in argv[1:] if a != "--dry-run"], dry)
    if argv[0] == "flush":
        return cmd_flush()
    if argv[0] == "selftest":
        return selftest()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
