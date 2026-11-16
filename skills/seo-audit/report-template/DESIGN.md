---
version: alpha
name: Aristral Audit Report
description: The house look for every client-facing audit Aristral sends, on screen and as a PDF. It is the aristral.com light identity applied to a report. Pale paper and warm cards carry the page, near-black ink appears only as the cover pane and the closing pane, a light serif sets headings, a grotesque sets everything else, and every number is drawn as a chart, a bar or a tile instead of a paragraph.
colors:
  primary: "#1a1613"
  secondary: "#e2542c"
  tertiary: "#f1b68a"
  neutral: "#f5efe6"
  paper: "#f5efe6"
  card: "#fffcf7"
  sand: "#ece3d6"
  skin: "#e8d3c1"
  mist: "#d9dfe4"
  ink: "#1a1613"
  ink-2: "#5e554c"
  ink-3: "#978c80"
  ember: "#e2542c"
  ember-deep: "#b8401d"
  apricot: "#f1b68a"
  clay: "#c2876a"
  sky: "#a7c4f0"
  good: "#4a7647"
  on-good: "#ffffff"
  line: "rgba(26, 22, 19, 0.14)"
  line-strong: "rgba(26, 22, 19, 0.3)"
  on-ink: "#f5efe6"
  on-ink-2: "rgba(245, 239, 230, 0.66)"
  on-ink-3: "rgba(245, 239, 230, 0.42)"
  line-on-ink: "rgba(245, 239, 230, 0.16)"
typography:
  display-cover:
    fontFamily: Newsreader
    fontSize: 83.2px
    fontWeight: 400
    lineHeight: 0.98
    letterSpacing: -0.03em
  display-close:
    fontFamily: Newsreader
    fontSize: 60.8px
    fontWeight: 400
    lineHeight: 1.04
    letterSpacing: -0.02em
  headline:
    fontFamily: Newsreader
    fontSize: 49.6px
    fontWeight: 400
    lineHeight: 1.04
    letterSpacing: -0.02em
  figure:
    fontFamily: Newsreader
    fontSize: 46.4px
    fontWeight: 400
    lineHeight: 1
    letterSpacing: -0.02em
  score:
    fontFamily: Newsreader
    fontSize: 64px
    fontWeight: 400
    lineHeight: 1
  title-card:
    fontFamily: Newsreader
    fontSize: 25.6px
    fontWeight: 400
    lineHeight: 1.15
    letterSpacing: -0.02em
  title-fix:
    fontFamily: Newsreader
    fontSize: 20px
    fontWeight: 400
    lineHeight: 1.15
  lede:
    fontFamily: Hanken Grotesk
    fontSize: 18.4px
    fontWeight: 400
    lineHeight: 1.5
  body:
    fontFamily: Hanken Grotesk
    fontSize: 17px
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: Hanken Grotesk
    fontSize: 15.5px
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  button:
    fontFamily: Hanken Grotesk
    fontSize: 15.2px
    fontWeight: 500
    lineHeight: 1
  mono:
    fontFamily: IBM Plex Mono
    fontSize: 12.8px
    fontWeight: 400
    lineHeight: 1.5
rounded:
  sm: 8px
  md: 12px
  lg: 14px
  pane: 22px
  full: 999px
spacing:
  wrap: 1120px
  gap: 28px
  section-gap: 96px
  section-gap-min: 56px
  edge-pad: 40px
  bar-height: 52px
  page-width: 1280px
  page-margin: 64px
  page-body-pad: 56px
  card-pad: 30px
  button-height: 44px
