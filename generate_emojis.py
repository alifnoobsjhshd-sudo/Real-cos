#!/usr/bin/env python3
"""
Emoji generator for Zyrox X bot — v3.
#FFD700 yellow rounded-square background, 4× supersampled smooth edges,
carved depth effect, thin black outline on every icon, bold modern white symbols.
Run: python generate_emojis.py
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import math

# ── Output config ─────────────────────────────────────────────────────────────
SIZE = 128
S    = 4          # background supersample scale
R    = SIZE * S   # 512 px render size
CX = CY = SIZE // 2
OUT  = "assets/emojis"
FONT = "utils/arial.ttf"

# ── Colors ────────────────────────────────────────────────────────────────────
BG     = (72,  72,  72)    # dark gray
SHADE  = (42,  42,  42)    # very dark shadow
HILITE = (105, 105, 105)   # slightly lighter edge highlight
WHITE  = (255, 255, 255)
HOLE   = BG
GOLD   = HOLE

os.makedirs(OUT, exist_ok=True)


# ── Background (4× supersampled) ──────────────────────────────────────────────

def _make_bg() -> Image.Image:
    bg = Image.new("RGBA", (R, R), (0, 0, 0, 0))
    d  = ImageDraw.Draw(bg)
    radius = 22 * S
    so, pad, hi = 2 * S, 3 * S, 2 * S
    d.rounded_rectangle([pad + so, pad + so, R - pad, R - pad],
                        radius=radius, fill=(*SHADE, 230))
    d.rounded_rectangle([pad, pad, R - pad - so, R - pad - so],
                        radius=radius, fill=(*BG, 255))
    d.rounded_rectangle([pad + hi, pad + hi, R - pad - so - hi, R - pad - so - hi],
                        radius=radius - hi, outline=(*HILITE, 155), width=hi)
    return bg.resize((SIZE, SIZE), Image.LANCZOS)


# ── Outline effect ────────────────────────────────────────────────────────────

def _add_outline(icon: Image.Image, width: int = 3) -> Image.Image:
    """Dilate alpha → paint dark under icon → gives a crisp black outline."""
    alpha = icon.split()[3]
    for _ in range(width):
        alpha = alpha.filter(ImageFilter.MaxFilter(3))
    solid = Image.new("RGBA", icon.size, (8, 8, 8, 215))
    solid.putalpha(alpha)
    result = Image.new("RGBA", icon.size, (0, 0, 0, 0))
    result.alpha_composite(solid)
    result.alpha_composite(icon)
    return result


# ── Canvas / save ─────────────────────────────────────────────────────────────

def canvas():
    bg   = _make_bg()
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return bg, icon, ImageDraw.Draw(icon)


def save(bg: Image.Image, icon: Image.Image, name: str):
    bg.alpha_composite(_add_outline(icon))
    bg.save(f"{OUT}/{name}.png", "PNG")


def make(name: str, draw_fn):
    bg, icon, d = canvas()
    draw_fn(d)
    save(bg, icon, name)
    print(f"  ✓ {name}.png")


# ── Font / text ───────────────────────────────────────────────────────────────

def font(sz: int):
    try:    return ImageFont.truetype(FONT, sz)
    except: return ImageFont.load_default()


def ctext(d, text, sz, color=WHITE, dy=0):
    f  = font(sz)
    bb = d.textbbox((0, 0), text, font=f)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((SIZE - w) // 2 - bb[0], (SIZE - h) // 2 - bb[1] + dy), text, fill=color, font=f)


def ctext_at(d, text, sz, x, y, color=GOLD):
    f  = font(sz)
    bb = d.textbbox((0, 0), text, font=f)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text((x - w // 2 - bb[0], y - h // 2 - bb[1]), text, fill=color, font=f)


# ── Draw functions (all at 128 × 128 coordinate space) ───────────────────────

def draw_checkmark(d, thick=8, pad=20):
    d.line([(pad, CY + 2), (CX - 5, SIZE - pad - 6), (SIZE - pad, pad + 6)],
           fill=WHITE, width=thick)


def draw_thick_check(d, pad=16):
    draw_checkmark(d, thick=12, pad=pad)


def draw_circle_check(d, pad=14):
    d.ellipse([pad, pad, SIZE - pad, SIZE - pad], outline=WHITE, width=8)
    draw_checkmark(d, thick=8, pad=28)


def draw_shield_check(d, pad=14):
    _shield_fill(d, pad)
    d.line([(CX - 14, CY), (CX - 2, CY + 14), (CX + 16, CY - 14)], fill=GOLD, width=6)


def draw_x(d, pad=18, thick=10):
    d.line([(pad, pad), (SIZE - pad, SIZE - pad)], fill=WHITE, width=thick)
    d.line([(SIZE - pad, pad), (pad, SIZE - pad)], fill=WHITE, width=thick)


def draw_circle_x(d, pad=12):
    d.ellipse([pad, pad, SIZE - pad, SIZE - pad], outline=WHITE, width=7)
    draw_x(d, pad=30, thick=8)


def draw_ban_circle(d, pad=12):
    d.ellipse([pad, pad, SIZE - pad, SIZE - pad], outline=WHITE, width=9)
    d.line([(pad + 14, SIZE - pad - 14), (SIZE - pad - 14, pad + 14)], fill=WHITE, width=9)


def draw_warning_triangle(d, pad=12, fill=True):
    pts = [(CX, pad + 2), (pad, SIZE - pad - 4), (SIZE - pad, SIZE - pad - 4)]
    if fill:
        d.polygon(pts, fill=WHITE)
        d.rectangle([CX - 5, CY - 2, CX + 5, CY + 16], fill=GOLD)
        d.ellipse([CX - 5, CY + 20, CX + 5, CY + 30], fill=GOLD)
    else:
        d.polygon(pts, outline=WHITE, width=8)


def draw_warning_square(d, pad=14):
    d.rectangle([pad, pad, SIZE - pad, SIZE - pad], outline=WHITE, width=7)
    ctext(d, "!", 58, dy=2)


def draw_octagon_exclaim(d, pad=14):
    a = pad + 10
    pts = [(a, pad), (SIZE - a, pad), (SIZE - pad, a), (SIZE - pad, SIZE - a),
           (SIZE - a, SIZE - pad), (a, SIZE - pad), (pad, SIZE - a), (pad, a)]
    d.polygon(pts, outline=WHITE, width=7)
    ctext(d, "!", 52)


def draw_toggle_on(d, pad=18):
    d.rounded_rectangle([pad, CY - 22, SIZE - pad, CY + 22], radius=22, outline=WHITE, width=7)
    d.ellipse([SIZE - pad - 42, CY - 18, SIZE - pad - 6, CY + 18], fill=WHITE)


def draw_toggle_off(d, pad=18):
    d.rounded_rectangle([pad, CY - 22, SIZE - pad, CY + 22], radius=22, outline=WHITE, width=7)
    d.ellipse([pad + 6, CY - 18, pad + 42, CY + 18], fill=WHITE)


def draw_new_badge(d, pad=14):
    d.rounded_rectangle([pad, CY - 24, SIZE - pad, CY + 24], radius=8, fill=WHITE)
    ctext(d, "NEW", 34, color=GOLD)


# ── Navigation ────────────────────────────────────────────────────────────────

def draw_arrow_right(d, pad=16, thick=10):
    my = CY
    d.line([(pad, my), (SIZE - pad - 14, my)], fill=WHITE, width=thick)
    d.polygon([(SIZE - pad - 14, my - 18), (SIZE - pad, my),
               (SIZE - pad - 14, my + 18)], fill=WHITE)


def draw_arrow_left(d, pad=16, thick=10):
    """← single left arrow — used for 'previous page' / back."""
    my = CY
    d.line([(pad + 14, my), (SIZE - pad, my)], fill=WHITE, width=thick)
    d.polygon([(pad + 14, my - 18), (pad, my), (pad + 14, my + 18)], fill=WHITE)


def draw_skip_to_end(d, pad=16):
    """⏭ skip to end — two right triangles + right bar."""
    for ox in [-26, -4]:
        d.polygon([(CX + ox, CY - 28), (CX + ox + 22, CY),
                   (CX + ox, CY + 28)], fill=WHITE)
    d.line([(SIZE - pad - 8, pad + 4), (SIZE - pad - 8, SIZE - pad - 4)],
           fill=WHITE, width=9)


def draw_skip_to_start(d, pad=16):
    """⏮ skip to start — left bar + two left triangles."""
    d.line([(pad + 8, pad + 4), (pad + 8, SIZE - pad - 4)],
           fill=WHITE, width=9)
    for ox in [4, 26]:
        d.polygon([(CX - ox, CY - 28), (CX - ox - 22, CY),
                   (CX - ox, CY + 28)], fill=WHITE)


def draw_skip_fwd(d, pad=16):
    """⏭ skip forward — identical to skip_to_end."""
    draw_skip_to_end(d, pad)


def draw_double_arrow_right(d, pad=16):
    my = CY
    d.line([(pad, my), (CX - 4, my)], fill=WHITE, width=8)
    d.polygon([(CX - 4, my - 15), (CX + 10, my), (CX - 4, my + 15)], fill=WHITE)
    d.line([(CX + 12, my), (SIZE - pad - 12, my)], fill=WHITE, width=8)
    d.polygon([(SIZE - pad - 12, my - 15), (SIZE - pad, my),
               (SIZE - pad - 12, my + 15)], fill=WHITE)


def draw_diag_arrow(d, pad=20):
    d.line([(pad, SIZE - pad), (SIZE - pad, pad)], fill=WHITE, width=8)
    tip = SIZE - pad
    d.polygon([(tip - 20, pad), (tip, pad), (tip, pad + 20)], fill=WHITE)


def draw_max_arrow(d, pad=16):
    draw_diag_arrow(d, pad)
    d.line([(SIZE - pad - 18, pad), (SIZE - pad, pad)], fill=WHITE, width=7)
    d.line([(SIZE - pad, pad), (SIZE - pad, pad + 18)], fill=WHITE, width=7)


def draw_plus(d, pad=20, thick=11):
    d.line([(CX, pad), (CX, SIZE - pad)], fill=WHITE, width=thick)
    d.line([(pad, CY), (SIZE - pad, CY)], fill=WHITE, width=thick)


def draw_plus_circle(d, pad=14):
    d.ellipse([pad, pad, SIZE - pad, SIZE - pad], outline=WHITE, width=7)
    draw_plus(d, pad=32, thick=9)


# ── Loading ───────────────────────────────────────────────────────────────────

def draw_loading_spinner(d, pad=16):
    r = (SIZE - 2 * pad) // 2
    for i in range(8):
        a = i * 45 - 90
        d.arc([CX - r, CY - r, CX + r, CY + r], start=a, end=a + 36, fill=WHITE, width=10)


def draw_dot(d, pad=26):
    d.ellipse([pad, pad, SIZE - pad, SIZE - pad], fill=WHITE)


# ── Interface ─────────────────────────────────────────────────────────────────

def draw_hashtag(d, pad=20, thick=8):
    y1, y2 = pad + 24, SIZE - pad - 24
    d.line([(pad, y1), (SIZE - pad, y1)], fill=WHITE, width=thick)
    d.line([(pad, y2), (SIZE - pad, y2)], fill=WHITE, width=thick)
    d.line([(CX - 14, pad), (CX - 14, SIZE - pad)], fill=WHITE, width=thick)
    d.line([(CX + 14, pad), (CX + 14, SIZE - pad)], fill=WHITE, width=thick)


def draw_house(d, pad=16):
    d.polygon([(pad, CY + 6), (CX, pad), (SIZE - pad, CY + 6)], fill=WHITE)
    d.rectangle([pad + 14, CY + 6, SIZE - pad - 14, SIZE - pad], fill=WHITE)
    d.rectangle([CX - 10, SIZE - pad - 26, CX + 10, SIZE - pad], fill=GOLD)


def draw_magnifier(d, pad=16):
    r = 30
    d.ellipse([pad, pad, pad + r * 2, pad + r * 2], outline=WHITE, width=8)
    ex, ey = pad + r * 2 - 6, pad + r * 2 - 6
    d.line([(ex, ey), (SIZE - pad, SIZE - pad)], fill=WHITE, width=10)


def draw_lock(d, pad=18):
    bx1, by1, bx2, by2 = pad + 6, CY, SIZE - pad - 6, SIZE - pad
    d.rounded_rectangle([bx1, by1, bx2, by2], radius=6, outline=WHITE, width=7)
    d.ellipse([CX - 5, CY + 10, CX + 5, CY + 22], fill=GOLD)
    sp = pad + 18
    d.arc([sp, pad, SIZE - sp, CY + 10], start=200, end=340, fill=WHITE, width=7)


def draw_unlock(d, pad=18):
    bx1, by1, bx2, by2 = pad + 6, CY, SIZE - pad - 6, SIZE - pad
    d.rounded_rectangle([bx1, by1, bx2, by2], radius=6, outline=WHITE, width=7)
    d.ellipse([CX - 5, CY + 10, CX + 5, CY + 22], fill=GOLD)
    sp = pad + 18
    d.arc([sp, pad - 14, SIZE - sp, CY - 4], start=200, end=340, fill=WHITE, width=7)


def draw_couch(d, pad=16):
    """🛋️ sofa / couch — Waiting Room."""
    # Back rest (tall top bar)
    d.rounded_rectangle([pad, pad + 8, SIZE - pad, CY + 4], radius=8, fill=WHITE)
    # Left armrest
    d.rounded_rectangle([pad, CY - 2, pad + 16, SIZE - pad - 10], radius=6, fill=WHITE)
    # Right armrest
    d.rounded_rectangle([SIZE - pad - 16, CY - 2, SIZE - pad, SIZE - pad - 10], radius=6, fill=WHITE)
    # Seat cushion (between arms)
    d.rounded_rectangle([pad + 14, CY + 4, SIZE - pad - 14, SIZE - pad - 10], radius=5, fill=WHITE)
    # Left leg
    d.rectangle([pad + 4, SIZE - pad - 10, pad + 10, SIZE - pad], fill=WHITE)
    # Right leg
    d.rectangle([SIZE - pad - 10, SIZE - pad - 10, SIZE - pad - 4, SIZE - pad], fill=WHITE)


def draw_trash(d, pad=18):
    bx1, by1, bx2, by2 = pad + 4, CY - 6, SIZE - pad - 4, SIZE - pad
    d.rectangle([bx1, by1, bx2, by2], outline=WHITE, width=6)
    for x in [bx1 + 13, CX, bx2 - 13]:
        d.line([(x, by1 + 9), (x, by2 - 9)], fill=WHITE, width=5)
    d.rectangle([pad + 12, pad + 12, SIZE - pad - 12, CY - 6], outline=WHITE, width=6)
    d.line([(pad + 4, pad + 12), (SIZE - pad - 4, pad + 12)], fill=WHITE, width=6)
    d.rectangle([CX - 10, pad + 4, CX + 10, pad + 13], outline=WHITE, width=5)


# ── People ────────────────────────────────────────────────────────────────────

def draw_person(d, pad=18):
    d.ellipse([CX - 20, pad, CX + 20, pad + 40], fill=WHITE)
    d.ellipse([CX - 28, CY + 2, CX + 28, SIZE - pad], fill=WHITE)


def draw_people(d, pad=12):
    for ox in [-20, 20]:
        d.ellipse([CX + ox - 15, pad + 4, CX + ox + 15, pad + 34], fill=WHITE)
        d.ellipse([CX + ox - 20, CY + 2, CX + ox + 20, SIZE - pad], fill=WHITE)


def draw_crown(d, pad=16):
    base_y = SIZE - pad - 8
    pts = [(pad, base_y), (pad, CY - 4), (CX - 20, CY + 14),
           (CX, pad + 4), (CX + 20, CY + 14), (SIZE - pad, CY - 4), (SIZE - pad, base_y)]
    d.polygon(pts, fill=WHITE)
    d.rectangle([pad, base_y - 6, SIZE - pad, base_y + 4], fill=WHITE)
    for x in [pad + 14, CX, SIZE - pad - 14]:
        d.ellipse([x - 7, base_y - 5, x + 7, base_y + 5], fill=GOLD)


def draw_staff_badge(d, pad=16):
    draw_star5(d, r_out=42, r_in=18)
    d.ellipse([CX - 11, CY - 11, CX + 11, CY + 11], fill=GOLD)


def draw_headmod(d, pad=14):
    draw_crown(d, pad)
    d.ellipse([pad + 16, CY + 4, SIZE - pad - 16, SIZE - pad], fill=WHITE)


def draw_handshake(d, pad=16):
    d.rounded_rectangle([pad, CY - 15, CX + 6, CY + 15], radius=11, fill=WHITE)
    d.rounded_rectangle([CX - 6, CY - 15, SIZE - pad, CY + 15], radius=11, fill=WHITE)
    d.ellipse([CX - 13, CY - 11, CX + 13, CY + 11], fill=GOLD)
    for x, y in [(pad + 14, CY - 30), (SIZE - pad - 14, CY + 30)]:
        d.line([(x, CY), (x, y)], fill=WHITE, width=9)


# ── Symbols ───────────────────────────────────────────────────────────────────

def draw_at_symbol(d, pad=14):
    r = (SIZE - 2 * pad) // 2
    d.ellipse([pad, pad, SIZE - pad, SIZE - pad], outline=WHITE, width=7)
    ir = r // 2
    d.ellipse([CX - ir, CY - ir, CX + ir, CY + ir], outline=WHITE, width=6)
    d.line([(CX + ir, CY), (CX + ir, pad + 8)], fill=WHITE, width=6)
    d.arc([CX - ir + 2, CY - ir + 2, CX + ir + 18, CY + ir - 2], start=330, end=30, fill=WHITE, width=6)


def draw_star5(d, cx=None, cy=None, r_out=46, r_in=20, thick=0):
    cx = cx if cx is not None else CX
    cy = cy if cy is not None else CY
    pts = []
    for i in range(10):
        angle = math.radians(i * 36 - 90)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    if thick:
        d.polygon(pts, outline=WHITE, width=thick)
    else:
        d.polygon(pts, fill=WHITE)


def draw_sparkle(d, pad=14):
    for angle_deg in [0, 45, 90, 135, 180, 225, 270, 315]:
        angle = math.radians(angle_deg)
        r = 46 if angle_deg % 90 == 0 else 30
        lw = 7 if angle_deg % 90 == 0 else 5
        ex = CX + int(r * math.cos(angle))
        ey = CY + int(r * math.sin(angle))
        d.line([(CX, CY), (ex, ey)], fill=WHITE, width=lw)
    d.ellipse([CX - 9, CY - 9, CX + 9, CY + 9], fill=WHITE)


def draw_heart(d, pad=18, thick=0):
    w = SIZE - 2 * pad
    h = int(w * 0.85)
    y0 = CY - h // 2 + 4
    lx = pad + w // 4
    by = y0 + h
    kw = dict(fill=WHITE) if not thick else dict(outline=WHITE, width=thick)
    d.ellipse([pad, y0, lx * 2, y0 + h // 2 + 4], **kw)
    d.ellipse([lx * 2 - w // 2, y0, SIZE - pad, y0 + h // 2 + 4], **kw)
    d.polygon([(pad + 2, y0 + h // 3), (CX, by + 8), (SIZE - pad - 2, y0 + h // 3)], fill=WHITE)


def draw_heart3(d, pad=16):
    for ox, oy in [(-22, -4), (22, -4), (0, 12)]:
        cx2, cy2 = CX + ox, CY + oy
        w = 20
        d.ellipse([cx2 - w, cy2 - w // 2, cx2 + w, cy2 + w // 2 + 6], fill=WHITE)
        d.ellipse([cx2, cy2 - w // 2, cx2 + w * 2, cy2 + w // 2 + 6], fill=WHITE)


def draw_circle_full(d, pad=18):
    d.ellipse([pad, pad, SIZE - pad, SIZE - pad], fill=WHITE)


def draw_circle_outline(d, pad=18):
    d.ellipse([pad, pad, SIZE - pad, SIZE - pad], outline=WHITE, width=9)


def draw_circle_minus(d, pad=14):
    d.ellipse([pad, pad, SIZE - pad, SIZE - pad], outline=WHITE, width=7)
    d.line([(pad + 18, CY), (SIZE - pad - 18, CY)], fill=WHITE, width=8)


# ── Actions ───────────────────────────────────────────────────────────────────

def draw_pushpin(d, pad=14):
    d.ellipse([pad + 8, pad, SIZE - pad - 8, CY + 8], fill=WHITE)
    d.rectangle([CX - 9, CY + 8, CX + 9, SIZE - pad - 16], fill=WHITE)
    d.line([(CX, SIZE - pad - 16), (CX + 9, SIZE - pad)], fill=WHITE, width=6)


def draw_sword(d, pad=14):
    d.line([(pad + 8, SIZE - pad), (SIZE - pad - 8, pad)], fill=WHITE, width=8)
    cx2 = pad + 8 + (SIZE - 2 * pad - 16) // 3
    cy2 = SIZE - pad - (SIZE - 2 * pad) // 3
    d.line([(cx2 - 15, cy2 - 8), (cx2 + 15, cy2 + 8)], fill=WHITE, width=9)
    d.ellipse([SIZE - pad - 14, pad + 2, SIZE - pad, pad + 16], fill=WHITE)


def draw_message(d, pad=16):
    d.rounded_rectangle([pad, pad, SIZE - pad, SIZE - pad - 18], radius=10, fill=WHITE)
    d.polygon([(pad + 16, SIZE - pad - 18), (pad + 8, SIZE - pad), (pad + 36, SIZE - pad - 18)], fill=WHITE)
    d.rectangle([pad + 14, pad + 16, SIZE - pad - 14, pad + 24], fill=GOLD)
    d.rectangle([pad + 14, CY - 4, SIZE - pad - 28, CY + 4], fill=GOLD)


def draw_puzzle(d, pad=16):
    # Four quadrants
    d.rectangle([pad, pad, CX - 2, CY - 2], fill=WHITE)
    d.rectangle([CX + 2, CY + 2, SIZE - pad, SIZE - pad], fill=WHITE)
    d.rectangle([pad, CY + 2, CX - 2, SIZE - pad], fill=WHITE)
    d.rectangle([CX + 2, pad, SIZE - pad, CY - 2], fill=WHITE)
    # Connectors (bumps)
    d.ellipse([CX - 12, CY - 24, CX + 12, CY - 2], fill=WHITE)
    d.ellipse([CX + 2, CY - 12, CX + 24, CY + 12], fill=GOLD)
    d.ellipse([CX - 12, CY + 2, CX + 12, CY + 24], fill=GOLD)
    d.ellipse([CX - 24, CY - 12, CX - 2, CY + 12], fill=WHITE)


def draw_gear(d, pad=14):
    teeth, r_out, r_in, r_hole = 8, 46, 36, 15
    pts = []
    for i in range(teeth * 2):
        angle = math.radians(i * 360 / (teeth * 2) - 90)
        r = r_out if i % 2 == 0 else r_in
        pts.append((CX + r * math.cos(angle), CY + r * math.sin(angle)))
    d.polygon(pts, fill=WHITE)
    d.ellipse([CX - r_hole, CY - r_hole, CX + r_hole, CY + r_hole], fill=GOLD)


def draw_wrench(d, pad=16):
    angle = 45
    for a in [angle, angle + 180]:
        r2 = math.radians(a)
        ex = CX + int(46 * math.cos(r2))
        ey = CY + int(46 * math.sin(r2))
        d.line([(CX, CY), (ex, ey)], fill=WHITE, width=12)
    d.ellipse([CX - 13, CY - 13, CX + 13, CY + 13], fill=GOLD, outline=WHITE, width=6)
    sx = CX + int(28 * math.cos(math.radians(angle)))
    sy = CY + int(28 * math.sin(math.radians(angle)))
    d.ellipse([sx - 11, sy - 11, sx + 11, sy + 11], outline=WHITE, width=6)


def draw_antenna(d, pad=16):
    d.line([(CX, SIZE - pad), (CX, CY - 8)], fill=WHITE, width=8)
    for i, a in enumerate([40, 28, 16]):
        d.arc([CX - a, CY - 20 - a, CX + a, CY - 20 + a],
              start=200, end=340, fill=WHITE, width=6 - i)
    d.ellipse([CX - 7, CY - 30, CX + 7, CY - 18], fill=WHITE)


def draw_antenna_broadcast(d, pad=14):
    d.line([(CX, SIZE - pad - 4), (CX, CY + 6)], fill=WHITE, width=8)
    d.rectangle([CX - 22, CY - 6, CX + 22, CY + 6], fill=WHITE)
    for a in [22, 36, 50]:
        d.arc([CX - a, CY - a - 20, CX + a, CY + a - 20], start=200, end=340, fill=WHITE, width=6)


def _shield_fill(d, pad=14):
    pts = [(CX, SIZE - pad - 4),
           (pad + 4, CY - 10), (pad + 4, pad),
           (SIZE - pad - 4, pad), (SIZE - pad - 4, CY - 10)]
    d.polygon(pts, fill=WHITE)


def draw_shield_heart(d, pad=14):
    _shield_fill(d, pad)
    hw = 18
    hx, hy = CX, CY - 4
    d.ellipse([hx - hw, hy - hw // 2, hx, hy + hw // 2 + 2], fill=GOLD)
    d.ellipse([hx, hy - hw // 2, hx + hw, hy + hw // 2 + 2], fill=GOLD)
    d.polygon([(hx - hw + 2, hy + hw // 3), (hx, hy + hw + 6), (hx + hw - 2, hy + hw // 3)], fill=GOLD)


def draw_cloud(d, pad=14):
    cy = CY + 6
    r1 = 30
    d.ellipse([CX - r1, cy - r1, CX + r1, cy + r1], fill=WHITE)
    d.ellipse([pad, cy - 20, pad + 44, cy + 20], fill=WHITE)
    d.ellipse([SIZE - pad - 44, cy - 20, SIZE - pad, cy + 20], fill=WHITE)
    d.ellipse([pad + 20, cy - r1 - 8, CX + 12, cy + 10], fill=WHITE)
    d.rectangle([pad, cy, SIZE - pad, cy + r1], fill=WHITE)


def draw_rocket(d, pad=16):
    d.polygon([(CX, pad), (CX + 22, CY + 18), (CX + 22, SIZE - pad - 8),
               (CX - 22, SIZE - pad - 8), (CX - 22, CY + 18)], fill=WHITE)
    d.polygon([(CX, pad), (CX - 22, CY + 8), (CX, CY + 18)], fill=WHITE)
    d.polygon([(CX, pad), (CX + 22, CY + 8), (CX, CY + 18)], fill=WHITE)
    d.ellipse([CX - 9, CY - 12, CX + 9, CY + 6], fill=GOLD)
    d.polygon([(CX - 16, SIZE - pad - 8), (CX - 28, SIZE - pad + 8),
               (CX + 28, SIZE - pad + 8), (CX + 16, SIZE - pad - 8)], fill=WHITE)


def draw_robot(d, pad=14):
    # Head
    d.rounded_rectangle([pad + 12, pad + 14, SIZE - pad - 12, CY + 2], radius=8, fill=WHITE)
    # Eyes
    for ex in [pad + 28, SIZE - pad - 28]:
        d.ellipse([ex - 9, CY - 14, ex + 9, CY + 2], fill=GOLD)
    # Mouth
    d.line([(pad + 26, CY + 14), (SIZE - pad - 26, CY + 14)], fill=GOLD, width=5)
    # Neck/Body
    d.rectangle([CX - 9, CY + 2, CX + 9, CY + 14], fill=WHITE)
    d.rounded_rectangle([pad + 10, CY + 14, SIZE - pad - 10, SIZE - pad], radius=6, fill=WHITE)
    # Antenna
    d.line([(CX, pad + 14), (CX, pad + 4)], fill=WHITE, width=6)
    d.ellipse([CX - 7, pad - 2, CX + 7, pad + 10], fill=WHITE)
    # Buttons on body
    for bx in [pad + 24, CX, SIZE - pad - 24]:
        d.ellipse([bx - 5, CY + 22, bx + 5, CY + 32], fill=GOLD)


def draw_wifi(d, pad=16):
    cy_base = CY + 24
    for i, r in enumerate([50, 34, 18]):
        d.arc([CX - r, cy_base - r, CX + r, cy_base + r],
              start=210, end=330, fill=WHITE, width=8 if i == 2 else 7)
    d.ellipse([CX - 8, cy_base - 8, CX + 8, cy_base + 8], fill=WHITE)


# ── Time ──────────────────────────────────────────────────────────────────────

def draw_clock(d, pad=14):
    d.ellipse([pad, pad, SIZE - pad, SIZE - pad], outline=WHITE, width=7)
    d.line([(CX, CY), (CX, pad + 18)], fill=WHITE, width=6)
    d.line([(CX, CY), (CX + 22, CY + 14)], fill=WHITE, width=6)
    d.ellipse([CX - 6, CY - 6, CX + 6, CY + 6], fill=WHITE)


def draw_stopwatch(d, pad=16):
    d.ellipse([pad, pad + 14, SIZE - pad, SIZE - pad], outline=WHITE, width=7)
    d.line([(CX, CY + 8), (CX, pad + 28)], fill=WHITE, width=6)
    d.line([(CX, CY + 8), (CX + 20, CY + 20)], fill=WHITE, width=6)
    d.rectangle([CX - 10, pad + 4, CX + 10, pad + 14], fill=WHITE)
    d.line([(CX - 14, pad + 8), (CX + 14, pad + 8)], fill=WHITE, width=7)


def draw_uptime_chart(d, pad=16):
    d.rectangle([pad, CY, SIZE - pad, SIZE - pad], outline=WHITE, width=6)
    pts = [(pad + 8, SIZE - pad - 8), (pad + 24, CY + 26), (pad + 44, SIZE - pad - 24),
           (CX + 12, CY + 12), (SIZE - pad - 8, CY + 6)]
    d.line(pts, fill=WHITE, width=6)


# ── Tech ──────────────────────────────────────────────────────────────────────

def draw_globe(d, pad=14):
    d.ellipse([pad, pad, SIZE - pad, SIZE - pad], outline=WHITE, width=7)
    d.line([(pad, CY), (SIZE - pad, CY)], fill=WHITE, width=6)
    d.arc([pad + 18, pad, SIZE - pad - 18, SIZE - pad], start=0, end=360, fill=WHITE, width=6)
    d.line([(CX, pad), (CX, SIZE - pad)], fill=WHITE, width=6)


def draw_ai_chip(d, pad=16):
    d.rounded_rectangle([pad + 12, pad + 12, SIZE - pad - 12, SIZE - pad - 12], radius=6, fill=WHITE)
    for y in [CY - 18, CY + 18]:
        d.rectangle([pad, y - 6, pad + 12, y + 6], fill=WHITE)
        d.rectangle([SIZE - pad - 12, y - 6, SIZE - pad, y + 6], fill=WHITE)
    for x in [CX - 18, CX + 18]:
        d.rectangle([x - 6, pad, x + 6, pad + 12], fill=WHITE)
        d.rectangle([x - 6, SIZE - pad - 12, x + 6, SIZE - pad], fill=WHITE)
    ctext(d, "AI", 32, color=GOLD)


def draw_hammer(d, pad=14):
    d.rectangle([pad + 10, pad + 8, CX + 18, CY - 4], fill=WHITE)
    d.line([(CX + 6, CY - 4), (SIZE - pad, SIZE - pad)], fill=WHITE, width=12)


def draw_connection(d, pad=16):
    d.ellipse([pad, CY - 15, pad + 28, CY + 15], fill=WHITE)
    d.ellipse([SIZE - pad - 28, CY - 15, SIZE - pad, CY + 15], fill=WHITE)
    d.line([(pad + 28, CY), (SIZE - pad - 28, CY)], fill=WHITE, width=8)
    d.ellipse([CX - 13, CY - 13, CX + 13, CY + 13], fill=GOLD, outline=WHITE, width=5)


def draw_link(d, pad=16):
    r = 14
    offset = 16
    d.arc([pad, CY - r - offset, pad + r * 2, CY + r - offset],
          start=90, end=270, fill=WHITE, width=8)
    d.arc([SIZE - pad - r * 2, CY - r + offset, SIZE - pad, CY + r + offset],
          start=270, end=90, fill=WHITE, width=8)
    d.line([(pad + r, CY - offset), (SIZE - pad - r, CY + offset)], fill=WHITE, width=8)


def draw_lightning(d, pad=16):
    pts = [(CX + 14, pad), (CX - 16, CY + 8), (CX + 6, CY + 8),
           (CX - 14, SIZE - pad), (CX + 24, CY - 4), (CX + 4, CY - 4)]
    d.polygon(pts, fill=WHITE)


def draw_lightning_multi(d, pad=16):
    for ox in [-16, 8]:
        pts = [(CX + ox + 10, pad), (CX + ox - 12, CY + 4), (CX + ox + 4, CY + 4),
               (CX + ox - 10, SIZE - pad), (CX + ox + 20, CY - 4), (CX + ox + 2, CY - 4)]
        d.polygon(pts, fill=WHITE)


def draw_code_brackets(d, pad=20):
    ctext(d, "</>", 46)


def draw_terminal(d, pad=18):
    d.rounded_rectangle([pad, pad, SIZE - pad, SIZE - pad], radius=6, outline=WHITE, width=6)
    d.line([(pad + 14, CY - 4), (pad + 34, CY + 14)], fill=WHITE, width=6)
    d.line([(pad + 14, CY + 14 + 6), (pad + 34, CY + 14)], fill=WHITE, width=6)
    d.line([(pad + 40, CY + 20), (pad + 60, CY + 20)], fill=WHITE, width=6)


# ── Features ──────────────────────────────────────────────────────────────────

def draw_gem(d, pad=16):
    top  = [(pad + 18, CY - 4), (CX - 18, pad + 12), (CX + 18, pad + 12), (SIZE - pad - 18, CY - 4)]
    d.polygon(top, fill=WHITE)
    d.polygon([(pad + 18, CY - 4), (CX, SIZE - pad - 6), (SIZE - pad - 18, CY - 4)], fill=WHITE)
    d.polygon([(CX - 18, pad + 12), (CX + 18, pad + 12), (CX, CY - 4)], fill=GOLD)


def draw_premium_badge(d, pad=14):
    draw_gem(d, pad)
    draw_star5(d, cx=CX, cy=CY - 4, r_out=20, r_in=9)


def draw_tada(d, pad=14):
    d.polygon([(pad + 8, SIZE - pad), (CX - 4, CY - 4), (pad + 32, SIZE - pad - 20)], fill=WHITE)
    for cx2, cy2, r in [(CX + 14, pad + 18, 11), (SIZE - pad - 10, CY - 14, 9),
                        (CX + 28, CY + 18, 7), (pad + 20, CY - 20, 8),
                        (SIZE - pad - 20, SIZE - pad - 24, 10)]:
        d.ellipse([cx2 - r, cy2 - r, cx2 + r, cy2 + r], fill=WHITE)
    d.line([(CX, pad), (CX + 6, pad + 20)], fill=WHITE, width=5)
    d.line([(SIZE - pad - 6, CY), (SIZE - pad - 24, CY + 12)], fill=WHITE, width=5)


def draw_gamepad(d, pad=16):
    d.rounded_rectangle([pad, CY - 24, SIZE - pad, CY + 24], radius=18, fill=WHITE)
    # D-pad
    d.line([(pad + 24, CY), (pad + 42, CY)], fill=GOLD, width=6)
    d.line([(pad + 33, CY - 9), (pad + 33, CY + 9)], fill=GOLD, width=6)
    # Buttons
    d.ellipse([SIZE - pad - 44, CY - 9, SIZE - pad - 30, CY + 9], fill=GOLD)
    d.ellipse([SIZE - pad - 28, CY - 9, SIZE - pad - 14, CY + 9], fill=GOLD)


def draw_ticket(d, pad=16):
    d.rounded_rectangle([pad, pad + 16, SIZE - pad, SIZE - pad - 16], radius=8, fill=WHITE)
    for y in [CY - 8, CY + 8]:
        d.ellipse([pad - 8, y - 7, pad + 8, y + 7], fill=GOLD)
        d.ellipse([SIZE - pad - 8, y - 7, SIZE - pad + 8, y + 7], fill=GOLD)
    d.line([(CX, pad + 22), (CX, SIZE - pad - 22)], fill=GOLD, width=5)


def draw_123(d, pad=18):
    ctext(d, "123", 38)


def draw_level_up(d, pad=16):
    draw_arrow_up(d, pad)
    d.line([(pad + 14, SIZE - pad - 4), (SIZE - pad - 14, SIZE - pad - 4)], fill=WHITE, width=8)
    d.line([(pad + 14, SIZE - pad - 14), (SIZE - pad - 14, SIZE - pad - 14)], fill=WHITE, width=6)


def draw_arrow_up(d, pad=16, thick=10):
    d.line([(CX, SIZE - pad), (CX, pad + 14)], fill=WHITE, width=thick)
    d.polygon([(CX - 18, pad + 14), (CX, pad), (CX + 18, pad + 14)], fill=WHITE)


def draw_leaf(d, pad=16):
    d.polygon([(CX, pad), (SIZE - pad, CY + 22), (CX + 4, SIZE - pad - 8)], fill=WHITE)
    d.ellipse([pad + 6, CY - 10, CX + 18, SIZE - pad - 4], fill=WHITE)
    d.line([(CX - 4, SIZE - pad - 4), (CX + 10, pad + 18)], fill=GOLD, width=5)


def draw_minecraft_creeper(d, pad=16):
    d.rectangle([pad + 10, pad, SIZE - pad - 10, SIZE - pad - 14], fill=WHITE)
    d.rectangle([pad, CY, SIZE - pad, CY + 28], fill=WHITE)
    for ex, ey in [(pad + 18, pad + 18), (SIZE - pad - 30, pad + 18)]:
        d.rectangle([ex, ey, ex + 16, ey + 16], fill=GOLD)
    d.rectangle([CX - 10, CY - 12, CX + 10, CY - 2], fill=GOLD)
    d.rectangle([CX - 18, CY - 2, CX - 8, CY + 12], fill=GOLD)
    d.rectangle([CX + 8, CY - 2, CX + 18, CY + 12], fill=GOLD)


def draw_folder(d, pad=16):
    d.rounded_rectangle([pad, CY - 16, SIZE - pad, SIZE - pad], radius=6, fill=WHITE)
    d.rounded_rectangle([pad, pad + 16, CX + 12, CY + 4], radius=6, fill=WHITE)


# ── Music ─────────────────────────────────────────────────────────────────────

def draw_music_note(d, pad=20):
    bx, by = CX - 8, pad + 16
    ey = SIZE - pad - 10
    d.ellipse([bx - 15, ey - 11, bx + 15, ey + 11], fill=WHITE)
    d.line([(bx + 15, by), (bx + 15, ey)], fill=WHITE, width=8)
    d.line([(bx + 15, by), (bx + 36, by - 12)], fill=WHITE, width=7)
    d.line([(bx + 36, by - 12), (bx + 36, ey - 20)], fill=WHITE, width=7)
    d.ellipse([bx + 22, ey - 32, bx + 50, ey - 10], fill=WHITE)


def draw_double_note(d, pad=18):
    for ox, oy in [(-16, 0), (8, -10)]:
        bx, by = CX + ox, pad + 20 + oy
        ey = SIZE - pad - 12 + oy
        d.ellipse([bx - 11, ey - 9, bx + 11, ey + 9], fill=WHITE)
        d.line([(bx + 11, by), (bx + 11, ey)], fill=WHITE, width=7)
    d.line([(CX - 5, pad + 20), (CX + 19, pad + 10)], fill=WHITE, width=7)


def draw_play_triangle(d, pad=20):
    d.polygon([(pad + 6, pad), (pad + 6, SIZE - pad), (SIZE - pad, CY)], fill=WHITE)


def draw_pause_bars(d, pad=22):
    bw = 17
    d.rectangle([pad + 2, pad, pad + 2 + bw, SIZE - pad], fill=WHITE)
    d.rectangle([SIZE - pad - 2 - bw, pad, SIZE - pad - 2, SIZE - pad], fill=WHITE)


def draw_stop_square(d, pad=22):
    d.rectangle([pad, pad, SIZE - pad, SIZE - pad], fill=WHITE)


def draw_rewind(d, pad=16):
    """⏮ skip to start — bar on left, two left-pointing triangles."""
    d.line([(pad + 8, pad + 4), (pad + 8, SIZE - pad - 4)], fill=WHITE, width=9)
    for ox in [4, 26]:
        d.polygon([(CX - ox, CY - 28), (CX - ox - 22, CY),
                   (CX - ox, CY + 28)], fill=WHITE)


def draw_replay(d, pad=16):
    """Circular replay arrow — single clockwise arc with arrowhead (restart current track)."""
    r = 34
    # Draw a ~300° clockwise arc, gap at upper-right for arrowhead
    # PIL arc: start=80, end=40 → clockwise from 80° to 40° = 320° arc
    d.arc([CX - r, CY - r, CX + r, CY + r], start=80, end=40, fill=WHITE, width=9)
    # Arrowhead at the END of the arc (at 40° in PIL convention)
    # At 40°: ex = CX + r*cos40°, ey = CY + r*sin40° (PIL y-down)
    ex = CX + int(r * math.cos(math.radians(40)))
    ey = CY + int(r * math.sin(math.radians(40)))
    # Clockwise tangent at 40°: direction (-sin40°, cos40°) in PIL (y-down) coords
    tx = -math.sin(math.radians(40))   # ≈ -0.643
    ty =  math.cos(math.radians(40))   # ≈  0.766 (downward component)
    # Perpendicular (radius direction): (cos40°, sin40°)
    px =  math.cos(math.radians(40))   # ≈  0.766
    py =  math.sin(math.radians(40))   # ≈  0.643
    sz, hw = 13, 9
    tip   = (ex + sz * tx,      ey + sz * ty)
    base1 = (ex + hw * px,      ey + hw * py)
    base2 = (ex - hw * px,      ey - hw * py)
    d.polygon([tip, base1, base2], fill=WHITE)


def draw_shuffle_arrows(d, pad=18):
    my1, my2 = CY - 18, CY + 18
    d.line([(pad, my1), (CX + 14, my1)], fill=WHITE, width=7)
    d.polygon([(CX + 14, my1 - 12), (CX + 28, my1), (CX + 14, my1 + 12)], fill=WHITE)
    d.line([(pad, my2), (SIZE - pad, my2 - 24)], fill=WHITE, width=7)
    d.polygon([(SIZE - pad - 15, my2 - 34), (SIZE - pad + 2, my2 - 24),
               (SIZE - pad - 15, my2 - 14)], fill=WHITE)


def draw_speaker(d, pad=16):
    """🔊 speaker with sound waves — for zunmute."""
    bx = pad + 6
    d.polygon([(bx, CY - 16), (bx + 20, CY - 28),
               (bx + 20, CY + 28), (bx, CY + 16)], fill=WHITE)
    cx_base = bx + 20
    for r in [22, 36]:
        d.arc([cx_base - r, CY - r, cx_base + r, CY + r],
              start=325, end=35, fill=WHITE, width=8)


def draw_speaker_muted(d, pad=16):
    """🔇 speaker with X — for zmute."""
    bx = pad + 4
    d.polygon([(bx, CY - 16), (bx + 20, CY - 26),
               (bx + 20, CY + 26), (bx, CY + 16)], fill=WHITE)
    xp = bx + 30
    d.line([(xp, CY - 22), (xp + 28, CY + 22)], fill=WHITE, width=9)
    d.line([(xp + 28, CY - 22), (xp, CY + 22)], fill=WHITE, width=9)


def draw_soundcloud(d, pad=16):
    d.arc([CX, CY - 24, CX + 50, CY + 24], start=240, end=120, fill=WHITE, width=9)
    d.arc([CX - 16, CY - 18, CX + 34, CY + 18], start=240, end=120, fill=WHITE, width=8)
    d.arc([CX - 30, CY - 12, CX + 20, CY + 12], start=250, end=110, fill=WHITE, width=7)
    d.arc([CX - 40, CY - 8, CX + 6, CY + 8], start=260, end=100, fill=WHITE, width=6)
    d.rectangle([pad + 4, CY, SIZE - pad, CY + 24], fill=WHITE)


def draw_yt_play(d, pad=14):
    d.rounded_rectangle([pad, CY - 32, SIZE - pad, CY + 32], radius=16, fill=WHITE)
    d.polygon([(CX - 14, CY - 20), (CX - 14, CY + 20), (CX + 24, CY)], fill=GOLD)


def draw_jiosaavn_j(d, pad=16):
    ctext(d, "J", 80)
    d.rectangle([pad + 10, SIZE - pad - 14, CX + 18, SIZE - pad - 6], fill=WHITE)


# ── Presence ──────────────────────────────────────────────────────────────────

def draw_moon(d, pad=16):
    d.ellipse([pad, pad, SIZE - pad, SIZE - pad], fill=WHITE)
    d.ellipse([pad + 18, pad, SIZE - pad + 4, SIZE - pad], fill=GOLD)


def draw_phone(d, pad=20):
    d.rounded_rectangle([pad + 8, pad, SIZE - pad - 8, SIZE - pad], radius=10, fill=WHITE)
    d.rounded_rectangle([pad + 16, pad + 10, SIZE - pad - 16, SIZE - pad - 10], radius=4, fill=GOLD)
    d.ellipse([CX - 6, SIZE - pad - 11, CX + 6, SIZE - pad - 1], fill=WHITE)


def draw_monitor(d, pad=14):
    d.rounded_rectangle([pad, pad + 8, SIZE - pad, SIZE - pad - 20], radius=6, fill=WHITE)
    d.rounded_rectangle([pad + 8, pad + 16, SIZE - pad - 8, SIZE - pad - 28], radius=4, fill=GOLD)
    d.rectangle([CX - 16, SIZE - pad - 20, CX + 16, SIZE - pad - 12], fill=WHITE)
    d.line([(CX - 22, SIZE - pad - 12), (CX + 22, SIZE - pad - 12)], fill=WHITE, width=6)


# ── Extra ─────────────────────────────────────────────────────────────────────

def draw_book(d, pad=14):
    d.rounded_rectangle([pad, pad, CX - 2, SIZE - pad], radius=4, fill=WHITE)
    d.rounded_rectangle([CX + 2, pad, SIZE - pad, SIZE - pad], radius=4, fill=WHITE)
    for y in [pad + 20, pad + 32, pad + 44]:
        d.line([(pad + 10, y), (CX - 10, y)], fill=GOLD, width=5)
    d.line([(CX + 10, pad + 22), (SIZE - pad - 10, pad + 22)], fill=GOLD, width=5)


def draw_smiley(d, pad=14):
    d.ellipse([pad, pad, SIZE - pad, SIZE - pad], outline=WHITE, width=7)
    d.ellipse([CX - 24, CY - 12, CX - 10, CY + 4], fill=WHITE)
    d.ellipse([CX + 10, CY - 12, CX + 24, CY + 4], fill=WHITE)
    d.arc([CX - 22, CY, CX + 22, CY + 30], start=10, end=170, fill=WHITE, width=7)


def draw_wave_hand(d, pad=16):
    d.ellipse([pad + 8, CY + 8, SIZE - pad - 8, SIZE - pad], fill=WHITE)
    for i, (bx, by) in enumerate([(CX - 22, pad + 8), (CX - 8, pad), (CX + 6, pad + 4),
                                   (CX + 18, pad + 12), (CX + 24, pad + 22)]):
        d.rectangle([bx, by, bx + 11, CY + 8 + i * 2], fill=WHITE)
        d.ellipse([bx, by - 9, bx + 11, by + 5], fill=WHITE)


def draw_panda(d, pad=14):
    d.ellipse([pad + 10, pad + 14, SIZE - pad - 10, SIZE - pad - 10], fill=WHITE)
    for ex in [pad + 4, SIZE - pad - 30]:
        d.ellipse([ex, pad, ex + 28, pad + 30], fill=WHITE)
    for ex in [pad + 22, SIZE - pad - 32]:
        d.ellipse([ex, CY - 4, ex + 18, CY + 14], fill=GOLD)
    d.arc([CX - 14, CY + 12, CX + 14, CY + 32], start=10, end=170, fill=GOLD, width=5)
    d.ellipse([CX - 6, CY - 3, CX + 6, CY + 9], fill=GOLD)


def draw_sparkles_multi(d, pad=14):
    for cx2, cy2, s2 in [(CX - 20, CY - 20, 18), (CX + 18, CY - 10, 14), (CX - 10, CY + 20, 12)]:
        for angle_deg in [0, 90, 180, 270]:
            angle = math.radians(angle_deg)
            ex = cx2 + int(s2 * math.cos(angle))
            ey = cy2 + int(s2 * math.sin(angle))
            d.line([(cx2, cy2), (ex, ey)], fill=WHITE, width=5)
        d.ellipse([cx2 - 5, cy2 - 5, cx2 + 5, cy2 + 5], fill=WHITE)


def draw_gif_label(d, pad=14):
    d.rounded_rectangle([pad, CY - 24, SIZE - pad, CY + 24], radius=8, outline=WHITE, width=7)
    ctext(d, "GIF", 40)


def draw_race_car(d, pad=14):
    d.rounded_rectangle([pad + 4, CY - 10, SIZE - pad - 4, CY + 18], radius=8, fill=WHITE)
    d.rounded_rectangle([pad + 16, pad + 12, SIZE - pad - 16, CY], radius=6, fill=WHITE)
    for wx in [pad + 18, SIZE - pad - 18]:
        d.ellipse([wx - 13, CY + 8, wx + 13, CY + 32], fill=WHITE)
        d.ellipse([wx - 6, CY + 14, wx + 6, CY + 26], fill=GOLD)
    d.line([(pad + 6, CY + 2), (SIZE - pad - 6, CY + 2)], fill=GOLD, width=5)


def draw_blob(d, pad=16):
    pts = []
    for i in range(12):
        angle = math.radians(i * 30)
        r = 42 + 10 * math.sin(i * 0.8)
        pts.append((CX + r * math.cos(angle), CY + r * math.sin(angle)))
    d.polygon(pts, fill=WHITE)


def draw_spinning_arrows(d, pad=16):
    for a in [30, 210]:
        r = math.radians(a)
        ex = CX + int(46 * math.cos(r + 0.6))
        ey = CY + int(46 * math.sin(r + 0.6))
        d.arc([CX - 38, CY - 38, CX + 38, CY + 38], start=a, end=a + 140, fill=WHITE, width=7)
        d.polygon([(ex - 9, ey - 7), (ex + 7, ey + 9), (ex + 9, ey - 7)], fill=WHITE)


# ── Badges ────────────────────────────────────────────────────────────────────

def draw_bug(d, pad=14):
    d.ellipse([pad + 14, pad, SIZE - pad - 14, CY - 4], fill=WHITE)
    d.ellipse([pad + 8, CY, SIZE - pad - 8, SIZE - pad - 4], fill=WHITE)
    for y in [CY + 8, CY + 22]:
        d.line([(pad, y), (pad + 22, y)], fill=WHITE, width=6)
        d.line([(SIZE - pad, y), (SIZE - pad - 22, y)], fill=WHITE, width=6)
    d.line([(pad + 14, pad + 4), (pad + 4, pad - 6)], fill=WHITE, width=5)
    d.line([(SIZE - pad - 14, pad + 4), (SIZE - pad - 4, pad - 6)], fill=WHITE, width=5)


def draw_mod_badge(d, pad=14):
    _shield_fill(d, pad)
    ctext(d, "M", 42, color=GOLD)


def draw_early_supporter(d, pad=14):
    draw_heart(d, pad)
    ctext(d, "♥", 22, color=GOLD)


def draw_early_dev(d, pad=14):
    draw_robot(d, pad)
    draw_star5(d, cx=SIZE - pad - 12, cy=pad + 12, r_out=11, r_in=4)


def draw_events_badge(d, pad=14):
    d.rectangle([pad, pad + 18, SIZE - pad, SIZE - pad], outline=WHITE, width=6)
    d.rectangle([CX - 22, pad + 8, CX + 22, pad + 24], fill=WHITE)
    d.line([(pad + 24, pad + 18), (pad + 24, SIZE - pad - 8)], fill=WHITE, width=5)
    draw_star5(d, cx=CX, cy=CY + 16, r_out=18, r_in=8)


def draw_balance_scales(d, pad=14):
    d.line([(CX, pad), (CX, SIZE - pad)], fill=WHITE, width=7)
    d.line([(pad + 6, CY - 4), (SIZE - pad - 6, CY - 4)], fill=WHITE, width=7)
    d.arc([pad + 6, CY - 4, CX, CY + 30], start=180, end=360, fill=WHITE, width=6)
    d.arc([CX, CY - 4, SIZE - pad - 6, CY + 30], start=180, end=360, fill=WHITE, width=6)


def draw_bravery_shield(d, pad=14):
    _shield_fill(d, pad)
    d.line([(CX - 14, CY - 10), (CX, pad + 20), (CX + 14, CY - 10)], fill=GOLD, width=6)
    d.line([(CX, pad + 20), (CX, CY + 18)], fill=GOLD, width=6)


def draw_brilliance_gem(d, pad=14):
    draw_gem(d, pad)
    d.line([(CX - 10, CY - 4), (CX + 10, pad + 20)], fill=GOLD, width=4)
    d.line([(CX + 10, CY - 4), (CX - 10, pad + 20)], fill=GOLD, width=4)


def draw_partner(d, pad=14):
    draw_handshake(d, pad)
    draw_star5(d, cx=CX, cy=pad + 16, r_out=12, r_in=5)


def draw_alert_bell(d, pad=14):
    _draw_bell_shape(d, pad)
    d.ellipse([SIZE - pad - 22, pad + 4, SIZE - pad - 4, pad + 22], fill=WHITE)
    ctext_at(d, "!", 22, SIZE - pad - 13, pad + 13, color=GOLD)


def _draw_bell_shape(d, pad=16):
    d.ellipse([pad + 8, pad + 10, SIZE - pad - 8, CY + 16], fill=WHITE)
    d.rectangle([pad + 4, CY, SIZE - pad - 4, SIZE - pad - 12], fill=WHITE)
    d.ellipse([CX - 16, SIZE - pad - 20, CX + 16, SIZE - pad], fill=WHITE)
    d.rectangle([CX - 4, pad + 2, CX + 4, pad + 12], fill=WHITE)


def draw_dice(d, pad=16):
    d.rounded_rectangle([pad, pad, SIZE - pad, SIZE - pad], radius=12, outline=WHITE, width=7)
    for cx2, cy2 in [(pad + 24, pad + 24), (CX, CY), (SIZE - pad - 24, SIZE - pad - 24)]:
        d.ellipse([cx2 - 8, cy2 - 8, cx2 + 8, cy2 + 8], fill=WHITE)


# ── Branch-4 new emoji draw functions ─────────────────────────────────────────

def draw_bar_chart(d, pad=16):
    """📊 bar chart — for zpoll / stats."""
    base_y = SIZE - pad - 4
    bars = [(pad + 8, 44), (pad + 30, 30), (pad + 52, 56), (pad + 74, 22)]
    for bx, h in bars:
        d.rectangle([bx, base_y - h, bx + 18, base_y], fill=WHITE)
    d.line([(pad + 4, base_y + 2), (SIZE - pad - 4, base_y + 2)], fill=WHITE, width=5)


def draw_picture_frame(d, pad=16):
    """🖼️ picture frame — for zimage."""
    d.rectangle([pad, pad, SIZE - pad, SIZE - pad], outline=WHITE, width=7)
    # Sky
    d.rectangle([pad + 8, pad + 8, SIZE - pad - 8, CY], fill=GOLD)
    # Mountain
    d.polygon([(pad + 14, CY), (CX, pad + 22), (SIZE - pad - 14, CY)], fill=WHITE)
    # Sun circle
    d.ellipse([SIZE - pad - 30, pad + 12, SIZE - pad - 10, pad + 32], fill=WHITE)


def draw_broom(d, pad=16):
    """🧹 broom — for zbroom (clear/sweep)."""
    # Handle
    d.line([(pad + 12, pad), (SIZE - pad - 8, SIZE - pad - 8)], fill=WHITE, width=9)
    # Bristles
    bx, by = SIZE - pad - 8, SIZE - pad - 8
    for ox, oy in [(-14, 8), (-6, 14), (2, 12), (10, 6)]:
        d.line([(bx, by), (bx + ox, by + oy)], fill=WHITE, width=6)
    d.ellipse([bx - 20, by - 6, bx + 18, by + 14], outline=WHITE, width=5)


def draw_theater_mask(d, pad=14):
    """🎭 theater mask — for zmask (AI personality/roleplay)."""
    # Happy mask (left)
    lx = pad + 4
    d.ellipse([lx, CY - 20, lx + 44, CY + 28], outline=WHITE, width=6)
    d.arc([lx + 10, CY, lx + 34, CY + 20], start=10, end=170, fill=WHITE, width=5)
    d.ellipse([lx + 10, CY - 12, lx + 18, CY - 2], fill=WHITE)
    d.ellipse([lx + 26, CY - 12, lx + 34, CY - 2], fill=WHITE)
    # Sad mask (right, offset)
    rx = CX + 2
    d.ellipse([rx, CY - 28, rx + 44, CY + 20], outline=WHITE, width=6)
    d.arc([rx + 10, CY - 2, rx + 34, CY + 18], start=190, end=350, fill=WHITE, width=5)
    d.ellipse([rx + 10, CY - 20, rx + 18, CY - 10], fill=WHITE)
    d.ellipse([rx + 26, CY - 20, rx + 34, CY - 10], fill=WHITE)


def draw_brain(d, pad=16):
    """🧠 brain — for zbrain (trivia/intelligence)."""
    # Left lobe
    d.ellipse([pad, CY - 28, CX + 4, CY + 28], outline=WHITE, width=7)
    # Right lobe
    d.ellipse([CX - 4, CY - 28, SIZE - pad, CY + 28], outline=WHITE, width=7)
    # Folds (horizontal lines inside)
    for y in [CY - 12, CY, CY + 12]:
        d.arc([pad + 10, y - 8, CX - 2, y + 8], start=0, end=180, fill=WHITE, width=5)
        d.arc([CX + 2, y - 8, SIZE - pad - 10, y + 8], start=0, end=180, fill=WHITE, width=5)
    # Bottom connector
    d.line([(CX - 6, CY + 20), (CX + 6, CY + 20)], fill=WHITE, width=6)


def draw_flower(d, pad=16):
    """🌸 flower — for zflower (memory)."""
    r_petal = 20
    for i in range(6):
        angle = math.radians(i * 60)
        px = CX + int(r_petal * math.cos(angle))
        py = CY + int(r_petal * math.sin(angle))
        d.ellipse([px - 13, py - 13, px + 13, py + 13], fill=WHITE)
    d.ellipse([CX - 14, CY - 14, CX + 14, CY + 14], fill=GOLD)


def draw_refresh_arrows(d, pad=16):
    """🔄 two circular refresh arrows — for zrefresh."""
    r = 34
    # Top arc (left-to-right, clockwise)
    d.arc([CX - r, CY - r, CX + r, CY + r], start=200, end=360, fill=WHITE, width=8)
    # Arrowhead at end of top arc (at 360°/0°)
    d.polygon([(CX + r - 4, CY - 10), (CX + r + 10, CY), (CX + r - 4, CY + 10)], fill=WHITE)
    # Bottom arc (right-to-left)
    d.arc([CX - r, CY - r, CX + r, CY + r], start=20, end=180, fill=WHITE, width=8)
    # Arrowhead at end of bottom arc (at 180°)
    d.polygon([(CX - r + 4, CY - 10), (CX - r - 10, CY), (CX - r + 4, CY + 10)], fill=WHITE)


def draw_coffee_cup(d, pad=16):
    """☕ coffee cup — for zcoffee (Java)."""
    # Cup body
    d.rounded_rectangle([pad + 4, CY - 12, SIZE - pad - 16, SIZE - pad - 4], radius=8, fill=WHITE)
    # Handle
    d.arc([SIZE - pad - 24, CY - 4, SIZE - pad - 4, CY + 22],
          start=300, end=60, fill=WHITE, width=7)
    # Saucer
    d.ellipse([pad, SIZE - pad - 8, SIZE - pad - 12, SIZE - pad + 4], outline=WHITE, width=5)
    # Steam lines
    for ox, oy_start in [(-14, 0), (0, -8), (14, 0)]:
        d.arc([CX + ox - 6, pad + oy_start, CX + ox + 6, CY - 12 + oy_start],
              start=200, end=340, fill=WHITE, width=5)


def draw_pickaxe(d, pad=16):
    """⛏️ pickaxe — for zpickaxe (Minecraft)."""
    # Handle (diagonal)
    d.line([(pad + 8, SIZE - pad - 8), (SIZE - pad - 8, pad + 8)], fill=WHITE, width=8)
    # Pick head — large horizontal rectangle at the top-right
    head_cx = SIZE - pad - 14
    head_cy = pad + 14
    d.polygon([
        (head_cx - 24, head_cy - 10),
        (head_cx + 14, head_cy - 18),
        (head_cx + 18, head_cy + 4),
        (head_cx - 8, head_cy + 16),
    ], fill=WHITE)


def draw_power_plug(d, pad=16):
    """🔌 power plug — for zplug (Bedrock/proxy)."""
    # Plug body
    d.rounded_rectangle([pad + 16, CY - 12, SIZE - pad - 16, CY + 28], radius=8, fill=WHITE)
    # Prongs
    d.rectangle([CX - 14, pad + 4, CX - 6, CY - 12], fill=WHITE)
    d.rectangle([CX + 6, pad + 4, CX + 14, CY - 12], fill=WHITE)
    # Cable
    d.line([(CX, CY + 28), (CX, SIZE - pad)], fill=WHITE, width=8)
    d.ellipse([CX - 6, SIZE - pad - 8, CX + 6, SIZE - pad + 4], fill=WHITE)


def draw_clipboard(d, pad=16):
    """📋 clipboard — for zclipboard (placeholders)."""
    # Board
    d.rounded_rectangle([pad + 4, pad + 12, SIZE - pad - 4, SIZE - pad], radius=6, fill=WHITE)
    # Clip
    d.rounded_rectangle([CX - 16, pad + 4, CX + 16, pad + 22], radius=6, fill=GOLD)
    # Lines
    for y in [pad + 34, pad + 46, pad + 58, pad + 70]:
        d.line([(pad + 16, y), (SIZE - pad - 16, y)], fill=GOLD, width=5)
    # Short last line
    d.line([(pad + 16, pad + 82), (CX + 8, pad + 82)], fill=GOLD, width=5)


def draw_ballot_box(d, pad=16):
    """🗳️ ballot box — for zvote."""
    # Box
    d.rounded_rectangle([pad, CY - 4, SIZE - pad, SIZE - pad], radius=6, outline=WHITE, width=7)
    # Slot at top
    d.rounded_rectangle([CX - 16, CY - 10, CX + 16, CY + 2], radius=3, fill=WHITE)
    # Ballot paper being inserted
    d.rectangle([CX - 10, pad + 4, CX + 10, CY - 4], fill=WHITE)
    # Checkmark on paper
    d.line([(CX - 6, CY - 16), (CX - 2, CY - 10), (CX + 8, CY - 28)], fill=GOLD, width=4)


def draw_birthday_cake(d, pad=16):
    """🎂 birthday cake — for zbirthday."""
    # Cake body
    d.rounded_rectangle([pad + 6, CY + 4, SIZE - pad - 6, SIZE - pad], radius=6, fill=WHITE)
    # Frosting
    d.rounded_rectangle([pad + 4, CY - 4, SIZE - pad - 4, CY + 14], radius=8, fill=WHITE)
    d.ellipse([pad + 20, CY - 6, pad + 28, CY + 4], fill=GOLD)
    d.ellipse([CX - 4, CY - 8, CX + 4, CY + 2], fill=GOLD)
    d.ellipse([SIZE - pad - 28, CY - 6, SIZE - pad - 20, CY + 4], fill=GOLD)
    # Candles
    for cx2 in [pad + 28, CX, SIZE - pad - 28]:
        d.rectangle([cx2 - 5, CY - 24, cx2 + 5, CY - 4], fill=WHITE)
        d.ellipse([cx2 - 5, CY - 30, cx2 + 5, CY - 20], fill=GOLD)


def draw_envelope(d, pad=16):
    """✉️ mail envelope — for zenvelope."""
    # Body
    d.rectangle([pad, CY - 16, SIZE - pad, SIZE - pad], outline=WHITE, width=6)
    # Flap (V shape from top)
    d.polygon([(pad, CY - 16), (CX, CY + 14), (SIZE - pad, CY - 16)], outline=WHITE, width=6)
    # Bottom seal line
    d.line([(pad + 12, SIZE - pad - 4), (SIZE - pad - 12, SIZE - pad - 4)], fill=WHITE, width=4)


def draw_number_circle(d, num: int, pad=18):
    """Numbered circle — for znum1–znum10."""
    d.ellipse([pad, pad, SIZE - pad, SIZE - pad], outline=WHITE, width=7)
    label = str(num)
    sz = 38 if num < 10 else 30
    ctext(d, label, sz)


# ── Emoji map (zero duplicate keys) ──────────────────────────────────────────

EMOJI_MAP: dict = {
    # ── Status ─────────────────────────────────────────────────────────────────
    "ztick":               lambda d: draw_thick_check(d),
    "tick":                lambda d: draw_checkmark(d, thick=8),
    "Ztick":               lambda d: draw_circle_check(d),
    "olympus_tick":        lambda d: draw_shield_check(d),
    "zcross":              lambda d: draw_x(d, thick=12),
    "CrossIcon":           lambda d: draw_x(d, thick=8),
    "ml_cross":            lambda d: draw_circle_x(d),
    "Denied":              lambda d: draw_ban_circle(d),
    "zwarning":            lambda d: draw_warning_triangle(d, fill=True),
    "warning":             lambda d: draw_warning_triangle(d, fill=False),
    "icons_warning":       lambda d: draw_warning_square(d),
    "error":               lambda d: draw_octagon_exclaim(d),
    "Enable":              lambda d: draw_toggle_on(d),
    "Disable":             lambda d: draw_toggle_off(d),
    "New":                 lambda d: draw_new_badge(d),
    "info":                lambda d: (d.ellipse([14, 14, 114, 114], outline=WHITE, width=8),
                                      ctext(d, "i", 62)),
    # ── Navigation ─────────────────────────────────────────────────────────────
    "zArrow":              lambda d: draw_arrow_right(d),
    "ArrowRed":            lambda d: draw_arrow_right(d, thick=13),
    "zback":               lambda d: draw_arrow_left(d),
    # ← FIXED: next = LEFT arrow (it's the "previous page" button in the help view)
    "next":                lambda d: draw_arrow_left(d),
    # → right arrow for "go to next page"
    "icons_next":          lambda d: draw_arrow_right(d),
    # ⏭ skip to end = "last page" button
    "forward":             lambda d: draw_skip_to_end(d),
    "max__A":              lambda d: draw_max_arrow(d),
    "zplus":               lambda d: draw_plus(d),
    "icons_plus":          lambda d: draw_plus_circle(d),
    # ── Loading ────────────────────────────────────────────────────────────────
    "loading":             lambda d: draw_loading_spinner(d),
    "loadingred":          lambda d: (draw_loading_spinner(d), draw_dot(d, pad=52)),
    "iconLoad":            lambda d: draw_loading_spinner(d),
    # ── Interface ──────────────────────────────────────────────────────────────
    "channel":             lambda d: draw_hashtag(d),
    "icons_channel":       lambda d: draw_hashtag(d, pad=22),
    "icons_home":          lambda d: draw_house(d),
    "icon_browser":        lambda d: draw_magnifier(d),
    "lock":                lambda d: draw_lock(d),
    "unlock":              lambda d: draw_unlock(d),
    "delete":              lambda d: draw_trash(d),
    # ── People ─────────────────────────────────────────────────────────────────
    "zHuman":              lambda d: draw_person(d),
    "zpeople":             lambda d: draw_people(d),
    "king":                lambda d: draw_crown(d),
    "manager":             lambda d: (draw_crown(d, pad=20), draw_person(d)),
    "headmod":             lambda d: draw_headmod(d),
    "staff":               lambda d: draw_staff_badge(d),
    "handshake":           lambda d: draw_handshake(d),
    # ── Symbols ────────────────────────────────────────────────────────────────
    "zyrox_mention":       lambda d: draw_at_symbol(d),
    "mention":             lambda d: draw_at_symbol(d),
    "starr":               lambda d: draw_star5(d),
    "star":                lambda d: draw_star5(d, r_out=44, r_in=20),
    "Star":                lambda d: (draw_star5(d, r_out=40, r_in=16), draw_sparkle(d)),
    "heart3":              lambda d: draw_heart3(d),
    "zdil":                lambda d: draw_heart(d),
    "RedHeart":            lambda d: draw_heart(d, pad=16),
    "heart_em":            lambda d: (draw_heart(d, pad=18), draw_sparkle(d)),
    "red_button":          lambda d: draw_dot(d, pad=18),
    "reddot":              lambda d: draw_dot(d, pad=30),
    # ── Actions ────────────────────────────────────────────────────────────────
    "zban":                lambda d: draw_ban_circle(d),
    "zpin":                lambda d: draw_pushpin(d),
    "red_pin":             lambda d: draw_pushpin(d),
    "zsowrd":              lambda d: draw_sword(d),
    "zmsg":                lambda d: draw_message(d),
    "zmodule":             lambda d: draw_puzzle(d),
    "zsettings":           lambda d: draw_gear(d),
    "zwrench":             lambda d: draw_wrench(d),
    "zcast":               lambda d: draw_antenna(d),
    "zSafe":               lambda d: draw_shield_heart(d),
    "zCloud":              lambda d: draw_cloud(d),
    "zrocket":             lambda d: draw_rocket(d),
    "zbot":                lambda d: draw_robot(d),
    "zwifi":               lambda d: draw_wifi(d),
    # ── Time ───────────────────────────────────────────────────────────────────
    "zyrox_time":          lambda d: draw_clock(d),
    "ztimer":              lambda d: draw_stopwatch(d),
    "timer":               lambda d: draw_stopwatch(d),
    "uptime":              lambda d: draw_uptime_chart(d),
    # ── Tech ───────────────────────────────────────────────────────────────────
    "zyrox_global":        lambda d: draw_globe(d),
    "zyroxsys":            lambda d: draw_gear(d),
    "zyrox_system":        lambda d: draw_ai_chip(d),
    "zyroxhammer":         lambda d: draw_hammer(d),
    "zyroxconnection":     lambda d: draw_connection(d),
    "zyroxlinks":          lambda d: draw_link(d),
    "zyrox_search":        lambda d: draw_magnifier(d),
    "zyroxthunder":        lambda d: draw_lightning(d),
    "codebase":            lambda d: draw_code_brackets(d),
    "coded":               lambda d: draw_terminal(d),
    "zai":                 lambda d: draw_ai_chip(d),
    # ── Features ───────────────────────────────────────────────────────────────
    "boost":               lambda d: draw_lightning(d),
    "boosts":              lambda d: draw_lightning_multi(d),
    "nitroboost":          lambda d: draw_gem(d),
    "premium":             lambda d: draw_premium_badge(d),
    "TADAA":               lambda d: draw_tada(d),
    "ztada":               lambda d: draw_tada(d),
    "games":               lambda d: draw_gamepad(d),
    "zticket":             lambda d: draw_ticket(d),
    "zcounting":           lambda d: draw_123(d),
    "zlevelup":            lambda d: draw_level_up(d),
    "zseed":               lambda d: draw_leaf(d),
    "j2c_wait":            lambda d: draw_couch(d),
    "zcircle":             lambda d: draw_circle_full(d),
    "zcircle2":            lambda d: draw_circle_outline(d),
    "zmc":                 lambda d: draw_minecraft_creeper(d),
    # ── Music ──────────────────────────────────────────────────────────────────
    "music":               lambda d: draw_music_note(d),
    "zmusic":              lambda d: draw_music_note(d),
    "icons_music":         lambda d: draw_double_note(d),
    "zmusicpause":         lambda d: (draw_music_note(d), draw_pause_bars(d)),
    "zplay":               lambda d: draw_play_triangle(d),
    "zpause":              lambda d: draw_pause_bars(d),
    "icons_pause":         lambda d: draw_pause_bars(d),
    "musicstop_icons":     lambda d: draw_stop_square(d),
    "rewind1":             lambda d: draw_rewind(d),        # ⏮ skip to start / previous
    "skip":                lambda d: draw_skip_fwd(d),       # ⏭ skip forward
    "zreplay":             lambda d: draw_replay(d),         # 🔄 replay / restart track (circular arrow)
    "shuffle":             lambda d: draw_shuffle_arrows(d),
    "zmute":               lambda d: draw_speaker_muted(d),  # 🔇 muted speaker
    "zunmute":             lambda d: draw_speaker(d),         # 🔊 speaker
    "SoundCloud":          lambda d: draw_soundcloud(d),
    "youtube":             lambda d: draw_yt_play(d),
    "YouTube":             lambda d: draw_yt_play(d),
    "jiosaavn":            lambda d: draw_jiosaavn_j(d),
    # ── Presence ───────────────────────────────────────────────────────────────
    "online":              lambda d: draw_circle_full(d, pad=28),
    "offline":             lambda d: draw_circle_outline(d, pad=28),
    "idle":                lambda d: draw_moon(d),
    "dnd":                 lambda d: draw_circle_minus(d),
    "mobile":              lambda d: draw_phone(d),
    "pc":                  lambda d: draw_monitor(d),
    # ── Extra ──────────────────────────────────────────────────────────────────
    "RedRulesBook":        lambda d: draw_book(d),
    "antenna":             lambda d: draw_antenna_broadcast(d),
    "emote":               lambda d: draw_smiley(d),
    "mingle":              lambda d: draw_wave_hand(d),
    "happy_panda":         lambda d: draw_panda(d),
    "Cute_Cute_Cute":      lambda d: draw_smiley(d),
    "Heeriye":             lambda d: draw_sparkles_multi(d),
    "racecar64":           lambda d: draw_race_car(d),
    "blobpart":            lambda d: draw_blob(d),
    "sg_rd":               lambda d: draw_spinning_arrows(d),
    "GIFD":                lambda d: draw_gif_label(d),
    "GIFN":                lambda d: draw_gif_label(d),
    # ── Discord Badges ─────────────────────────────────────────────────────────
    "Active_Developer":    lambda d: draw_terminal(d),
    "BugHunterLevel1":     lambda d: draw_bug(d),
    "BugHunterLvl2":       lambda d: (draw_bug(d),
                                       draw_star5(d, cx=SIZE - 28, cy=28, r_out=12, r_in=5)),
    "CertifiedDiscordModerator": lambda d: draw_mod_badge(d),
    "EarlySupporter":      lambda d: draw_early_supporter(d),
    "EarlyVerifiedBotDeveloper": lambda d: draw_early_dev(d),
    "HypesquadEvents":     lambda d: draw_events_badge(d),
    "Hypesquad_Brilliance":lambda d: draw_brilliance_gem(d),
    "a_Hypesquad_Balance": lambda d: draw_balance_scales(d),
    "a_Hypesquad_Bravery": lambda d: draw_bravery_shield(d),
    "PartneredServerOwner":lambda d: draw_partner(d),
    "BlackCrown":          lambda d: draw_crown(d),
    # ── Misc ───────────────────────────────────────────────────────────────────
    "37496alert":          lambda d: draw_alert_bell(d),
    "3d4":                 lambda d: draw_dice(d),
    # ── Branch 4 — new semantic emojis ────────────────────────────────────────
    "zpoll":               lambda d: draw_bar_chart(d),
    "zimage":              lambda d: draw_picture_frame(d),
    "zbroom":              lambda d: draw_broom(d),
    "zmood":               lambda d: draw_smiley(d),
    "zmask":               lambda d: draw_theater_mask(d),
    "zbrain":              lambda d: draw_brain(d),
    "zflower":             lambda d: draw_flower(d),
    "zrefresh":            lambda d: draw_refresh_arrows(d),
    "zcoffee":             lambda d: draw_coffee_cup(d),
    "zpickaxe":            lambda d: draw_pickaxe(d),
    "zplug":               lambda d: draw_power_plug(d),
    "zclipboard":          lambda d: draw_clipboard(d),
    "zvote":               lambda d: draw_ballot_box(d),
    "zbirthday":           lambda d: draw_birthday_cake(d),
    "zenvelope":           lambda d: draw_envelope(d),
    "zvoice":              lambda d: draw_speaker(d),
    "zbook":               lambda d: draw_book(d),
    "znum1":               lambda d: draw_number_circle(d, 1),
    "znum2":               lambda d: draw_number_circle(d, 2),
    "znum3":               lambda d: draw_number_circle(d, 3),
    "znum4":               lambda d: draw_number_circle(d, 4),
    "znum5":               lambda d: draw_number_circle(d, 5),
    "znum6":               lambda d: draw_number_circle(d, 6),
    "znum7":               lambda d: draw_number_circle(d, 7),
    "znum8":               lambda d: draw_number_circle(d, 8),
    "znum9":               lambda d: draw_number_circle(d, 9),
    "znum10":              lambda d: draw_number_circle(d, 10),
}


if __name__ == "__main__":
    print(f"\n🎨 Generating {len(EMOJI_MAP)} emoji images → {OUT}/\n")
    ok = err = 0
    for name, fn in EMOJI_MAP.items():
        try:
            make(name, fn)
            ok += 1
        except Exception as ex:
            print(f"  ✗ {name}: {ex}")
            err += 1
    print(f"\n✅ Done — {ok} emojis saved to {OUT}/  ({err} errors)")
