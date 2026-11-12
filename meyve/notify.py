"""Telegram bildirimi: video yüklenince videonun kendisi + başlık + link; hata olursa uyarı.
Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (ikisi de GitHub Secrets). Yoksa sessizce atlanır.
Kurulum: python tools/telegram_setup.py
"""
import os

API = 'https://api.telegram.org/bot{token}/{method}'


def _quiet():   # kullanıcı isteği (2026-11-12): TR 21:00–09:00 arası Telegram bildirimi sessiz gelsin
    from datetime import datetime, timedelta, timezone
    h = (datetime.now(timezone.utc) + timedelta(hours=3)).hour
    return {'disable_notification': 'true'} if (h >= 21 or h < 9) else {}


def enabled():
    return bool(os.environ.get('TELEGRAM_BOT_TOKEN') and os.environ.get('TELEGRAM_CHAT_ID'))


def _call(method, files=None, **data):
    import requests
    r = requests.post(API.format(token=os.environ['TELEGRAM_BOT_TOKEN'], method=method),
                      data={'chat_id': os.environ['TELEGRAM_CHAT_ID'], **_quiet(), **data}, files=files, timeout=120)
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
    return  # 2026-11-11: açıklama metinleri artık gönderilmiyor
    """Başlık + dokununca kopyalanan kutu (Telegram'da <pre> bloğuna dokunmak içeriği kopyalar)."""
    if not enabled():
        return
    esc = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    try:
        _call('sendMessage', text=f'{label}\n<pre>{esc[:3800]}</pre>', parse_mode='HTML', disable_web_page_preview='true')
    except Exception as e:
        print(f'[notify] telegram mesajı gönderilemedi: {e}', flush=True)
        message(f'{label}\n\n{text}')


# 2026-11-11: kullanıcı Telegram'a dosya istemiyor; sadece "paylaşıldı" yazısı (album/document/video metne düşer)
def album(paths, caption=''):
    if caption:
        message(caption)
    return True


def document(path, caption):
    message(caption)


def video(path, caption):
    message(caption)
