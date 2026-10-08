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
from . import lang
from .lang import LANG, TR

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / 'prompts' if TR else ROOT / 'prompts' / LANG
BANK = ROOT / 'bank' if TR else ROOT / 'bank' / LANG     # hazır senaryolar dile özel (en: henüz yok)
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
    'normal_psikopat': 'Normal vs Psikopat: aynı mutfak durumu iki kez: sahne etiketi "Normal meyve" (sakin, mantıklı), '
                       'sonra "Psikopat meyve" (abartılı, absürt, çizgi film gibi; gerçek şiddet yok); son replik en komik.',
    'tipler': 'Tipler: "Mutfaktaki X tipleri" -> 3-4 hızlı sahne, her sahne bir tip (sahne "label" ile, ör. "Gösterişçi"), '
              'sonuncusu en absürt.',
}
# Haftalık uzun bölüm dizileri (yatay, 3-5 dk)
LONG_SERIES = {
    'mutfak_mahkemesi': 'Mutfak Mahkemesi: bir meyve diğerini mahkemeye verir; hâkim, avukatlar, tanıklar ve '
                        'delil olarak gerçek meyve bilgileri; karar ters köşe.',
    'tezgah_ofisi': 'Tezgâh Ofisi: meyveler bir ofiste çalışıyormuş gibi; patron, toplantı, terfi kavgası, '
                    'iş yeri dedikodusu; yetişkin iş hayatı parodisi.',
    'buzdolabi_apartmani': 'Buzdolabı Apartmanı: her raf bir daire; komşu kavgaları, aidat, yönetici seçimi, '
                           'kapı açılınca herkes donup kalır.',
}
TOPICS = ['meyve mi sebze mi', 'yaşlanmak / kararmak', 'buzdolabında gece', 'pazarda seçilmemek', 'smoothie seçmeleri',
          'meyve salatası seçmeleri', 'kahvaltı sofrası', 'diyet yapan insan', 'pahalı olmak', 'ekşi olmak',
          'su oranı yarışması', 'yaz geldi', 'kış meyvesi olmak', 'reçel olmak', 'turşu tehlikesi', 'sosyal medya',
          'ofiste öğle yemeği', 'manavda indirim', 'çekirdek / tohum', 'vitamin yarışı', 'tartıya çıkmak',
          'egzotik meyve kıskançlığı', 'ilk iş günü (pazar tezgâhı)', 'sağlıklı beslenme', 'smoothie', 'ağaçtan düşmek',
          'sınav stresi', 'dedikodu', 'doğum günü pastası', 'piknik', 'tatil (plaj)', 'spor salonu',
          'patronla toplantı', 'kira zammı', 'maaş günü', 'ilk buluşma', 'ev arkadaşı', 'aile grup sohbeti',
          'pazartesi sendromu', 'trafikte sıkışmak', 'kargo iadesi', 'diyetisyen randevusu', 'iş görüşmesi',
          'bayram ziyareti', 'kayınvalide geliyor', 'yeni yıl kararları']
BANNED = re.compile(r'\b(öl|öldür|kan|seks|içki|bira|şarap|uyuşturucu|aptal|salak|gerizekalı|lanet|siktir|kahretsin|'
                    r'kill|dead|blood|sex|drunk|beer|wine|drug)\b', re.I)

# Başlık/kanca korku-gerilim-şok üzerine kurulmasın (komedi kanalı); çizgi film gag'leri sahnede serbest
SHOCK = re.compile(r'(bıçak|gerilim|dehşet|korku|kâbus|kabus|vahşet|katliam|🔪|knife|terror|horror|nightmare|'
                   r'scary|creepy|massacre|brutal|disturbing)', re.I)

