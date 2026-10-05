"""Senaryo üretimi: Gemini yazar -> Gemini hakem (1-10, bilgi doğruluğu dahil) -> doğrulama.
Anahtar yoksa / başarısızsa bank/ kullanılır. (Dex and Friends'ten uyarlandı.)"""
import json
import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import backgrounds
from .cast import ACTIONS, CAST, EMOTIONS, POSES, SFX, bible

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / 'prompts'
BANK = ROOT / 'bank'
# flash modelleri aynı kapasite havuzunda, çoğu zaman birlikte 503 veriyor; lite ve gemma genelde yanıt verir
MODELS = ('gemini-3.8-flash,gemini-3.5-flash,gemini-flash-latest,gemini-3.7-flash,gemini-3-flash-preview,'
          'gemini-flash-lite-latest,gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemma-4-26b-a4b-it,gemma-4-31b-it')

SHORT_TEMPLATES = {
    'anlatiyor': 'Meyve anlatıyor: tek bir meyve kameraya kendini anlatır (look_camera), komik ama GERÇEK bilgilerle '
                 '(3-4 "fact"); sonda başka bir meyve araya girip ters köşe yapar.',
    'kavga': 'Kavga: iki meyve bir konuda iddialaşır, her biri kendi gerçek özelliğiyle övünür (fact), '
             'laf sokmalar giderek büyür, son replik ters köşe.',
    'kimlik_krizi': 'Kimlik krizi: bir meyve/sebze kendisi hakkında şaşırtıcı bir gerçeği öğrenir ve dramatik tepki verir.',
    'buzdolabi': 'Buzdolabı draması: buzdolabında/mutfakta meyveler kendi aralarında konuşur; insan gelince herkes '
                 'normal davranır; sonda dev el ("grabbed") beklenmedik birini alır.',
    'ters_kose': 'Ters köşe: sıradan bir sohbet, son 3 saniyede tamamen beklenmedik bir sonla biter '
                 '(blender, salata, reçel, dev el vb.).',
    'tipler': 'Tipler: "Mutfaktaki X tipleri" -> 3-4 hızlı sahne, her sahne bir tip (sahne "label" ile, ör. "Gösterişçi"), '
              'sonuncusu en absürt.',
}
TOPICS = ['meyve mi sebze mi', 'yaşlanmak / kararmak', 'buzdolabında gece', 'pazarda seçilmemek', 'blender korkusu',
          'meyve salatası seçmeleri', 'kahvaltı sofrası', 'diyet yapan insan', 'pahalı olmak', 'ekşi olmak',
          'su oranı yarışması', 'yaz geldi', 'kış meyvesi olmak', 'reçel olmak', 'turşu tehlikesi', 'sosyal medya',
          'okul beslenme çantası', 'manavda indirim', 'çekirdek / tohum', 'vitamin yarışı', 'bıçak geldi',
          'egzotik meyve kıskançlığı', 'ilk iş günü (pazar tezgâhı)', 'sağlıklı beslenme', 'smoothie', 'ağaçtan düşmek',
          'sınav stresi', 'dedikodu', 'doğum günü pastası', 'piknik', 'tatil (plaj)', 'spor salonu']
BANNED = re.compile(r'\b(öl|öldür|kan|seks|içki|bira|şarap|uyuşturucu|aptal|salak|gerizekalı|lanet|siktir|kahretsin|'
                    r'kill|dead|blood|sex|drunk|beer|wine|drug)\b', re.I)


def log(m):
    print(f'[writer] {m}', flush=True)


def gemini(prompt, temperature=0.95, timeout=120, as_json=True):
    key = (os.environ.get('GEMINI_API_KEY') or '').strip().lstrip('﻿')
    if not key:
        raise RuntimeError('GEMINI_API_KEY not set')
    models = [m.strip() for m in (os.environ.get('GEMINI_MODELS') or MODELS).split(',') if m.strip()]
    errors = []
    for attempt in range(2):
        for model in models:
            cfg = {'temperature': temperature}
            if as_json and not model.startswith('gemma'):   # gemma'da JSON modu yok; parse_json çitleri temizler
                cfg['responseMimeType'] = 'application/json'
            body = {'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': cfg}
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
            try:
                r = requests.post(url, json=body, headers={'x-goog-api-key': key}, timeout=timeout)
            except requests.RequestException as e:
                errors.append(f'{model}:{type(e).__name__}'); continue
            if r.status_code == 200:
                cands = r.json().get('candidates') or [{}]
                parts = cands[0].get('content', {}).get('parts', [])
                text = ''.join(p.get('text', '') for p in parts if not p.get('thought')).strip()
                if text:
                    return text
                errors.append(f'{model}:empty'); continue
            errors.append(f'{model}:{r.status_code}')
            if r.status_code not in (404, 429, 500, 503):
                r.raise_for_status()
        if attempt == 0:
            time.sleep(60)   # tüm modeller meşgul: yoğunluk genelde 1-2 dakikada geçer
    raise RuntimeError(f"Gemini unavailable: {', '.join(errors)}")


