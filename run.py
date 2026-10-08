"""Konuşan Meyveler pipeline (Dex and Friends'ten uyarlandı). Bir çalıştırma = bir Shorts ya da bir uzun bölüm.

    senaryo (Gemini yazar + hakem, yoksa bank/) -> ses + animasyon render -> YouTube'a yükle -> kaydet -> Telegram

Kullanım
  python run.py                    # 1 Shorts
  python run.py --format long      # 1 haftalık uzun bölüm (yatay, 3-5 dk, Gemini gerekir)
  python run.py --no-upload        # sadece render (output/<id>/video.mp4)
  python run.py --script bank/001_domates_kimlik.json --no-upload

Env
  GEMINI_API_KEY   senaryo üretimi (yoksa bank/ kullanılır)
  YT_PRIVACY       public | private | unlisted | off  (varsayılan: YT secrets varsa private, yoksa off)
  MAX_PER_DAY      Shorts günlük üst sınırı (varsayılan 3)
  AZURE_SPEECH_KEY / AZURE_SPEECH_REGION  (opsiyonel) resmî Microsoft ses; yoksa edge-tts
  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID    (opsiyonel) video + açıklama bildirimi
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN, YT_CHANNEL_ID
Yüklemesi başarısız olan video queue/<id>.json'a yazılır, sonraki çalıştırmada aynı senaryo yeniden render edilip yüklenir.
"""
import argparse
import csv
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from meyve import lang, notify, render, writer  # noqa: E402
from meyve.cast import CAST  # noqa: E402

# kayıtlar dile göre ayrı: published.csv (tr) / published_en.csv (en) ...
HIST = lang.data('history.json')
PUBLISHED = lang.data('published.csv')
QUEUE = lang.data('queue')
PLAYLISTS = lang.data('playlists.json')
OUT = HERE / 'output'
FIELDS = ['id', 'date_utc', 'format', 'video_id', 'privacy', 'template', 'source', 'score', 'title']
BASE_TAGS_TR = ['konuşan meyveler', 'meyveler', 'komik', 'animasyon', 'çizgi film', 'komik videolar', 'shorts',
             'meyve', 'sebze', 'eğlenceli bilgiler', 'bilgi', 'mizah']
BASE_TAGS_EN = ['talking fruit', 'fruit drama', 'funny fruit', 'comedy', 'animation', 'cartoon comedy', 'shorts',
                'funny shorts', 'fruit facts', 'fun facts', 'relatable comedy', 'animated comedy']
T = {'tr': dict(facts='\n\n🍓 Bu videodaki gerçek bilgiler:\n', cast='Oyuncular',
                daily='Her gün yeni konuşan meyve videosu! Abone ol, sıradaki kim kızacak kaçırma 🍋\n\n',
                weekly='Her hafta yeni bölüm, her gün yeni Shorts! Abone ol, bildirimleri aç 🔔🍋\n\n'),
     'en': dict(facts='\n\n🍓 Real fruit facts in this video:\n', cast='Cast',
                daily='New fruit drama every day! Subscribe so you never miss who snaps next 🍋\n\n',
                weekly='New episode every week, new Shorts every day! Subscribe and turn on notifications 🔔🍋\n\n'),
     }[lang.LANG]


def log(msg):
    print(f'[run] {msg}', flush=True)


def gh_annotation(level, msg):
    print(f'::{level}::{msg}' if os.environ.get('GITHUB_ACTIONS') else f'[run] {level.upper()}: {msg}', flush=True)


def published_rows():
    if not PUBLISHED.exists():
        return []
    with PUBLISHED.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def uploaded_today(fmt):
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    return sum(1 for r in published_rows() if r['date_utc'].startswith(today) and r.get('format', 'short') == fmt)


def record(sc, video_id, privacy):
    new = not PUBLISHED.exists()
    with PUBLISHED.open('a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({'id': sc['id'], 'date_utc': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'),
                    'format': sc['format'], 'video_id': video_id, 'privacy': privacy,
                    'template': sc.get('template'), 'source': sc.get('source'), 'score': sc.get('judge_score', ''),
                    'title': sc['title']})