# ---------------------------------------------------------------- ABD kanalı (CONTENT_LANG=en)
# Türkçe kanalın çevirisi DEĞİL: Amerikan izleyiciye özel şablon, konu ve diziler (özgün içerik).
SHORT_TEMPLATES_EN = {
    'pov': 'POV: the hook starts with "POV:" and drops the viewer into a relatable American everyday moment; the '
           'fruits react to "you" and it escalates every line; last line flips it.',
    'types_of': 'Types of...: "Types of fruit at the X" -> 3-4 fast scenes, each a type (scene "label", e.g. '
                '"The Influencer"), the last one the most absurd.',
    'roast': 'Roast battle: two fruits roast each other with REAL facts about themselves (fact), the burns get '
             'harder, the last line is a twist burn from a third fruit.',
    'confessional': 'Reality-show confessional: fruits talk to the camera (look_camera) about drama in the fruit '
                    'bowl, cutting between them like a reality TV show; the last confessional reveals the twist.',
    'fridge_after_dark': 'Fridge after dark: what the fruits do when the fridge door closes; when the human opens '
                         'it everyone freezes; at the end a giant hand ("grabbed") takes the least expected one.',
    'normal_vs_psycho': 'Normal vs Psycho: the same kitchen situation twice - scene label "Normal fruit" (calm, sensible), '
                        'then scene label "Psycho fruit" (unhinged, absurd, cartoonish; no real violence); the last line is '
                        'the funniest.',
    'plot_twist': 'Plot twist: a totally normal conversation that ends in the last 3 seconds with a twist '
                  '(smoothie, blender, fruit salad, giant hand).',
}
TOPICS_EN = ['Monday morning meeting', 'rent is due', 'group chat drama', 'the office potluck', 'meal prep Sunday',
             'gym bros', 'brunch with the girls', 'first date', 'roommate rules', 'the self-checkout machine',
             'tipping screens', 'road trip', 'Thanksgiving dinner with family', 'Fourth of July barbecue',
             'Halloween costume party', 'pumpkin spice season', 'Black Friday shopping', 'New Year resolutions',
             'smoothie bowl influencers', 'keto diet', 'farmers market', 'job interview', 'performance review',
             'working from home', 'the HOA meeting', 'a wedding toast', 'college dorm life', 'tax season',
             'the dentist appointment', 'the weather app lying', 'airport security', 'the neighbor who borrows things',
             'the fruit bowl seating chart', 'organic vs regular price tag', 'picnic in the park', 'the big game party']
LONG_SERIES_EN = {
    'fruit_court': 'Fruit Court: a daytime-TV-style courtroom show; one fruit sues another, judge, lawyers, '
                   'witnesses, real fruit facts as evidence; the verdict is a twist.',
    'fridge_office': 'The Fridge Office: a mockumentary about a small office inside a fridge; boss, meetings, '
                     'promotion rivalry and talking-head confessionals to the camera.',
    'fruit_villa': 'Fruit Villa: a reality dating show parody in a summer villa; couples, challenges, '
                   'dramatic recouplings, a host who loves a dramatic pause; keep it clean.',
}
BANNED_EN = re.compile(r'\b(kill|dead|die|blood|sex|sexy|drunk|beer|wine|vodka|drugs?|weed|damn|hell|stupid|idiot|'
                       r'shut up|crap|wtf)\b', re.I)
if not TR:
    SHORT_TEMPLATES, TOPICS, LONG_SERIES, BANNED = SHORT_TEMPLATES_EN, TOPICS_EN, LONG_SERIES_EN, BANNED_EN
