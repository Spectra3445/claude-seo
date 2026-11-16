#!/usr/bin/env python3
"""Print a rendered audit page to a paginated PDF. Spec: DESIGN.md beside this file.

    python3 build_pdf.py report.html [-o report.pdf]

Fixed 1280px-wide pages, a cover, the same header bar on every page and a centred page number at
the foot. Cards never split. Page breaks and page height are chosen together (dynamic programming)
to leave the least empty space; what is left is shared across the gaps, then split evenly above
and below the content.
"""
import argparse
import subprocess
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def strip_block(css: str, opener: str) -> str:
    i = css.index(opener)
    depth, j = 0, i
    while True:
        if css[j] == "{":
            depth += 1
        elif css[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return css[:i] + css[j + 1:]


PRINT_CSS = """<style id="print-css">
html,body{margin:0;padding:0!important;background:var(--paper);-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{width:1280px}
.page{width:1280px;box-sizing:border-box;padding:64px;display:flex;flex-direction:column;background:var(--paper);overflow:hidden;break-after:page}
.page:last-child{break-after:auto}
.page > .bar{flex:none}
.pbody{flex:1;display:flex;flex-direction:column;padding:56px 0;min-height:0}
.pbody > *{flex:none}
  .pbody.cover > div{flex:1!important;display:flex} .pbody.cover .pane{flex:1;align-items:stretch;padding:72px}
.pbody.cover .pane h1{font-size:112px} .pbody.cover .pane .lede{font-size:21px;max-width:30ch} .pbody.cover .pane .kick{font-size:17px}
.pbody.cover .ring{width:300px} .pbody.cover .field{max-width:470px;gap:22px} .pbody.cover .pane-r{gap:64px}
.pbody.cover .facts b{font-size:44px} .pbody.cover .facts span{font-size:15px}
.pfoot{flex:none;height:52px;display:flex;align-items:center;justify-content:center;font:400 13px var(--mono);color:var(--ink-2)}
.wins.row{grid-template-columns:repeat(2,minmax(0,1fr))}
#src{position:absolute;left:-99999px;top:0;width:1152px}
</style>"""

PAGINATE_JS = r"""<script>
(function(){
  const GAP_IN = 28, GAP_SEC = 72, PAD = 64, BAR = 52, BODY_PAD = 56, W = 1280;
  const src = document.getElementById('src');
  const head = src.querySelector('header.bar'), foot = src.querySelector('footer.bar');

  // Flatten the report into units that must stay whole. A section head sticks to the unit after it.
  const units = [];
  let sec = 0;
  for (const el of [...src.children]) {
    if (el === head || el === foot) continue;
    sec++;
    if (el.tagName !== 'SECTION' || el.classList.contains('pane') || el.classList.contains('close')) {
      units.push({nodes:[el], sec}); continue;
    }
    const parts = [];
    for (const ch of [...el.children]) {
      if (ch.classList.contains('fixgrp')) {
        let pend = null;
        for (const f of [...ch.children]) {
          if (f.classList.contains('grp-h')) { pend = f; continue; }
          const g = document.createElement('div'); g.className = 'fixgrp';
          if (pend) { g.appendChild(pend); pend = null; }
          g.appendChild(f); parts.push(g);
        }
      } else parts.push(ch);
    }
    // glue the head (and a following caption) to its neighbour
    const glued = [];
    for (let i = 0; i < parts.length; i++) {
      const p = parts[i];
      if (p.classList.contains('head') && parts[i+1]) { glued.push([p, parts[++i]]); continue; }
      if (p.classList.contains('cap') && glued.length) { glued[glued.length-1].push(p); continue; }
      glued.push([p]);
    }
    glued.forEach((nodes, k) => units.push({nodes, sec, first: k === 0}));
  }

  // Measure each unit at print width.
  const meas = document.createElement('div'); meas.style.cssText = 'position:absolute;left:-99999px;top:0;width:1152px';
  document.body.appendChild(meas);
  for (const u of units) {
    const box = document.createElement('div'); box.style.cssText = 'display:flex;flex-direction:column;gap:' + GAP_IN + 'px';
    u.nodes.forEach(n => box.appendChild(n)); meas.appendChild(box);
    u.h = Math.ceil(box.getBoundingClientRect().height); u.box = box;
  }

  // Optimal page breaks for a given height (dynamic programming over unit boundaries).
  function pageLen(us) {
    return us.reduce((s,u,i) => s + u.h + (i ? (us[i-1].sec !== u.sec ? GAP_SEC : GAP_IN) : 0), 0);
  }
  function pageCost(us, room, isLast) {
    const used = pageLen(us); if (used > room) return Infinity;
    const left = room - used;
    if (isLast) return 0.6 * left * left;
    let cap = 0;
    us.forEach((u, i) => { if (i) cap += (us[i-1].sec !== u.sec ? 84 : 24); });
    const absorbed = Math.min(left, cap), bare = left - absorbed;
    return bare * bare * 4 + absorbed * absorbed * 0.2;
  }
  function plan(H) {
    const room = H - 2*PAD - 2*BAR - 2*BODY_PAD; const body = units.slice(1), N = body.length;
    if (body.some(u => u.h > room)) return null;
    const dp = new Array(N + 1).fill(Infinity), cut = new Array(N + 1).fill(-1); dp[0] = 0;
    for (let i = 1; i <= N; i++) for (let j = i - 1; j >= 0; j--) {
      const us = body.slice(j, i); if (pageLen(us) > room) break;
      const c = dp[j] + pageCost(us, room, i === N) + 9000;
      if (c < dp[i]) { dp[i] = c; cut[i] = j; }
    }
    const pages = []; for (let i = N; i > 0; i = cut[i]) pages.unshift(body.slice(cut[i], i));
    pages.unshift([units[0]]); const left = pages.map(p => room - pageLen(p)); left[0] = 0;
    return {H, room, pages, left, cost: dp[N]};
  }

  let best = null;
  for (let H = 1500; H <= 2600; H += 4) {  // past 1900 only when one block is taller than a normal page
    const p = plan(H); if (!p) continue;
    p.cost += 0;
    if (H > 1900 && best) break;
    if (!best || p.cost < best.cost) best = p;
  }

  const st = document.createElement('style');
  st.textContent = '@page{size:' + W + 'px ' + best.H + 'px;margin:0}.page{height:' + best.H + 'px}';
  document.head.appendChild(st);

  const n = best.pages.length;
  best.pages.forEach((pg, i) => {
    const page = document.createElement('div'); page.className = 'page';
    const h = head.cloneNode(true);
    // footer is just the page number, in a strip the same height as the header bar so margins stay equal
    const f = document.createElement('div'); f.className = 'pfoot';
    f.textContent = 'Page ' + (i+1) + ' of ' + n;
    const body = document.createElement('div'); body.className = 'pbody';
    // spread leftover across the gaps (section gaps take more than inner gaps); the cover's pane fills its page
    const left = best.left[i];
    let w = 0; pg.forEach((u, k) => { if (k) w += (pg[k-1].sec !== u.sec ? 84 : 24); });
    const share = (i < n - 1 && w) ? Math.min(1, left / w) : 0;
    pg.forEach((u, k) => {
      if (k) u.box.style.marginTop = ((pg[k-1].sec !== u.sec ? GAP_SEC + 84*share : GAP_IN + 24*share)) + 'px';
      body.appendChild(u.box);
    });
    if (i === 0) { body.classList.add('cover'); } else { body.style.justifyContent = 'center'; }
    page.append(h, body, f);
    document.body.appendChild(page);
  });
  src.remove(); meas.remove();
  document.title = document.title;
  document.documentElement.dataset.pages = n + ' pages at ' + best.H + 'px, foot space ' + best.left.join(',');
})();
</script>"""


def build(src: Path, pdf: Path):
    html = src.read_text()
    head, body = html.split('<div class="wrap">', 1)
    for q in ("@media (max-width:900px){", "@media (max-width:560px){"):
        head = strip_block(head, q)
    body = body.rsplit("</div>", 1)[0]
    doc = ("<!doctype html><html lang=\"en-GB\"><head><meta charset=\"utf-8\">"
           "<meta name=\"viewport\" content=\"width=1280\">" + head + PRINT_CSS + "</head><body>"
           "<div id=\"src\" class=\"wrap\">" + body + "</div>" + PAGINATE_JS + "</body></html>")
    tmp = src.with_name(src.stem + ".print.html")
    tmp.write_text(doc)
    subprocess.run([CHROME, "--headless=new", "--no-pdf-header-footer", "--virtual-time-budget=10000",
                    "--window-size=1280,1800", f"--print-to-pdf={pdf}", tmp.as_uri()],
                   check=True, stderr=subprocess.DEVNULL)
    tmp.unlink()
    print(pdf)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    src = Path(a.html).resolve()
    build(src, Path(a.out).resolve() if a.out else src.with_suffix(".pdf"))