components:
  page:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
  bar:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink-2}"
    typography: "{typography.mono}"
    rounded: "{rounded.md}"
    height: 52px
    padding: 20px
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: 30px
  card-sand:
    backgroundColor: "{colors.sand}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
  card-skin:
    backgroundColor: "{colors.skin}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
  card-body:
    textColor: "{colors.ink-2}"
    typography: "{typography.body-sm}"
  pane:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-ink}"
    rounded: "{rounded.pane}"
    padding: 60px
  pane-secondary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-ink-2}"
  pane-faint:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-ink-3}"
  pane-rule:
    backgroundColor: "{colors.line-on-ink}"
    height: 1px
  score-ring:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.apricot}"
    typography: "{typography.score}"
  glyph-lit-ember:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ember}"
  glyph-lit-sky:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sky}"
  divider:
    backgroundColor: "{colors.line}"
    height: 1px
  bar-track:
    backgroundColor: "{colors.sand}"
    rounded: "{rounded.full}"
    height: 10px
  bar-fill-good:
    backgroundColor: "{colors.good}"
    rounded: "{rounded.full}"
  bar-fill-mid:
    backgroundColor: "{colors.apricot}"
    rounded: "{rounded.full}"
  bar-fill-low:
    backgroundColor: "{colors.ember}"
    rounded: "{rounded.full}"
  volume-bar:
    backgroundColor: "{colors.clay}"
    rounded: "{rounded.full}"
    height: 8px
  rival-bar:
    backgroundColor: "{colors.ink-3}"
    rounded: "{rounded.full}"
    height: 12px
  chip-top:
    backgroundColor: "{colors.good}"
    textColor: "{colors.on-good}"
    typography: "{typography.mono}"
    rounded: "{rounded.full}"
  chip-first-page:
    backgroundColor: "{colors.mist}"
    textColor: "{colors.ink}"
    rounded: "{rounded.full}"
  chip-low:
    backgroundColor: "{colors.apricot}"
    textColor: "{colors.ink}"
    rounded: "{rounded.full}"
  chip-missing:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ember-deep}"
    rounded: "{rounded.full}"
  chip-missing-outline:
    backgroundColor: "{colors.ember}"
    height: 1px
  tile:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    typography: "{typography.figure}"
    rounded: "{rounded.lg}"
    padding: 22px
  tile-warn:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ember-deep}"
    typography: "{typography.figure}"
  shelf-well:
    backgroundColor: "{colors.sand}"
    rounded: "{rounded.sm}"
  shelf-drawing:
    backgroundColor: "{colors.clay}"
    width: 1.6px
  shelf-card:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.md}"
    padding: 10px
  shelf-missing:
    backgroundColor: "{colors.card}"
    rounded: "{rounded.sm}"
  shelf-missing-mark:
    backgroundColor: "{colors.ember}"
    width: 1.5px
  outline-strong:
    backgroundColor: "{colors.line-strong}"
    height: 1px
  button-on-ink:
    backgroundColor: "{colors.on-ink}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.full}"
    height: 44px
    padding: 20px
  focus-ring:
    backgroundColor: "{colors.secondary}"
    width: 2px
  accent-tertiary:
    backgroundColor: "{colors.tertiary}"
  page-ground:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.primary}"
---

# Aristral audit report

Every audit a client sees (SEO, local, technical, AI readiness) uses this look, on screen and as a PDF. It is the aristral.com light identity (`~/Documents/GitHub/Aristral-redesign/DESIGN.md`) applied to a report. The reference build is the Pipinchick Silkies audit of 2026-11-15 (`example/pipinchick.json`).

The files beside this one are the template. Write the findings as JSON, render it, print it. Do not hand-write report HTML.

```
python3 render_report.py report.json            # -> report.html (refuses to render if a rule below is broken)
python3 build_pdf.py report.html                # -> report.pdf
```

`template.css` holds every screen style (the print-only page rules live in `build_pdf.py`), `brand.html` the Aristral mark and wordmark, `example/pipinchick.json` a complete report to copy from.

## Overview

The reader is a business owner, not an SEO. They should understand the state of their site from the cover and the first page, and know what to do from the fix list. Three rules shape everything:

1. **Show it, don't write it.** Every number is a chart, a bar, a chip or a tile. Prose explains a picture; it never replaces one.
2. **Everything lines up.** One 1120px column. Every two-up block splits 1fr / 1fr, so the right-hand column starts on the same line in every section. Rows of cards are always full: 3 summary cards, 4 tiles, 2 compare cards, an even number of wins, 3 plan stages.
3. **Header and footer mirror each other.** The same bar, the same distance from the page edge, the same gap to the content.

## Colors