FACT_TEMPLATES = ('anlatiyor', 'kavga', 'kimlik_krizi', 'roast')
MSG = {'tr': dict(examples='\n\nİstediğimiz tempo, uzunluk ve espri yoğunluğuna ÖRNEKLER. Her replik ya espri ya hazırlık; '
                           'son replik her şeyi ters çevirir. Bu esprileri ve konuları KOPYALAMA:\n\n',
                  rejected='\n\nÖnceki senaryon şu sebeplerle reddedildi: {p}. Bunları düzelt.',
                  judged="\n\nBir komedi editörü son senaryona {score}/10 verdi. En zayıf kısım: {weak}. "
                         "Düzeltme: {fix}. YENİ ve daha komik bir senaryo yaz."),
       'en': dict(examples='\n\nEXAMPLES of the pacing and joke density we want. Do NOT copy these jokes or topics:\n\n',
                  rejected='\n\nYour previous script was rejected for: {p}. Fix these.',
                  judged="\n\nA comedy editor rated your last script {score}/10. Weakest part: {weak}. "
                         "Fix: {fix}. Write a NEW, funnier script.")}[LANG]


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
    max_words = 15 if fmt == 'short' else 22
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
    lo, hi = (7, 14) if fmt == 'short' else (32, 65)
    if not lo <= n_lines <= hi:
        problems.append(f'{n_lines} spoken lines (want {lo}-{hi})')
    if sc.get('template') in FACT_TEMPLATES and n_facts < 1:
        problems.append('no "fact" (real fruit info) in any line')
    if not has_gag:
        problems.append('no physical gag / sound effect')
    if fmt == 'long' and n_facts < 3:
        problems.append(f'only {n_facts} "fact" lines (want 4-8)')
    for k in ('title', 'hook'):
        if not sc.get(k):
            problems.append(f'missing {k}')
        elif SHOCK.search(sc[k]):  # YouTube (Tem 2026): şok/korku için tasarlanmış başlıklar para kazanamaz
            problems.append(f'{k} leans on fear/shock, make it comedic instead: {sc[k]}')
    return problems


# ------------------------------------------------------------------ üretim

def load_hist(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'recent': [], 'bank_used': []}


