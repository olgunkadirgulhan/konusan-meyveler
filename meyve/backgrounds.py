"""Arka planlar: uzak katman (çok bulanık, alan derinliği) + yakın yüzey (az bulanık) + vinyet.

Meyveler hep bir yüzeyin üstünde durur (tezgâh, raf, tahta...). Zemin çizgisi = ground.
Her video için hafif renk/ışık kayması: aynı sahne bile birebir tekrar etmez.
"""
import colorsys
import math
import random

import cairo
import numpy as np
from PIL import Image, ImageFilter

from .render_util import rrect

NAMES = ['kitchen', 'fridge', 'market', 'cutting_board', 'table', 'garden', 'beach', 'blender']


class P:
    def __init__(self, ctx, W, H, g, rnd):
        self.c, self.W, self.H, self.g, self.r = ctx, W, H, g, rnd
        self.hue = rnd.uniform(-0.03, 0.03)
        self.u = min(W, H) / 100.0

    def col(self, rgb):
        h, l, s = colorsys.rgb_to_hls(*rgb)
        return colorsys.hls_to_rgb((h + self.hue) % 1, l, s)

    def rect(self, x, y, w, h, rgb, r=0, a=1.0):
        if r:
            rrect(self.c, x, y, w, h, r)
        else:
            self.c.rectangle(x, y, w, h)
        self.c.set_source_rgba(*self.col(rgb), a); self.c.fill()

    def circle(self, x, y, r, rgb, a=1.0):
        self.c.arc(x, y, r, 0, 2 * math.pi); self.c.set_source_rgba(*self.col(rgb), a); self.c.fill()

    def vgrad(self, y0, y1, top, bottom, x0=0, x1=None):
        g = cairo.LinearGradient(0, y0, 0, y1)
        g.add_color_stop_rgb(0, *self.col(top)); g.add_color_stop_rgb(1, *self.col(bottom))
        self.c.rectangle(x0, y0, (x1 if x1 is not None else self.W) - x0, y1 - y0); self.c.set_source(g); self.c.fill()

    def glow(self, x, y, r, rgb, a):
        g = cairo.RadialGradient(x, y, 0, x, y, r)
        g.add_color_stop_rgba(0, *rgb, a); g.add_color_stop_rgba(1, *rgb, 0)
        self.c.arc(x, y, r, 0, 2 * math.pi); self.c.set_source(g); self.c.fill()

    def bokeh(self, n, y0, y1, colors, rmin, rmax, a=0.5):
        for _ in range(n):
            self.circle(self.r.uniform(0, self.W), self.r.uniform(y0, y1), self.r.uniform(rmin, rmax) * self.u,
                        self.r.choice(colors), a * self.r.uniform(0.5, 1))

    def fruit_blob(self, x, y, r, rgb):
        g = cairo.RadialGradient(x - r * 0.35, y - r * 0.35, r * 0.1, x, y, r)
        c = self.col(rgb)
        g.add_color_stop_rgb(0, *[v + (1 - v) * 0.4 for v in c]); g.add_color_stop_rgb(1, *[v * 0.6 for v in c])
        self.c.arc(x, y, r, 0, 2 * math.pi); self.c.set_source(g); self.c.fill()


FRUITS = [(1, 0.55, 0.1), (0.95, 0.2, 0.15), (1, 0.85, 0.2), (0.4, 0.7, 0.25), (0.6, 0.2, 0.5), (1, 0.4, 0.5)]


# ------------------------------------------------------------------ uzak katmanlar (çizilip çok bulanıklaşır)