| Token | Hex | Use |
| --- | --- | --- |
| `paper` | `#f5efe6` | Page ground |
| `card` | `#fffcf7` | Cards, the header and footer bars |
| `sand`, `skin` | `#ece3d6`, `#e8d3c1` | Second and third card in a row of three; bar tracks; shelf wells |
| `mist` | `#d9dfe4` | "First page" rank chip only |
| `ink` | `#1a1613` | Text; the cover pane and closing pane |
| `ink-2` | `#5e554c` | Ledes, card body, captions |
| `ink-3` | `#978c80` | Axis labels, fix numbers, rival bars. Not for sentences |
| `ember` | `#e2542c` | The one thing that is wrong: low scores, missing rank, the client's own bar, the empty shelf slot |
| `ember-deep` | `#b8401d` | Ember text: warning tiles, "Not in top 50" |
| `apricot` | `#f1b68a` | Middle scores, ranks 11+, the score ring |
| `clay` | `#c2876a` | Search volume bars, shelf drawings |
| `good` | `#4a7647` | Scores 75+, ranks 1 to 3, ticks on wins |
| `sky` | `#a7c4f0` | One lit drawing on the cover. Never UI |

Measured contrast (WCAG): ink on paper 15.7:1, ink-2 on card 7.1:1, ink-2 on sand 5.7:1, ink-2 on skin 5.0:1, white on good 5.3:1, ember-deep on card 5.4:1, ember-deep on paper 4.8:1, ink on apricot 10.1:1, ink on mist 13.4:1, paper on ink 15.7:1. ink-3 on card is 3.2:1, which is why it is kept to labels and numerals.

Status colour always means the same thing: good is green, middling is apricot, bad is ember. Never use ember for decoration.

## Typography

Newsreader (light serif) for the cover title, section headings, card titles, big figures and the score. Hanken Grotesk for everything a reader reads in sentences. IBM Plex Mono only for data: dates in the bars, axis labels, volumes, rank chips, fix numbers. All three load from Google Fonts in the rendered page.

| Token | Rule |
| --- | --- |
| `display-cover` | `clamp(2.6rem, 6vw, 5.2rem)`; 112px on the PDF cover |
| `headline` | `clamp(2rem, 4vw, 3.1rem)`, the section `h2` |
| `title-card` | `clamp(1.3rem, 2vw, 1.6rem)` |
| `figure` | `clamp(2rem, 3.6vw, 2.9rem)`, tile numbers |
| `display-close` | `clamp(2.2rem, 4.6vw, 3.8rem)`, the closing line |
| `title-fix` | `1.25rem` |
| `lede` | `clamp(1.02rem, 1.3vw, 1.15rem)`, max 46ch |

Each `fontSize` token above is the size at a 1440px screen, the top of its `clamp()`.

Sentence case everywhere. No uppercase tracked eyebrows. Headings use `text-wrap: balance`.

## Layout

- One column, `max-width: 1120px`, side gutter at least 16px. Blocks sit `clamp(56px, 7vw, 96px)` apart, 96px on a laptop.
- Every section opens with a head: `h2` on the left, lede on the right, bottom-aligned, on the same 1fr / 1fr split as the cards below it.
- Under 900px everything stacks to one column; under 560px the four tiles and the shelf go two by two. The page never scrolls sideways.
- Header bar at the top, footer bar at the bottom, identical in size, colour and shadow. The page pads top and bottom by the same `clamp(16px, 3vw, 40px)`, and each bar sits one block gap from the content, so the two ends mirror at every width.

## Elevation & Depth

Flat. The only shadow is the soft one under the header and footer bars. Cards have no border and no shadow; they are separated by colour from the paper.

## Shapes

Bars 12px, cards and tiles 14px, panes 22px, chips, buttons and data bars full pills. Drawings are 24-unit line icons with round caps and joins, stroke 1.6.

## Components

Sections are chosen from this set and ordered for the story of the audit. The renderer refuses a report that breaks any shape in this table, and names the rule it broke.

