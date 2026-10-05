"""Senaryo JSON -> MP4 (Dex and Friends render motorundan uyarlandı).

1. Her replik için ses (voice.py) -> zaman çizelgesi (replik, aksiyon, SFX, sahne kartı, bilgi kartı)
2. Ses mix (konuşma + SFX + ducking'li müzik)
3. Kare kare cairo çizim -> ffmpeg (H.264 + AAC)
"""
import math
import random
import subprocess
import zlib
from pathlib import Path

import cairo
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

from . import audio, backgrounds, fruit, voice
from .cast import CAST, SFX
from .render_util import rrect

FPS = 30
ROOT = Path(__file__).resolve().parent.parent
FONT = str(ROOT / 'fonts' / 'LuckiestGuy-Regular.ttf')
CTA_SECONDS = 2.8   # videonun son kaç saniyesinde 'abone ol & beğen' görünür

FORMATS = {
    'short': dict(W=1080, H=1920, ground=1420, s=7.6, sub_y=1640, font=80, top=140,
                  xs={1: [0.5], 2: [0.26, 0.74], 3: [0.18, 0.5, 0.82]}),
    # haftalık uzun bölüm (yatay)
    'long': dict(W=1920, H=1080, ground=905, s=6.0, sub_y=985, font=60, top=60,
                 xs={1: [0.5], 2: [0.33, 0.67], 3: [0.24, 0.5, 0.76]}),
}
LIMITS = {'short': 58.5, 'long': 600.0}   # saniye; Shorts 60 sn altında kalmalı

# aksiyon: (süre, [(t, sfx)], darbe anı)
ACTIONS = {
    'slap': (0.85, [(0.32, 'slap')], 0.32),
    'faint': (1.0, [(0.55, 'thud')], 0.55),
    'run_away': (0.9, [(0.05, 'whoosh')], None),
    'jump': (0.75, [(0.02, 'boing')], None),
    'spin': (0.8, [(0.0, 'whoosh')], None),
    'dramatic_zoom': (1.5, [(0.0, 'sting')], None),
    'rimshot': (1.0, [(0.0, 'rimshot')], None),
    'shiver': (1.0, [(0.0, 'buzz')], None),
    'roll_away': (1.1, [(0.0, 'whoosh'), (0.2, 'boing')], None),
    'grabbed': (1.6, [(0.0, 'sting'), (0.55, 'pop'), (0.75, 'whoosh')], None),
    'squish': (0.9, [(0.25, 'squish')], 0.25),
}
IMPACT_WORD = {'slap': 'ŞAP!', 'thud': 'GÜM!', 'crash': 'ÇAT!', 'boing': 'BOİNG!', 'pop': 'HOP!', 'squish': 'ÇIRT!'}


def log(m):
    print(f'[render] {m}', flush=True)


def tr_upper(s):
    return s.replace('i', 'İ').replace('ı', 'I').upper()


# ------------------------------------------------------------------ yazı yardımcıları

def pil_to_surface(img):
    a = np.asarray(img.convert('RGBA')).astype(np.float32)
    alpha = a[:, :, 3:4] / 255.0
    rgb = a[:, :, :3] * alpha
    out = np.empty(a.shape, np.uint8)
    out[:, :, 0] = rgb[:, :, 2]; out[:, :, 1] = rgb[:, :, 1]; out[:, :, 2] = rgb[:, :, 0]
    out[:, :, 3] = a[:, :, 3]
    h, w = out.shape[:2]
    return cairo.ImageSurface.create_for_data(memoryview(np.ascontiguousarray(out)), cairo.FORMAT_ARGB32, w, h, w * 4)


def wrap(words, font, maxw, draw):
    lines, cur = [], []
    for i, w in enumerate(words):
        test = ' '.join(x for _, x in cur + [(i, w)])
        if cur and draw.textlength(test, font=font) > maxw:
            lines.append(cur); cur = []
        cur.append((i, w))
    if cur:
        lines.append(cur)
    return lines


