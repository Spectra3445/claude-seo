#!/usr/bin/env python3
"""One-off (re-runnable) backfill: every past geo-grid in the vault that has per-cell data ->
canonical runs (maps_grid_db.py shape) -> seo.maps_grid_runs / maps_grid_points.

  backfill_vault.py                 # parse + write JSONL + print counts (no DB)
  backfill_vault.py --load          # ...then upsert (idempotent; re-running changes nothing)

Output: ~/.local/share/aristral/seodb/maps-backfill.jsonl. Partial grids (cells < n*n) and
summary-only runs are skipped and listed. Rows/cols are re-derived from lat/lng (row 0 = north,
col 0 = west), so source files with south-up or "N+3" labels all land the same way up.
Markdown-only grids (Shah & Shah) are rebuilt from the ASCII heatmap + stated centre/spacing
using the skill's Haversine offsets; their run_context says so.
"""
import glob
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import maps_grid_db  # noqa: E402

VAULT = Path.home() / "Desktop/Claude code"
OUT = Path.home() / ".local/share/aristral/seodb/maps-backfill.jsonl"

BIZ = {  # cid -> (client, business name)
    "6103403894420122339": ("natapmu", "Nata Beauty"),
    "9561839107554253696": ("aristral", "Aristral (Bristol)"),
    "1016138559708588603": ("aristral", "Aristral (Derby)"),
    "9472182753400843456": ("skinandbeautybox", "Skin and Beauty Box (Clifton Down)"),
    "9905672806149774034": ("skinandbeautybox", "Skin and Beauty Box (Westbury Park)"),
    "14167964739531836451": ("skinandbeautybox", "Skin and Beauty Box (Westbury on Trym)"),
    "12451585508685552860": ("cookingit", "Cooking It"),
    "5327527557271379435": ("premierconstruction", "Premier Construction"),
    "16318037709921400096": ("saeedlawfirm", "Saeed Law Firm"),
    "16946226628968197241": ("cartcourier", "Cart Courier"),
    "1212786551794589906": ("chdevelopment", "CH Developments"),
    "6260713009236674564": ("shahlawyers", "Shah & Shah Lawyers"),
}
runs, skipped = [], []


def rel(p):
    return str(Path(p).resolve().relative_to(VAULT))


def jload(p):
    return json.load(open(p))


def axis(values):
    """distinct coordinate values (clustered within ~1 m), sorted ascending"""
    out = []
    for v in sorted(values):
        if not out or abs(v - out[-1]) > 1e-5:
            out.append(v)
    return out


def norm_top3(raw):
    if not raw:
        return [] if raw == [] else None
    out = []
    for k, t in enumerate(raw, 1):
        if isinstance(t, str):
            out.append({"rank": k, "title": t})
        elif isinstance(t, (list, tuple)):  # [title, reviews, rank?]
            out.append({"rank": t[2] if len(t) > 2 else k, "title": t[0], "reviews": t[1] if len(t) > 1 else None})
        else:
            r = t.get("rank") or t.get("r") or t.get("rank_group") or k
            rating = t.get("rating")
            if isinstance(rating, dict):
                rating = rating.get("value")
            out.append({"rank": r, "title": t.get("title") or t.get("t"), "cid": t.get("cid") if t.get("cid") != "None" else None,
                        "rating": rating, "reviews": t.get("reviews") or t.get("votes")})
    return [x for x in sorted(out, key=lambda x: x["rank"] or 99) if (x["rank"] or 99) <= 3]


def items_top3(items):
    its = [i for i in (items or []) if i.get("type", "maps_search") == "maps_search"]
    return norm_top3([{"rank": i.get("rank_group") or i.get("rank"), "title": i.get("title"), "cid": i.get("cid"),
                       "rating": i.get("rating"), "reviews": (i.get("rating") or {}).get("votes_count")
                       if isinstance(i.get("rating"), dict) else i.get("reviews") or i.get("votes")} for i in its])