def remember(hist, sc):
    hist['recent'].append({'id': sc['id'], 'format': sc['format'], 'template': sc.get('template'),
                           'topic': sc.get('topic'), 'title': sc.get('title'),
                           'date': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')})
    hist['recent'] = hist['recent'][-120:]
    if sc.get('bank_id'):
        hist.setdefault('bank_used', []).append(sc['bank_id'])
    HIST.write_text(json.dumps(hist, indent=2, ensure_ascii=False), encoding='utf-8')


def metadata(sc):
    names = sorted({CAST[c['id']]['name'] for S in sc['scenes'] for c in S['characters']})
    tags = (BASE_TAGS_TR if lang.TR else BASE_TAGS_EN) + [t for t in sc.get('tags', []) if isinstance(t, str)] + [n.lower() for n in names]
    facts = [L['fact'] for S in sc['scenes'] for L in S['lines'] if L.get('fact')]
    by_template = {'pov': '#pov', 'types_of': '#typesof', 'roast': '#roast', 'confessional': '#realitytv',
                   'fridge_after_dark': '#fridge', 'plot_twist': '#plottwist','anlatiyor': '#bilgi', 'kavga': '#kavga', 'kimlik_krizi': '#bunubiliyormuydunuz',
                   'buzdolabi': '#buzdolabı', 'ters_kose': '#terskose', 'tipler': '#tipler'}
    short = sc.get('format', 'short') == 'short'
    base = '#konuşanmeyveler #meyveler #komik #animasyon' if lang.TR else '#fruitdramaclub #talkingfruit #comedy #animation'
    hashtags = ('#shorts ' if short else '') + \
        f"{base} {by_template.get(sc.get('template'), '#mizah' if lang.TR else '#funny')}"
    desc = sc.get('description', '')
    if facts:
        desc += T['facts'] + '\n'.join(f'• {f}' for f in facts)
    desc += (f"\n\n{T['cast']}: {', '.join(names)}\n" + (T['daily'] if short else T['weekly']) + hashtags)
    seen, uniq = set(), []
    for t in tags if short else [t for t in tags if t != 'shorts']:
        if t.lower() not in seen and sum(len(x) for x in uniq) + len(t) < 450:
            seen.add(t.lower()); uniq.append(t)
    return sc['title'][:100], desc, uniq


def privacy_mode(no_upload):
    import upload
    if no_upload:
        return 'off'
    if not upload.configured():
        gh_annotation('warning', 'YouTube secrets missing: render only. Run auth_setup.py to connect the channel.')
        return 'off'
    mode = (os.environ.get('YT_PRIVACY') or '').strip().lower()
    if mode not in ('public', 'private', 'unlisted', 'off'):
        mode = 'private'
    return mode


def enqueue(sc, error, qpath=None):
    QUEUE.mkdir(exist_ok=True)
    p = qpath or QUEUE / f"{sc['id']}.json"
    prev = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    p.write_text(json.dumps({'scenario': sc, 'attempts': prev.get('attempts', 0) + 1, 'last_error': str(error)[:500]},
                            indent=2, ensure_ascii=False), encoding='utf-8')
    log(f"queued {sc['id']} for retry")



def social_once(mp4, title, url, sc):
    """Günün ilk İngilizce Short'u → social/ (artifact 'social-<run>'): fenek-shorts telegram-relay her gün
    TR 18:00'de diğer kanallarla birlikte TikTok/Instagram için Telegram'a yollar."""
    import shutil
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    rows = list(csv.DictReader(PUBLISHED.open(encoding='utf-8'))) if PUBLISHED.exists() else []
    if sum(1 for r in rows if r.get('date_utc', '').startswith(today)) > 1:  # bu video zaten kaydedildi → 1 = ilk
        return
    soc = HERE / 'social'
    soc.mkdir(exist_ok=True)
    shutil.copy(mp4, soc / 'video.mp4')
    tiktok = f"{title}\n\nWhich fruit are you? 👇\n\n#fruitdramaclub #talkingfruit #funny #animation #comedy #fyp"
    insta = (f"{title}\n\nFollow for daily fruit drama 🍋🍉\n\n"
             "#funny #animation #comedy #relatable #fruit")  # Instagram: en fazla 5 etiket
    (soc / 'post.json').write_text(json.dumps({'channel': 'Fruit Drama Club', 'title': title, 'url': url,
                                               'tiktok': tiktok, 'instagram': insta}, ensure_ascii=False, indent=1),
                                   encoding='utf-8')
    log('social: günün videosu hazır (Telegram relay)')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--format', choices=['short', 'long'], default='short')
    ap.add_argument('--no-upload', action='store_true')
    ap.add_argument('--script', help='belirli bir senaryo JSON dosyası')
    args = ap.parse_args()
    import upload

    fmt = args.format
    mode = privacy_mode(args.no_upload)
    log(f'format {fmt} | upload mode: {mode}')
    if mode != 'off':
        cap = int(os.environ.get('MAX_PER_DAY') or 3)
        if uploaded_today(fmt) >= cap:
            log(f'daily cap of {cap} {fmt} reached, nothing to do'); return
        try:
            log(f'channel check ok: {upload.check_channel()}')
        except Exception as e:
            gh_annotation('error', f'channel check failed, nothing uploaded: {e}'); raise SystemExit(1)

    hist = writer.load_hist(HIST)
    qpath = None
    queued = sorted(p for p in QUEUE.glob('*.json')) if QUEUE.exists() else []
    queued = [p for p in queued if json.loads(p.read_text(encoding='utf-8'))['scenario'].get('format') == fmt]
    if args.script:
        sc = json.loads(Path(args.script).read_text(encoding='utf-8'))
        writer.normalize(sc, sc.get('format', fmt))
        sc.setdefault('source', 'file')
    elif queued:
        qpath = queued[0]
        sc = json.loads(qpath.read_text(encoding='utf-8'))['scenario']
        log(f"retrying queued {sc['id']}")
    else:
        sc = writer.make_script(fmt, hist)
    log(f"script [{sc.get('source')}] {sc.get('template')} | {sc['title']}")

    out = OUT / sc['id']
    out.mkdir(parents=True, exist_ok=True)
    (out / 'script.json').write_text(json.dumps(sc, indent=2, ensure_ascii=False), encoding='utf-8')
    try:
        mp4, dur = render.render(sc, out, preview_png=out / 'thumb.png')
    except Exception as e:
        traceback.print_exc(); gh_annotation('error', f'render failed: {e}')
        notify.message(f"🍋 {lang.S['channel']}: render failed — {str(e)[:300]}"); raise SystemExit(1)
    title, desc, tags = metadata(sc)
    (out / 'meta.json').write_text(json.dumps({'title': title, 'description': desc, 'tags': tags, 'duration': dur},
                                              indent=2, ensure_ascii=False), encoding='utf-8')
    log(f'rendered {mp4} ({dur:.1f}s)')
    if not qpath and not args.no_upload:
        remember(hist, sc)

    if mode == 'off':
        log('upload skipped (mode off)'); return
    try:
        vid = upload.upload(mp4, title, desc, tags, mode)
    except upload.QuotaError as e:
        enqueue(sc, e, qpath); gh_annotation('warning', 'YouTube quota reached, video queued for the next run.')
        notify.message(f"🍋 {lang.S['channel']}: YouTube quota reached, video queued."); return
    except Exception as e:
        traceback.print_exc(); enqueue(sc, e, qpath); gh_annotation('error', f'upload failed: {e}'); raise SystemExit(1)
    record(sc, vid, mode)
    if qpath:
        qpath.unlink(missing_ok=True)
    url = f'https://youtube.com/shorts/{vid}' if fmt == 'short' else f'https://youtu.be/{vid}'
    if fmt == 'long' and (out / 'thumb.png').exists():   # uzun videoda kapak görseli tıklanmada belirleyici
        try:
            upload.set_thumbnail(vid, out / 'thumb.png'); log('thumbnail set')
        except Exception as e:
            log(f'thumbnail skipped (kanal telefonla doğrulanmamış olabilir): {str(e)[:160]}')
    log(f'uploaded {url} ({mode})')
    if not lang.TR and fmt == 'short' and mode == 'public':
        social_once(mp4, title, url, sc)
    pls = json.loads(PLAYLISTS.read_text(encoding='utf-8')) if PLAYLISTS.exists() else {}
    if sc.get('template') in pls:
        try:
            upload.add_to_playlist(pls[sc['template']], vid); log(f"added to playlist {sc['template']}")
        except Exception as e:
            log(f'playlist add skipped: {str(e)[:160]}')
    notify.video(mp4, f'🍓 {title}\n{url}')
    notify.copyable('TikTok / Instagram:', f"{title}\n\n{desc.split(chr(10) + chr(10) + T['cast'])[0]}\n\n"
                    + ('#konuşanmeyveler #meyveler #komik #animasyon #keşfet #fyp' if lang.TR else
                       '#fruitdramaclub #talkingfruit #comedy #fyp'))


if __name__ == '__main__':
    main()