def text_block(words, size, maxw, hi=None, hi_color=(255, 214, 0), color=(255, 255, 255), stroke=(0, 0, 0),
               stroke_w=None, bg=None, pad=0, outline=(20, 20, 24)):
    font = ImageFont.truetype(FONT, size)
    tmp = ImageDraw.Draw(Image.new('RGBA', (8, 8)))
    rows = wrap(words, font, maxw, tmp)
    sw = stroke_w if stroke_w is not None else max(3, size // 9)
    lh = int(size * 1.15)
    widths = [tmp.textlength(' '.join(w for _, w in r), font=font) for r in rows]
    W = int(max(widths) + 2 * sw + 2 * pad + 10)
    H = int(lh * len(rows) + 2 * sw + 2 * pad + size * 0.3)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if bg:
        d.rounded_rectangle((0, 0, W - 1, H - 1), radius=int(size * 0.45), fill=bg, outline=outline, width=5)
    space = tmp.textlength(' ', font=font)
    for r, row in enumerate(rows):
        x = (W - widths[r]) / 2
        y = pad + sw + r * lh
        for i, w in row:
            col = hi_color if i == hi else color
            d.text((x, y), w, font=font, fill=col, stroke_width=sw, stroke_fill=stroke)
            x += tmp.textlength(w, font=font) + space
    return img


def stable(x):
    return zlib.crc32(str(x).encode())


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, k):
    return a + (b - a) * k


def lerp2(a, b, k):
    return (lerp(a[0], b[0], k), lerp(a[1], b[1], k))


# ------------------------------------------------------------------ zaman çizelgesi

def build_timeline(sc, workdir, speed_mul=1.0):
    t = 0.25
    voices, effects, mask = [], [], [(0, 0)]
    scenes = []
    for si, scene in enumerate(sc['scenes']):
        S = dict(scene, start=t, lines=[])
        if si > 0:
            effects.append((max(0, t - 0.05), audio.sfx('whoosh', si), 0.35))
        if scene.get('card'):
            S['card_span'] = (t, t + 1.3)
            t += 1.3
        for li, line in enumerate(scene['lines']):
            L = dict(line, start=t)
            text = (line.get('text') or '').strip()
            if text:
                samples, words = voice.speak(line['char'], text, line.get('emotion', 'neutral'), speed_mul)
                L['speech'] = (t + 0.05, t + 0.05 + len(samples) / audio.SR)
                L['words'] = words
                hop = audio.SR // FPS
                n = len(samples) // hop + 1
                env = np.array([np.sqrt(np.mean(samples[i * hop:(i + 1) * hop] ** 2)) if i * hop < len(samples) else 0
                                for i in range(n)])
                L['env'] = env / (env.max() + 1e-6)
                voices.append((L['speech'][0], samples, 1.0))
                mask += [(L['speech'][0] - 0.05, 0), (L['speech'][0], 1), (L['speech'][1], 1), (L['speech'][1] + 0.05, 0)]
                t = L['speech'][1]
            act = line.get('action')
            if act in ACTIONS:
                dur, snds, impact = ACTIONS[act]
                a0 = t + 0.05
                L['act'] = (a0, a0 + dur, impact)
                for dt, name in snds:
                    effects.append((a0 + dt, audio.sfx(name, li), 0.9))
                    if name in IMPACT_WORD and impact is not None and abs(dt - impact) < 1e-6:
                        L['impact_word'] = (a0 + dt, IMPACT_WORD[name])
                t = a0 + dur
            if line.get('sfx') in SFX:
                at = L['speech'][1] - 0.1 if 'speech' in L else t
                effects.append((max(0, at), audio.sfx(line['sfx'], li + 7), 0.85))
                if line['sfx'] in IMPACT_WORD and 'impact_word' not in L:
                    L['impact_word'] = (at, IMPACT_WORD[line['sfx']])
                if 'speech' not in L and 'act' not in L:
                    t += 0.6 if line['sfx'] != 'blender' else 1.4
            if line.get('fact'):
                effects.append((L['start'], audio.sfx('ding', li + 3), 0.45))
            t += 0.32 if si < len(sc['scenes']) - 1 or li < len(scene['lines']) - 1 else 0.9
            L['end'] = t
            S['lines'].append(L)
        S['end'] = t
        scenes.append(S)
    total = t + 0.3
    mt = np.array([m[0] for m in mask] + [total]); mv = np.array([m[1] for m in mask] + [0])
    order = np.argsort(mt, kind='stable')
    stereo = audio.mix(total, voices, effects, audio.music(total + 1, seed=stable(sc['id']) % 10_000),
                       (mt[order], mv[order]))
    wav = Path(workdir) / 'audio.wav'
    sf.write(str(wav), stereo, audio.SR)
    return scenes, total, wav


# ------------------------------------------------------------------ aktör