def template_performance():
    """Bu kanalın Shorts şablonlarının ortalama izlenmesi (en az 20 saatlik videolar; YouTube'a erişilemezse boş)."""
    import csv
    from datetime import datetime, timezone
    path = lang.data('published.csv')
    if not path.exists() or not os.environ.get('YT_REFRESH_TOKEN'):
        return {}
    now = datetime.now(timezone.utc)
    rows = [r for r in csv.DictReader(open(path, encoding='utf-8'))
            if r.get('format', 'short') == 'short' and r.get('video_id') and r.get('template') in SHORT_TEMPLATES
            and (now - datetime.strptime(r['date_utc'], '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)).total_seconds() > 20 * 3600]
    rows = rows[-40:]
    if not rows:
        return {}
    try:
        import upload
        items = upload.client().videos().list(part='statistics', id=','.join(r['video_id'] for r in rows)).execute()['items']
    except Exception as e:
        print(f'[writer] performans okunamadı: {str(e)[:150]}', flush=True)
        return {}
    views = {i['id']: int(i['statistics'].get('viewCount', 0)) for i in items}
    out = {}
    for r in rows:
        if r['video_id'] in views:
            out.setdefault(r['template'], []).append(views[r['video_id']])
    return {k: sum(v) / len(v) for k, v in out.items()}



def viewer_request(path, rnd, chance=0.5):
    """Yorumlardan gelen izleyici isteği (tools/auto_reply.py yazar): varsa yarı olasılıkla sıradaki konu olur."""
    if not path.exists() or rnd.random() > chance:
        return None
    reqs = json.loads(path.read_text(encoding='utf-8'))
    for r in reqs:
        if not r.get('used'):
            r['used'] = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            path.write_text(json.dumps(reqs, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
            print(f"[writer] izleyici isteği konu oldu: {r['topic']}", flush=True)
            return r['topic']
    return None

def pick(hist, fmt, rnd):
    recent = [r for r in hist['recent'] if r.get('format', 'short') == fmt]
    if fmt == 'long':                                   # diziler sırayla döner
        order = list(LONG_SERIES)
        template = order[len(recent) % len(order)]
    else:
        last = [r['template'] for r in recent[-2:]]
        keys = [k for k in SHORT_TEMPLATES if k not in last]
        perf = template_performance()
        top = max(perf.values(), default=0)
        # keşif + sömürü: iyi giden şablon en fazla 6 kat sık; hiç/az izlenen de taban şansını korur
        w = [1.0 + 5.0 * perf[k] / top if top and k in perf else 1.0 for k in keys]
        if perf:
            print('[writer] şablon ortalama izlenme:', {k: round(v) for k, v in perf.items()}, flush=True)
        template = rnd.choices(keys, weights=w)[0]
    used = {r.get('topic') for r in hist['recent'][-14:]}
    topic = rnd.choice([t for t in TOPICS if t not in used] or TOPICS)
    if fmt == 'short':
        topic = viewer_request(Path(__file__).resolve().parent.parent / ('viewer_requests.json' if TR else 'viewer_requests_en.json'), rnd) or topic
    return template, topic


def schema_text():
    return (PROMPTS / 'schema.json').read_text(encoding='utf-8')


def write_with_gemini(fmt, template, topic, hist):
    base = (PROMPTS / ('script_short.txt' if fmt == 'short' else 'script_long.txt')).read_text(encoding='utf-8')
    recent_titles = '\n'.join('- ' + r.get('title', '') for r in hist['recent'][-15:])
    prompt = base.format(
        character_bible=bible(),
        template=(SHORT_TEMPLATES if fmt == 'short' else LONG_SERIES)[template],
        topic=topic,
        schema=schema_text(),
        backgrounds=', '.join(backgrounds.NAMES),
        poses=', '.join(POSES), emotions=', '.join(EMOTIONS), actions=', '.join(ACTIONS), sfx=', '.join(SFX),
        recent=recent_titles or '(none yet)',
    )
    ex = sorted(BANK.glob('*.json'))
    random.shuffle(ex)
    shots = []
    for p in ex[:2 if fmt == 'short' else 0]:      # bank'ta sadece Shorts var; uzun bölüme örnek verilmez
        e = json.loads(p.read_text(encoding='utf-8'))
        shots.append('\n'.join(f"{L['char']}: {L['text']}" + (f"  [fact: {L['fact']}]" if L.get('fact') else '')
                               + (f"  [action: {L['action']}]" if L.get('action') else '')
                               for S in e['scenes'] for L in S['lines']))
    if shots:
        prompt += MSG['examples'] + '\n\n---\n\n'.join(shots)
    judge_tpl = (PROMPTS / 'judge.txt').read_text(encoding='utf-8')
    best, best_score, feedback = None, -1, ''
    for attempt in range(7):   # 7/10 kalite çıtasını yakalamak için daha çok deneme
        try:
            sc = parse_json(gemini(prompt + feedback, timeout=120 if fmt == 'short' else 300))
        except Exception as e:
            log(f'write attempt {attempt + 1} failed: {str(e)[:200]}'); continue
        problems = normalize(sc, fmt)
        if problems:
            log(f'attempt {attempt + 1} rejected: {problems[:3]}')
            feedback = MSG['rejected'].format(p='; '.join(problems[:5]))
            continue
        try:
            j = parse_json(gemini(judge_tpl + '\n\nSCRIPT:\n' + json.dumps(sc, ensure_ascii=False), temperature=0.2))
            score = float(j.get('score', 0))
        except Exception as e:
            log(f'judge failed ({str(e)[:120]})'); score, j = 6.0, {}
        log(f'attempt {attempt + 1}: score {score} | {sc.get("title")}')
        if score > best_score:
            best, best_score = sc, score
        if score >= 7:
            break
        feedback = MSG['judged'].format(score=score, weak=j.get('weakest_part'), fix=j.get('fix'))
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
            # kalite çıtası: 6'nın altı yüklenmez (bank varsa onu kullan) — düşük kalite seri üretim sinyali verir
            if sc.get('judge_score', 0) >= 6 or from_bank(fmt, hist) is None:
                return sc
            log(f"best Gemini score {sc['judge_score']} < 6, using a bank script instead")
        except Exception as e:
            log(f'Gemini failed, falling back to bank: {str(e)[:200]}')
    sc = from_bank(fmt, hist)
    if sc is None:
        raise RuntimeError(f'no {fmt} script available: set GEMINI_API_KEY or add scripts to bank/')
    sc['bank_id'] = sc['id']
    sc['id'] = f"{fmt}_{stamp}"
    return sc
