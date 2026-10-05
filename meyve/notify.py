"""Telegram bildirimi: video yüklenince videonun kendisi + başlık + link; hata olursa uyarı.
Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (ikisi de GitHub Secrets). Yoksa sessizce atlanır.
Kurulum: python tools/telegram_setup.py
"""
import os

API = 'https://api.telegram.org/bot{token}/{method}'


def enabled():
    return bool(os.environ.get('TELEGRAM_BOT_TOKEN') and os.environ.get('TELEGRAM_CHAT_ID'))


def _call(method, files=None, **data):
    import requests
    r = requests.post(API.format(token=os.environ['TELEGRAM_BOT_TOKEN'], method=method),
                      data={'chat_id': os.environ['TELEGRAM_CHAT_ID'], **data}, files=files, timeout=120)
    if not r.ok:
        raise RuntimeError(f'telegram {r.status_code}: {r.text[:200]}')


def message(text):
    """Metin gönder (hata vermez: bildirim yüzünden video akışı asla durmaz)."""
    if not enabled():
        return
    try:
        _call('sendMessage', text=text[:4000], disable_web_page_preview='true')
    except Exception as e:
        print(f'[notify] telegram mesajı gönderilemedi: {e}', flush=True)


def copyable(label, text):
    """Başlık + dokununca kopyalanan kutu (Telegram'da <pre> bloğuna dokunmak içeriği kopyalar)."""
    if not enabled():
        return
    esc = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    try:
        _call('sendMessage', text=f'{label}\n<pre>{esc[:3800]}</pre>', parse_mode='HTML', disable_web_page_preview='true')
    except Exception as e:
        print(f'[notify] telegram mesajı gönderilemedi: {e}', flush=True)
        message(f'{label}\n\n{text}')


def album(paths, caption=''):
    """Fotoğraf albümü (en fazla 10): kaydırmalı gönderi slaytları."""
    if not enabled():
        return False
    import json
    files, media = {}, []
    try:
        for i, p in enumerate(paths[:10]):
            files[f'p{i}'] = (os.path.basename(str(p)), open(p, 'rb'), 'image/jpeg')
            media.append({'type': 'photo', 'media': f'attach://p{i}', **({'caption': caption[:1000]} if i == 0 and caption else {})})
        _call('sendMediaGroup', files=files, media=json.dumps(media))
        return True
    except Exception as e:
        print(f'[notify] telegram albümü gönderilemedi: {e}', flush=True)
        return False
    finally:
        for f in files.values():
            f[1].close()


def document(path, caption):
    """Orijinal dosyayı sıkıştırmadan gönder (TikTok/Instagram'a kaliteli yüklemek için)."""
    if not enabled():
        return
    try:
        with open(path, 'rb') as f:
            _call('sendDocument', files={'document': (os.path.basename(str(path)), f, 'video/mp4')}, caption=caption[:1000])
    except Exception as e:
        print(f'[notify] telegram dosyası gönderilemedi: {e}', flush=True)
        message(caption)


def video(path, caption):
    """Videoyu gönder (Telegram botları 50 MB'a kadar); olmazsa metne düş."""
    if not enabled():
        return
    try:
        with open(path, 'rb') as f:
            _call('sendVideo', files={'video': ('video.mp4', f, 'video/mp4')}, caption=caption[:1000],
                  supports_streaming='true', width='1080', height='1920')
    except Exception as e:
        print(f'[notify] telegram videosu gönderilemedi: {e}', flush=True)
        message(caption)
