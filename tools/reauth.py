"""Herhangi bir kanal reposunu YouTube'a yeniden bağla (token GitHub secrets'a yazılır, ekrana basılmaz).

    python tools/reauth.py --repo olgunkadirgulhan/finans-shorts-otomasyon-2 --prefix YOUTUBE \
        --client ~/Downloads/client_secret_XXX.json [--scope upload] [--channel-secret]

--prefix YT      -> YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (+ YT_CHANNEL_ID)
--prefix YOUTUBE -> YOUTUBE_CLIENT_ID, ...
Uygulama Google Cloud'da 'Testing' modundaysa token 7 gün sonra ölür; araç bunu uyarır.
"""
import argparse
import os
import subprocess
import sys

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = {'full': ['https://www.googleapis.com/auth/youtube'],
          'upload': ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--prefix', default='YT')
    ap.add_argument('--client', required=True, help='client_secret json yolu')
    ap.add_argument('--scope', choices=list(SCOPES), default='full')
    ap.add_argument('--channel-secret', action='store_true', help='<PREFIX>_CHANNEL_ID de yazılsın')
    ap.add_argument('--expect', default='', help='kanal adında geçmesi gereken metin')
    ap.add_argument('--port', type=int, default=0,
                    help="web tipi istemcide kayıtlı localhost portu (örn. 53682 -> http://localhost:53682)")
    ap.add_argument('--login-hint', default='', help='giriş ekranında önerilecek Gmail')
    a = ap.parse_args()

    flow = InstalledAppFlow.from_client_secrets_file(os.path.expanduser(a.client), SCOPES[a.scope])
    extra = {'login_hint': a.login_hint} if a.login_hint else {}
    creds = flow.run_local_server(port=a.port, prompt='consent select_account', access_type='offline',
                                  redirect_uri_trailing_slash=not a.port, **extra)
    expires = flow.oauth2session.token.get('refresh_token_expires_in')
    yt = build('youtube', 'v3', credentials=creds, cache_discovery=False)
    items = yt.channels().list(part='id,snippet', mine=True).execute().get('items', [])
    if not items:
        sys.exit('bu hesapta YouTube kanalı yok, hiçbir şey kaydedilmedi')
    cid, title = items[0]['id'], items[0]['snippet']['title']
    print(f'Kanal: {title}')
    if a.expect and a.expect.lower() not in title.lower():
        sys.exit(f"Bu '{a.expect}' değil. Tekrar çalıştır ve doğru kanalı seç. Hiçbir şey kaydedilmedi.")
    values = {f'{a.prefix}_CLIENT_ID': creds.client_id, f'{a.prefix}_CLIENT_SECRET': creds.client_secret,
              f'{a.prefix}_REFRESH_TOKEN': creds.refresh_token}
    if a.channel_secret:
        values[f'{a.prefix}_CHANNEL_ID'] = cid
    for k, v in values.items():
        subprocess.run(['gh', 'secret', 'set', k, '--repo', a.repo, '--body', v], check=True, capture_output=True)
    print(f'GitHub secrets yazıldı: {", ".join(values)} -> {a.repo}')
    if expires:
        print(f'UYARI: uygulama TESTING modunda, token {int(expires) // 86400} gün sonra ölecek. '
              'Google Cloud > Google Auth Platform > Audience > Publish app, sonra bu aracı tekrar çalıştır.')
    else:
        print('Token kalıcı (uygulama yayında).')


if __name__ == '__main__':
    main()