class Actor:
    def __init__(self, cid, x, facing, pose, emotion, seed):
        self.cid, self.x, self.facing = cid, x, facing
        self.pose, self.emotion = pose or 'standing', emotion or 'neutral'
        P = fruit.pose_targets(cid, self.pose)
        self.hands = {'F': P['F'], 'B': P['B']}
        self.rng = random.Random(seed)
        self.next_blink = self.rng.uniform(0.5, 3)
        self.dizzy = self.gone = self.fallen = False
        self.hit_at = None
        self.offset_x = 0.0
        self.squish_at = None


# ------------------------------------------------------------------ ana render

class Renderer:
    def __init__(self, sc, scenes, total, seed):
        self.sc, self.F, self.scenes, self.total = sc, FORMATS[sc.get('format', 'short')], scenes, total
        self.W, self.H = self.F['W'], self.F['H']
        self.rng = random.Random(seed)
        self.bg_cache, self.sub_cache = {}, {}
        self.surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.W, self.H)
        self.ctx = cairo.Context(self.surf)
        self.hook = None
        if sc.get('hook') and sc.get('format', 'short') == 'short':   # uzun bölümde sabit üst yazı yok
            self.hook = pil_to_surface(text_block(tr_upper(sc['hook']).split(), 70, self.W * 0.82, color=(20, 20, 24),
                                                  stroke_w=0, bg=(255, 255, 255, 245), pad=22))
        # kapanış çağrısı: son saniyelerde üstteki başlık kutusunun yerine geçer (espriyi ve altyazıyı kapatmaz)
        fs = self.F['font']
        self.cta = pil_to_surface(text_block(tr_upper('Abone ol & beğen!').split(), int(fs * 0.92), self.W * 0.84,
                                             color=(255, 255, 255), stroke_w=0, bg=(230, 33, 39, 255), pad=26))
        sub = 'Yarın yeni meyve kavgası!' if sc.get('format', 'short') == 'short' else 'Her hafta yeni bölüm!'
        self.cta_sub = pil_to_surface(text_block(tr_upper(sub).split(), int(fs * 0.62),
                                                 self.W * 0.84, color=(255, 236, 120)))
        self.cta_start = max(0.0, total - CTA_SECONDS)
        for si, S in enumerate(scenes):
            chars = S['characters']
            xs = self.F['xs'][min(3, len(chars))]
            order = {'left': 0, 'center': 1 if len(chars) == 3 else 0, 'right': len(xs) - 1}
            used, S['actors'] = set(), {}
            for i, ch in enumerate(chars):
                slot = order.get(ch.get('pos'), i)
                if slot in used or slot >= len(xs):
                    slot = next(k for k in range(len(xs)) if k not in used)
                used.add(slot)
                x = xs[slot] * self.W
                facing = 1 if xs[slot] <= 0.5 else -1
                if len(chars) == 1:
                    facing = 1 if self.rng.random() < 0.5 else -1
                S['actors'][ch['id']] = Actor(ch['id'], x, facing, ch.get('pose'), ch.get('emotion'), seed + si * 31 + i)
            S['bg_name'] = S.get('bg') if S.get('bg') in backgrounds.NAMES else 'kitchen'
            for L in S['lines']:
                L['shot'] = self.plan_shot(S, L)

    # ---- kamera
    def plan_shot(self, S, L):
        a = S['actors'].get(L.get('char'))
        emo = L.get('emotion', 'neutral')
        r = self.rng.random()
        if L.get('action') == 'dramatic_zoom' and a:
            return ('zoom_face', L['char'])
        if L.get('action') in ('slap', 'faint', 'run_away', 'jump', 'spin', 'roll_away', 'grabbed', 'squish'):
            return ('wide', None)
        if a is None:
            return ('wide', None)
        if L.get('fact'):   # bilgi kartı üstte: yüzü kapatmasın
            return ('wide', None) if len(S['actors']) > 1 else ('fact', L['char'])
        if len(S['actors']) == 1:
            return ('close', L['char']) if r < 0.55 else ('push', L['char'])
        if emo in ('angry', 'shock', 'excited') and r < 0.55:
            return ('punch', L['char'])
        if r < 0.5:
            return ('close', L['char'])
        if r < 0.7:
            return ('push', L['char'])
        return ('wide', None)

    def camera(self, S, L, t):
        W, H, s, ground = self.W, self.H, self.F['s'], self.F['ground']
        cx, cy, z = W / 2, H / 2, 1.0
        if L is None:
            return cx, cy, 1.0
        kind, who = L['shot']
        k = (t - L['start']) / max(0.1, L['end'] - L['start'])
        a = S['actors'].get(who) if who else None
        if a:
            hx = a.x + a.offset_x
            face_y, _ = fruit.body_top(a.cid, ground, s)
        if kind == 'close' and a:
            z = 1.38 + 0.05 * k
            cx, cy = hx, face_y + 0.1 * H
        elif kind == 'punch' and a:
            p = ease((t - L['start']) / 0.18)
            z = lerp(1.1, 1.55, p) + 0.03 * k
            cx, cy = lerp(W / 2, hx, p), lerp(H / 2, face_y + 0.08 * H, p)
        elif kind == 'push' and a:
            z = 1.08 + 0.14 * ease(k)
            cx, cy = lerp(W / 2, hx, 0.35), H / 2 + 0.03 * H
        elif kind == 'fact' and a:
            z = 1.15
            cx, cy = hx, face_y - 0.04 * H
        elif kind == 'zoom_face' and a:
            p = ease((t - L['start']) / 0.5)
            z = lerp(1.0, 2.4, p)
            cx, cy = lerp(W / 2, hx, p), lerp(H / 2, face_y, p)
        else:
            z = 1.0 + 0.03 * k
        hw, hh = W / (2 * z), H / (2 * z)
        cx = min(max(cx, hw), W - hw)
        cy = min(max(cy, hh), H - hh)
        return cx, cy, z

    # ---- yardımcı
    def bg(self, S, si):
        key = (S['bg_name'], si)
        if key not in self.bg_cache:
            self.bg_cache = {key: backgrounds.render(S['bg_name'], self.W, self.H, self.F['ground'],
                                                     seed=stable((self.sc['id'], si)) % 1000)}
        return self.bg_cache[key]

    def subtitle(self, key, L, wi):
        ck = (key, wi)
        if ck not in self.sub_cache:
            if len(self.sub_cache) > 400:
                self.sub_cache.clear()
            words = [tr_upper(w['text']) for w in L['words']]
            acc = tuple(int(v * 255) for v in CAST[L['char']]['accent'])
            self.sub_cache[ck] = pil_to_surface(text_block(words, self.F['font'], self.W * 0.86, hi=wi, hi_color=acc))
        return self.sub_cache[ck]

    def find(self, t):
        for si, S in enumerate(self.scenes):
            if t < S['end'] or si == len(self.scenes) - 1:
                cur = None
                for L in S['lines']:
                    if t >= L['start']:
                        cur = L
                return si, S, cur
        return 0, self.scenes[0], None

    # ---- kare
    def frame(self, t, prev_line):
        ctx, W, H, s, ground = self.ctx, self.W, self.H, self.F['s'], self.F['ground']
        si, S, L = self.find(t)
        actors = S['actors']
        if L is not None and L is not prev_line:
            a = actors.get(L.get('char'))
            if a:
                if L.get('emotion'):
                    a.emotion = L['emotion']
                if L.get('pose'):
                    a.pose = L['pose']
            for cid, emo in (L.get('reactions') or {}).items():
                if cid in actors:
                    actors[cid].emotion = emo

        cx, cy, z = self.camera(S, L, t)
        shake = 0.0
        for LL in S['lines']:
            if 'impact_word' in LL and 0 <= t - LL['impact_word'][0] < 0.4:
                shake = max(shake, 1 - (t - LL['impact_word'][0]) / 0.4)
        sx = (math.sin(t * 91) * 22 + math.sin(t * 57) * 10) * shake
        sy = (math.cos(t * 77) * 22) * shake

        ctx.save()
        ctx.translate(W / 2 + sx, H / 2 + sy)
        ctx.scale(z, z)
        ctx.translate(-cx, -cy)
        ctx.set_source_surface(self.bg(S, si), 0, 0)
        ctx.get_source().set_filter(cairo.FILTER_BILINEAR)
        ctx.paint()

        act_line = None
        if L is not None and 'act' in L and L['act'][0] <= t < L['act'][1] + 0.001:
            act_line = L

        def target_of(cid):
            if L and L.get('target') in actors and L.get('target') != cid:
                return actors[L['target']]
            others = [a for k, a in actors.items() if k != cid and not a.gone]
            if not others:
                return None
            me = actors[cid]
            return min(others, key=lambda o: abs(o.x - me.x))

        grab = None   # (hedef aktör, k)
        if act_line is not None and act_line.get('action') == 'grabbed':
            a0, a1, _ = act_line['act']
            victim = actors.get(act_line.get('target')) or actors.get(act_line.get('char'))
            if victim:
                grab = (victim, (t - a0) / (a1 - a0))

        for cid, a in actors.items():
            action = None
            speaking = L is not None and L.get('char') == cid and 'speech' in L and L['speech'][0] <= t < L['speech'][1]
            if act_line is not None and act_line.get('char') == cid and act_line.get('action') != 'grabbed':
                a0, a1, imp = act_line['act']
                action = (act_line['action'], (t - a0) / (a1 - a0))
            if a.gone:
                continue
            P = fruit.pose_targets(cid, a.pose, t)
            kinds = {'F': P['hand_F'], 'B': P['hand_B']}
            prop = P['prop']
            lift, tilt, spin, fall, squash, walk = 0.0, 0.0, 1.0, 0.0, 1.0, None
            ox = 0.0
            if action:
                name, k = action
                tgt = target_of(cid)
                if name == 'jump':
                    lift = math.sin(math.pi * min(1, k * 1.1)) * 22
                    squash = 1 + 0.15 * math.sin(math.pi * min(1, k * 1.1))
                    P = fruit.pose_targets(cid, 'celebrate', t); kinds = {'F': 'fist', 'B': 'fist'}
                elif name == 'faint' and k >= 0.2:
                    fall = ease((k - 0.2) / 0.35)
                    if k > 0.55:
                        a.fallen = a.dizzy = True
                elif name == 'run_away':
                    walk = t * 22
                    a.offset_x = -a.facing * (k ** 1.6) * W * 0.9
                    if k > 0.98:
                        a.gone = True
                elif name == 'roll_away':
                    a.offset_x = -a.facing * (k ** 1.4) * W * 0.95
                    tilt = -a.facing * k * 720
                    if k > 0.98:
                        a.gone = True
                elif name == 'spin':
                    spin = math.cos(k * 4 * math.pi)
                elif name == 'shiver':
                    ox = math.sin(t * 90) * 6
                    squash = 0.96
                elif name == 'slap' and tgt:
                    reach = (abs(tgt.x - a.x) - 34 * s) * (1 if tgt.x > a.x else -1)
                    p = ease(k / 0.25) if k < 0.6 else 1 - ease((k - 0.6) / 0.4)
                    a.offset_x = reach * p
                    G = fruit.geometry(cid)
                    sl, sr, shy = G['sh']
                    P = dict(P, F=(sr + 4 + 14 * ease(k / 0.35), shy - 14 + 18 * ease((k - 0.2) / 0.2)))
                    kinds = {'F': 'open', 'B': P['hand_B']}
                    if k >= 0.38 and tgt.hit_at is None:
                        tgt.hit_at = t; tgt.dizzy = True; tgt.emotion = 'shock'
                elif name == 'squish' and tgt:
                    if k >= 0.25 and tgt.squish_at is None:
                        tgt.squish_at = t; tgt.emotion = 'shock'
                    P = fruit.pose_targets(cid, 'pointing', t); kinds = {'F': 'point', 'B': 'open'}
            if a.squish_at is not None:
                d = t - a.squish_at
                if d < 0.9:
                    squash = 1 - 0.45 * math.exp(-d * 5) * abs(math.cos(d * 14))
            if a.fallen:
                fall = 1.0
            hit_tilt = 0.0
            if a.hit_at is not None and t - a.hit_at < 0.6:
                d = t - a.hit_at
                hit_tilt = -22 * math.exp(-d * 6) * math.cos(d * 25)
            # yumuşatılmış eller
            kk = 0.45 if action else 0.28
            a.hands['F'] = lerp2(a.hands['F'], P['F'], kk)
            a.hands['B'] = lerp2(a.hands['B'], P['B'], kk)
            # göz kırpma
            blink = 0.0
            if t >= a.next_blink:
                p = (t - a.next_blink) / 0.14
                blink = 1 - abs(2 * p - 1) if p < 1 else 0
                if p >= 1:
                    a.next_blink = t + a.rng.uniform(2.2, 4.5)
            mouth, lvl = 'closed', 0.0
            if speaking:
                i = int((t - L['speech'][0]) * FPS)
                lvl = float(L['env'][min(i, len(L['env']) - 1)])
                mouth = mouth_shape(lvl, L, t - L['speech'][0], a.emotion)
                tilt += 2.5 * math.sin(t * 6)
                squash *= 1 + 0.03 * lvl
            # karşısındakine bakar
            other = target_of(cid)
            look = (0.7, 0.0)
            if other is not None:
                look = (0.8 if (other.x - a.x) * a.facing > 0 else -0.8, -0.1)
            if L is not None and L.get('look_camera') and L.get('char') == cid:
                look = (0, 0)
            if len(actors) == 1:
                look = (0.0, 0.0)
            if a.emotion == 'shock' and not speaking:
                mouth = 'closed'
            y_off = 0.0
            if grab and grab[0] is a:
                gk = grab[1]
                if gk > 0.45:
                    y_off = -ease((gk - 0.45) / 0.55) * H * 0.9
                    a.emotion = 'shock'
                    walk = t * 30
                if gk > 0.98:
                    a.gone = True
            st = dict(emotion=a.emotion, mouth=mouth, blink=blink, t=t, lvl=lvl, look=look, hands=a.hands,
                      hand_kinds=kinds, prop=prop, tilt=tilt + hit_tilt, lift=lift, fall=fall, squash=squash,
                      dizzy=a.dizzy, walk=walk, spin=spin if abs(spin) > 0.05 else 0.05,
                      breath=1 + 0.012 * math.sin(t * math.pi + stable(cid) % 7))
            ctx.save()
            ctx.translate(0, y_off)
            fruit.draw(ctx, cid, a.x + a.offset_x + ox, ground, s, a.facing, st)
            ctx.restore()
            if action and action[0] in ('run_away', 'roll_away'):
                speed_lines(ctx, a.x + a.offset_x, ground - 30 * s, s, a.facing, t)

        if grab:
            victim, gk = grab
            hx = victim.x + victim.offset_x
            _, top_y = fruit.body_top(victim.cid, ground, s)
            hy = lerp(-H * 0.2, top_y + 8 * s, ease(gk / 0.4))
            if gk > 0.45:
                hy += -ease((gk - 0.45) / 0.55) * H * 0.9
            giant_hand(ctx, hx, hy, s, closed=gk > 0.42)

        for LL in S['lines']:
            iw = LL.get('impact_word')
            if iw and 0 <= t - iw[0] < 0.45:
                tgt = actors.get(LL.get('target')) if LL.get('target') in actors else None
                if tgt is None:
                    tgt = next((a for k, a in actors.items() if k != LL.get('char')), None) or actors.get(LL.get('char'))
                x, y = ((tgt.x + tgt.offset_x) if tgt else W / 2), ground - 55 * s
                burst(ctx, x, y, s, iw[1], (t - iw[0]) / 0.45)
        ctx.restore()

        # ekran-uzayı katmanları
        y_top = self.F['top']
        if t >= self.cta_start:
            self.draw_cta(t - self.cta_start, y_top)
            y_top += self.cta.get_height() + self.cta_sub.get_height() + 40
        elif self.hook is not None:
            ctx.set_source_surface(self.hook, (W - self.hook.get_width()) / 2, y_top)
            ctx.paint()
            y_top += self.hook.get_height() + 24
        if S.get('label'):
            label = self.sub_cache.setdefault(('label', si), pil_to_surface(
                text_block(tr_upper(S['label']).split(), 54, W * 0.8, color=(255, 255, 255), stroke_w=0,
                           bg=(230, 40, 60, 255), pad=12)))
            ctx.set_source_surface(label, 40, y_top)
            ctx.paint()
            y_top += label.get_height() + 20
        if L is not None and L.get('fact'):
            self.fact_card(L, t, y_top)
        if L is not None and 'words' in L and t < L['speech'][1] + 0.25:
            rel = t - L['speech'][0]
            wi = 0
            for i, w in enumerate(L['words']):
                if rel >= w['start']:
                    wi = i
            sub = self.subtitle(id(L), L, wi)
            pop = 0.85 + 0.15 * ease((t - L['speech'][0]) / 0.12)
            ctx.save()
            ctx.translate(W / 2, self.F['sub_y'])
            ctx.scale(pop, pop)
            ctx.set_source_surface(sub, -sub.get_width() / 2, -sub.get_height() / 2)
            ctx.paint()
            ctx.restore()
        if S.get('card_span') and S['card_span'][0] <= t < S['card_span'][1]:
            k = (t - S['card_span'][0]) / (S['card_span'][1] - S['card_span'][0])
            card(ctx, W, H, S['card'], k, self.F['font'], t)
        if si > 0 and 0 <= t - S['start'] < 0.1:
            ctx.set_source_rgba(1, 1, 1, 1 - (t - S['start']) / 0.1)
            ctx.paint()
        self.surf.flush()
        return L

    def draw_cta(self, k, y):
        ctx, W = self.ctx, self.W
        pop = 0.6 + 0.4 * ease(k / 0.3) + 0.04 * math.sin(k * 9)      # zıplayarak gelir, hafif nabız atar
        ctx.save()
        ctx.translate(W / 2, y + self.cta.get_height() / 2)
        ctx.rotate(-0.02)
        ctx.scale(pop, pop)
        ctx.set_source_surface(self.cta, -self.cta.get_width() / 2, -self.cta.get_height() / 2)
        ctx.paint_with_alpha(min(1.0, k / 0.15))
        ctx.restore()
        ctx.set_source_surface(self.cta_sub, (W - self.cta_sub.get_width()) / 2, y + self.cta.get_height() + 22)
        ctx.paint_with_alpha(min(1.0, max(0.0, (k - 0.3) / 0.3)))

    def fact_card(self, L, t, y):
        key = ('fact', id(L))
        if key not in self.sub_cache:
            img = text_block(['BİLGİ:'] + tr_upper(L['fact']).split(), 46, self.W * 0.74, hi=0,
                             hi_color=(230, 60, 40), color=(30, 30, 35), stroke_w=0, bg=(255, 236, 120, 250), pad=18)
            self.sub_cache[key] = pil_to_surface(img)
        surf = self.sub_cache[key]
        k = ease((t - L['start']) / 0.25)
        ctx = self.ctx
        ctx.save()
        ctx.translate(self.W / 2, y + surf.get_height() / 2)
        ctx.rotate(-0.03)
        ctx.scale(0.6 + 0.4 * k, 0.6 + 0.4 * k)
        ctx.set_source_surface(surf, -surf.get_width() / 2, -surf.get_height() / 2)
        ctx.paint_with_alpha(k)
        ctx.restore()


