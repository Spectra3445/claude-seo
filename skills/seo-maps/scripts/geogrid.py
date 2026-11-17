#!/usr/bin/env python3
"""Geo-grid rank scan: grid geometry -> DataForSEO Maps SERP via the standard queue ->
rank/top-3 per cell -> SoLV/avg rank -> ASCII heatmap + canonical JSON -> Supabase write-through.

  geogrid.py run --client natapmu --cid 6103403894420122339 --center 51.4676293,-2.6060209 \\
      --keyword "permanent makeup" --keyword "lip blush" [--grid 7] [--spacing-km 0.667] \\
      [--zoom 14z] [--business "Nata Beauty"] [--place-id ChIJ...] [--context seo-routine] \\
      [--out DIR] [--yes] [--dry-run]
  geogrid.py run ... --from-raw results.json   # parse a saved `dataforseo.py queue` stdout, no spend

Every run (one per keyword) is saved to DIR/grid-<client>-<date>.json ({"runs": [...]}, the
canonical shape in maps_grid_db.py) and written to public.maps_grid_runs / maps_grid_points.
A DB failure only warns (and queues to the outbox); the scan itself still succeeds.
Spend: DFS queue $0.0006/cell. tools/dataforseo.py caps apply; exit 3 = over cap, ask Taha
before re-running with --yes.
"""
import argparse
import datetime as dt
import json
import uuid
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import maps_grid_db  # noqa: E402

VAULT = Path(os.environ.get("ARISTRAL_VAULT", Path.home() / "Desktop/Claude code"))
DFS = VAULT / "tools/dataforseo.py"
MAPS_LIVE = "v3/serp/google/maps/live/advanced"
QUEUE_COST_PER_CELL = 0.0006


def grid_points(lat, lng, n, step_km):
    """row 0 = north, col 0 = west; centre cell = business pin."""
    c = (n - 1) / 2
    pts = []
    for i in range(n):
        for j in range(n):
            plat = lat + (c - i) * step_km / 111.32
            plng = lng + (j - c) * step_km / (111.32 * math.cos(math.radians(lat)))
            pts.append((i, j, round(plat, 7), round(plng, 7)))
    return pts


def match_rank(items, cid=None, place_id=None, title=None):
    for it in items or []:
        if it.get("type") not in (None, "maps_search"):
            continue
        if (cid and str(it.get("cid")) == str(cid)) or (place_id and it.get("place_id") == place_id) \
                or (title and not cid and not place_id and title.lower() in (it.get("title") or "").lower()):
            return it.get("rank_group") or it.get("rank_absolute")
    return None


def top3_of(items):
    out = []
    for it in items or []:
        r = it.get("rank_group") or it.get("rank_absolute")
        if r and r <= 3 and it.get("type") in (None, "maps_search"):
            rating = it.get("rating") or {}
            out.append({"rank": r, "title": it.get("title"), "cid": it.get("cid"),
                        "rating": rating.get("value"), "reviews": rating.get("votes_count")})
    return sorted(out, key=lambda x: x["rank"])


def ascii_heatmap(run):
    n = run["grid_size"]
    grid = [["  ." for _ in range(n)] for _ in range(n)]
    for c in run["cells"]:
        grid[c["row"]][c["col"]] = f"{c['rank']:>3}" if c.get("rank") else "  ."
    mid = (n - 1) // 2
    lines = [f'Geo-grid "{run["keyword"]}" {n}x{n} @ {run["spacing_km"]} km, {run.get("zoom")}, '
             f'centre {run["center_lat"]:.5f},{run["center_lng"]:.5f}   (N up, W left, . = not in top 20)']
    for i, row in enumerate(grid):
        lines.append("".join(row) + ("   <- pin" if i == mid else ""))
    expected = run["grid_size"] ** 2
    avg, solv = maps_grid_db.metrics(run["cells"], expected)
    ranked = sum(1 for c in run["cells"] if c.get("rank"))
    lines.append(f"SoLV {solv if solv is not None else 'partial'}{'%' if solv is not None else ''}"
                 f" · ranked {ranked}/{len(run['cells'])} · coverage {len(run['cells'])}/{expected}"
                 f" · avg rank {avg if avg is not None else 'partial'}")
    return "\n".join(lines)


