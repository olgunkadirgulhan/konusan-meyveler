"""Kanal kurulumu (tekrar çalıştırılabilir, GitHub Actions 'channel' workflow'u ile, secrets'taki token kullanılır):
açıklama, anahtar kelimeler, ülke/dil, banner, filigran, oynatma listeleri, ana sayfa bölümleri,
yüklenmiş videoların listelere eklenmesi.

Profil fotoğrafı ve @handle API ile değiştirilemez: branding/profile.png'yi YouTube Studio > Özelleştirme'den yükle.
"""
import csv
import json
import os
import sys
from pathlib import Path

from googleapiclient.http import MediaFileUpload

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import upload  # noqa: E402

BRAND = HERE / 'branding'
PLAYLISTS_FILE = HERE / 'playlists.json'

DESCRIPTION = """Mutfakta işler karıştı! 🍋🍅🍉

Konuşan Fruits'e hoş geldin: tezgâhta, buzdolabında ve pazar tezgâhında yaşanan meyve ve sebze dramaları.
Laf sokan limonlar, kendini sebze sanmayan domatesler, blender korkusu yaşayan çilekler...

Her videoda kahkahanın yanında meyveler hakkında GERÇEK bir bilgi var: ekranda sarı BİLGİ kartında görürsün,
açıklamada da yazar.

Kadro:
🍋 Limon: ekşi, laf sokmayı sever
🍅 Domates: "Ben meyveyim!" diye bağırmaktan yorulmadı
🍉 Karpuz: yazın kralı, biraz şişkin ego
🍊 Portakal: C vitamini şampiyonu olduğunu sanıyor
🌶️ Acı Biber: kısa boylu, yüksek gerilimli
🥑 Avokado: pahalı ve bunu herkese hatırlatıyor
🍓 Çilek, 🍌 Muz, 🧅 Soğan, 🍍 Ananas, 🥒 Salatalık

Her gün yeni meyve kavgası! Abone ol, yorumlara sıradaki kavgayı kimin çıkaracağını yaz 👇

#KonuşanFruits #konuşanmeyveler #komedi"""

KEYWORDS = ('"Konuşan Fruits" "konuşan meyveler" "komik meyveler" "meyve kavgası" "komik animasyon" '
            '"komik videolar" "türkçe komedi" "animasyon shorts" "meyve bilgileri" "ilginç bilgiler" '
            '"mutfak komedisi" "komik shorts"')

PLAYLISTS = {
    'kavga': ('Meyve Kavgaları 🥊', 'İki meyve, bir iddia, sıfır geri adım.'),
    'anlatiyor': ('Meyve Anlatıyor 🍋', 'Bir meyve kendini anlatır: komik ama gerçek bilgilerle.'),
    'kimlik_krizi': ('Kimlik Krizi 😱', 'Bir meyve kendisi hakkındaki gerçeği öğrenir. Sonuç: dram.'),
    'buzdolabi': ('Buzdolabı Dramaları 🧊', 'Kapı kapanınca buzdolabında neler oluyor?'),
    'ters_kose': ('Ters Köşe 💀', 'Normal bir sohbet... son 3 saniyeye kadar.'),
    'tipler': ('Mutfaktaki Tipler', 'Her mutfakta bu tipler var.'),
    'mutfak_mahkemesi': ('Mutfak Mahkemesi ⚖️', 'Uzun bölümler: meyveler mahkemede, deliller gerçek bilgiler.'),
    'tezgah_ofisi': ('Tezgâh Ofisi 💼', 'Uzun bölümler: patron, toplantı, terfi kavgası... meyve versiyonu.'),
    'buzdolabi_apartmani': ('Buzdolabı Apartmanı 🏢', 'Uzun bölümler: her raf bir daire, her kat bir dram.'),
}
SECTIONS = ['kavga', 'ters_kose', 'kimlik_krizi', 'buzdolabi', 'anlatiyor', 'tipler']


def step(name, fn):
    try:
        fn(); print(f'✓ {name}', flush=True)
    except Exception as e:
        print(f'✗ {name}: {str(e)[:300]}', flush=True)


