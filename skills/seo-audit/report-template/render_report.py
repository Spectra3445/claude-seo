#!/usr/bin/env python3
"""Render an Aristral audit report from a JSON file. Spec: DESIGN.md beside this file.

    python3 render_report.py report.json [-o out.html]

The JSON holds the words and numbers; this script holds the look. It refuses layouts that break
the symmetry rules (odd card counts, empty sections) and text that breaks house style (em dashes,
prices, our tooling names), so a report that renders is a report that can go to a client.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent

# ---------- house rules -------------------------------------------------------------------------

BANNED = [  # our stack never appears in a client report; pricing never appears anywhere
    "dataforseo", "lighthouse", "pagespeed insights", "luna", "codex", "claude", "supabase", "semrush", "ahrefs",
    "screaming frog", "seodb", "aristral loop", "gsc_", "crux", "ollama", "openai", "gpt",
]
PRICE = re.compile(r"[£$€]\s?\d")


def lint_text(data):
    errs = []

    def walk(v, path):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{path}.{k}")
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f"{path}[{i}]")
        elif isinstance(v, str):
            low = v.lower()
            if "—" in v or "–" in v:
                errs.append(f"{path}: em or en dash (use a full stop, comma, colon or brackets)")
            for b in BANNED:
                if re.search(rf"\b{re.escape(b)}\b", low):
                    errs.append(f"{path}: names our tooling ('{b}'); describe the source plainly instead")
            if PRICE.search(v):
                errs.append(f"{path}: contains a price; Aristral reports never show prices")
    walk(data, "report")
    return errs


def need(cond, msg, errs):
    if not cond:
        errs.append(msg)


# ---------- drawings ----------------------------------------------------------------------------

GLYPHS = {
    # search and web
    "mag": '<circle cx="10.5" cy="10.5" r="6"/><path d="M15 15l5.5 5.5"/>',
    "pin": '<path d="M12 21s-6-6-6-11a6 6 0 0112 0c0 5-6 11-6 11z"/><circle cx="12" cy="10" r="2"/>',
    "chart": '<path d="M4 20V10M10 20V5M16 20v-7M22 20H2"/>',
    "trend": '<path d="M3 17l6-6 4 4 8-8M15 7h6v6"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
    "star": '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
    "phone": '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
    "browser": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 8.5h18M6 6.3h.01M8.5 6.3h.01"/>',
    "cart": '<path d="M3 4h2l2.5 11h11L21 7H7"/><circle cx="9" cy="19.5" r="1.3"/><circle cx="17" cy="19.5" r="1.3"/>',
    "link": '<path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1"/>',
    "doc": '<path d="M7 3h7l4 4v14H7zM14 3v4h4M10 12h5M10 16h5"/>',
    "chat": '<path d="M4 5h16v11H9l-5 4z"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "plus": '<path d="M12 7v10M7 12h10"/>',
    # trades and subjects
    "hen": '<path d="M6 16c0-4 3-7 7-7 1-3 4-4 6-2-1 1-1 2 0 3 1 3-1 8-6 9H9c-2 0-3-1-3-3z"/><path d="M12 19v3M15 19v3"/><circle cx="16.5" cy="8.5" r=".6"/>',
    "egg": '<path d="M12 3c3.5 0 6 5 6 9.5S15.5 21 12 21s-6-4-6-8.5S8.5 3 12 3z"/>',
    "coop": '<path d="M3 11l9-7 9 7M5 9.5V20h14V9.5"/><path d="M10 20v-5h4v5"/>',
    "house": '<path d="M3 11l9-7 9 7M5 9.5V20h14V9.5"/><path d="M10 20v-5h4v5"/>',
    "scales": '<path d="M12 4v16M7 20h10M5 7h14M5 7l-3 6h6zM19 7l-3 6h6z"/>',
    "cutlery": '<path d="M7 3v8M5 3v5a2 2 0 004 0V3M7 11v10M16 3c-2 2-2 6 0 8v10"/>',
    "cross": '<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z"/>',
    "briefcase": '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5h6v2M3 12h18"/>',
    "bottle": '<path d="M10 3h4v3l2 3v12H8V9l2-3z"/><path d="M8 13h8"/>',
    "scissors": '<circle cx="6" cy="17" r="3"/><circle cx="18" cy="17" r="3"/><path d="M8 15L19 4M16 15L5 4"/>',
    "car": '<path d="M4 15l2-6h12l2 6v4H4zM4 15h16"/><circle cx="8" cy="17.5" r="1.2"/><circle cx="16" cy="17.5" r="1.2"/>',
    "box": '<path d="M3 7l9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10"/>',
}
SEARCH_SET = ["mag", "pin", "chart", "star", "cart", "globe", "phone", "trend", "browser", "link"]


def glyph_svg(name, cls="gl"):
    if name not in GLYPHS:
        raise SystemExit(f"unknown glyph '{name}'. Known: {', '.join(sorted(GLYPHS))}")
    return f'<svg viewBox="0 0 24 24" class="{cls}" aria-hidden="true">{GLYPHS[name]}</svg>'


def glyph_field(subject):
    """30 cells, 10 x 3. Subject drawings take every other cell; about one cell in five is lit."""
    subject = subject or ["globe", "doc", "chat"]
    cells, s_i, q_i = [], 0, 0
    for i in range(30):
        row_shift = (i // 10) % 2
        if (i + row_shift) % 2 == 0:
            cells.append(subject[s_i % len(subject)]); s_i += 1
        else:
            cells.append(SEARCH_SET[(q_i * 3) % len(SEARCH_SET)]); q_i += 1
    lit = {2: "lit-e", 7: "lit-a", 12: "lit-e", 16: "lit-s", 21: "lit-a", 26: "lit-e"}
    return "".join(glyph_svg(n, f"gl {lit.get(i, '')}".strip()) for i, n in enumerate(cells))


# ---------- pieces ------------------------------------------------------------------------------

def e(s):
    return html.escape(str(s), quote=False)


def ea(s):
    return html.escape(str(s), quote=True)


def fmt_num(n, style):
    if style == "k":
        return f"{n/1000:.0f}k" if n >= 1000 else f"{n:,}"
    return f"{n:,}"


def line_chart(c):
    labels = [p[0] for p in c["points"]]
    values = [p[1] for p in c["points"]]
    w, h, pad_l, pad_r, pad_t, pad_b = 560, 230, 46, 16, 18, 34
    ymin, ymax = c.get("ymin", 0), c.get("ymax", max(values))
    ticks, style = c.get("ticks", []), c.get("format", "int")
    f = lambda n: fmt_num(n, style)
    iw, ih = w - pad_l - pad_r, h - pad_t - pad_b
    xs = [pad_l + i * iw / (len(values) - 1) for i in range(len(values))]
    ys = [pad_t + ih - (v - ymin) / (ymax - ymin) * ih for v in values]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = f"M{xs[0]:.1f},{pad_t+ih:.1f} L" + " L".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys)) + f" L{xs[-1]:.1f},{pad_t+ih:.1f} Z"
    grid = "".join(
        f'<line x1="{pad_l}" x2="{w-pad_r}" y1="{pad_t+ih-(t-ymin)/(ymax-ymin)*ih:.1f}" y2="{pad_t+ih-(t-ymin)/(ymax-ymin)*ih:.1f}" class="g"/>'
        f'<text x="{pad_l-8}" y="{pad_t+ih-(t-ymin)/(ymax-ymin)*ih+4:.1f}" class="ax" text-anchor="end">{f(t)}</text>' for t in ticks)
    at = c.get("x_labels_at", [0, len(values) // 2, len(values) - 1])
    xl = "".join(
        f'<text x="{xs[i]:.1f}" y="{h-10}" class="ax" text-anchor="{"start" if i == 0 else ("end" if i == len(values)-1 else "middle")}">{e(labels[i])}</text>'
        for i in at)
    peak = max(range(len(values)), key=lambda i: values[i])
    below = len(values) > 1 and values[-2] > values[-1]
    marks = f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="5" class="dot-end"/>'
    lab = f'<text x="{xs[-1]-10:.1f}" y="{ys[-1] + (18 if below else -12):.1f}" class="val" text-anchor="end">{f(values[-1])}</text>'
    if peak != len(values) - 1:
        marks += f'<circle cx="{xs[peak]:.1f}" cy="{ys[peak]:.1f}" r="3.5" class="dot"/>'
        lab += f'<text x="{xs[peak]:.1f}" y="{ys[peak]-10:.1f}" class="val" text-anchor="middle">{f(values[peak])}</text>'
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{ea(c["aria"])}" class="chart">{grid}'
            f'<path d="{area}" class="area"/><polyline points="{pts}" class="ln"/>{marks}{lab}{xl}</svg>')


def score_ring(score):
    r, c = 76, 2 * 3.14159 * 76
    return (f'<svg viewBox="0 0 188 188" class="ring" role="img" aria-label="Overall score {score} out of 100">'
            f'<circle cx="94" cy="94" r="{r}" class="ring-bg"/>'
            f'<circle cx="94" cy="94" r="{r}" class="ring-fg" stroke-dasharray="{c:.1f}" stroke-dashoffset="{c*(1-score/100):.1f}" transform="rotate(-90 94 94)"/>'
            f'<text x="94" y="100" text-anchor="middle" class="ring-n">{score}</text>'
            f'<text x="94" y="128" text-anchor="middle" class="ring-of">out of 100</text></svg>')


def head(sid, title, lede):
    return f'<div class="head"><h2 id="{sid}">{e(title)}</h2><p class="lede">{e(lede)}</p></div>'


TONE = {"good": ("t-good", "Working"), "bad": ("t-bad", "Costing you"), "opp": ("t-opp", "Biggest opening")}
CHECK = '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>'


# ---------- section renderers -------------------------------------------------------------------

def sec_summary(s, sid, errs, r):
    cards = s["cards"]
    need(len(cards) == 3, "summary: exactly 3 cards (working, costing you, biggest opening)", errs)
    need([c.get("tone") for c in cards] == ["good", "bad", "opp"], "summary: tones must run good, bad, opp in that order", errs)
    body = ""
    for c in cards:
        cls, default = TONE[c["tone"]]
        body += f'<div class="card"><span class="dotlab {cls}"><i></i>{e(c.get("label", default))}</span><h3>{e(c["title"])}</h3><p>{e(c["text"])}</p></div>'
    return head(sid, s.get("title", "The short version"), s["lede"]) + f'<div class="three trio">{body}</div>'


def sec_scorecard(s, sid, errs, r):
    need(5 <= len(r["scores"]) <= 8, "scores: 5 to 8 areas", errs)
    need(2 <= len(s["notes"]) <= 5, "scorecard.notes: 2 to 5 short paragraphs so both cards end near the same line", errs)
    rows = ""
    for a in sorted(r["scores"], key=lambda a: -a["score"]):
        tone = "good" if a["score"] >= 75 else ("mid" if a["score"] >= 60 else "low")
        rows += (f'<div class="srow"><span class="sname">{e(a["name"])}</span><span class="sbar"><span class="sfill {tone}" '
                 f'style="width:{a["score"]}%"></span></span><span class="snum">{a["score"]}</span></div>')
    legend = '<div class="legend"><span class="dotlab"><i class="g"></i>75 and up</span><span class="dotlab"><i class="m"></i>60 to 74</span><span class="dotlab"><i class="l"></i>Under 60</span></div>'
    notes = "".join(f"<p>{e(p)}</p>" for p in s["notes"])
    lede = s["lede"].replace("{overall}", str(r["_overall"]))
    return (head(sid, s.get("title", "Scorecard"), lede) +
            f'<div class="two"><div class="card">{rows}{legend}</div><div class="card sidecopy"><h3>{e(s.get("notes_title", "What the scores mean"))}</h3>{notes}</div></div>')


def sec_trend(s, sid, errs, r):
    need(len(s["charts"]) == 2, f"{sid} trend: exactly 2 charts side by side", errs)
    cards = "".join(f'<div class="card chart-card"><h3>{e(c["title"])}</h3><p class="label">{e(c["label"])}</p>{line_chart(c)}</div>' for c in s["charts"])
    return head(sid, s["title"], s["lede"]) + f'<div class="two">{cards}</div><p class="cap">{e(s["caption"])}</p>'


def sec_tiles(s, sid, errs, r):
    need(len(s["tiles"]) == 4, f"{sid} tiles: exactly 4", errs)
    t = "".join(f'<div class="tile{" warn" if x.get("warn") else ""}"><b>{e(x["value"])}</b><span class="vs">{e(x["vs"])}</span><p>{e(x["text"])}</p></div>' for x in s["tiles"])
    return head(sid, s["title"], s["lede"]) + f'<div class="four">{t}</div><p class="cap">{e(s["caption"])}</p>'


def sec_rankings(s, sid, errs, r):
    rows_in = s["rows"]
    need(6 <= len(rows_in) <= 14, f"{sid} rankings: 6 to 14 searches", errs)
    need(len(s.get("cards", [])) in (0, 2), f"{sid} rankings: 0 or 2 cards under the table", errs)
    mx = max(x["volume"] for x in rows_in)
    rows = ""
    for x in sorted(rows_in, key=lambda x: -x["volume"]):
        pos = x.get("position")
        need(pos is None or (isinstance(pos, int) and 1 <= pos <= 50), f"{sid} rankings: position for '{x['search']}' must be 1 to 50, or null when not in the top 50", errs)
        if pos is None or not isinstance(pos, int) or pos > 50:
            chip, cls = s.get("miss_label", "Not in top 50"), "c-miss"
        else:
            chip, cls = f"#{pos}", "c-top" if pos <= 3 else ("c-ok" if pos <= 10 else "c-low")
        rows += (f'<div class="brow"><span class="bkw">{e(x["search"])}</span><span class="bvol"><span class="bvbar" '
                 f'style="width:{x["volume"]/mx*100:.1f}%"></span><span class="bvn">{x["volume"]:,}</span></span>'
                 f'<span class="chip {cls}">{e(chip)}</span></div>')
    cols = s.get("columns", ["Search", "Monthly searches", "Your spot"])
    table = (f'<div class="card"><div class="brow bhead"><span>{e(cols[0])}</span><span>{e(cols[1])}</span><span class="r">{e(cols[2])}</span></div>'
             f'<div class="blist">{rows}</div></div>')
    cards = ""
    if s.get("cards"):
        cards = '<div class="two after">' + "".join(f'<div class="card"><h3>{e(c["title"])}</h3><p class="cap body">{e(c["text"])}</p></div>' for c in s["cards"]) + "</div>"
    return head(sid, s["title"], s["lede"]) + table + cards


def card_bars(c, errs):
    need(3 <= len(c["rows"]) <= 6, "bars card: 3 to 6 rows", errs)
    mx = max(x["value"] for x in c["rows"])
    rows = "".join(f'<div class="lrow{" me" if x.get("me") else ""}"><span class="lname">{e(x["name"])}</span><span class="lbar">'
                   f'<span class="lfill" style="width:{x["value"]/mx*100:.1f}%"></span></span><span class="lnum">{x["value"]:,}</span></div>'
                   for x in c["rows"])
    return f'<div class="card"><h3>{e(c["title"])}</h3><p class="label sub">{e(c["label"])}</p>{rows}<p class="cap">{e(c["caption"])}</p></div>'


def card_shelf(c, errs):
    need(len(c["items"]) == 4, "shelf card: exactly 4 items (three rivals and the client)", errs)
    items = ""
    for x in c["items"]:
        you = x.get("missing")
        icon = GLYPHS["plus" if you else x.get("icon", "box")]
        items += (f'<div class="pc{" you" if you else ""}"><div class="img"><svg viewBox="0 0 24 24">{icon}</svg></div>'
                  f'<span>{e(x["name"])}</span></div>')
    return (f'<div class="card"><h3>{e(c["title"])}</h3><p class="label sub">{e(c["label"])}</p>'
            f'<div class="shop" aria-label="{ea(c["aria"])}">{items}</div><p class="cap">{e(c["caption"])}</p></div>')


def card_text(c, errs):
    return f'<div class="card"><h3>{e(c["title"])}</h3><p class="cap body">{e(c["text"])}</p></div>'


def sec_compare(s, sid, errs, r):
    need(len(s["cards"]) == 2, f"{sid} compare: exactly 2 cards", errs)
    kinds = {"bars": card_bars, "shelf": card_shelf, "text": card_text}
    return head(sid, s["title"], s["lede"]) + '<div class="two">' + "".join(kinds[c["kind"]](c, errs) for c in s["cards"]) + "</div>"


def sec_wins(s, sid, errs, r):
    need(len(s["items"]) % 2 == 0 and 4 <= len(s["items"]) <= 8, f"{sid} wins: an even number, 4 to 8, so the two columns close square", errs)
    w = "".join(f'<div class="win">{CHECK}<p>{e(x["lead"])} <span>{e(x["detail"])}</span></p></div>' for x in s["items"])
    return head(sid, s.get("title", "What's already working"), s["lede"]) + f'<div class="wins">{w}</div>'


def sec_fixes(s, sid, errs, r):
    n, body = 0, ""
    tiers = {"now": "Fix first", "soon": "Fix next", "later": "Tidy up"}
    seq = [g.get("tier") for g in s["groups"]]
    need(seq == [t for t in tiers if t in seq], f"{sid} fixes: groups run now, soon, later, each at most once", errs)
    need("now" in seq, f"{sid} fixes: there must be a 'now' group", errs)
    for g in s["groups"]:
        need(g["tier"] in tiers, f"{sid} fixes: tier must be now, soon or later", errs)
        need(g["items"], f"{sid} fixes: empty group", errs)
        body += f'<div class="grp-h {g["tier"]}"><i></i><span>{e(g.get("label", tiers[g["tier"]]))}</span></div>'
        for x in g["items"]:
            n += 1
            body += (f'<div class="fix"><span class="n">{n}</span><div><h3>{e(x["title"])}</h3><p class="what">{e(x["what"])}</p></div>'
                     f'<p class="do"><b>Do</b>{e(x["do"])}</p></div>')
    need(6 <= n <= 14, f"{sid} fixes: 6 to 14 fixes in all", errs)
    return head(sid, s.get("title", "What to fix"), s.get("lede", "Most important first.")) + f'<div class="fixgrp">{body}</div>'


def sec_plan(s, sid, errs, r):
    need(len(s["stages"]) == 3, f"{sid} plan: exactly 3 stages", errs)
    counts = {len(x["items"]) for x in s["stages"]}
    need(min(counts or {0}) >= 2, f"{sid} plan: at least 2 items per stage", errs)
    for x, d in zip(s["stages"], ["First", "Next", "Then"]):
        x.setdefault("step", d)
    need(len(counts) == 1, f"{sid} plan: every stage needs the same number of items so the cards end level", errs)
    st = "".join(f'<div class="card"><span class="step">{e(x["step"])}</span><h3>{e(x["title"])}</h3><ul>' +
                 "".join(f"<li>{e(i)}</li>" for i in x["items"]) + "</ul></div>" for x in s["stages"])
    return head(sid, s.get("title", "How we'd go about it"), s["lede"]) + f'<div class="three plan">{st}</div>'


SECTIONS = {"summary": sec_summary, "scorecard": sec_scorecard, "trend": sec_trend, "tiles": sec_tiles,
            "rankings": sec_rankings, "compare": sec_compare, "wins": sec_wins, "fixes": sec_fixes, "plan": sec_plan}


# ---------- page --------------------------------------------------------------------------------

def render(r):
    errs = lint_text(r)
    need(len(r["hero"]["facts"]) == 3, "hero.facts: exactly 3", errs)
    w = sum(a["weight"] for a in r["scores"])
    r["_overall"] = round(sum(a["score"] * a["weight"] for a in r["scores"]) / w)
    brand = (HERE / "brand.html").read_text().strip()
    css = (HERE / "template.css").read_text()

    hero = r["hero"]
    facts = "".join(f'<div><b>{e(f["value"])}</b><span>{e(f["label"])}</span></div>' for f in hero["facts"])
    out = [f'<header class="bar">{brand}<span class="mono">{e(r.get("kind", "SEO audit"))} · {e(r["date_label"])}</span></header>',
           f'<section class="pane" aria-labelledby="t"><div class="pane-l"><div><p class="kick">{e(hero["kicker"])}</p>'
           f'<h1 id="t">{e(hero["title"])}</h1><p class="lede">{e(hero["lede"])}</p></div><div class="facts">{facts}</div></div>'
           f'<div class="pane-r">{score_ring(r["_overall"])}<div class="field" aria-hidden="true">{glyph_field(hero.get("glyphs"))}</div></div></section>']
    for i, s in enumerate(r["sections"], 1):
        if s["type"] not in SECTIONS:
            errs.append(f"sections[{i-1}]: unknown type '{s['type']}' (known: {', '.join(SECTIONS)})"); continue
        out.append(f'<section aria-labelledby="s{i}">{SECTIONS[s["type"]](s, f"s{i}", errs, r)}</section>')
    c = r["close"]
    need(c.get("href", "https://aristral.com/contact").rstrip("/") == "https://aristral.com/contact", "close.href: the only call to action is https://aristral.com/contact", errs)
    out.append(f'<section class="close" aria-labelledby="sc"><h2 id="sc">{e(c["title"])}</h2><div class="act"><p>{e(c["text"])}</p>'
               f'<a class="btn" href="{ea(c.get("href", "https://aristral.com/contact"))}">{e(c.get("cta", "Talk to Aristral"))}</a></div></section>')
    foot_brand = brand.replace('aria-label="Aristral"', 'aria-hidden="true"')
    out.append(f'<footer class="bar">{foot_brand}'
               f'<span class="mono">aristral.com · Bristol</span></footer>')

    if errs:
        sys.exit("report did not render:\n  - " + "\n  - ".join(errs))

    fonts = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
             '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,300;6..72,400&family=Hanken+Grotesk:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">')
    return (f'<title>{e(r["page_title"])}</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n{fonts}\n<style>\n{css}</style>\n'
            f'<div class="wrap">\n' + "\n".join(out) + "\n</div>\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    src = Path(a.json)
    r = json.loads(src.read_text())
    out = Path(a.out) if a.out else src.with_suffix(".html")
    out.write_text(render(r))
    print(f"{out}  overall {r['_overall']}")


if __name__ == "__main__":
    main()