| Section `type` | What it shows | Fixed shape |
| --- | --- | --- |
| cover (`hero`) | Ink pane: who it is for, the title, one-sentence lede, 3 facts, the score ring and a field of drawings | exactly 3 facts |
| `summary` | Working, costing you, biggest opening | exactly 3 cards, tones `good`, `bad`, `opp` in that order (card, sand, skin) |
| `scorecard` | Score bars from top-level `scores`, sorted high to low, legend, short notes | 5 to 8 areas, 2 to 5 notes |
| `trend` | Two line charts side by side and a source caption | exactly 2 charts |
| `tiles` | Four big numbers with a comparison under each | exactly 4 tiles |
| `rankings` | Searches sorted by volume, each with a volume bar and a rank chip, then optional notes | 6 to 14 rows, position 1 to 50 or `null`, 0 or 2 cards |
| `compare` | Two cards: `bars` (client against rivals), `shelf` (three rivals and the empty client slot) or `text` | exactly 2 cards; `bars` 3 to 6 rows, `shelf` exactly 4 items |
| `wins` | Ticks with a bold lead and a plain detail | even count, 4 to 8 |
| `fixes` | Numbered fixes in Fix first, Fix next, Tidy up; each says what we found and what to do | 6 to 14 fixes; groups `now`, `soon`, `later` in that order, `now` required |
| `plan` | First, Next, Then (the default labels) | exactly 3 stages, the same item count, at least 2 each |
| close | Ink pane: one line, one sentence, one button | always last; the button must go to `https://aristral.com/contact` |

Rank chips: green `#1` to `#3`, mist `#4` to `#10`, apricot `#11` to `#50`, ember outline "Not in top 50" for `null`.

Scores: the overall in the ring is the weighted mean of `scores`, rounded. The renderer uses the weights in the JSON; copy them from the audit skill's Weights line. Bars are green at 75 and up, apricot 60 to 74, ember under 60.

Charts plot real numbers on one scale with labelled ticks, mark the latest value with an ember dot and, when the peak is earlier, the peak with an open dot, and carry an `aria-label` that states the takeaway. A caption under every chart or tile row names the kind of source in plain words.

The cover's drawing field mixes the client's own subject (pass `hero.glyphs`, e.g. `["hen", "egg", "coop"]`, `["scales", "doc", "briefcase"]` for a law firm, `["cutlery"]` for a restaurant) with search drawings (default subject `globe`, `doc`, `chat`). Only names in `GLYPHS` in `render_report.py` are accepted; add a drawing there in the same 24-unit pen if a trade needs one. Six fixed cells are lit: ember, apricot and one sky.

## PDF

`build_pdf.py` prints the rendered page to fixed 1280px-wide pages:

- Page 1 is the cover: the ink pane fills the body between the header bar and the page number, with the title at 112px.
- Every page has the same header bar 64px from the top and a centred "Page X of Y" in the same 52px band 64px from the bottom. No footer bar in the PDF.
- Blocks never split across pages: a card row, a table, a tile row, each fix. A section head travels with its first block, a caption with the block above it, and a fix group's label with its first fix.
- Page height (1500 to 1900px, in 4px steps) and the breaks are chosen together by a scored search that punishes space left at the foot of a page far more than space spread through the gaps. On every page but the last, leftover goes into the gaps first (up to 84px per section gap and 24px per inner gap), then splits evenly above and below the content, so no page ends in a blank strip. A block taller than any normal page makes the page taller, up to 2600px; split that block in the JSON instead.
- Backgrounds run to the page edge; print colour is exact.

## Voice and Content

- British English, short sentences, second person to the client ("you rank fourth").
- Plain words for every source: "Google UK search estimates", "a standard phone speed test", "live Google results on a phone". Never name our tools or our stack. The renderer refuses a report that mentions them.
- No prices anywhere. The only call to action is Talk to Aristral, linking to `/contact`.
- No em dashes or en dashes; the renderer refuses them.
- Every number is one we measured and checked against the live site. Say what a modelled number is ("read them as a trend rather than a count").
- No delivery dates in the plan; stages are First, Next, Then.
- Run the humanizer pass on the copy before rendering.

The renderer checks dashes, prices (a currency sign before a digit), a fixed list of our tool names and the contact link. The rest of this section is the author's job: it cannot tell British English from American or a modelled number from a measured one.

## Do's and Don'ts

- Do keep each row of cards full and the same height. Don't leave one card alone on a row.
- Do draw a number. Don't write a paragraph that lists numbers.
- Do keep ember for the problem. Don't use it to decorate.
- Do use the template. Don't fork the CSS into a one-off report; change `template.css` and this file together.
- Don't add sections the reader has to decode: no tables of raw crawl output, no URLs longer than a domain, no jargon without a one-line explanation.