def main():
    yt = upload.client()
    ch = yt.channels().list(part='id,snippet,brandingSettings,status', mine=True).execute()['items'][0]
    cid, title = ch['id'], ch['snippet']['title']
    print(f'kanal: {title}')
    published = list(csv.DictReader(open(HERE / 'published.csv', encoding='utf-8'))) if (HERE / 'published.csv').exists() else []

    def branding():
        banner = yt.channelBanners().insert(
            media_body=MediaFileUpload(str(BRAND / 'banner.png'), mimetype='image/png')).execute()
        channel = {'title': title, 'description': DESCRIPTION, 'keywords': KEYWORDS, 'country': 'TR',
                   'defaultLanguage': 'tr'}
        yt.channels().update(part='brandingSettings', body={'id': cid, 'brandingSettings': {
            'channel': channel, 'image': {'bannerExternalUrl': banner['url']}}}).execute()
    step('açıklama, anahtar kelimeler, ülke/dil, banner', branding)

    # hedef kitle gençler ve yetişkinler (prompts/script_short.txt); videolar da böyle yükleniyor
    step('kanal: çocuklara yönelik değil', lambda: yt.channels().update(part='status', body={
        'id': cid, 'status': {'selfDeclaredMadeForKids': False}}).execute())

    def watermark():
        # googleapiclient bu uç noktada hata veriyor -> ham multipart istek
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2.credentials import Credentials
        creds = Credentials(None, refresh_token=os.environ['YT_REFRESH_TOKEN'], client_id=os.environ['YT_CLIENT_ID'],
                            client_secret=os.environ['YT_CLIENT_SECRET'], token_uri='https://oauth2.googleapis.com/token')
        b = 'meyveBoundary'
        meta = json.dumps({'timing': {'type': 'offsetFromStart', 'offsetMs': 0},
                           'position': {'type': 'corner', 'cornerPosition': 'topRight'}})
        data = (f'--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n--{b}\r\n'
                'Content-Type: image/png\r\n\r\n').encode() + (BRAND / 'watermark.png').read_bytes() + f'\r\n--{b}--\r\n'.encode()
        r = AuthorizedSession(creds).post(
            f'https://www.googleapis.com/upload/youtube/v3/watermarks/set?channelId={cid}&uploadType=multipart',
            data=data, headers={'Content-Type': f'multipart/related; boundary={b}'})
        if r.status_code >= 300:
            raise RuntimeError(f'{r.status_code} {r.text[:200]}')
    step('filigran (abone ol)', watermark)

    existing = {p['snippet']['title']: p['id'] for p in
                yt.playlists().list(part='snippet', mine=True, maxResults=50).execute().get('items', [])}
    ids = json.loads(PLAYLISTS_FILE.read_text(encoding='utf-8')) if PLAYLISTS_FILE.exists() else {}
    for key, (ptitle, pdesc) in PLAYLISTS.items():
        if key in ids:
            continue
        if ptitle in existing:
            ids[key] = existing[ptitle]; continue
        p = yt.playlists().insert(part='snippet,status', body={
            'snippet': {'title': ptitle, 'description': pdesc + '\n\nHer gün yeni Konuşan Fruits videosu. #KonuşanFruits',
                        'defaultLanguage': 'tr'},
            'status': {'privacyStatus': 'public'}}).execute()
        ids[key] = p['id']; print(f'✓ oynatma listesi: {ptitle}')
    PLAYLISTS_FILE.write_text(json.dumps(ids, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    for row in published:
        key = row.get('template')
        if key not in ids:
            continue
        have = yt.playlistItems().list(part='contentDetails', playlistId=ids[key], maxResults=50).execute().get('items', [])
        if any(i['contentDetails']['videoId'] == row['video_id'] for i in have):
            continue
        step(f"video {row['video_id']} -> {key}", lambda: upload.add_to_playlist(ids[key], row['video_id']))

    if not ids.get('_sections_done'):
        sections = yt.channelSections().list(part='snippet,contentDetails', mine=True).execute().get('items', [])
        seen = {(s['snippet']['type'].lower(), tuple(s.get('contentDetails', {}).get('playlists', []))) for s in sections}
        wanted = [('recentUploads', ()), ('popularUploads', ())] + [('singlePlaylist', (ids[k],)) for k in SECTIONS]
        for pos, (stype, pls) in enumerate(wanted):
            if (stype.lower(), pls) in seen:
                continue
            body = {'snippet': {'type': stype, 'position': pos}}
            if pls:
                body['contentDetails'] = {'playlists': list(pls)}
            step(f'ana sayfa bölümü {stype} {pls}', lambda: yt.channelSections().insert(
                part='snippet,contentDetails', body=body).execute())
        ids['_sections_done'] = True
        PLAYLISTS_FILE.write_text(json.dumps(ids, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('\nElle yapılacak: branding/profile.png -> YouTube Studio > Özelleştirme > Marka > Resim')


if __name__ == '__main__':
    main()
