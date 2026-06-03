"""Generate the six portfolio screenshots for Strata as PIL composites.

Each PNG is a 1600×1000 image mocking the Strata trading-terminal workspace.
Colors and layout match the live Streamlit CSS in frontend/app.py.

  workspace.png — main candlestick + overlays + sidebar + analyst panel
  wyckoff.png   — variant emphasising Wyckoff phase bands
  chat.png      — grounded chat panel (full-frame)
  backtest.png  — per-detector backtest stats table + equity curve
  api.png       — django-ninja OpenAPI explorer mockup
  traces.png    — Langfuse trace mockup of one briefing run

Run from the repo root:  python3 scripts/make_screenshots.py
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ──────────────────────────────────────────────────────────────────────────────
# Palette — matches the CSS in frontend/app.py
# ──────────────────────────────────────────────────────────────────────────────
BG_DEEP    = (11, 15, 23)         # #0b0f17
BG_SURFACE = (14, 19, 28)         # #0e131c
BG_PANEL   = (19, 26, 38)         # #131a26
BG_PANEL_2 = (15, 21, 33)         # #0f1521
BORDER     = (28, 35, 49)         # #1c2331
INK        = (214, 221, 231)      # #d6dde7
INK_MUTE   = (139, 148, 158)      # #8b949e
INK_DIM    = (110, 118, 129)      # #6e7681
ACCENT     = (88, 166, 255)       # #58a6ff  (BoS/info)
ACCENT_2   = (188, 140, 255)      # #bc8cff
UP         = (63, 185, 80)        # #3fb950
DOWN       = (248, 81, 73)        # #f85149
AMBER      = (233, 178, 88)       # #e9b258

W, H = 1600, 1000
OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _font(size: int, *, bold: bool = False, mono: bool = True) -> ImageFont.FreeTypeFont:
    candidates = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]
        if mono else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    chosen = candidates[0] if bold else candidates[-1]
    try:
        return ImageFont.truetype(chosen, size=size)
    except OSError:
        return ImageFont.load_default()


def _new_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG_DEEP)
    return img, ImageDraw.Draw(img, "RGBA")


# ──────────────────────────────────────────────────────────────────────────────
# Synthetic OHLCV — deterministic so screenshots are reproducible
# ──────────────────────────────────────────────────────────────────────────────


def synth_ohlcv(n: int = 220, seed: int = 7) -> list[tuple[float, float, float, float]]:
    rng = random.Random(seed)
    price = 67_400.0
    out: list[tuple[float, float, float, float]] = []
    # Five visible regimes: down → accumulation → markup → distribution → markdown.
    regime = [(-1, 0.0028), (0, 0.0010), (1, 0.0032), (0, 0.0014), (-1, 0.0026)]
    sizes = [40, 30, 60, 40, n - 170]
    seg = 0
    seg_left = sizes[0]
    for _ in range(n):
        if seg_left == 0:
            seg = min(seg + 1, len(regime) - 1)
            seg_left = sizes[seg]
        d, vol = regime[seg]
        drift = d * price * 0.0015
        noise = rng.gauss(0, price * vol)
        op = price
        cl = price + drift + noise
        hi = max(op, cl) + abs(rng.gauss(0, price * vol * 0.55))
        lo = min(op, cl) - abs(rng.gauss(0, price * vol * 0.55))
        out.append((op, hi, lo, cl))
        price = cl
        seg_left -= 1
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Primitives
# ──────────────────────────────────────────────────────────────────────────────


def rounded_rect(draw, box, fill, radius=4, outline=None):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=fill, outline=outline)


def pill(draw, xy, text, fg, bg, *, font=None, pad=(10, 4), radius=10):
    font = font or _font(11, bold=True)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = xy
    draw.rounded_rectangle((x, y, x + tw + 2 * pad[0], y + th + 2 * pad[1]),
                            radius=radius, fill=bg, outline=(*fg, 80), width=1)
    draw.text((x + pad[0], y + pad[1] - 1), text, fill=fg, font=font)


def metric(draw, xy, label, value, *, accent=None, w=180):
    x, y = xy
    label_font = _font(10, mono=False)
    value_font = _font(22, bold=True)
    draw.text((x, y), label.upper(), fill=INK_DIM, font=label_font)
    fg = accent or INK
    draw.text((x, y + 14), value, fill=fg, font=value_font)


# ──────────────────────────────────────────────────────────────────────────────
# Header / sidebar
# ──────────────────────────────────────────────────────────────────────────────


def draw_header(draw, *, symbol="BTCUSDT", interval="1h"):
    h = 40
    draw.rectangle((0, 0, W, h), fill=BG_SURFACE)
    draw.rectangle((0, h - 1, W, h), fill=BORDER)
    draw.text((20, 11), "◰ STRATA", fill=ACCENT, font=_font(15, bold=True))
    draw.text((125, 14), "market-structure analyst", fill=INK_DIM, font=_font(10, mono=False))
    draw.text((W - 380, 14), f"{symbol}", fill=INK, font=_font(13, bold=True))
    pill(draw, (W - 290, 9), interval, INK_MUTE, (110, 118, 129, 46))
    pill(draw, (W - 235, 9), "● live", UP, (63, 185, 80, 46))
    draw.text((W - 170, 14), "12:41:08 UTC", fill=INK_DIM, font=_font(11))
    draw.text((W - 70, 14),  "vlad@vltech55", fill=INK_DIM, font=_font(11))


def draw_sidebar(draw):
    sb_x = 0
    sb_w = 240
    draw.rectangle((sb_x, 40, sb_x + sb_w, H), fill=BG_SURFACE)
    draw.rectangle((sb_x + sb_w - 1, 40, sb_x + sb_w, H), fill=BORDER)

    x = 16
    y = 56
    draw.text((x, y), "◰ STRATA", fill=ACCENT, font=_font(13, bold=True))
    draw.text((x, y + 16), "v0.1 · vltech55", fill=INK_DIM, font=_font(10, mono=False))
    y += 40
    draw.line((x, y, x + sb_w - 32, y), fill=BORDER, width=1)
    y += 12
    draw.text((x, y), "INSTRUMENT", fill=INK_DIM, font=_font(10, mono=False))
    y += 16
    rounded_rect(draw, (x, y, x + sb_w - 32, y + 26), fill=BG_PANEL, radius=3)
    draw.text((x + 8, y + 7), "BTCUSDT", fill=INK, font=_font(12, bold=True))
    y += 32
    rounded_rect(draw, (x, y, x + sb_w - 32, y + 26), fill=BG_PANEL, radius=3)
    draw.text((x + 8, y + 7), "1h", fill=INK, font=_font(12, bold=True))
    draw.text((x + sb_w - 50, y + 7), "▼", fill=INK_DIM, font=_font(11))
    y += 32
    draw.text((x, y), "Lookback (bars)  500", fill=INK_DIM, font=_font(10, mono=False))
    y += 14
    rounded_rect(draw, (x, y, x + sb_w - 32, y + 4), fill=BG_PANEL, radius=2)
    rounded_rect(draw, (x, y, x + 100, y + 4), fill=ACCENT, radius=2)
    y += 24
    draw.line((x, y, x + sb_w - 32, y), fill=BORDER, width=1)
    y += 12

    draw.text((x, y), "WATCHLIST", fill=INK_DIM, font=_font(10, mono=False))
    y += 18
    watch = [("BTCUSDT", True), ("ETHUSDT", False), ("SOLUSDT", False),
             ("ARBUSDT", False), ("OPUSDT", False), ("AVAXUSDT", False),
             ("BNBUSDT", False), ("LINKUSDT", False)]
    for code, active in watch:
        bg = ACCENT if active else BG_PANEL
        fg = (255, 255, 255) if active else INK
        rounded_rect(draw, (x, y, x + sb_w - 32, y + 24), fill=bg, radius=3)
        draw.text((x + 8, y + 6), code, fill=fg, font=_font(11, bold=True))
        y += 28
    y += 10
    draw.line((x, y, x + sb_w - 32, y), fill=BORDER, width=1)
    y += 12

    draw.text((x, y), "CHART OVERLAYS", fill=INK_DIM, font=_font(10, mono=False))
    y += 18
    for label, on in (("Swing pivots", True), ("BoS / CHoCH lines", True),
                       ("Order blocks", True), ("Fair-value gaps", True),
                       ("Wyckoff bands", True)):
        sq_color = ACCENT if on else BG_PANEL
        draw.rounded_rectangle((x, y, x + 12, y + 12), fill=sq_color, radius=2)
        if on:
            draw.line((x + 3, y + 6, x + 5, y + 9), fill="white", width=2)
            draw.line((x + 5, y + 9, x + 10, y + 3), fill="white", width=2)
        draw.text((x + 22, y - 1), label, fill=INK, font=_font(11, mono=False))
        y += 20

    return sb_w


# ──────────────────────────────────────────────────────────────────────────────
# Candlestick chart (with overlays)
# ──────────────────────────────────────────────────────────────────────────────


def draw_chart(draw, box, candles, *, swings=True, events=True, wyckoff=True, obs=True, fvgs=True):
    x0, y0, x1, y1 = box
    rounded_rect(draw, (x0, y0, x1, y1), fill=BG_DEEP, radius=4, outline=BORDER)
    pad = 14
    inner = (x0 + pad, y0 + pad + 26, x1 - pad, y1 - pad)
    ix0, iy0, ix1, iy1 = inner
    iw = ix1 - ix0
    ih = iy1 - iy0
    n = len(candles)
    cw = max(2, int(iw / n) - 1)

    highs = [c[1] for c in candles]
    lows = [c[2] for c in candles]
    hi_max = max(highs)
    lo_min = min(lows)
    rng = hi_max - lo_min

    def yp(price: float) -> int:
        return int(iy1 - (price - lo_min) / rng * ih)

    # Top chrome
    draw.text((x0 + pad, y0 + 8), "BTCUSDT  ·  1h", fill=INK, font=_font(12, bold=True))
    pill(draw, (x0 + 150, y0 + 6), "TREND: UP", UP, (63, 185, 80, 46))

    # Right-side price axis tick lines
    for k in (0.0, 0.25, 0.5, 0.75, 1.0):
        ty = int(iy0 + ih * k)
        draw.line((ix0, ty, ix1, ty), fill=BORDER, width=1)
        price = hi_max - (hi_max - lo_min) * k
        draw.text((ix1 + 4, ty - 6), f"{price:,.0f}", fill=INK_DIM, font=_font(10))

    # Wyckoff bands (drawn first, behind candles)
    if wyckoff:
        # 4 segments: accumulation → markup → distribution → markdown
        bounds_pct = [(0.18, 0.32), (0.32, 0.55), (0.62, 0.78)]
        labels = ["accumulation", "markup", "distribution"]
        fills = [(63, 185, 80, 18), (63, 185, 80, 30), (248, 81, 73, 18)]
        for (a, b), lab, fill in zip(bounds_pct, labels, fills):
            bx0 = int(ix0 + iw * a)
            bx1 = int(ix0 + iw * b)
            draw.rectangle((bx0, iy0, bx1, iy1), fill=fill)
            draw.text((bx0 + 6, iy0 + 4), lab, fill=INK_MUTE, font=_font(10, mono=False))

    # Order blocks (semi-transparent rect, behind candles)
    if obs:
        for cx, lo, hi, bull in [
            (int(ix0 + iw * 0.30), 65_300, 65_900, True),
            (int(ix0 + iw * 0.68), 71_800, 72_400, False),
        ]:
            color = (63, 185, 80, 35) if bull else (248, 81, 73, 35)
            draw.rectangle((cx, yp(hi), ix1, yp(lo)), fill=color)

    # Fair value gaps
    if fvgs:
        for ci, top, bot, bull in [
            (int(ix0 + iw * 0.42), 68_900, 68_500, True),
        ]:
            draw.rectangle((ci, yp(top), ix1, yp(bot)), fill=(88, 166, 255, 38))

    # Candles
    for i, (op, hi, lo, cl) in enumerate(candles):
        x = ix0 + int(i * (iw / n)) + 1
        is_up = cl >= op
        color = UP if is_up else DOWN
        # wick
        draw.line((x + cw // 2, yp(hi), x + cw // 2, yp(lo)), fill=color, width=1)
        # body
        top = yp(max(op, cl))
        bot = yp(min(op, cl))
        if bot - top < 1:
            bot = top + 1
        draw.rectangle((x, top, x + cw, bot), fill=color, outline=color)

    # Swings
    if swings:
        sample_swings = [int(n * p) for p in (0.10, 0.18, 0.27, 0.36, 0.50, 0.58, 0.65, 0.74, 0.82)]
        for j, idx in enumerate(sample_swings):
            if idx >= n:
                continue
            cnd = candles[idx]
            if j % 2 == 0:  # high
                px = cnd[1]
                cx = ix0 + int(idx * (iw / n)) + cw // 2
                cy = yp(px) - 10
                draw.polygon([(cx - 5, cy - 5), (cx + 5, cy - 5), (cx, cy + 4)], fill=DOWN)
            else:  # low
                px = cnd[2]
                cx = ix0 + int(idx * (iw / n)) + cw // 2
                cy = yp(px) + 10
                draw.polygon([(cx - 5, cy + 5), (cx + 5, cy + 5), (cx, cy - 4)], fill=UP)

    # BoS / CHoCH dashed levels
    if events:
        for price, kind, color in [
            (66_200, "CHoCH up", UP),
            (68_700, "BoS up",   ACCENT),
            (71_900, "BoS up",   ACCENT),
            (70_400, "CHoCH down", DOWN),
        ]:
            py = yp(price)
            # dashed
            x = ix0
            while x < ix1:
                draw.line((x, py, min(x + 8, ix1), py), fill=color, width=1)
                x += 14
            draw.text((ix1 - 90, py - 12), f"{kind}  {price:,.0f}", fill=color, font=_font(10))


# ──────────────────────────────────────────────────────────────────────────────
# Right-side analyst panel
# ──────────────────────────────────────────────────────────────────────────────


def draw_analyst_panel(draw, box):
    x0, y0, x1, y1 = box
    rounded_rect(draw, (x0, y0, x1, y1), fill=BG_SURFACE, radius=4, outline=BORDER)
    pad = 14
    x = x0 + pad
    y = y0 + pad

    draw.text((x, y), "Analyst", fill=INK, font=_font(14, bold=True))
    draw.text((x + 96, y + 3), "↻ refresh", fill=ACCENT, font=_font(11))
    y += 24

    # meta row
    for i, (lab, val, col) in enumerate([
        ("TREND", "UP", UP), ("MTF", "+0.67", INK), ("ITER", "1", INK),
    ]):
        draw.text((x + i * 90, y), lab, fill=INK_DIM, font=_font(10, mono=False))
        draw.text((x + i * 90, y + 12), val, fill=col, font=_font(15, bold=True))
    y += 38

    # Briefing markdown
    body = [
        ("# BTCUSDT · 1h — Structure Briefing", INK, _font(13, bold=True)),
        ("**Trend:** UP · **Multi-TF coherence:** +0.67", INK, _font(11)),
        ("", INK, _font(11)),
        ("## What the structure says", AMBER, _font(11, bold=True)),
        ("CHoCH_UP printed at 2026-05-29 14:00 on close 66,243.",  INK, _font(11)),
        ("Follow-up BoS_UP confirmed 2026-06-01 09:00 @ 68,712.",  INK, _font(11)),
        ("Second BoS_UP 2026-06-02 22:00 @ 71,948 — trend intact.", INK, _font(11)),
        ("", INK, _font(11)),
        ("## Wyckoff", AMBER, _font(11, bold=True)),
        ("Phase: MARKUP · Confidence: 0.78", INK, _font(11)),
        ("Volume profile supports the label; expansion on each", INK, _font(11)),
        ("BoS, contraction on retracement.", INK, _font(11)),
        ("", INK, _font(11)),
        ("## Levels to watch", AMBER, _font(11, bold=True)),
        ("Resistance: 72,400  ·  Support: 68,712 (BoS retest)",   INK, _font(11)),
        ("Last BoS: 2026-06-02 22:00  @ 71,948",                  INK, _font(11)),
        ("Last CHoCH: 2026-05-29 14:00 @ 66,243",                 INK, _font(11)),
        ("", INK, _font(11)),
        ("## Risk notes", AMBER, _font(11, bold=True)),
        ("None flagged.",                                          INK_DIM, _font(11)),
    ]
    for text, fg, font in body:
        if text:
            draw.text((x, y), text, fill=fg, font=font)
        y += font.size + 4


def draw_chat_panel(draw, box, full: bool = False):
    x0, y0, x1, y1 = box
    rounded_rect(draw, (x0, y0, x1, y1), fill=BG_SURFACE, radius=4, outline=BORDER)
    pad = 14
    x = x0 + pad
    y = y0 + pad
    draw.text((x, y), "Ask", fill=INK, font=_font(13, bold=True))
    draw.text((x, y + 18), "Grounded on BTCUSDT 1h structure.", fill=INK_DIM, font=_font(11, mono=False))
    y += 42
    msgs = [
        ("user", "Why is the trend up?"),
        ("assistant",
         "The 2026-05-29 14:00 CHoCH_UP @ 66,243 reversed the prior downtrend; "
         "subsequent BoS_UP at 68,712 and 71,948 confirmed continuation. "
         "The MTF score is +0.67 — 1h and 4h are both UP, 1d still UNDEFINED."),
        ("user", "When was the most recent CHoCH?"),
        ("assistant",
         "2026-05-29 14:00 UTC, closing at 66,243. That print broke the prior swing low "
         "and flipped the trend from DOWN to UP."),
    ]
    if full:
        msgs += [
            ("user", "What about volume on the latest BoS?"),
            ("assistant",
             "Volume on the 2026-06-02 22:00 BoS_UP was 1.4× the 30-bar median — supportive. "
             "The next-bar retest came on declining volume, which is the canonical Wyckoff "
             "spring-confirmation pattern."),
        ]
    for role, text in msgs:
        is_user = role == "user"
        bar_color = ACCENT if is_user else UP
        bg = BG_PANEL if is_user else BG_PANEL_2
        # Bar on the left
        draw.rectangle((x, y, x + 3, y + 56), fill=bar_color)
        rounded_rect(draw, (x + 8, y, x1 - pad, y + 56), fill=bg, radius=4)
        draw.text((x + 16, y + 4), role.upper(), fill=bar_color, font=_font(9, mono=False))
        # word-wrap the body
        words = text.split()
        line = ""
        line_y = y + 18
        for w in words:
            trial = (line + " " + w).strip()
            tw = draw.textlength(trial, font=_font(11, mono=False))
            if tw > (x1 - x - 40):
                draw.text((x + 16, line_y), line, fill=INK, font=_font(11, mono=False))
                line_y += 14
                line = w
            else:
                line = trial
        if line:
            draw.text((x + 16, line_y), line, fill=INK, font=_font(11, mono=False))
        y += 68

    # Input
    y = y1 - 46
    rounded_rect(draw, (x, y, x1 - pad, y + 32), fill=BG_PANEL, radius=4, outline=BORDER)
    draw.text((x + 10, y + 8), "e.g. 'What does the latest order block imply?'",
               fill=INK_DIM, font=_font(11, mono=False))


# ──────────────────────────────────────────────────────────────────────────────
# Compositions
# ──────────────────────────────────────────────────────────────────────────────


def make_workspace():
    img, draw = _new_canvas()
    draw_header(draw)
    sb_w = draw_sidebar(draw)
    candles = synth_ohlcv(220, seed=7)

    # KPI strip
    kpi_y = 50
    draw.text((sb_w + 16, kpi_y), "BTCUSDT · 1h", fill=INK, font=_font(13, bold=True))
    metric_row_y = kpi_y + 22
    for i, (lab, val, accent) in enumerate([
        ("LAST",        "71,948.20",  None),
        ("CHANGE",      "+4.62%",     UP),
        ("RANGE HIGH",  "72,418.00",  None),
        ("RANGE LOW",   "63,710.50",  None),
        ("SWINGS",      "27",         None),
        ("EVENTS",      "9",          None),
    ]):
        metric(draw, (sb_w + 16 + i * 180, metric_row_y), lab, val, accent=accent)

    # Tabs
    tabs_y = metric_row_y + 56
    tab_x = sb_w + 16
    draw.line((tab_x, tabs_y + 22, W - 30, tabs_y + 22), fill=BORDER, width=1)
    for i, (label, active) in enumerate([("📈 Chart", True), ("🧭 Multi-TF", False), ("🧪 Backtest", False)]):
        bbox = draw.textbbox((0, 0), label, font=_font(12, mono=False))
        tw = bbox[2] - bbox[0]
        col = ACCENT if active else INK_DIM
        draw.text((tab_x + i * 130, tabs_y), label, fill=col, font=_font(12, mono=False))
        if active:
            draw.rectangle((tab_x + i * 130, tabs_y + 21, tab_x + i * 130 + tw + 8, tabs_y + 23), fill=ACCENT)

    # Chart box
    chart_box = (sb_w + 16, tabs_y + 32, sb_w + 16 + 900, H - 30)
    draw_chart(draw, chart_box, candles)

    # Analyst panel
    panel_box = (chart_box[2] + 16, kpi_y, W - 30, H - 30)
    draw_analyst_panel(draw, panel_box)

    img.save(OUT_DIR / "workspace.png", "PNG", optimize=True)


def make_wyckoff():
    img, draw = _new_canvas()
    draw_header(draw, symbol="ETHUSDT", interval="4h")
    sb_w = draw_sidebar(draw)
    candles = synth_ohlcv(200, seed=17)

    draw.text((sb_w + 16, 50), "ETHUSDT · 4h — Wyckoff view", fill=INK, font=_font(13, bold=True))
    pill(draw, (sb_w + 270, 50), "phase: MARKUP", UP, (63, 185, 80, 46))
    pill(draw, (sb_w + 380, 50), "confidence: 0.78", AMBER, (233, 178, 88, 46))

    chart_box = (sb_w + 16, 90, W - 30, H - 30)
    draw_chart(draw, chart_box, candles, swings=True, events=True, wyckoff=True, obs=False, fvgs=False)

    # Phase legend (bottom-left of chart)
    lx, ly = chart_box[0] + 18, chart_box[3] - 90
    rounded_rect(draw, (lx, ly, lx + 220, ly + 78), fill=BG_PANEL, radius=4, outline=BORDER)
    draw.text((lx + 10, ly + 8), "WYCKOFF SEGMENTS", fill=INK_DIM, font=_font(10, mono=False))
    for i, (lab, col) in enumerate([
        ("accumulation  · conf 0.71", (63, 185, 80, 180)),
        ("markup        · conf 0.84", (63, 185, 80, 255)),
        ("distribution  · conf 0.62", (248, 81, 73, 180)),
    ]):
        sw_y = ly + 26 + i * 16
        draw.rectangle((lx + 10, sw_y + 3, lx + 22, sw_y + 11), fill=col)
        draw.text((lx + 28, sw_y), lab, fill=INK, font=_font(11))

    img.save(OUT_DIR / "wyckoff.png", "PNG", optimize=True)


def make_chat():
    img, draw = _new_canvas()
    draw_header(draw)
    sb_w = draw_sidebar(draw)
    # full-frame chat: bigger panel
    draw.text((sb_w + 16, 50), "Strata chat", fill=INK, font=_font(14, bold=True))
    draw.text((sb_w + 16, 68), "All answers grounded on the latest structure snapshot",
               fill=INK_DIM, font=_font(11, mono=False))
    draw_chat_panel(draw, (sb_w + 16, 96, W - 30, H - 30), full=True)
    img.save(OUT_DIR / "chat.png", "PNG", optimize=True)


def make_backtest():
    img, draw = _new_canvas()
    draw_header(draw)
    sb_w = draw_sidebar(draw)
    draw.text((sb_w + 16, 50), "Backtest snapshot — BTCUSDT · 1h", fill=INK, font=_font(14, bold=True))
    draw.text((sb_w + 16, 70), "Nightly per-detector hit-rate / drawdown / risk-reward · tagged by git SHA",
               fill=INK_DIM, font=_font(11, mono=False))

    # Table
    headers = ["DETECTOR", "SIGNALS", "HIT-RATE", "AVG P&L %", "MAX DD %", "RISK / RWD", "GIT SHA"]
    rows = [
        ("bos_up",      "47", "0.617", "+1.42",  "-3.6", "1.93", "a4f1e22"),
        ("bos_down",    "38", "0.553", "+0.96",  "-4.1", "1.62", "a4f1e22"),
        ("choch_up",    "12", "0.667", "+1.81",  "-2.0", "2.41", "a4f1e22"),
        ("choch_down",  "11", "0.636", "+1.55",  "-2.4", "2.05", "a4f1e22"),
    ]
    tx = sb_w + 30
    ty = 110
    rounded_rect(draw, (tx, ty, W - 40, ty + 200), fill=BG_SURFACE, radius=4, outline=BORDER)
    col_x = [tx + 20, tx + 200, tx + 320, tx + 440, tx + 580, tx + 720, tx + 880]
    for i, h in enumerate(headers):
        draw.text((col_x[i], ty + 14), h, fill=INK_DIM, font=_font(11, mono=False))
    draw.line((tx + 12, ty + 36, W - 52, ty + 36), fill=BORDER, width=1)
    for r, row in enumerate(rows):
        ry = ty + 50 + r * 34
        for i, val in enumerate(row):
            color = INK
            if i == 2 and float(val) >= 0.6:
                color = UP
            if i == 3 and val.startswith("+"):
                color = UP
            if i == 4:
                color = DOWN
            font = _font(12, bold=(i == 0))
            draw.text((col_x[i], ry), val, fill=color, font=font)

    # Equity curve chart (right-bottom area)
    cb = (sb_w + 30, ty + 230, W - 40, H - 30)
    rounded_rect(draw, cb, fill=BG_SURFACE, radius=4, outline=BORDER)
    draw.text((cb[0] + 16, cb[1] + 12), "EQUITY CURVE — last 30 days", fill=INK_DIM, font=_font(11, mono=False))
    # synthetic curve
    pts = []
    val = 1.0
    rng = random.Random(11)
    for i in range(180):
        val *= (1 + rng.gauss(0.0006, 0.006))
        pts.append(val)
    x0, y0, x1, y1 = cb[0] + 30, cb[1] + 40, cb[2] - 20, cb[3] - 24
    mn, mx = min(pts), max(pts)
    coords = []
    for i, v in enumerate(pts):
        cx = x0 + int((i / (len(pts) - 1)) * (x1 - x0))
        cy = int(y1 - (v - mn) / (mx - mn) * (y1 - y0))
        coords.append((cx, cy))
    # fill below curve
    poly = coords + [(x1, y1), (x0, y1)]
    draw.polygon(poly, fill=(63, 185, 80, 55))
    draw.line(coords, fill=UP, width=2)

    img.save(OUT_DIR / "backtest.png", "PNG", optimize=True)


def make_api():
    img, draw = _new_canvas()
    # White-ish OpenAPI explorer feel — django-ninja docs theme
    draw.rectangle((0, 0, W, H), fill=(245, 247, 250))
    draw.rectangle((0, 0, W, 60), fill=(28, 35, 49))
    draw.text((24, 18), "◰ STRATA  ·  django-ninja  ·  /api/v1", fill=(214, 221, 231), font=_font(14, bold=True))
    draw.text((W - 240, 22), "OpenAPI 3.1 · v1.0.0", fill=INK_DIM, font=_font(11, mono=False))

    # Side TOC
    draw.rectangle((0, 60, 260, H), fill=(255, 255, 255))
    draw.rectangle((259, 60, 260, H), fill=(220, 224, 230))
    toc = [
        "auth  ·  4 endpoints",
        "users  ·  2 endpoints",
        "stock  ·  3 endpoints",
        "chart  ·  2 endpoints",
        "ai  ·  2 endpoints",
        "chat  ·  4 endpoints",
    ]
    for i, line in enumerate(toc):
        draw.text((20, 80 + i * 30), line, fill=(45, 55, 72), font=_font(12, mono=False))

    # Sections
    methods = [
        ("POST", "/v1/auth/signup",                     "Create a new account",          (63, 185, 80)),
        ("POST", "/v1/auth/login",                      "Exchange credentials for tokens", (63, 185, 80)),
        ("POST", "/v1/auth/refresh",                    "Rotate a refresh token",        (63, 185, 80)),
        ("POST", "/v1/auth/logout",                     "Revoke a refresh token",        (63, 185, 80)),
        ("GET",  "/v1/users/me",                        "Current user",                  (88, 166, 255)),
        ("GET",  "/v1/stock/symbols",                   "List symbols (paginated)",      (88, 166, 255)),
        ("GET",  "/v1/stock/candles/{symbol_code}",     "Fetch OHLCV series",            (88, 166, 255)),
        ("POST", "/v1/stock/backfill",                  "Trigger historical backfill",   (63, 185, 80)),
        ("GET",  "/v1/chart/structure/{symbol_code}",   "Detect swings/BoS/CHoCH/Wyckoff/OB/FVG", (88, 166, 255)),
        ("GET",  "/v1/chart/mtf/{symbol_code}",         "Multi-timeframe coherence",     (88, 166, 255)),
        ("POST", "/v1/ai/briefing",                     "Generate a fresh briefing (LangGraph)", (63, 185, 80)),
        ("GET",  "/v1/ai/briefing/{symbol}/{interval}/latest", "Most recent briefing",   (88, 166, 255)),
        ("POST", "/v1/chat/ask",                        "Ask a grounded question",       (63, 185, 80)),
    ]
    y = 90
    for method, path, desc, color in methods:
        rounded_rect(draw, (280, y, W - 30, y + 56), fill=(255, 255, 255), radius=6, outline=(225, 230, 236))
        rounded_rect(draw, (296, y + 14, 360, y + 42), fill=color, radius=4)
        draw.text((306, y + 19), method, fill=(255, 255, 255), font=_font(13, bold=True))
        draw.text((376, y + 14), path, fill=(20, 30, 48), font=_font(13, bold=True, mono=True))
        draw.text((376, y + 32), desc, fill=(98, 108, 124), font=_font(11, mono=False))
        y += 64
        if y > H - 80:
            break

    img.save(OUT_DIR / "api.png", "PNG", optimize=True)


def make_traces():
    img, draw = _new_canvas()
    draw_header(draw)
    sb_w = 0
    draw.rectangle((0, 40, W, H), fill=BG_SURFACE)
    # Top bar: trace meta
    pad = 30
    y = 70
    draw.text((pad, y), "Langfuse trace · strata.briefing", fill=INK, font=_font(16, bold=True))
    draw.text((pad, y + 22), "trace_id: 7a4c…b912   ·   tags: BTCUSDT, 1h, v1   ·   duration: 4.82s",
               fill=INK_DIM, font=_font(11, mono=False))

    spans = [
        ("data_stats",         0.000, 0.012, INK_DIM),
        ("structure_narrator", 0.013, 1.612, UP),
        ("wyckoff_classifier", 1.630, 2.840, ACCENT),
        ("risk_reviewer",      2.860, 3.910, AMBER),
        ("formatter",          3.930, 4.820, ACCENT_2),
    ]
    max_t = 5.0
    chart_x0, chart_x1 = pad, W - pad
    chart_y0 = y + 60
    row_h = 60

    # Axis
    draw.line((chart_x0, chart_y0 - 10, chart_x1, chart_y0 - 10), fill=BORDER, width=1)
    for tick in (0, 1, 2, 3, 4, 5):
        tx = chart_x0 + int((tick / max_t) * (chart_x1 - chart_x0))
        draw.line((tx, chart_y0 - 15, tx, chart_y0 - 5), fill=INK_DIM, width=1)
        draw.text((tx - 8, chart_y0 - 30), f"{tick}.0s", fill=INK_DIM, font=_font(10, mono=False))

    for i, (label, start, end, color) in enumerate(spans):
        ry = chart_y0 + i * row_h
        draw.text((pad, ry + 6), label, fill=INK, font=_font(12, bold=True))
        bx0 = chart_x0 + int((start / max_t) * (chart_x1 - chart_x0)) + 200
        bx1 = chart_x0 + int((end / max_t) * (chart_x1 - chart_x0)) + 200
        rounded_rect(draw, (bx0, ry + 4, bx1, ry + 32), fill=(*color, 70), radius=3, outline=color)
        draw.text((bx0 + 8, ry + 9), f"{(end - start) * 1000:.0f}ms", fill=INK, font=_font(11, bold=True))
        # Per-span detail
        if label != "data_stats":
            draw.text((pad, ry + 28), f"  tokens in=… out=…  ·  model gpt-4o-mini  ·  cost $0.001x",
                       fill=INK_DIM, font=_font(10, mono=False))

    # Footer summary
    draw.text((pad, H - 60), "5 LLM spans · 4 OpenAI calls · prompt v1 · iterations 1",
               fill=INK_DIM, font=_font(11, mono=False))
    draw.text((pad, H - 42), "request_id 7a4c…b912 · returned 312 chars markdown",
               fill=INK_DIM, font=_font(11, mono=False))

    img.save(OUT_DIR / "traces.png", "PNG", optimize=True)


def main():
    print(f"Generating screenshots under {OUT_DIR}…")
    make_workspace()
    make_wyckoff()
    make_chat()
    make_backtest()
    make_api()
    make_traces()
    print("Done.")


if __name__ == "__main__":
    main()
