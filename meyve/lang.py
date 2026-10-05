"""İçerik dili: CONTENT_LANG=tr (varsayılan, Konuşan Fruits) | en (ABD kanalı).

Aynı kod iki kanalı üretir; dile bağlı her şey buradan okunur. Kayıt dosyaları dile göre ayrılır
(published.csv / published_en.csv ...), böylece kanalların geçmişi birbirine karışmaz.
"""
import os
from pathlib import Path

LANG = (os.environ.get('CONTENT_LANG') or 'tr').strip().lower()
if LANG not in ('tr', 'en'):
    raise SystemExit(f'CONTENT_LANG must be tr or en, got {LANG!r}')
TR = LANG == 'tr'
ROOT = Path(__file__).resolve().parent.parent


def data(name):
    """'published.csv' -> 'published.csv' (tr) | 'published_en.csv' (en); klasörler için de geçerli."""
    p = ROOT / name
    if TR:
        return p
    return p.with_name(f'{p.stem}_{LANG}{p.suffix}')


def upper(s):
    """Ekran yazısı büyük harf: Türkçede i -> İ, ı -> I."""
    if TR:
        return s.replace('i', 'İ').replace('ı', 'I').upper()
    return s.upper()


S = {
    'tr': dict(
        channel='Konuşan Fruits',
        fact_label='BİLGİ:',
        cta='Abone ol & beğen!',
        cta_short='Yarın yeni meyve kavgası!',
        cta_long='Her hafta yeni bölüm!',
        tts_lang='tr-TR',
        amp=' ve ', pct=' yüzde ',
    ),
    'en': dict(
        channel='Fruit Drama Club',
        fact_label='FUN FACT:',
        cta='Like & subscribe!',
        cta_short='New fruit drama every day!',
        cta_long='New episode every week!',
        tts_lang='en-US',
        amp=' and ', pct=' percent ',
    ),
}[LANG]