def parse_json(text):
    text = re.sub(r'^```(?:json)?|```$', '', text.strip(), flags=re.M).strip()
    start = text.find('{')
    return json.loads(text[start: text.rfind('}') + 1])


# ------------------------------------------------------------------ doğrulama

def normalize(sc, fmt):
    """Bilinmeyen değerleri güvenli varsayılana çek; ciddi sorunları liste olarak döndür."""
    problems = []
    max_words = 15
    sc['format'] = fmt
    if not sc.get('scenes'):
        return ['no scenes']
    n_lines = 0
    n_facts = 0
    has_gag = False
    for S in sc['scenes']:
        if S.get('bg') not in backgrounds.NAMES:
            S['bg'] = 'kitchen'
        chars = [c for c in S.get('characters', []) if c.get('id') in CAST][:3]
        ids = [c['id'] for c in chars]
        S['characters'] = chars
        for L in S.get('lines', []):
            if L.get('char') not in CAST:
                problems.append(f"unknown character {L.get('char')}"); continue
            if L['char'] not in ids and len(chars) < 3:
                chars.append({'id': L['char'], 'pos': 'right' if chars and chars[0].get('pos') == 'left' else 'left'})
                ids.append(L['char'])
            if L.get('emotion') not in EMOTIONS:
                L['emotion'] = 'neutral'
            if L.get('pose') and L['pose'] not in POSES:
                L['pose'] = 'standing'
            if L.get('action') and L['action'] not in ACTIONS:
                L['action'] = None
            if L.get('sfx') and L['sfx'] not in SFX:
                L['sfx'] = None
            if L.get('target') and L['target'] not in ids:
                L['target'] = None
            fact = (L.get('fact') or '').strip() if isinstance(L.get('fact'), str) else ''
            L['fact'] = fact or None
            if fact and len(fact.split()) > 18:
                problems.append(f'fact too long: {fact}')
            if fact:
                n_facts = n_facts + 1
            L['reactions'] = {k: v for k, v in (L.get('reactions') or {}).items() if k in ids and v in EMOTIONS}
            text = (L.get('text') or '').strip()
            L['text'] = text
            if len(text.split()) > max_words:
                problems.append(f'line too long ({len(text.split())} words): {text}')
            if BANNED.search(text):
                problems.append(f'not family friendly: {text}')
            if text:
                n_lines += 1
            if L.get('action') or L.get('sfx'):
                has_gag = True
        S['lines'] = [L for L in S.get('lines', []) if L.get('char') in ids and (L['text'] or L.get('action') or L.get('sfx'))]
        if not S['characters']:
            problems.append('scene without characters')
    sc['scenes'] = [S for S in sc['scenes'] if S['lines']]
    lo, hi = 7, 14
    if not lo <= n_lines <= hi:
        problems.append(f'{n_lines} spoken lines (want {lo}-{hi})')
    if sc.get('template') in ('anlatiyor', 'kavga', 'kimlik_krizi') and n_facts < 1:
        problems.append('no "fact" (real fruit info) in any line')
    if not has_gag:
        problems.append('no physical gag / sound effect')
    for k in ('title', 'hook'):
        if not sc.get(k):
            problems.append(f'missing {k}')
    return problems


# ------------------------------------------------------------------ üretim

def load_hist(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'recent': [], 'bank_used': []}


def pick(hist, fmt, rnd):
    recent = [r for r in hist['recent'] if r.get('format', 'short') == fmt]
    last = [r['template'] for r in recent[-2:]]
    template = rnd.choice([k for k in SHORT_TEMPLATES if k not in last])
    used = {r.get('topic') for r in hist['recent'][-14:]}
    topic = rnd.choice([t for t in TOPICS if t not in used] or TOPICS)
    return template, topic


def schema_text():
    return (PROMPTS / 'schema.json').read_text(encoding='utf-8')