def mouth_shape(lvl, L, rel, emo):
    if lvl < 0.12:
        return 'closed'
    if lvl > 0.8 and emo in ('angry', 'shock', 'excited', 'cry'):
        return 'wide'
    word = L['words'][0]
    for w in L['words']:
        if rel >= w['start']:
            word = w
    letters = [c for c in word['text'].lower() if c.isalpha()] or ['a']
    p = (rel - word['start']) / max(0.05, word['end'] - word['start'])
    ch = letters[min(len(letters) - 1, int(p * len(letters)))]
    vow = [c for c in letters if c in 'aeıioöuü']
    if ch not in 'aeıioöuüvwy' and vow:
        ch = vow[min(len(vow) - 1, int(p * len(vow)))]
    shape = {'a': 'ai', 'ı': 'e', 'i': 'e', 'e': 'e', 'y': 'e', 'o': 'o', 'ö': 'o', 'u': 'u', 'ü': 'u', 'v': 'u',
             'w': 'u'}.get(ch, 'e')
    if lvl < 0.3:
        return 'e' if shape != 'u' else 'u'
    return shape


def speed_lines(ctx, x, y, s, facing, t):
    ctx.save()
    ctx.set_source_rgba(1, 1, 1, 0.85)
    ctx.set_line_width(s * 0.8)
    r = random.Random(int(t * 30))
    for i in range(7):
        yy = y + (i - 3) * s * 7 + r.uniform(-s * 2, s * 2)
        x0 = x + facing * s * r.uniform(28, 36)
        ctx.move_to(x0, yy); ctx.line_to(x0 + facing * s * r.uniform(25, 50), yy)
    ctx.stroke()
    ctx.restore()