def far_kitchen(p, blender=False):
    u, g, W = p.u, p.g, p.W
    p.vgrad(0, g, (0.93, 0.88, 0.8), (0.82, 0.74, 0.64))
    for x in np.arange(0, W, u * 9):            # fayans
        for y in np.arange(g - u * 48, g - u * 4, u * 9):
            p.rect(x + u * 0.3, y + u * 0.3, u * 8.4, u * 8.4, (0.95, 0.94, 0.9), r=u * 0.6)
    p.rect(0, 0, W, g - u * 52, (0.55, 0.38, 0.25))          # üst dolaplar
    for x in np.arange(u * 2, W, u * 26):
        p.rect(x, u * 4, u * 24, g - u * 60, (0.63, 0.45, 0.3), r=u)
        p.rect(x + u * 20, (g - u * 60) * 0.55, u * 1.2, u * 7, (0.85, 0.8, 0.7), r=u * 0.5)
    wx = p.r.uniform(0.15, 0.55) * W                           # pencere ışığı
    p.rect(wx, g - u * 46, u * 30, u * 30, (1, 0.97, 0.85))
    p.glow(wx + u * 15, g - u * 30, u * 45, (1, 0.95, 0.8), 0.55)
    p.rect(wx + u * 14.5, g - u * 46, u, u * 30, (0.8, 0.75, 0.65))
    for i in range(3):                                         # tezgâh arkasında kavanoz / şişe siluetleri
        x = p.r.uniform(0, W)
        p.rect(x, g - u * (14 + 6 * i), u * 7, u * (14 + 6 * i), p.r.choice([(0.45, 0.6, 0.5), (0.8, 0.5, 0.3), (0.9, 0.9, 0.85)]), r=u * 1.5)
    if blender:
        x = W * 0.7
        p.rect(x - u * 8, g - u * 12, u * 16, u * 12, (0.2, 0.2, 0.22), r=u * 2)
        p.c.move_to(x - u * 9, g - u * 12); p.c.line_to(x + u * 9, g - u * 12); p.c.line_to(x + u * 7, g - u * 48)
        p.c.line_to(x - u * 7, g - u * 48); p.c.close_path(); p.c.set_source_rgba(0.85, 0.92, 0.95, 0.75); p.c.fill()
        p.rect(x - u * 8, g - u * 52, u * 16, u * 5, (0.15, 0.15, 0.17), r=u)
        p.circle(x, g - u * 6, u * 2, (0.9, 0.2, 0.2))


def far_fridge(p):
    u, g, W = p.u, p.g, p.W
    p.vgrad(0, p.H, (0.9, 0.95, 1.0), (0.75, 0.84, 0.92))
    p.glow(W / 2, 0, u * 90, (1, 1, 1), 0.9)
    for y in (g - u * 55, g - u * 110):                       # üst raflar ve üstlerindeki şeyler
        p.rect(0, y, W, u * 1.6, (0.85, 0.93, 0.98), a=0.9)
        for i in range(5):
            x = p.r.uniform(0, W); h = p.r.uniform(10, 26) * u
            kind = p.r.random()
            if kind < 0.4:
                p.rect(x, y - h, u * 8, h, p.r.choice([(1, 1, 1), (0.95, 0.85, 0.4), (0.9, 0.3, 0.3)]), r=u * 2)
            elif kind < 0.7:
                p.fruit_blob(x, y - u * 6, u * 6, p.r.choice(FRUITS))
            else:
                p.rect(x, y - u * 8, u * 16, u * 8, (0.95, 0.9, 0.8), r=u)
    for x in (u * 2, W - u * 3):
        p.rect(x, 0, u * 1.2, p.H, (0.8, 0.88, 0.95))


def far_market(p):
    u, g, W = p.u, p.g, p.W
    p.vgrad(0, g, (0.7, 0.85, 0.98), (0.95, 0.9, 0.8))
    for i, x in enumerate(np.arange(-u * 5, W + u * 10, u * 14)):   # tente
        p.c.move_to(x, 0); p.c.line_to(x + u * 14, 0); p.c.line_to(x + u * 14, u * 22)
        p.c.curve_to(x + u * 10, u * 27, x + u * 4, u * 27, x, u * 22); p.c.close_path()
        p.c.set_source_rgb(*p.col((0.9, 0.2, 0.2) if i % 2 else (1, 1, 1))); p.c.fill()
    for row in range(3):                                          # kasa kasa meyve
        y = g - u * (12 + row * 17)
        for x in np.arange(-u * 3, W, u * 22):
            p.rect(x, y, u * 20, u * 12, (0.7, 0.5, 0.3), r=u * 0.6)
            colr = p.r.choice(FRUITS)
            for k in range(6):
                p.fruit_blob(x + u * (3 + k * 3), y - u * 1 + p.r.uniform(-1, 1) * u, u * 3.2, colr)
    p.bokeh(25, 0, g, [(1, 1, 0.9), (1, 0.9, 0.6)], 2, 6, 0.35)


def far_table(p):
    u, g, W = p.u, p.g, p.W
    p.vgrad(0, g, (0.98, 0.9, 0.78), (0.85, 0.75, 0.62))
    wx = W * p.r.uniform(0.2, 0.6)
    p.rect(wx, g - u * 75, u * 40, u * 50, (1, 0.98, 0.9))
    p.glow(wx + u * 20, g - u * 50, u * 60, (1, 0.95, 0.8), 0.6)
    p.rect(wx - u * 6, g - u * 78, u * 10, u * 58, (0.85, 0.35, 0.3), r=u)   # perde
    p.rect(wx + u * 36, g - u * 78, u * 10, u * 58, (0.85, 0.35, 0.3), r=u)
    p.rect(W * 0.05, g - u * 30, u * 3, u * 25, (0.4, 0.28, 0.2))           # sandalye
    p.rect(W * 0.8, g - u * 30, u * 3, u * 25, (0.4, 0.28, 0.2))
    p.bokeh(12, 0, g, [(1, 0.95, 0.8)], 2, 5, 0.35)