def write_with_gemini(fmt, template, topic, hist):
    base = (PROMPTS / 'script_short.txt').read_text(encoding='utf-8')
    recent_titles = '\n'.join('- ' + r.get('title', '') for r in hist['recent'][-15:])
    prompt = base.format(
        character_bible=bible(),
        template=SHORT_TEMPLATES[template],
        topic=topic,
        schema=schema_text(),
        backgrounds=', '.join(backgrounds.NAMES),
        poses=', '.join(POSES), emotions=', '.join(EMOTIONS), actions=', '.join(ACTIONS), sfx=', '.join(SFX),
        recent=recent_titles or '(none yet)',
    )
    ex = sorted(BANK.glob('*.json'))
    random.shuffle(ex)
    shots = []
    for p in ex[:2]:
        e = json.loads(p.read_text(encoding='utf-8'))
        shots.append('\n'.join(f"{L['char']}: {L['text']}" + (f"  [fact: {L['fact']}]" if L.get('fact') else '')
                               + (f"  [action: {L['action']}]" if L.get('action') else '')
                               for S in e['scenes'] for L in S['lines']))
    prompt += ('\n\nİstediğimiz tempo, uzunluk ve espri yoğunluğuna ÖRNEKLER. Her replik ya espri ya hazırlık; '
               'son replik her şeyi ters çevirir. Bu esprileri ve konuları KOPYALAMA:\n\n' + '\n\n---\n\n'.join(shots))
    judge_tpl = (PROMPTS / 'judge.txt').read_text(encoding='utf-8')
    best, best_score, feedback = None, -1, ''
    for attempt in range(4):
        try:
            sc = parse_json(gemini(prompt + feedback))
        except Exception as e:
            log(f'write attempt {attempt + 1} failed: {str(e)[:200]}'); continue
        problems = normalize(sc, fmt)
        if problems:
            log(f'attempt {attempt + 1} rejected: {problems[:3]}')
            feedback = '\n\nÖnceki senaryon şu sebeplerle reddedildi: ' + '; '.join(problems[:5]) + '. Bunları düzelt.'
            continue
        try:
            j = parse_json(gemini(judge_tpl + '\n\nSCRIPT:\n' + json.dumps(sc, ensure_ascii=False), temperature=0.2))
            score = float(j.get('score', 0))
        except Exception as e:
            log(f'judge failed ({str(e)[:120]}), accepting script'); score, j = 7.0, {}
        log(f'attempt {attempt + 1}: score {score} | {sc.get("title")}')
        if score > best_score:
            best, best_score = sc, score
        if score >= 7:
            break
        feedback = (f"\n\nBir komedi editörü son senaryona {score}/10 verdi. En zayıf kısım: {j.get('weakest_part')}. "
                    f"Düzeltme: {j.get('fix')}. YENİ ve daha komik bir senaryo yaz.")
    if best is None:
        raise RuntimeError('Gemini produced no valid script')
    best['judge_score'] = best_score
    return best


def from_bank(fmt, hist):
    used = set(hist.get('bank_used', []))
    for p in sorted(BANK.glob('*.json')):
        sc = json.loads(p.read_text(encoding='utf-8'))
        if sc.get('format', 'short') == fmt and sc['id'] not in used:
            normalize(sc, fmt)
            sc['source'] = 'bank'
            return sc
    return None


def make_script(fmt, hist, seed=None):
    rnd = random.Random(seed)
    template, topic = pick(hist, fmt, rnd)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    prefer_bank = os.environ.get('SCRIPT_SOURCE', '').lower() == 'bank'
    if os.environ.get('GEMINI_API_KEY') and not prefer_bank:
        try:
            sc = write_with_gemini(fmt, template, topic, hist)
            sc.update(id=f'{fmt}_{stamp}', template=template, topic=topic, source='gemini')
            if sc.get('judge_score', 0) >= 5 or from_bank(fmt, hist) is None:
                return sc
            log(f"best Gemini score {sc['judge_score']} < 5, using a bank script instead")
        except Exception as e:
            log(f'Gemini failed, falling back to bank: {str(e)[:200]}')
    sc = from_bank(fmt, hist)
    if sc is None:
        raise RuntimeError(f'no {fmt} script available: set GEMINI_API_KEY or add scripts to bank/')
    sc['bank_id'] = sc['id']
    sc['id'] = f"{fmt}_{stamp}"
    return sc
