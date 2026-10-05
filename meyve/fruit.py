"""Meyve karakter çizimi (cairo, tamamen kod; telif yok).

Yerel koordinat: zemin y=0, yukarı negatif, +x karakterin baktığı yön (facing=-1 ise ayna).
1 birim = s piksel. Gövde: gölgeli gradyan + doku + parlama; üstüne yüz (iri gözler, kaşlar, ağız), kollar, bacaklar.
"""
import math
import random

import cairo

from .cast import CAST

LEG = 8.0          # bacak boyu
TUCK = 2.0         # bacakların gövdeye giren kısmı
ARM_LEN = 22.0
LIMB_W = 2.4
_poly_cache = {}
_tex_cache = {}


# ------------------------------------------------------------------ renk yardımcıları

def lighten(c, k):
    return tuple(v + (1 - v) * k for v in c)


def darken(c, k):
    return tuple(v * k for v in c)


def mix(a, b, k):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


# ------------------------------------------------------------------ gövde biçimleri

def _polar(kind, a, b, n=96):
    pts = []
    for i in range(n):
        th = 2 * math.pi * i / n - math.pi / 2          # tepeden başla
        cx, sy = math.cos(th), math.sin(th)              # sy < 0: üst yarı
        x, y = a * cx, b * sy
        if kind == 'tomato':
            r = 1 + 0.025 * math.cos(6 * th)
            x, y = x * r, y * r * (0.88 if sy < 0 else 1.0)
        elif kind == 'lemon':
            r = 1 + 0.16 * abs(sy) ** 14
            x, y = x * (1 - 0.06 * abs(sy) ** 2), y * r
        elif kind == 'strawberry':
            if sy > 0:
                x *= 1 - 0.55 * sy ** 1.3
                y *= 1.08
            else:
                y *= 0.82
                x *= 1 + 0.05 * (1 - abs(cx))
        elif kind == 'onion':
            if sy < 0:
                x *= 1 - 0.55 * (-sy) ** 2.2
                y *= 1.12
        elif kind == 'avocado':
            if sy < 0:
                x *= 1 - 0.36 * (-sy) ** 1.4
                y *= 1.05
            else:
                x *= 1.04
        elif kind == 'orange':
            r = 1 + 0.015 * math.cos(3 * th)
            x, y = x * r, y * r
        pts.append((x, y))
    return pts


def _spine(kind, a, b, n=60):
    """Uzun meyveler: eğri bir omurga + kalınlık profili."""
    cen, hw = [], []
    for i in range(n + 1):
        u = i / n
        y = -b + 2 * b * u
        if kind == 'banana':
            xc = -a * 0.75 * (1 - (2 * u - 1) ** 2) + a * 0.35
            p = max(0.0, math.sin(math.pi * min(1, max(0, (u - 0.02) / 0.96)))) ** 0.55 * 0.62
        elif kind == 'pepper':
            xc = a * 0.55 * u ** 2.2 - a * 0.1
            p = min(1, math.sqrt(u / 0.1)) * (1 - u) ** 0.75 * 0.98
        else:  # cucumber
            xc = a * 0.18 * math.sin(math.pi * u)
            p = min(1, math.sqrt(u / 0.12), math.sqrt(max(0, 1 - u) / 0.12)) * 0.97
        cen.append((xc, y)); hw.append(a * p)
    left, right = [], []
    for i, ((x, y), w) in enumerate(zip(cen, hw)):
        x0, y0 = cen[max(0, i - 1)]; x1, y1 = cen[min(n, i + 1)]
        tx, ty = x1 - x0, y1 - y0
        d = math.hypot(tx, ty) or 1
        nx, ny = ty / d, -tx / d
        right.append((x + nx * w, y + ny * w)); left.append((x - nx * w, y - ny * w))
    return right + left[::-1], cen


def poly(cid):
    if cid not in _poly_cache:
        c = CAST[cid]
        a, b = c['w'] / 2, c['h'] / 2
        if c['shape'] in ('banana', 'pepper', 'cucumber'):
            pts, cen = _spine(c['shape'], a, b)
        else:
            pts, cen = _polar(c['shape'], a, b), None
        _poly_cache[cid] = (pts, cen)
    return _poly_cache[cid]


def span_at(pts, y):
    xs = []
    n = len(pts)
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        if (y0 - y) * (y1 - y) <= 0 and y0 != y1:
            xs.append(x0 + (x1 - x0) * (y - y0) / (y1 - y0))
    return (min(xs), max(xs)) if xs else (0.0, 0.0)


def path(ctx, pts):
    ctx.new_path()
    n = len(pts)
    # orta noktalar arasında ikinci dereceden eğri: yumuşak kenar
    mx, my = (pts[-1][0] + pts[0][0]) / 2, (pts[-1][1] + pts[0][1]) / 2
    ctx.move_to(mx, my)
    for i in range(n):
        x, y = pts[i]
        nx, ny = pts[(i + 1) % n]
        ex, ey = (x + nx) / 2, (y + ny) / 2
        cx0, cy0 = ctx.get_current_point()
        ctx.curve_to(cx0 + 2 / 3 * (x - cx0), cy0 + 2 / 3 * (y - cy0), ex + 2 / 3 * (x - ex), ey + 2 / 3 * (y - ey), ex, ey)
    ctx.close_path()


def geometry(cid):
    """Yüz, omuz ve kalça noktaları (gövde merkezine göre)."""
    c = CAST[cid]
    pts, cen = poly(cid)
    fy = c['face_y']
    l, r = span_at(pts, fy)
    fx = (l + r) / 2 + 2.0
    half = (r - l) / 2
    er = max(4.6, min(7.2, half * 0.3))
    ex = min(half * 0.42, er * 1.25)
    sy = fy + er + 8
    sl, sr = span_at(pts, sy)
    hy = c['h'] / 2 - 4
    hl, hr = span_at(pts, hy)
    return {'face': (fx, fy), 'er': er, 'ex': ex, 'sh': (sl * 0.96, sr * 0.96, sy), 'hip': (hl, hr, hy),
            'top': min(p[1] for p in pts)}


# ------------------------------------------------------------------ dokular

def _rng(cid, k):
    return random.Random(hash((cid, k)) & 0xffffffff)