def far_garden(p):
    u, g, W = p.u, p.g, p.W
    p.vgrad(0, g, (0.55, 0.78, 0.98), (0.8, 0.92, 0.85))
    for i in range(14):
        p.circle(p.r.uniform(0, W), g - p.r.uniform(15, 55) * u, p.r.uniform(10, 22) * u,
                 p.r.choice([(0.3, 0.6, 0.25), (0.4, 0.7, 0.3), (0.25, 0.5, 0.2)]))
    p.rect(W * 0.12, g - u * 60, u * 7, u * 60, (0.45, 0.32, 0.2))
    for i in range(8):
        p.fruit_blob(p.r.uniform(0, W), g - p.r.uniform(30, 60) * u, u * 2.6, (1, 0.5, 0.1))
    p.bokeh(30, 0, g, [(1, 1, 0.85), (0.9, 1, 0.8)], 1.5, 5, 0.45)


def far_beach(p):
    u, g, W = p.u, p.g, p.W
    p.vgrad(0, g - u * 22, (0.35, 0.65, 0.98), (0.75, 0.9, 1.0))
    p.circle(W * 0.78, g - u * 70, u * 10, (1, 0.97, 0.8))
    p.glow(W * 0.78, g - u * 70, u * 30, (1, 0.95, 0.7), 0.6)
    p.vgrad(g - u * 22, g - u * 6, (0.1, 0.55, 0.75), (0.3, 0.75, 0.85))
    for i in range(6):
        p.rect(p.r.uniform(0, W), g - u * p.r.uniform(8, 20), u * p.r.uniform(8, 20), u * 0.5, (1, 1, 1), a=0.7)
    x = W * 0.15                                              # palmiye
    p.c.move_to(x, g); p.c.curve_to(x + u * 3, g - u * 30, x + u * 8, g - u * 50, x + u * 12, g - u * 62)
    p.c.set_source_rgb(*p.col((0.5, 0.35, 0.2))); p.c.set_line_width(u * 3); p.c.stroke()
    for a in range(6):
        ang = a * math.pi / 3 + 0.3
        p.c.save(); p.c.translate(x + u * 12, g - u * 62); p.c.rotate(ang); p.c.scale(1, 0.3)
        p.c.arc(u * 12, 0, u * 12, 0, 2 * math.pi); p.c.restore()
        p.c.set_source_rgb(*p.col((0.2, 0.6, 0.25))); p.c.fill()


# ------------------------------------------------------------------ yakın yüzeyler (az bulanık)