def items_rank(items, cid):
    for i in items or []:
        if str(i.get("cid")) == str(cid) and i.get("type", "maps_search") == "maps_search":
            return i.get("rank_group") or i.get("rank")
    return None


def add(src, keyword, cid, date, cells, n=None, zoom=None, center=None, spacing=None, cost=0.0, note=None, place_id=None):
    """cells: [(lat, lng, rank, top3)]"""
    client, biz = BIZ[str(cid)]
    tag = f"{rel(src)} :: {keyword}" + (f" [{zoom}]" if zoom else "")
    lats, lngs = axis(c[0] for c in cells), axis(c[1] for c in cells)
    n = n or max(len(lats), len(lngs))
    if len(cells) < n * n or len(lats) != n or len(lngs) != n:
        skipped.append(f"{tag}: partial/irregular grid ({len(cells)} cells, {len(lats)}x{len(lngs)} axes, n={n})")
        return
    if spacing is None:
        spacing = round((lats[-1] - lats[0]) / (n - 1) * 111.32, 3)
    if center is None:
        center = (lats[(n - 1) // 2], lngs[(n - 1) // 2])

    def idx(ax, v):
        return min(range(len(ax)), key=lambda k: abs(ax[k] - v))
    out = [{"row": n - 1 - idx(lats, la), "col": idx(lngs, ln), "lat": la, "lng": ln,
            "rank": int(rk) if rk else None, "top3": t3} for la, ln, rk, t3 in cells]
    runs.append({"client": client, "keyword": keyword.strip(), "business_name": biz, "cid": str(cid),
                 "place_id": place_id, "center_lat": center[0], "center_lng": center[1], "grid_size": n,
                 "spacing_km": spacing, "zoom": zoom, "device": "mobile", "cost_usd": round(cost, 4),
                 "source": "seo-maps-backfill", "run_context": "backfill: " + tag + (f" ({note})" if note else ""),
                 "run_at": f"{date}T12:00:00Z", "cells": out})


# ---- format F: {meta:{center,n,step_km,zoom,cid,date}, cells:{kw:[{i,j,lat,lng,rank,top3|items}]}}
def fmt_meta_cells(p):
    d = jload(p)
    if not isinstance(d, dict) or "meta" not in d or "cells" not in d:
        return
    m = d["meta"]
    cost = (d.get("cost") or 0) / max(len(d["cells"]), 1) if isinstance(d.get("cost"), (int, float)) else 0
    for kw, cells in d["cells"].items():
        add(p, kw, m["cid"], m["date"],
            [(c["lat"], c["lng"], c.get("rank"), norm_top3(c["top3"]) if "top3" in c else items_top3(c.get("items")))
             for c in cells if c.get("ok", True)],
            n=m["n"], zoom=m["zoom"], center=tuple(m["center"]), spacing=m["step_km"], cost=cost)


# ---- Aristral: {meta, kw:{kw:{cells:[{i,j,lat,lng,rank,top,cost}]}}}
def fmt_aristral(p):
    d = jload(p)
    m = d["meta"]
    for kw, g in d["kw"].items():
        add(p, kw, m["cid"], m["date"], [(c["lat"], c["lng"], c.get("rank"), norm_top3(c.get("top"))) for c in g["cells"]],
            n=m["n"], zoom=m["zoom"], center=tuple(m["center"]), spacing=m["step_km"], cost=g.get("cost") or 0)


def fmt_premier(p):
    d = jload(p)
    for kw, g in d["grids"].items():
        add(p, kw, "5327527557271379435", "2026-09-05",
            [(c["lat"], c["lng"], c.get("rank"), norm_top3(c.get("top3"))) for c in g.values()],
            n=d["n"], zoom="14z", center=tuple(d["center"]), spacing=d["step_km"], cost=d["cost"] / len(d["grids"]))


def fmt_cookingit():
    base = VAULT / "50-Audits/CookingIt"
    p = base / "evidence-2026-09-03/maps_grid_7x7_2026-09-03.json"
    d = jload(p)
    m = d["meta"]
    add(p, m["keyword"], m["target_cid"], m["date"], [(c["lat"], c["lng"], c.get("target_rank"), norm_top3(c.get("top3")))
                                                     for c in d["cells"]],
        n=7, zoom="14z", center=(51.471173, -2.5926414), spacing=1.0, cost=m["cost_usd"])
    p = base / "evidence-2026-09-02/maps_grid_3x3.json"
    d = jload(p)
    add(p, d["keyword"], d["target_cid"], d["date"], [(c["lat"], c["lng"], c.get("rank"), norm_top3([c["top"]] if c.get("top") else []))
                                                     for c in d["points"]], n=3, zoom=d["zoom"], note="top = #1 only")
    p = base / "evidence-2026-09-23/maps_run_2026-09-23.json"
    d = jload(p)
    grid = [x for x in d["results"] if x["kind"] == "grid"]
    for kw in dict.fromkeys(x["keyword"] for x in grid):
        cells = [(x["lat"], x["lng"], x.get("target_rank"), items_top3(x.get("items"))) for x in grid if x["keyword"] == kw]
        add(p, kw, d["cid"], d["date"], cells, n=7, zoom=d["zoom"], center=tuple(d["centre_pin"]),
            spacing=d["spacing_km"], cost=d["cost_usd"] * len(cells) / d["calls"])


def fmt_saeed():
    base = VAULT / "20-Clients/SaeedLawFirm/Data"
    for p in sorted(glob.glob(str(base / "audit-2026-0[78]-*/grid-*.json"))):
        d = jload(p)
        date = d.get("date") or d.get("baseline_date") or re.search(r"audit-(\d{4}-\d\d-\d\d)", p).group(1)
        add(p, d["keyword"], d["target_cid"], date,
            [(c["lat"], c["lng"], c.get("target_rank"), norm_top3(c.get("top3"))) for c in d["points"] if not c.get("error")],
            n=7, zoom=d.get("zoom", "13z"), spacing=d.get("spacing_km"))
    for p in sorted(glob.glob(str(base / "audit-2026-09-23/grid-*.json")) + glob.glob(str(base / "audit-2026-10-1[58]/grid/grid-*.json"))):
        d = jload(p)
        cells = [(d["lats"][c["i"]], d["lngs"][c["j"]], c.get("rank"), items_top3(c.get("items")))
                 for c in d["cells"] if c.get("ok", True)]
        add(p, d["keyword"], d["target_cid"], d["date"], cells, n=7, zoom=d["zoom"], spacing=d["spacing_km"])


def fmt_nata_1015():
    base = VAULT / "20-Clients/NataPMU/research-2026-10-15-full-audit/evidence/data"
    coords = {(x["kw"], x["i"], x["j"]): (x["lat"], x["lng"]) for f in ("idx_b1.json", "idx_b2.json") for x in jload(base / f)}
    for kw, g in jload(base / "grid_summary.json").items():
        cells = [(*coords[(kw, i, j)], g["grid"][i][j], None) for i in range(7) for j in range(7)
                 if (kw, i, j) in coords and g["grid"][i][j] != "?"]  # "?" = cell never returned
        add(base / "grid_summary.json", kw, "6103403894420122339", "2026-10-15", cells, n=7, zoom="14z",
            center=(51.4676293, -2.6060209), spacing=0.667, note="rank only, no per-cell top-3 kept")


def fmt_tasks_results(tasks_files, res_files, cid, date, src, group_of, cost_per_cell=0.0006):
    tasks = [t for f in tasks_files for t in jload(f)]
    res = [r for f in res_files for r in jload(f)]
    assert len(tasks) == len(res), (src, len(tasks), len(res))
    groups = {}
    for t, r in zip(tasks, res):
        g = group_of(t["tag"])
        if g is None or r is None:
            continue
        lat, lng, zoom = t["location_coordinate"].split(",")
        items = (r[0] or {}).get("items") if r else []
        groups.setdefault((g, t["keyword"], zoom), []).append((float(lat), float(lng), items_rank(items, cid), items_top3(items)))
    for (g, kw, zoom), cells in groups.items():
        add(src, kw, cid, date, cells, zoom=zoom, cost=cost_per_cell * len(cells))


def fmt_cart():
    b = VAULT / "20-Clients/CartCourier/audit-2026-10-15/evidence/data/dfs"
    fmt_tasks_results([b / "grid_tasks.json"], [b / "grid_results.json"], "16946226628968197241", "2026-10-15",
                      b / "grid_results.json", lambda tag: "grid" if tag.startswith("grid|") else None)


def fmt_chdev():
    b = VAULT / "20-Clients/CHDevelopment/research-2026-10-15-seo-audit-v5/research/data"
    fmt_tasks_results([b / f"maps_tasks_{i}.json" for i in range(3)], [b / f"maps_res_{i}.json" for i in range(3)],
                      "1212786551794589906", "2026-10-15", b / "maps_res_0.json",
                      lambda tag: tag.split("|")[0] if tag[:2] in ("g5", "g7") else None)


def haversine_cells(center, n, step, ranks):
    c = (n - 1) / 2
    return [(round(center[0] + (c - i) * step / 111.32, 7),
             round(center[1] + (j - c) * step / (111.32 * math.cos(math.radians(center[0]))), 7), ranks[i][j], None)
            for i in range(n) for j in range(n)]


def ascii_grid(block):
    rows = []
    for line in block.strip("\n").splitlines():
        toks = line.split("<-")[0].split()
        if toks and all(t.isdigit() or t in ("·", "o", "-", chr(0x2014), ".") for t in toks):  # skip legend lines
            rows.append([int(t) if t.isdigit() else None for t in toks])
    return rows


def fmt_shah():
    centre, cid, pid = (43.6292666, -79.667317), "6260713009236674564", "ChIJ44yutlg_K4gRBAg4rE-F4lY"
    base = VAULT / "20-Clients/ShahLawyers/Local SEO"
    for name, date in (("MAPS-ANALYSIS-shahlawyers.ca-2026-08-03.md", "2026-08-03"),
                       ("MAPS-ANALYSIS-shahlawyers.ca-2026-10-16.md", "2026-10-16")):
        p = base / name
        text = p.read_text()
        last_kw = None
        for m in re.finditer(r'### Grid ([A-Z])[^\n]*', text):
            head = m.group(0)
            kw = re.search(r'"([^"]+)"', head)
            kw = kw.group(1) if kw else (last_kw if "same keyword" in head else None)
            last_kw = kw
            km = re.search(r'([\d.]+) km', head)
            zoom = re.search(r'(1\d)z', head)
            block = re.search(r'```(?:text)?\n(.*?)```', text[m.end():m.end() + 1500], re.S)
            if not (kw and km and block) or text[m.end():block.start() + m.end()].count("###"):
                if "Grid D and E" not in head:
                    skipped.append(f"{rel(p)} :: {head.strip('# ')}: no ASCII grid found")
                continue
            ranks = ascii_grid(block.group(1))
            if len(ranks) != 7 or any(len(r) != 7 for r in ranks):
                skipped.append(f"{rel(p)} :: {head.strip('# ')}: grid not 7x7")
                continue
            add(p, kw, cid, date, haversine_cells(centre, 7, float(km.group(1)), ranks), n=7,
                zoom=(zoom.group(0) if zoom else "14z"), center=centre, spacing=float(km.group(1)), place_id=pid,
                note="rebuilt from markdown ASCII grid; no top-3")
        if date == "2026-10-16":  # Grid D/E: ranked only at the office cell
            for kw, r in (("real estate lawyer", 15), ("immigration lawyer", 16)):
                ranks = [[None] * 7 for _ in range(7)]
                ranks[3][3] = r
                add(p, kw, cid, date, haversine_cells(centre, 7, 2.0, ranks), n=7, zoom="14z", center=centre,
                    spacing=2.0, place_id=pid, note="rebuilt from markdown: ranked only at the office cell")


SKIPPED_SUMMARY_ONLY = [
    "*/seo-routine/state.json `maps_pin_rank` (CookingIt and others): one pin per keyword, no grid",
    "50-Audits/CookingIt/evidence-2026-09-03/maps_sweep_15kw_2026-09-03.json + 09-23 'sweep' rows: pin + centre only",
    "20-Clients/CartCourier/.../grid_parsed.json: found-cells only (full grid loaded from grid_results.json instead)",
    "20-Clients/NataPMU/research-2026-10-15-full-audit grid_summary `old_grid`: duplicate of the 2026-09-23 run (loaded from its own file)",
    "20-Clients/NataPMU/LOCAL SEO/MAPS-ANALYSIS v2-v8 (2026-05-22..2026-08-10): markdown summaries; v7 says full grids live only in the corpus append",
    "50-Audits/Aristral/Local SEO/MAPS-ANALYSIS-aristral.com-2026-05-29.md: 3x3 Google Places proxy, not a Maps SERP grid",
    "MAPS-RANK-DASHBOARD-*.html: rank-only render of runs already loaded from their JSON",
    "40-Aristral/SEO/routine-observer/measurements/*_maps_raw.json, Premier 2026-09-24-ring*.json, Derby data/maps_*.json: single-point SERP checks",
    "50-Audits/buytretinoin.org 2026-10-15: no listing, grid deliberately not run",
]


def main():
    fmt_meta_cells_files = (glob.glob(str(VAULT / "20-Clients/NataPMU/content-2026-09-05/geo-grid-2026-09-06.json"))
                            + glob.glob(str(VAULT / "20-Clients/NataPMU/LOCAL SEO/maps-local-2026-09-23/grid-2026-09-23.json"))
                            + glob.glob(str(VAULT / "40-Aristral/Research/gbp-derby-2026-10-11/grid/grid-baseline-2026-10-11.json"))
                            + sorted(glob.glob(str(VAULT / "20-Clients/SkinAndBeautyBox/Local SEO/grid-2026-09-23/*.json")))
                            + sorted(glob.glob(str(VAULT / "20-Clients/SkinAndBeautyBox/Local SEO/audit-2026-10-12/grid/*.json")))
                            + sorted(glob.glob(str(VAULT / "20-Clients/SkinAndBeautyBox/audit-2026-10-15/evidence/grid/*.json"))))
    for p in fmt_meta_cells_files:
        fmt_meta_cells(p)
    for p in sorted(glob.glob(str(VAULT / "50-Audits/Aristral/Local SEO/run-2026-09-*/grid*.json"))):
        fmt_aristral(p)
    fmt_premier(VAULT / "50-Audits/PremierConstruction/audit-2026-09-05/data/grid.json")
    fmt_cookingit()
    fmt_saeed()
    fmt_nata_1015()
    fmt_cart()
    fmt_chdev()
    fmt_shah()

    ids = {}
    for r in runs:
        ids.setdefault(maps_grid_db.run_id(r), r)
    dupes = len(runs) - len(ids)
    final = list(ids.values())
    bad = [(r, maps_grid_db.validate(r)) for r in final if maps_grid_db.validate(r)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in final))
    by = {}
    for r in final:
        by.setdefault(r["client"], [0, 0, set()])
        by[r["client"]][0] += 1
        by[r["client"]][1] += len(r["cells"])
        by[r["client"]][2].add(r["run_at"][:10])
    print(f"runs {len(final)} (dupes collapsed {dupes}), points {sum(len(r['cells']) for r in final)}, invalid {len(bad)}")
    for c, (n, pts, dates) in sorted(by.items()):
        print(f"  {c:20} {n:4} runs {pts:6} points  dates {', '.join(sorted(dates))}")
    print(f"skipped partial/irregular: {len(skipped)}")
    for s in skipped:
        print("  - " + s)
    print("skipped summary-only / not a grid:")
    for s in SKIPPED_SUMMARY_ONLY:
        print("  - " + s)
    print(f"wrote {OUT}")
    if "--load" in sys.argv:
        maps_grid_db.push(final)
        print(f"loaded {len(final)} runs")


if __name__ == "__main__":
    main()