def call_queue(tasks, client, context, yes):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(tasks, f)
        tpath = f.name
    cmd = [sys.executable, str(DFS), "queue", MAPS_LIVE, "--data", f"@{tpath}",
           "--pending-file", str(Path(tempfile.gettempdir()) / f"geogrid-pending-{client}.json")]
    if yes:
        cmd.append("--yes")
    env = dict(os.environ, DFS_TAG=os.environ.get("DFS_TAG", client), SEODB_RUN_CONTEXT=context or "")
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    sys.stderr.write(p.stderr)
    if p.returncode != 0:
        sys.exit(p.returncode)  # 3 = spend cap: ask Taha before --yes
    m = re.search(r"cost=\$([0-9.]+)", p.stderr)
    return json.loads(p.stdout), (float(m.group(1)) if m else len(tasks) * QUEUE_COST_PER_CELL)


def cmd_run(a):
    lat, lng = (float(x) for x in a.center.split(","))
    pts = grid_points(lat, lng, a.grid, a.spacing_km)
    tasks, index = [], []
    for kw in a.keyword:
        for (i, j, plat, plng) in pts:
            tasks.append({"keyword": kw, "location_coordinate": f"{plat},{plng},{a.zoom}",
                          "language_code": a.lang, "device": a.device, "os": "android", "depth": a.depth})
            index.append((kw, i, j, plat, plng))
    est = len(tasks) * QUEUE_COST_PER_CELL
    print(f"Geo-Grid Scan: {', '.join(a.keyword)} | Grid: {a.grid}x{a.grid} ({len(pts)} points) | "
          f"Keywords: {len(a.keyword)} | Est. cost: ${est:.4f} (DFS standard queue)", file=sys.stderr)
    if a.dry_run:
        return 0
    if a.from_raw:
        results, cost = json.loads(Path(a.from_raw).read_text()), 0.0
    else:
        results, cost = call_queue(tasks, a.client, a.context, a.yes)
    if len(results) != len(tasks):
        sys.exit(f"result count {len(results)} != task count {len(tasks)}")

    run_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    runs = []
    for kw in a.keyword:
        cells, missing = [], 0
        for (k, i, j, plat, plng), res in zip(index, results):
            if k != kw:
                continue
            if res is None:  # still queued / failed: unknown, not "unranked"
                missing += 1
                continue
            items = (res[0] or {}).get("items") if res else []
            cells.append({"row": i, "col": j, "lat": plat, "lng": plng,
                          "rank": match_rank(items, a.cid, a.place_id, a.business),
                          "top3": top3_of(items)})
        if missing:
            print(f"# {kw}: {missing} cells had no result (excluded)", file=sys.stderr)
        runs.append({"client": a.client, "keyword": kw, "business_name": a.business, "place_id": a.place_id,
                     "cid": a.cid, "center_lat": lat, "center_lng": lng, "grid_size": a.grid,
                     "spacing_km": a.spacing_km, "zoom": a.zoom, "device": a.device,
                     "cost_usd": round(cost / len(a.keyword), 4), "source": "seo-maps",
                     "run_context": a.context, "run_at": run_at, "cells": cells,
                     "expected_cells": a.grid * a.grid, "received_cells": len(cells)})
    run_stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(a.out) / f"grid-{a.client}-{run_stamp}-{uuid.uuid4().hex[:8]}.json"
    out.write_text(json.dumps({"runs": runs}, ensure_ascii=False, indent=1))
    for r in runs:
        print(ascii_heatmap(r) + "\n")
        rid = maps_grid_db.write_run(r)
        if rid:
            print(f"# seodb maps: run {rid} written ({len(r['cells'])} points)", file=sys.stderr)
    print(f"# saved {out}  cost=${cost:.4f}", file=sys.stderr)
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--client", required=True, help="clients.slug, e.g. natapmu")
    r.add_argument("--keyword", action="append", required=True)
    r.add_argument("--center", required=True, help="lat,lng of the GBP pin")
    r.add_argument("--cid", help="Google CID of the target listing (preferred match key)")
    r.add_argument("--place-id")
    r.add_argument("--business", help="business name (stored; title fallback match when no cid/place_id)")
    r.add_argument("--grid", type=int, default=7)
    r.add_argument("--spacing-km", type=float, default=1.0)
    r.add_argument("--zoom", default="14z")
    r.add_argument("--device", default="mobile")
    r.add_argument("--lang", default="en")
    r.add_argument("--depth", type=int, default=20)
    r.add_argument("--context", help="run_context: routine or audit name")
    r.add_argument("--out", default=".")
    r.add_argument("--yes", action="store_true", help="pass --yes to dataforseo.py (only after Taha OKs)")
    r.add_argument("--dry-run", action="store_true", help="print the cost estimate only")
    r.add_argument("--from-raw", help="saved queue stdout to parse instead of calling DataForSEO")
    a = p.parse_args()
    if not a.cid and not a.place_id and not a.business:
        p.error("need --cid, --place-id or --business to find the target listing")
    return cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