def texture(ctx, cid, c, pts, t):
    shape, a, b = c['shape'], c['w'] / 2, c['h'] / 2
    base = c['color']
    if shape in ('orange', 'lemon'):
        dots = _tex_cache.setdefault((cid, 'pores'), [(r.uniform(-a, a), r.uniform(-b, b), r.uniform(0.25, 0.55))
                                                      for r in [_rng(cid, 1)] for _ in range(260)])
        ctx.set_source_rgba(*darken(base, 0.7), 0.22)
        for x, y, rr in dots:
            ctx.new_sub_path(); ctx.arc(x, y, rr, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.12)
        for x, y, rr in dots[::3]:
            ctx.new_sub_path(); ctx.arc(x - 0.3, y - 0.3, rr * 0.6, 0, 2 * math.pi)
        ctx.fill()
    elif shape == 'watermelon':
        dark = (0.1, 0.33, 0.1)
        ctx.set_source_rgb(*dark)
        for k in range(-3, 4):
            x0 = k * a * 0.3
            wv = a * 0.1
            ctx.new_path()
            steps = 24
            for i in range(steps + 1):
                y = -b + 2 * b * i / steps
                q = math.sqrt(max(0, 1 - (y / b) ** 2))
                jag = (0.45 if i % 2 else -0.45)
                ctx.line_to(x0 * (0.25 + 0.75 * q) - wv * q + jag * q, y)
            for i in range(steps, -1, -1):
                y = -b + 2 * b * i / steps
                q = math.sqrt(max(0, 1 - (y / b) ** 2))
                jag = (0.45 if i % 2 else -0.45)
                ctx.line_to(x0 * (0.25 + 0.75 * q) + wv * q - jag * q, y)
            ctx.close_path(); ctx.fill()
    elif shape == 'strawberry':
        seeds = _tex_cache.setdefault((cid, 'seeds'), None)
        if seeds is None:
            seeds, r = [], _rng(cid, 2)
            for row in range(12):
                y = -b * 0.62 + row * (2 * b * 1.05) / 12
                l, rr = span_at(pts, y)
                n = max(1, int((rr - l) / 5.2))
                for i in range(n):
                    x = l + (i + 0.5 + (0.5 if row % 2 else 0)) * (rr - l) / (n + 0.5)
                    if l + 2 < x < rr - 2:
                        seeds.append((x + r.uniform(-0.6, 0.6), y + r.uniform(-0.6, 0.6)))
            _tex_cache[(cid, 'seeds')] = seeds
        for x, y in seeds:
            ctx.save(); ctx.translate(x, y); ctx.scale(0.75, 1.1)
            ctx.arc(0, 0.25, 1.15, 0, 2 * math.pi); ctx.restore()
            ctx.set_source_rgba(*darken(base, 0.55), 0.55); ctx.fill()
            ctx.save(); ctx.translate(x, y); ctx.scale(0.45, 0.75)
            ctx.arc(0, 0, 1.0, 0, 2 * math.pi); ctx.restore()
            ctx.set_source_rgb(1.0, 0.88, 0.35); ctx.fill()
    elif shape == 'onion':
        ctx.set_line_width(0.45)
        for k in range(-4, 5):
            ctx.new_path()
            for i in range(31):
                y = -b * 1.12 + 2.12 * b * i / 30
                l, r = span_at(pts, y)
                xm = (l + r) / 2 + (r - l) / 2 * k / 4.6
                ctx.line_to(xm, y)
            ctx.set_source_rgba(*darken(base, 0.62), 0.45); ctx.stroke()
        ctx.set_line_width(1.4)
        for k in (-2.5, 1.5):
            ctx.new_path()
            for i in range(31):
                y = -b * 0.9 + 1.7 * b * i / 30
                l, r = span_at(pts, y)
                ctx.line_to((l + r) / 2 + (r - l) / 2 * k / 4.6, y)
            ctx.set_source_rgba(1, 0.92, 0.75, 0.22); ctx.stroke()
    elif shape == 'pineapple':
        ctx.set_line_width(0.7)
        ctx.set_source_rgba(*darken(base, 0.45), 0.75)
        step = 6.0
        for k in range(-14, 15):
            ctx.move_to(k * step - b, -b); ctx.line_to(k * step + b, b)
            ctx.move_to(k * step + b, -b); ctx.line_to(k * step - b, b)
        ctx.stroke()
        for i in range(-14, 15):
            for j in range(-14, 15):
                x, y = (i + j) * step / 2, (j - i) * step / 2
                if abs(x) < a + 2 and abs(y) < b + 2:
                    ctx.new_sub_path(); ctx.arc(x, y, 0.75, 0, 2 * math.pi)
        ctx.set_source_rgba(0.35, 0.2, 0.05, 0.85); ctx.fill()
        g = cairo.RadialGradient(0, 0, 0, 0, 0, a)
        g.add_color_stop_rgba(0, 0.6, 0.75, 0.2, 0.0); g.add_color_stop_rgba(1, 0.4, 0.55, 0.15, 0.25)
        ctx.rectangle(-a - 2, -b - 2, 2 * a + 4, 2 * b + 4); ctx.set_source(g); ctx.fill()
    elif shape == 'avocado':
        dots = _tex_cache.setdefault((cid, 'bumps'), [(r.uniform(-a, a), r.uniform(-b * 1.1, b), r.uniform(0.4, 0.9))
                                                      for r in [_rng(cid, 3)] for _ in range(320)])
        ctx.set_source_rgba(*lighten(base, 0.3), 0.35)
        for x, y, rr in dots[::2]:
            ctx.new_sub_path(); ctx.arc(x, y, rr, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgba(*darken(base, 0.55), 0.4)
        for x, y, rr in dots[1::2]:
            ctx.new_sub_path(); ctx.arc(x, y, rr * 0.8, 0, 2 * math.pi)
        ctx.fill()
    elif shape == 'cucumber':
        _, cen = poly(cid)
        ctx.set_line_width(2.2)
        for off in (-0.45, 0.1, 0.6):
            ctx.new_path()
            for x, y in cen[3:-3]:
                l, r = span_at(pts, y)
                ctx.line_to(x + (r - l) / 2 * off, y)
            ctx.set_source_rgba(*lighten(base, 0.35), 0.35); ctx.stroke()
        bumps = _tex_cache.setdefault((cid, 'bumps'), [(r.uniform(-a, a), r.uniform(-b, b)) for r in [_rng(cid, 4)]
                                                       for _ in range(70)])
        for x, y in bumps:
            ctx.new_sub_path(); ctx.arc(x, y, 0.8, 0, 2 * math.pi)
        ctx.set_source_rgba(*lighten(base, 0.5), 0.55); ctx.fill()
        for x, y in bumps:
            ctx.new_sub_path(); ctx.arc(x + 0.2, y + 0.2, 0.35, 0, 2 * math.pi)
        ctx.set_source_rgba(*darken(base, 0.5), 0.6); ctx.fill()
    elif shape == 'banana':
        _, cen = poly(cid)
        ctx.set_line_width(0.6)
        for off in (-0.35, 0.35):
            ctx.new_path()
            for x, y in cen[4:-4]:
                l, r = span_at(pts, y)
                ctx.line_to(x + (r - l) / 2 * off, y)
            ctx.set_source_rgba(*darken(base, 0.75), 0.5); ctx.stroke()
        for x, y, rr in [(-3, 18, 0.9), (4, 8, 0.6), (-1, 24, 0.7), (5, -14, 0.5)]:
            ctx.new_sub_path(); ctx.arc(x + cen[int(30 + y)][0] * 0, y, rr, 0, 2 * math.pi)
        ctx.set_source_rgba(0.45, 0.3, 0.1, 0.45); ctx.fill()
    elif shape == 'tomato':
        ctx.set_line_width(0.6)
        for k in range(5):
            ang = -math.pi / 2 + (k - 2) * 0.45
            ctx.move_to(0, -b * 0.85)
            ctx.curve_to(a * 0.4 * math.cos(ang + 1.57) , -b * 0.4, a * 0.6 * (k - 2) / 2, 0, a * 0.5 * (k - 2) / 2, b * 0.3)
        ctx.set_source_rgba(*darken(base, 0.7), 0.25); ctx.stroke()


def back_accessory(ctx, cid, c):
    a, b = c['w'] / 2, c['h'] / 2
    if c['shape'] == 'pineapple':
        top = -b + 2
        for i, ang in enumerate([-0.75, -0.45, -0.2, 0.05, 0.3, 0.55, 0.8, -0.05]):
            L = 26 - abs(ang) * 12 + (6 if i == 7 else 0)
            ctx.save(); ctx.translate(0, top); ctx.rotate(ang)
            ctx.move_to(-2.4, 0); ctx.curve_to(-2.0, -L * 0.5, -0.6, -L * 0.9, 0, -L)
            ctx.curve_to(0.6, -L * 0.9, 2.0, -L * 0.5, 2.4, 0); ctx.close_path()
            g = cairo.LinearGradient(0, 0, 0, -L)
            g.add_color_stop_rgb(0, 0.15, 0.42, 0.16); g.add_color_stop_rgb(1, 0.38, 0.7, 0.3)
            ctx.set_source(g); ctx.fill_preserve()
            ctx.set_source_rgba(0.05, 0.2, 0.05, 0.6); ctx.set_line_width(0.4); ctx.stroke()
            ctx.restore()


def front_accessory(ctx, cid, c, pts, t):
    shape, a, b = c['shape'], c['w'] / 2, c['h'] / 2
    top = min(p[1] for p in pts)
    leaf = (0.22, 0.6, 0.2)

    def leaf_shape(x, y, L, W, ang, col=leaf):
        ctx.save(); ctx.translate(x, y); ctx.rotate(ang)
        ctx.move_to(0, 0); ctx.curve_to(W, -L * 0.3, W, -L * 0.75, 0, -L)
        ctx.curve_to(-W, -L * 0.75, -W, -L * 0.3, 0, 0); ctx.close_path()
        g = cairo.LinearGradient(-W, 0, W, -L)
        g.add_color_stop_rgb(0, *darken(col, 0.7)); g.add_color_stop_rgb(1, *lighten(col, 0.25))
        ctx.set_source(g); ctx.fill_preserve()
        ctx.set_source_rgba(*darken(col, 0.45), 0.8); ctx.set_line_width(0.4); ctx.stroke()
        ctx.move_to(0, 0); ctx.line_to(0, -L * 0.85)
        ctx.set_source_rgba(*darken(col, 0.5), 0.6); ctx.set_line_width(0.3); ctx.stroke()
        ctx.restore()

    def stem(x, y, L, ang=0.15, col=(0.42, 0.32, 0.15), w=1.3):
        ctx.save(); ctx.translate(x, y); ctx.rotate(ang)
        ctx.move_to(-w / 2, 1); ctx.curve_to(-w / 2, -L * 0.6, w * 0.3, -L * 0.9, w, -L)
        ctx.line_to(w * 1.6, -L + 0.6); ctx.curve_to(w * 0.9, -L * 0.8, w / 2, -L * 0.5, w / 2, 1); ctx.close_path()
        ctx.set_source_rgb(*col); ctx.fill_preserve()
        ctx.set_source_rgba(0, 0, 0, 0.35); ctx.set_line_width(0.3); ctx.stroke()
        ctx.restore()

    sway = 0.06 * math.sin(t * 2.1 + len(cid))
    if shape == 'tomato':
        for k in range(6):
            ang = k * math.pi / 3 + 0.3
            ctx.save(); ctx.translate(0, top + 2.5); ctx.scale(1, 0.45); ctx.rotate(ang)
            ctx.move_to(0, 0); ctx.curve_to(2.5, 3, 3, 9, 0.5, 13); ctx.curve_to(-1, 9, -2.5, 3, 0, 0)
            ctx.restore()
            ctx.set_source_rgb(*leaf); ctx.fill_preserve()
            ctx.set_source_rgba(0.05, 0.3, 0.05, 0.7); ctx.set_line_width(0.35); ctx.stroke()
        stem(0, top + 2.5, 5, 0.25 + sway, col=(0.18, 0.48, 0.15), w=1.4)
    elif shape == 'strawberry':
        for k in range(7):
            ang = -2.0 + k * (4.0 / 6)
            leaf_shape(0, top + 3.0, 8.5 - abs(k - 3) * 0.4, 2.6, ang + sway * (1 if k % 2 else -1))
        stem(0, top + 1.5, 6, 0.1 + sway, col=(0.2, 0.5, 0.15), w=1.2)
    elif shape == 'orange':
        stem(0, top + 1, 3.5, 0.1, w=1.2)
        leaf_shape(0.8, top - 1.8, 12, 3.6, 0.95 + sway)
    elif shape == 'lemon':
        ctx.arc(0, top + 0.8, 1.6, 0, 2 * math.pi); ctx.set_source_rgb(*darken(c['color'], 0.75)); ctx.fill()
        leaf_shape(0.4, top + 0.6, 10, 3.0, 0.7 + sway)
        leaf_shape(-0.4, top + 0.6, 8, 2.6, -0.6 - sway)
    elif shape == 'onion':
        ctx.save(); ctx.translate(0, top + 1)
        ctx.move_to(-1.5, 0); ctx.curve_to(-1.2, -4, 1.5 + sway * 20, -7, 3 + sway * 30, -10)
        ctx.curve_to(1.8 + sway * 20, -6, 1.5, -3, 1.5, 0); ctx.close_path()
        ctx.set_source_rgb(0.82, 0.66, 0.42); ctx.fill_preserve()
        ctx.set_source_rgba(0.4, 0.25, 0.1, 0.6); ctx.set_line_width(0.35); ctx.stroke(); ctx.restore()
    elif shape in ('avocado', 'watermelon'):
        stem(0, top + 0.8, 3.2, 0.3, col=(0.38, 0.28, 0.12), w=1.4)
        if shape == 'watermelon':
            ctx.save(); ctx.translate(1.5, top - 2.2)
            ctx.arc(1.5, 0, 1.5, math.pi, 2.5 * math.pi)
            ctx.set_source_rgb(0.25, 0.5, 0.15); ctx.set_line_width(0.6); ctx.stroke(); ctx.restore()
    elif shape == 'pepper':
        ctx.save(); ctx.translate(-a * 0.1, top + 2.5)
        ctx.save(); ctx.scale(1, 0.4); ctx.arc(0, 0, a * 0.75, 0, 2 * math.pi); ctx.restore()
        ctx.set_source_rgb(0.2, 0.52, 0.16); ctx.fill_preserve()
        ctx.set_source_rgba(0.05, 0.25, 0.05, 0.7); ctx.set_line_width(0.4); ctx.stroke()
        ctx.restore()
        stem(-a * 0.1, top + 1.5, 9, -0.5 + sway, col=(0.2, 0.5, 0.16), w=2.0)
    elif shape == 'cucumber':
        stem(pts[0][0] - 1, top + 1, 3.0, 0.2, col=(0.4, 0.42, 0.18), w=1.6)
    elif shape == 'banana':
        x0 = pts[0][0]
        ctx.save(); ctx.translate(x0 - 0.5, top + 1.5); ctx.rotate(0.25)
        ctx.rectangle(-1.6, -5.5, 3.2, 6.5); ctx.set_source_rgb(0.5, 0.48, 0.2); ctx.fill_preserve()
        ctx.set_source_rgba(0.2, 0.15, 0.05, 0.6); ctx.set_line_width(0.35); ctx.stroke()
        ctx.rectangle(-1.6, -6.3, 3.2, 1.2); ctx.set_source_rgb(0.25, 0.18, 0.08); ctx.fill()
        ctx.restore()
        bx, by = pts[len(pts) // 2]
        ctx.arc(bx, by - 0.5, 1.4, 0, 2 * math.pi); ctx.set_source_rgb(0.25, 0.18, 0.08); ctx.fill()


# ------------------------------------------------------------------ gövde

def body(ctx, cid, c, t, emotion):
    pts, _ = poly(cid)
    a, b = c['w'] / 2, c['h'] / 2
    base = c['color']
    back_accessory(ctx, cid, c)
    path(ctx, pts)
    g = cairo.RadialGradient(-a * 0.35, -b * 0.4, 0, -a * 0.1, -b * 0.1, max(a, b) * 1.35)
    g.add_color_stop_rgb(0, *lighten(base, 0.38))
    g.add_color_stop_rgb(0.42, *base)
    g.add_color_stop_rgb(0.85, *darken(base, 0.68))
    g.add_color_stop_rgb(1, *darken(base, 0.5))
    ctx.set_source(g)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    texture(ctx, cid, c, pts, t)
    # sağ alt kenar: yansıyan sıcak ışık (kenar ışığı)
    rim = cairo.RadialGradient(a * 0.9, b * 0.5, 0, a * 0.9, b * 0.5, max(a, b) * 0.6)
    rim.add_color_stop_rgba(0, 1, 0.95, 0.85, 0.18); rim.add_color_stop_rgba(1, 1, 1, 1, 0)
    ctx.set_source(rim); ctx.paint()
    if emotion == 'angry':   # öfke: kızarma
        ctx.set_source_rgba(0.95, 0.1, 0.05, 0.07 + 0.03 * math.sin(t * 9)); ctx.paint()
    elif emotion == 'shock':
        ctx.set_source_rgba(0.85, 0.9, 1.0, 0.1); ctx.paint()
    # parlama
    ctx.save(); ctx.translate(-a * 0.42, -b * 0.48); ctx.rotate(-0.6); ctx.scale(a * 0.2, b * 0.11)
    hl = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
    hl.add_color_stop_rgba(0, 1, 1, 1, 0.75 if c['shape'] in ('pepper', 'tomato') else 0.5)
    hl.add_color_stop_rgba(1, 1, 1, 1, 0)
    ctx.arc(0, 0, 1, 0, 2 * math.pi); ctx.set_source(hl); ctx.fill(); ctx.restore()
    ctx.restore()
    path(ctx, pts)
    ctx.set_source_rgba(*darken(base, 0.35), 0.55)
    ctx.set_line_width(0.55)
    ctx.stroke()
    front_accessory(ctx, cid, c, pts, t)


# ------------------------------------------------------------------ yüz

INK = (0.14, 0.08, 0.06)


def eye(ctx, x, y, er, c, emo, blink, look, t, side):
    base = c['color']
    lid = darken(base, 0.82)
    rx, ry = er * 0.86, er
    if emo == 'shock':
        rx, ry = er * 0.98, er * 1.12
    closed = blink > 0.5 or emo == 'cry'
    if closed:
        ctx.set_source_rgb(*INK); ctx.set_line_width(0.9); ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.new_path()
        if emo == 'cry':
            ctx.move_to(x - rx, y - 0.5); ctx.curve_to(x - rx * 0.3, y + ry * 0.5, x + rx * 0.3, y + ry * 0.5, x + rx, y - 0.5)
        elif emo == 'happy':
            ctx.move_to(x - rx, y + 1); ctx.curve_to(x - rx * 0.4, y - ry * 0.6, x + rx * 0.4, y - ry * 0.6, x + rx, y + 1)
        else:
            ctx.move_to(x - rx, y); ctx.curve_to(x - rx * 0.3, y + ry * 0.35, x + rx * 0.3, y + ry * 0.35, x + rx, y)
        ctx.stroke()
        # kirpikler
        ctx.set_line_width(0.6)
        for k in (-1, 0, 1):
            ctx.move_to(x + k * rx * 0.45 + side * rx * 0.3, y + ry * 0.2)
            ctx.line_to(x + k * rx * 0.55 + side * rx * 0.55, y + ry * 0.2 + 1.2)
        ctx.stroke()
        return
    # göz akı
    ctx.save(); ctx.translate(x, y); ctx.scale(rx, ry); ctx.arc(0, 0, 1, 0, 2 * math.pi); ctx.restore()
    g = cairo.LinearGradient(x, y - ry, x, y + ry)
    g.add_color_stop_rgb(0, 0.82, 0.82, 0.84); g.add_color_stop_rgb(0.35, 1, 1, 1); g.add_color_stop_rgb(1, 0.93, 0.93, 0.95)
    ctx.set_source(g); ctx.fill_preserve()
    ctx.save(); ctx.clip_preserve()
    # iris + göz bebeği
    ir = er * (0.6 if emo != 'shock' else 0.42)
    pr = ir * (0.5 if emo != 'shock' else 0.42)
    if emo == 'excited':
        pr = ir * 0.62
    lx, ly = look
    px, py = x + lx * rx * 0.32, y + ly * ry * 0.25 + 0.4
    ctx.new_path()
    ig = cairo.RadialGradient(px - ir * 0.2, py - ir * 0.3, ir * 0.1, px, py, ir)
    iris = c['iris']
    ig.add_color_stop_rgb(0, *lighten(iris, 0.5)); ig.add_color_stop_rgb(0.7, *iris); ig.add_color_stop_rgb(1, *darken(iris, 0.4))
    ctx.arc(px, py, ir, 0, 2 * math.pi); ctx.set_source(ig); ctx.fill()
    ctx.arc(px, py, pr, 0, 2 * math.pi); ctx.set_source_rgb(0.03, 0.02, 0.02); ctx.fill()
    ctx.arc(px + ir * 0.35, py - ir * 0.4, ir * 0.3, 0, 2 * math.pi); ctx.set_source_rgba(1, 1, 1, 0.95); ctx.fill()
    ctx.arc(px - ir * 0.35, py + ir * 0.35, ir * 0.13, 0, 2 * math.pi); ctx.fill()
    if emo == 'excited':
        ctx.arc(px - ir * 0.1, py - ir * 0.05, ir * 0.12, 0, 2 * math.pi); ctx.fill()
    # göz kapakları (duyguya göre)
    top = None
    if emo in ('smug', 'suspicious'):
        top = (y - ry * 0.05, y - ry * 0.05) if emo == 'suspicious' else (y - ry * 0.3, y - ry * 0.3)
    elif emo == 'angry':
        top = (y - ry * 0.75, y - ry * 0.25) if side < 0 else (y - ry * 0.25, y - ry * 0.75)
        top = (top[1], top[0]) if side < 0 else top
    elif emo in ('sad', 'nervous'):
        top = (y - ry * 0.4, y - ry * 0.85) if side < 0 else (y - ry * 0.85, y - ry * 0.4)
    elif emo == 'neutral' or emo == 'confused':
        top = (y - ry * 0.82, y - ry * 0.82)
    if blink > 0:
        top = (y + ry * (2 * blink - 1), y + ry * (2 * blink - 1))
    if top:
        ctx.new_path()
        ctx.move_to(x - rx - 1, y - ry - 1); ctx.line_to(x + rx + 1, y - ry - 1)
        ctx.line_to(x + rx + 1, top[1]); ctx.line_to(x - rx - 1, top[0]); ctx.close_path()
        lg = cairo.LinearGradient(x, y - ry, x, max(top))
        lg.add_color_stop_rgb(0, *lighten(lid, 0.2)); lg.add_color_stop_rgb(1, *lid)
        ctx.set_source(lg); ctx.fill()
        ctx.move_to(x - rx - 1, top[0]); ctx.line_to(x + rx + 1, top[1])
        ctx.set_source_rgba(*INK, 0.8); ctx.set_line_width(0.7); ctx.stroke()
    ctx.restore()
    ctx.save(); ctx.translate(x, y); ctx.scale(rx, ry); ctx.arc(0, 0, 1, 0, 2 * math.pi); ctx.restore()
    ctx.set_source_rgba(*INK, 0.85); ctx.set_line_width(0.55); ctx.stroke()
    # üst kirpik çizgisi
    ctx.save(); ctx.translate(x, y); ctx.scale(rx, ry)
    ctx.arc(0, 0, 1, math.pi * 1.1, math.pi * 1.9); ctx.restore()
    ctx.set_line_width(1.0); ctx.stroke()


def brows(ctx, f, er, ex, emo, lvl, t):
    fx, fy = f
    by = fy - er * 1.35 - 1.2 - lvl * 1.4
    if emo == 'shock':
        by -= 2.2
    ctx.set_source_rgb(0.2, 0.11, 0.06)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for side in (-1, 1):
        x = fx + side * ex
        if emo == 'angry':
            inner, outer = by + 2.6, by - 1.6
        elif emo in ('sad', 'cry', 'nervous'):
            inner, outer = by - 2.2, by + 1.2
        elif emo in ('smug', 'suspicious', 'confused'):
            inner, outer = (by, by) if side < 0 else (by - 2.2, by - 2.8)
        elif emo in ('happy', 'excited'):
            inner, outer = by - 0.8, by - 0.6
        else:
            inner, outer = by, by - 0.4
        xi, xo = x - side * er * 0.75, x + side * er * 0.85
        ctx.new_path()
        ctx.move_to(xi, inner)
        mx, my = (xi + xo) / 2, min(inner, outer) - 1.2
        ctx.curve_to(xi + (mx - xi) * 0.6, my, xo - (xo - mx) * 0.6, my, xo, outer)
        ctx.set_line_width(2.2 if emo == 'angry' else 1.8)
        ctx.stroke()


def mouth(ctx, at, w, shape, emo, c):
    x, y = at
    line = darken(c['color'], 0.3)
    inside, tongue = (0.32, 0.04, 0.06), (0.95, 0.42, 0.45)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    if shape == 'closed':
        ctx.new_path()
        ctx.set_source_rgb(*line); ctx.set_line_width(1.1)
        if emo == 'shock':
            ctx.save(); ctx.translate(x, y + 1); ctx.scale(w * 0.3, w * 0.42); ctx.arc(0, 0, 1, 0, 2 * math.pi); ctx.restore()
            ctx.set_source_rgb(*inside); ctx.fill_preserve(); ctx.set_source_rgb(*line); ctx.stroke(); return
        if emo in ('happy', 'excited'):   # açık gülümseme (dişler görünür)
            ctx.move_to(x - w, y - 1); ctx.curve_to(x - w * 0.5, y + w * 0.75, x + w * 0.5, y + w * 0.75, x + w, y - 1)
            ctx.curve_to(x + w * 0.4, y + 0.6, x - w * 0.4, y + 0.6, x - w, y - 1); ctx.close_path()
            ctx.set_source_rgb(*inside); ctx.fill_preserve()
            ctx.save(); ctx.clip()
            ctx.rectangle(x - w, y - 2, 2 * w, 2.4); ctx.set_source_rgb(1, 1, 1); ctx.fill()
            ctx.arc(x, y + w * 0.75, w * 0.45, 0, 2 * math.pi); ctx.set_source_rgb(*tongue); ctx.fill()
            ctx.restore()
            ctx.move_to(x - w, y - 1); ctx.curve_to(x - w * 0.5, y + w * 0.75, x + w * 0.5, y + w * 0.75, x + w, y - 1)
            ctx.curve_to(x + w * 0.4, y + 0.6, x - w * 0.4, y + 0.6, x - w, y - 1); ctx.close_path()
            ctx.set_source_rgb(*line); ctx.stroke(); return
        if emo == 'smug':
            ctx.move_to(x - w * 0.7, y + 0.5); ctx.curve_to(x - w * 0.1, y + 2, x + w * 0.5, y + 1, x + w * 0.85, y - 2)
        elif emo in ('sad', 'cry', 'angry'):
            ctx.move_to(x - w * 0.75, y + 2); ctx.curve_to(x - w * 0.3, y - 1.6, x + w * 0.3, y - 1.6, x + w * 0.75, y + 2)
        elif emo == 'nervous':
            ctx.move_to(x - w * 0.8, y)
            for i in range(1, 7):
                ctx.line_to(x - w * 0.8 + i * w * 0.27, y + (1.0 if i % 2 else -1.0))
        elif emo == 'confused':
            ctx.move_to(x - w * 0.6, y + 1); ctx.curve_to(x - w * 0.2, y - 1, x + w * 0.2, y + 2, x + w * 0.6, y - 0.5)
        else:
            ctx.move_to(x - w * 0.6, y); ctx.curve_to(x - w * 0.2, y + 1.6, x + w * 0.2, y + 1.6, x + w * 0.6, y)
        ctx.stroke()
        return
    mw, mh = {'e': (0.8, 0.32), 'ai': (0.72, 0.62), 'o': (0.45, 0.6), 'u': (0.32, 0.4), 'wide': (0.95, 0.95)}.get(shape, (0.6, 0.45))
    mw, mh = w * mw, w * mh
    if emo in ('angry', 'sad', 'cry') and shape != 'o':
        def outline():
            ctx.new_path()
            ctx.move_to(x - mw, y + mh * 0.4)
            ctx.curve_to(x - mw * 0.5, y - mh * 0.7, x + mw * 0.5, y - mh * 0.7, x + mw, y + mh * 0.4)
            ctx.curve_to(x + mw * 0.6, y + mh * 1.2, x - mw * 0.6, y + mh * 1.2, x - mw, y + mh * 0.4)
            ctx.close_path()
    else:
        def outline():
            ctx.new_path()
            ctx.move_to(x - mw, y - mh * 0.2)
            ctx.curve_to(x - mw * 0.5, y - mh * 0.45, x + mw * 0.5, y - mh * 0.45, x + mw, y - mh * 0.2)
            ctx.curve_to(x + mw * 0.8, y + mh * 1.3, x - mw * 0.8, y + mh * 1.3, x - mw, y - mh * 0.2)
            ctx.close_path()
    outline()
    ctx.set_source_rgb(*inside); ctx.fill_preserve()
    ctx.save(); ctx.clip()
    if shape in ('ai', 'wide', 'o'):
        ctx.save(); ctx.translate(x, y + mh * 1.0); ctx.scale(mw * 0.65, mh * 0.45)
        ctx.arc(0, 0, 1, 0, 2 * math.pi); ctx.restore()
        ctx.set_source_rgb(*tongue); ctx.fill()
    if shape in ('wide', 'e', 'ai'):
        ctx.rectangle(x - mw, y - mh, 2 * mw, mh * 0.75)
        ctx.set_source_rgb(1, 1, 0.97); ctx.fill()
    ctx.restore()
    outline()
    ctx.set_source_rgb(*line); ctx.set_line_width(1.0); ctx.stroke()


def face(ctx, cid, c, G, st):
    emo, t = st['emotion'], st['t']
    fx, fy = G['face']
    er, ex = G['er'], G['ex']
    look = st.get('look', (0.6, 0))
    if emo == 'nervous':
        look = (look[0] + 0.5 * math.sin(t * 30), look[1])
    elif emo == 'sad':
        look = (look[0] * 0.4, 0.8)
    # yanaklar
    for side in (-1, 1):
        cx, cy = fx + side * (ex + er * 0.55), fy + er * 1.05
        g = cairo.RadialGradient(cx, cy, 0, cx, cy, er * 0.85)
        blush = 0.45 if emo in ('happy', 'excited', 'smug') else 0.3
        g.add_color_stop_rgba(0, 1, 0.35, 0.4, blush); g.add_color_stop_rgba(1, 1, 0.35, 0.4, 0)
        ctx.arc(cx, cy, er * 0.85, 0, 2 * math.pi); ctx.set_source(g); ctx.fill()
    for side in (-1, 1):
        eye(ctx, fx + side * ex, fy, er, c, emo, st.get('blink', 0), look, t, side)
    brows(ctx, (fx, fy), er, ex, emo, st.get('lvl', 0), t)
    mouth(ctx, (fx + 0.5, fy + er + 4.2), er * 0.95, st.get('mouth', 'closed'), emo, c)


# ------------------------------------------------------------------ kol / bacak

def pose_targets(cid, pose, t=0.0):
    """Ellerin hedef noktaları (gövde merkezine göre, +x = baktığı yön). -> dict(F, B, hand_F, hand_B, prop)"""
    G = geometry(cid)
    sl, sr, sy = G['sh']
    fx, fy = G['face']
    er = G['er']
    down = sy + 15
    P = {'F': (sr + 7, down), 'B': (sl - 7, down), 'hand_F': 'open', 'hand_B': 'open', 'prop': None}
    if pose == 'hips':
        P.update(F=(sr - 1.5, sy + 9), B=(sl + 1.5, sy + 9), hand_F='fist', hand_B='fist')
    elif pose == 'arms_crossed':
        P.update(F=(fx - 7, sy + 6), B=(fx + 8, sy + 5))
    elif pose == 'pointing':
        P.update(F=(sr + 19, sy - 4), hand_F='point')
    elif pose == 'shrug':
        P.update(F=(sr + 11, sy - 5), B=(sl - 11, sy - 5))
    elif pose == 'celebrate':
        P.update(F=(sr + 8, sy - 24), B=(sl - 8, sy - 24), hand_F='fist', hand_B='fist')
    elif pose == 'facepalm':
        P.update(F=(fx + 2, fy + 1))
    elif pose == 'thinking':
        P.update(F=(fx + 3, fy + er + 8), B=(sl + 1.5, sy + 9), hand_F='fist', hand_B='fist')
    elif pose == 'phone':
        P.update(F=(sr + 12, sy - 12), prop='phone')
    elif pose == 'fist':
        P.update(F=(sr + 9, sy - 16 + 2 * math.sin(t * 18)), B=(sl + 1.5, sy + 9), hand_F='fist', hand_B='fist')
    elif pose == 'crying':
        P.update(F=(fx + G['ex'] + 1, fy + 1), B=(fx - G['ex'] - 1, fy + 1), hand_F='fist', hand_B='fist')
    elif pose == 'wave':
        P.update(F=(sr + 11 + 3 * math.sin(t * 12), sy - 20))
    return P


def limb(ctx, a, b, length, bend, col, w=LIMB_W):
    """Lastik hortum kol/bacak: a'dan b'ye, boyu sabit kalacak şekilde bükülür."""
    (x0, y0), (x1, y1) = a, b
    d = math.hypot(x1 - x0, y1 - y0) or 0.01
    sag = math.sqrt(max(0.0, (length / 2) ** 2 - (d / 2) ** 2)) * bend
    nx, ny = -(y1 - y0) / d, (x1 - x0) / d
    cx, cy = (x0 + x1) / 2 + nx * sag, (y0 + y1) / 2 + ny * sag
    ctx.new_path()
    ctx.move_to(x0, y0); ctx.curve_to(x0 + (cx - x0) * 0.66, y0 + (cy - y0) * 0.66,
                                      x1 + (cx - x1) * 0.66, y1 + (cy - y1) * 0.66, x1, y1)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgb(*darken(col, 0.55)); ctx.set_line_width(w + 0.7); ctx.stroke_preserve()
    ctx.set_source_rgb(*col); ctx.set_line_width(w); ctx.stroke()


def hand(ctx, x, y, kind, col, ang=0.0):
    ctx.save(); ctx.translate(x, y); ctx.rotate(ang)
    edge = darken(col, 0.55)
    if kind == 'point':
        ctx.move_to(0, 0); ctx.line_to(5.2, -0.6)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgb(*edge); ctx.set_line_width(2.3); ctx.stroke_preserve()
        ctx.set_source_rgb(*col); ctx.set_line_width(1.6); ctx.stroke()
    r = 2.7 if kind != 'fist' else 2.5
    ctx.arc(0, 0, r, 0, 2 * math.pi)
    g = cairo.RadialGradient(-0.8, -0.8, 0.2, 0, 0, r)
    g.add_color_stop_rgb(0, *lighten(col, 0.3)); g.add_color_stop_rgb(1, *col)
    ctx.set_source(g); ctx.fill_preserve()
    ctx.set_source_rgb(*edge); ctx.set_line_width(0.5); ctx.stroke()
    if kind == 'open':   # başparmak
        ctx.arc(-1.2, -2.2, 1.1, 0, 2 * math.pi)
        ctx.set_source_rgb(*col); ctx.fill_preserve(); ctx.set_source_rgb(*edge); ctx.set_line_width(0.4); ctx.stroke()
    ctx.restore()


def phone(ctx, x, y, t):
    ctx.save(); ctx.translate(x, y - 3); ctx.rotate(-0.2)
    from .render_util import rrect
    rrect(ctx, -2.8, -5, 5.6, 9.5, 1.2)
    ctx.set_source_rgb(0.1, 0.1, 0.12); ctx.fill()
    rrect(ctx, -2.3, -4.4, 4.6, 8.2, 0.8)
    g = cairo.LinearGradient(0, -4, 0, 4)
    g.add_color_stop_rgb(0, 0.5, 0.75, 1.0); g.add_color_stop_rgb(1, 0.9, 0.5, 0.9)
    ctx.set_source(g); ctx.fill()
    ctx.restore()


def legs(ctx, c, G, st):
    a = c['w'] / 2
    col = c['limb']
    hl, hr, hy = G['hip']
    xs = (hl * 0.45, hr * 0.45)
    walk = st.get('walk')
    for i, hx in enumerate(xs):
        ph = 0.0
        if walk is not None:
            ph = math.sin(walk + i * math.pi)
        foot = (hx + ph * 5 + (1.5 if i else -0.5), -max(0.0, -ph) * 3)
        hip = (hx, -LEG - TUCK + 0.5)
        limb(ctx, hip, (foot[0], foot[1] - 1.2), LEG + 1.5, 1 if i else -1, col, LIMB_W + 0.3)
        # ayak (baktığı yöne doğru uzun)
        ctx.save(); ctx.translate(foot[0] + 1.3, foot[1] - 1.1); ctx.scale(3.4, 1.7)
        ctx.arc(0, 0, 1, 0, 2 * math.pi); ctx.restore()
        g = cairo.LinearGradient(0, foot[1] - 3, 0, foot[1])
        g.add_color_stop_rgb(0, *lighten(col, 0.25)); g.add_color_stop_rgb(1, *darken(col, 0.8))
        ctx.set_source(g); ctx.fill_preserve()
        ctx.set_source_rgb(*darken(col, 0.5)); ctx.set_line_width(0.5); ctx.stroke()


# ------------------------------------------------------------------ efektler

def fx_overlay(ctx, c, G, st):
    emo, t = st['emotion'], st['t']
    fx, fy = G['face']
    er, ex = G['er'], G['ex']
    top = G['top']
    a = c['w'] / 2
    if emo == 'cry':
        for side in (-1, 1):
            x = fx + side * ex
            ctx.new_path()
            ctx.move_to(x - 1.2, fy + 0.5)
            ctx.curve_to(x - 1.5 + side, fy + 8, x - 1 + side * 2, fy + 16, x + side * 2.5, fy + 24)
            ctx.line_to(x + side * 2.5 + 2.2, fy + 24)
            ctx.curve_to(x + 1 + side * 2, fy + 16, x + 1.5 + side, fy + 8, x + 1.2, fy + 0.5)
            ctx.close_path()
            ctx.set_source_rgba(0.45, 0.75, 1.0, 0.85); ctx.fill()
            for k in range(2):
                p = ((t * 1.6 + k * 0.5 + (0.25 if side > 0 else 0)) % 1)
                drop(ctx, x + side * (3 + p * 8), fy + 4 + p * 26, 1.3)
    elif emo == 'nervous':
        p = (t * 0.7) % 1
        drop(ctx, fx + a * 0.75, top + 10 + p * 10, 2.2, alpha=1 - p * 0.6)
    elif emo == 'angry':
        for k in range(3):
            p = ((t * 0.9 + k / 3) % 1)
            x = fx + (k - 1) * 9 + math.sin(p * 6 + k) * 2
            y = top - 4 - p * 16
            ctx.arc(x, y, 2.4 + p * 3.5, 0, 2 * math.pi)
            ctx.set_source_rgba(1, 1, 1, 0.75 * (1 - p)); ctx.fill()
        vein(ctx, fx + a * 0.55, top + 9, 3.2)
    elif emo == 'confused':
        q_mark(ctx, fx + a * 0.7, top - 4 + math.sin(t * 3) * 1.5)
    if st.get('dizzy'):
        for k in range(4):
            ang = t * 4 + k * math.pi / 2
            star(ctx, fx + math.cos(ang) * a * 0.7, top - 4 + math.sin(ang) * 3, 2.4)
    if emo == 'excited':
        for k in range(3):
            p = ((t * 0.8 + k / 3) % 1)
            sparkle(ctx, fx + (k - 1) * a * 0.8, top - 2 - p * 8, 2.2 * math.sin(math.pi * p))


def drop(ctx, x, y, r, alpha=0.9):
    ctx.new_path()
    ctx.move_to(x, y - r * 1.8)
    ctx.curve_to(x + r * 0.2, y - r, x + r, y - r * 0.2, x + r, y + r * 0.3)
    ctx.arc(x, y + r * 0.3, r, 0, math.pi)
    ctx.curve_to(x - r, y - r * 0.2, x - r * 0.2, y - r, x, y - r * 1.8)
    ctx.close_path()
    ctx.set_source_rgba(0.55, 0.82, 1.0, alpha); ctx.fill_preserve()
    ctx.set_source_rgba(0.2, 0.45, 0.8, alpha); ctx.set_line_width(0.35); ctx.stroke()


def vein(ctx, x, y, r):
    ctx.set_source_rgb(0.9, 0.1, 0.1); ctx.set_line_width(1.0); ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for k in range(4):
        ang = k * math.pi / 2 + math.pi / 4
        cx, cy = x + math.cos(ang) * r, y + math.sin(ang) * r
        ctx.new_path(); ctx.arc(cx, cy, r * 0.7, ang + math.pi * 0.6, ang + math.pi * 1.4); ctx.stroke()


def star(ctx, x, y, r):
    ctx.new_path()
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        ctx.line_to(x + rr * math.cos(a), y + rr * math.sin(a))
    ctx.close_path()
    ctx.set_source_rgb(1, 0.88, 0.15); ctx.fill_preserve()
    ctx.set_source_rgb(0.5, 0.35, 0); ctx.set_line_width(0.35); ctx.stroke()


def sparkle(ctx, x, y, r):
    if r <= 0.05:
        return
    ctx.new_path()
    for i in range(8):
        a = i * math.pi / 4
        rr = r if i % 2 == 0 else r * 0.25
        ctx.line_to(x + rr * math.cos(a), y + rr * math.sin(a))
    ctx.close_path(); ctx.set_source_rgba(1, 1, 0.75, 0.95); ctx.fill()


def q_mark(ctx, x, y):
    ctx.save(); ctx.translate(x, y)
    ctx.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(12)
    ctx.move_to(-3, 4); ctx.text_path('?')
    ctx.set_source_rgb(1, 1, 1); ctx.fill_preserve()
    ctx.set_source_rgb(0.15, 0.15, 0.2); ctx.set_line_width(0.6); ctx.stroke()
    ctx.restore()


# ------------------------------------------------------------------ ana çizim

def shadow(ctx, cid, x, ground, s, lift=0.0):
    c = CAST[cid]
    rx = c['w'] * 0.55 * s * c['scale'] * (1 - min(0.5, lift / 60))
    ctx.save(); ctx.translate(x, ground + 0.3 * s); ctx.scale(rx, 3.6 * s * c['scale'])
    g = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
    g.add_color_stop_rgba(0, 0, 0, 0, 0.42); g.add_color_stop_rgba(1, 0, 0, 0, 0)
    ctx.arc(0, 0, 1, 0, 2 * math.pi); ctx.set_source(g); ctx.fill(); ctx.restore()


def draw(ctx, cid, x, ground, s, facing, st):
    """st: emotion, mouth, blink, t, lvl, look, hands{F,B}, hand_kinds, prop, tilt (derece), lift, fall (0-1),
    squash, dizzy, walk, spin"""
    c = CAST[cid]
    G = geometry(cid)
    k = s * c['scale']
    shadow(ctx, cid, x, ground, s, st.get('lift', 0))
    ctx.save()
    ctx.translate(x, ground - st.get('lift', 0) * k)
    ctx.scale(k * facing * st.get('spin', 1.0), k)
    fall = st.get('fall', 0.0)
    if fall:
        ctx.rotate(-fall * math.pi / 2 * 0.92)
    ctx.rotate(math.radians(st.get('tilt', 0)))
    sq = st.get('squash', 1.0)
    ctx.scale(1 / math.sqrt(sq), sq)
    legs(ctx, c, G, st)
    cy = -(LEG + TUCK) - c['h'] / 2 + 1
    breath = st.get('breath', 1.0)
    ctx.translate(0, cy)
    ctx.scale(1 / breath, breath)
    sl, sr, sy = G['sh']
    hands = st.get('hands') or {}
    kinds = st.get('hand_kinds') or {}
    HF = hands.get('F', (sr + 7, sy + 15)); HB = hands.get('B', (sl - 7, sy + 15))
    # arka kol gövdenin arkasında
    limb(ctx, (sl + 1.5, sy), HB, ARM_LEN, 1, c['limb'])
    hand(ctx, *HB, kinds.get('B', 'open'), c['limb'])
    body(ctx, cid, c, st['t'], st['emotion'])
    face(ctx, cid, c, G, st)
    limb(ctx, (sr - 1.5, sy), HF, ARM_LEN, -1, c['limb'])
    hand(ctx, *HF, kinds.get('F', 'open'), c['limb'])
    if st.get('prop') == 'phone':
        phone(ctx, HF[0], HF[1], st['t'])
    fx_overlay(ctx, c, G, st)
    ctx.restore()


def body_top(cid, ground, s):
    """Karakterin başının ekran y'si (kamera için)."""
    c = CAST[cid]
    G = geometry(cid)
    cy = -(LEG + TUCK) - c['h'] / 2 + 1
    return ground + (cy + G['face'][1]) * s * c['scale'], ground + (cy + G['top']) * s * c['scale']