def giant_hand(ctx, x, y, s, closed=False):
    """Yukarıdan inen insan eli (y = parmak uçları)."""
    skin, edge = (0.98, 0.8, 0.66), (0.6, 0.38, 0.28)
    u = s
    ctx.save(); ctx.translate(x, y)
    rrect(ctx, -22 * u, -130 * u, 44 * u, 80 * u, 10 * u)           # kol (gömlek kolu)
    ctx.set_source_rgb(0.25, 0.45, 0.85); ctx.fill()
    rrect(ctx, -20 * u, -62 * u, 40 * u, 42 * u, 14 * u)            # avuç
    g = cairo.LinearGradient(-20 * u, 0, 20 * u, 0)
    g.add_color_stop_rgb(0, *skin); g.add_color_stop_rgb(1, 0.9, 0.68, 0.55)
    ctx.set_source(g); ctx.fill_preserve(); ctx.set_source_rgb(*edge); ctx.set_line_width(0.6 * u); ctx.stroke()
    for i, dx in enumerate((-14, -5, 4, 13)):
        L = (22 if i in (1, 2) else 18) * (0.55 if closed else 1)
        rrect(ctx, (dx - 4) * u, -26 * u, 8 * u, L * u, 4 * u)
        ctx.set_source_rgb(*skin); ctx.fill_preserve(); ctx.set_source_rgb(*edge); ctx.stroke()
    ctx.save(); ctx.translate(-20 * u, -40 * u); ctx.rotate(0.5 if not closed else 1.1)   # başparmak
    rrect(ctx, -4 * u, 0, 8 * u, 20 * u, 4 * u)
    ctx.set_source_rgb(*skin); ctx.fill_preserve(); ctx.set_source_rgb(*edge); ctx.stroke(); ctx.restore()
    ctx.restore()