def surface(p, kind):
    u, g, W, H = p.u, p.g, p.W, p.H
    top = g - u * 8
    if kind in ('kitchen', 'blender', 'market'):
        base = (0.92, 0.9, 0.87) if kind != 'market' else (0.72, 0.52, 0.32)
        p.vgrad(top, H, base, tuple(v * 0.78 for v in base))
        if kind == 'market':                                  # tahta
            for y in np.arange(top, H, u * 7):
                p.rect(0, y, W, u * 0.35, (0.45, 0.3, 0.18), a=0.6)
        else:                                                 # mermer damarları
            for _ in range(9):
                x = p.r.uniform(0, W); y = p.r.uniform(top, H)
                p.c.move_to(x, y)
                for k in range(5):
                    x += p.r.uniform(-8, 14) * u; y += p.r.uniform(-2, 5) * u
                    p.c.line_to(x, y)
                p.c.set_source_rgba(0.55, 0.55, 0.6, 0.25); p.c.set_line_width(u * 0.3); p.c.stroke()
        p.rect(0, top, W, u * 0.8, (1, 1, 1), a=0.6)
    elif kind == 'fridge':
        p.vgrad(top, H, (0.85, 0.93, 0.98), (0.65, 0.78, 0.88))
        p.rect(0, top, W, u * 1.2, (1, 1, 1), a=0.85)            # cam raf kenarı
        for _ in range(40):                                    # buğu damlaları
            p.circle(p.r.uniform(0, W), p.r.uniform(top + u * 3, H), p.r.uniform(0.2, 0.6) * u, (1, 1, 1), 0.45)
    elif kind == 'cutting_board':
        p.vgrad(top - u * 2, H, (0.9, 0.88, 0.85), (0.7, 0.68, 0.66))
        rrect(p.c, -u * 5, top, W + u * 10, H - top + u * 10, u * 6)
        p.c.set_source_rgb(*p.col((0.78, 0.55, 0.32))); p.c.fill()
        for y in np.arange(top + u * 3, H, u * 3.5):
            p.c.move_to(0, y)
            p.c.curve_to(W * 0.3, y + p.r.uniform(-1, 1) * u, W * 0.7, y + p.r.uniform(-1, 1) * u, W, y)
            p.c.set_source_rgba(0.5, 0.32, 0.15, 0.35); p.c.set_line_width(u * 0.25); p.c.stroke()
        x0, y0 = W * 0.06, H - u * 10                          # kenarda büyük bıçak
        p.c.save(); p.c.translate(x0, y0); p.c.rotate(-0.12)
        p.c.move_to(0, 0); p.c.line_to(u * 55, -u * 2); p.c.curve_to(u * 62, -u * 2, u * 64, u * 3, u * 60, u * 5)
        p.c.line_to(0, u * 5); p.c.close_path()
        gr = cairo.LinearGradient(0, -u * 2, 0, u * 5)
        gr.add_color_stop_rgb(0, 0.95, 0.96, 0.98); gr.add_color_stop_rgb(1, 0.6, 0.62, 0.66)
        p.c.set_source(gr); p.c.fill()
        rrect(p.c, -u * 26, -u * 1, u * 27, u * 7, u * 2); p.c.set_source_rgb(0.12, 0.1, 0.1); p.c.fill()
        p.c.restore()
    elif kind == 'table':
        p.vgrad(top, H, (0.95, 0.95, 0.95), (0.8, 0.8, 0.8))
        sq = u * 8
        for i, x in enumerate(np.arange(0, W, sq)):           # kareli örtü (perspektifsiz, sade)
            for j, y in enumerate(np.arange(top, H, sq)):
                if (i + j) % 2 == 0:
                    p.rect(x, y, sq, sq, (0.85, 0.2, 0.2), a=0.8)
    elif kind == 'garden':
        p.vgrad(top, H, (0.45, 0.7, 0.3), (0.3, 0.5, 0.2))
        for _ in range(260):
            x = p.r.uniform(0, W); y = p.r.uniform(top, H)
            p.c.move_to(x, y); p.c.line_to(x + p.r.uniform(-1, 1) * u, y - p.r.uniform(1.5, 3.5) * u)
        p.c.set_source_rgba(*p.col((0.25, 0.55, 0.2)), 0.8); p.c.set_line_width(u * 0.35); p.c.stroke()
    elif kind == 'beach':
        p.vgrad(top, H, (0.98, 0.88, 0.65), (0.88, 0.74, 0.5))
        for _ in range(300):
            p.circle(p.r.uniform(0, W), p.r.uniform(top, H), 0.25 * u, (0.7, 0.55, 0.35), 0.5)


FAR = {'kitchen': far_kitchen, 'blender': lambda p: far_kitchen(p, blender=True), 'fridge': far_fridge,
       'market': far_market, 'cutting_board': far_kitchen, 'table': far_table, 'garden': far_garden,
       'beach': far_beach}


def _layer(W, H, fn):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    fn(cairo.Context(surf))
    surf.flush()
    arr = np.ndarray((H, W, 4), np.uint8, surf.get_data()).copy()
    return Image.fromarray(arr[:, :, [2, 1, 0, 3]], 'RGBA')


def render(name, W, H, ground, seed=0):
    """cairo.ImageSurface döndürür."""
    name = name if name in FAR else 'kitchen'
    rnd = random.Random(seed)
    far = _layer(W, H, lambda c: FAR[name](P(c, W, H, ground, rnd)))
    far = far.filter(ImageFilter.GaussianBlur(min(W, H) / 70))
    near = _layer(W, H, lambda c: surface(P(c, W, H, ground, rnd), name))
    near = near.filter(ImageFilter.GaussianBlur(min(W, H) / 600))
    img = Image.alpha_composite(far.convert('RGBA'), near).convert('RGB')
    a = np.asarray(img).astype(np.float32)
    # sıcak ışık + vinyet
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.55) / (H * 0.7)) ** 2)
    a *= np.clip(1.08 - 0.45 * d ** 2, 0.55, 1.05)[:, :, None]
    a = np.clip(a, 0, 255).astype(np.uint8)
    out = np.empty((H, W, 4), np.uint8)
    out[:, :, 0], out[:, :, 1], out[:, :, 2], out[:, :, 3] = a[:, :, 2], a[:, :, 1], a[:, :, 0], 255
    return cairo.ImageSurface.create_for_data(memoryview(out), cairo.FORMAT_ARGB32, W, H, W * 4)
