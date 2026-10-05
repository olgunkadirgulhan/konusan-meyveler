"""Kanal görselleri: banner (2560x1440), profil (800x800), filigran (150x150) -> branding/

    python branding.py
"""
import math
import sys
from pathlib import Path

import cairo
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from meyve import fruit  # noqa: E402
from meyve.render import pil_to_surface, text_block, tr_upper  # noqa: E402

OUT = HERE / 'branding'


def rays(ctx, W, H, cx, cy, c1, c2, n=18):
    ctx.set_source_rgb(*c1); ctx.paint()
    ctx.save(); ctx.translate(cx, cy)
    for i in range(n):
        a = i * 2 * math.pi / n
        ctx.move_to(0, 0); ctx.arc(0, 0, max(W, H) * 1.5, a, a + math.pi / n); ctx.close_path()
    ctx.set_source_rgb(*c2); ctx.fill(); ctx.restore()


def character(ctx, cid, x, ground, s, facing, emotion, pose, mouth='closed', look=(0, 0)):
    P = fruit.pose_targets(cid, pose)
    st = dict(emotion=emotion, mouth=mouth, blink=0, t=0.3, lvl=0.6 if mouth != 'closed' else 0, look=look,
              hands={'F': P['F'], 'B': P['B']}, hand_kinds={'F': P['hand_F'], 'B': P['hand_B']}, prop=P['prop'],
              tilt=0, lift=0, fall=0, squash=1.0, dizzy=False, walk=0, spin=1.0, breath=1.0)
    fruit.draw(ctx, cid, x, ground, s, facing, st)


def paste_text(ctx, text, size, cx, cy, maxw, color=(255, 255, 255)):
    surf = pil_to_surface(text_block(tr_upper(text).split(), size, maxw, color=color))
    ctx.set_source_surface(surf, cx - surf.get_width() / 2, cy - surf.get_height() / 2)
    ctx.paint()


def banner():
    W, H = 2560, 1440
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    rays(ctx, W, H, W / 2, H / 2, (1.0, 0.55, 0.1), (1.0, 0.64, 0.2), 22)
    # tezgâh (güvenli alanın altı)
    ground = 925
    ctx.rectangle(0, ground - 8, W, H - ground + 8); ctx.set_source_rgb(0.96, 0.93, 0.86); ctx.fill()
    ctx.rectangle(0, ground - 8, W, 10); ctx.set_source_rgb(0.42, 0.28, 0.18); ctx.fill()
    s = 3.4
    cast = [('karpuz', 200, 1, 'happy', 'celebrate', 'ai'), ('domates', 440, 1, 'angry', 'hips', 'closed'),
            ('limon', 660, 1, 'smug', 'arms_crossed', 'closed'),
            ('portakal', 1900, -1, 'excited', 'pointing', 'ai'), ('biber', 2130, -1, 'suspicious', 'hips', 'closed'),
            ('avokado', 2370, -1, 'shock', 'shrug', 'o')]
    for cid, x, f, emo, pose, mouth in cast:
        character(ctx, cid, x, ground, s, f, emo, pose, mouth)
    paste_text(ctx, 'Konuşan Fruits', 190, W / 2, 630, 1300, color=(255, 236, 80))
    paste_text(ctx, 'Her gün yeni meyve kavgası', 62, W / 2, 805, 1300)
    surf.write_to_png(str(OUT / 'banner.png'))


def head_shot(cid, size, bg1, bg2, emotion='happy', ring=True):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surf)
    rays(ctx, size, size, size / 2, size / 2, bg1, bg2, 16)
    s = size / 78
    face_y, _ = fruit.body_top(cid, 0, s)            # yüzün zemine göre yüksekliği (negatif)
    character(ctx, cid, size / 2, size * 0.52 - face_y, s, 1, emotion, 'standing', 'ai', look=(0.2, 0))
    if ring:
        ctx.arc(size / 2, size / 2, size / 2 - size * 0.02, 0, 2 * math.pi)
        ctx.set_source_rgb(0.12, 0.1, 0.08); ctx.set_line_width(size * 0.035); ctx.stroke()
    return surf


def main():
    OUT.mkdir(exist_ok=True)
    banner()
    head_shot('limon', 800, (0.18, 0.62, 0.32), (0.26, 0.72, 0.4), emotion='excited').write_to_png(str(OUT / 'profile.png'))
    wm = head_shot('limon', 300, (0.9, 0.12, 0.15), (0.97, 0.25, 0.25), emotion='excited')
    wm.write_to_png(str(OUT / 'watermark.png'))
    Image.open(OUT / 'watermark.png').resize((150, 150), Image.LANCZOS).save(OUT / 'watermark.png')
    for p in sorted(OUT.glob('*.png')):
        print(p.name, Image.open(p).size, f'{p.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