def burst(ctx, x, y, s, word, k):
    sc = s * (0.6 + 0.6 * ease(k / 0.3)) * (1 - 0.3 * max(0, k - 0.7) / 0.3)
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(-0.15)
    ctx.new_path()
    for i in range(24):
        a = i * math.pi / 12
        r = (16 if i % 2 == 0 else 10) * sc
        (ctx.move_to if i == 0 else ctx.line_to)(r * math.cos(a) * 1.35, r * math.sin(a))
    ctx.close_path()
    ctx.set_source_rgba(1, 0.86, 0.1, 1 - max(0, k - 0.75) * 4)
    ctx.fill_preserve()
    ctx.set_source_rgb(0.1, 0.1, 0.1); ctx.set_line_width(sc * 0.8); ctx.stroke()
    ctx.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(7.0 * sc)
    ext = ctx.text_extents(word)
    ctx.move_to(-ext.width / 2 - ext.x_bearing, ext.height / 2)
    ctx.text_path(word)
    ctx.set_source_rgb(0.9, 0.1, 0.12); ctx.fill_preserve()
    ctx.set_source_rgb(1, 1, 1); ctx.set_line_width(sc * 0.35); ctx.stroke()
    ctx.restore()


_card_cache = {}


def card(ctx, W, H, text, k, size, t):
    ctx.save()
    ctx.set_source_rgb(0.98, 0.55, 0.1); ctx.paint()
    ctx.translate(W / 2, H / 2)
    ctx.rotate(t * 0.6)
    for i in range(16):
        ctx.move_to(0, 0)
        ctx.arc(0, 0, max(W, H), i * math.pi / 8, i * math.pi / 8 + math.pi / 16)
        ctx.close_path()
    ctx.set_source_rgba(1, 1, 1, 0.14); ctx.fill()
    ctx.restore()
    key = (text, W)
    if key not in _card_cache:
        _card_cache[key] = pil_to_surface(text_block(tr_upper(text).split(), int(size * 1.4), W * 0.8,
                                                     color=(255, 245, 120)))
    surf = _card_cache[key]
    p = 0.7 + 0.3 * ease(k / 0.2)
    ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(p, p)
    ctx.set_source_surface(surf, -surf.get_width() / 2, -surf.get_height() / 2); ctx.paint()
    ctx.restore()


# ------------------------------------------------------------------ giriş noktası

def render(sc, out_dir, preview_png=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = sc.get('format', 'short')
    F = FORMATS[fmt]
    scenes, total, wav = build_timeline(sc, out_dir)
    limit = LIMITS[fmt]
    if total > limit:
        k = min(1.3, total / (limit - 1.5))
        log(f'{total:.1f}s too long, re-voicing at x{k:.2f}')
        scenes, total, wav = build_timeline(sc, out_dir, speed_mul=k)
    log(f'timeline {total:.1f}s, {sum(len(S["lines"]) for S in scenes)} lines')
    R = Renderer(sc, scenes, total, seed=stable(sc['id']) % 100000)
    mp4 = out_dir / 'video.mp4'
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f"{F['W']}x{F['H']}",
           '-r', str(FPS), '-i', '-', '-i', str(wav), '-map', '0:v', '-map', '1:a',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
           '-c:a', 'aac', '-b:a', '192k', '-shortest', str(mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(total * FPS)
    prev = None
    for i in range(n):
        t = i / FPS
        prev = R.frame(t, prev)
        proc.stdin.write(bytes(R.surf.get_data()))
        if preview_png and i == int(n * 0.3):
            R.surf.write_to_png(str(preview_png))
        if i % (FPS * 10) == 0:
            log(f'frame {i}/{n}')
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError('ffmpeg failed')
    return mp4, total
