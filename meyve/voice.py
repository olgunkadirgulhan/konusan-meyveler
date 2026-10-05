"""Karakter sesleri (Türkçe) — yedekli zincir:

  1. azure  Microsoft Azure Speech (resmî). AZURE_SPEECH_KEY (+ AZURE_SPEECH_REGION) varsa.
  2. edge   edge-tts: aynı Microsoft sesleri; kelime zamanlarını da verir (altyazı tam senkron).
  3. piper  İkisi de çalışmazsa Türkçe Piper sesi (perde kaydırmalı). Gün boş geçmez.
TTS_ENGINE ile tek motor zorlanabilir: azure | edge | piper. Aynı replik tekrar üretilmez (~/.cache/meyve/tts).
"""
import hashlib
import json
import os
import re
import subprocess
import wave
from pathlib import Path

import numpy as np
import soundfile as sf

from .cast import CAST
from .lang import S as LS

SR = 48000
CACHE = Path(os.environ.get('MEYVE_CACHE', Path.home() / '.cache' / 'meyve'))
TTS_CACHE = CACHE / 'tts'
FFMPEG = os.environ.get('FFMPEG', 'ffmpeg')
EMO_RATE = {'angry': 8, 'excited': 10, 'shock': 6, 'nervous': 6, 'sad': -8, 'cry': -6}
EMO_PITCH = {'excited': 8, 'shock': 10, 'sad': -6, 'cry': 4, 'angry': -3}
VOWELS = set('aeıioöuüâîûAEIİOÖUÜ')
_piper = {}


def log(m):
    print(f'[tts] {m}', flush=True)


def spoken(text):
    t = re.sub(r'[\U00010000-\U0010ffff☀-⟿]', '', text)   # emoji
    t = t.replace('&', LS['amp']).replace('%', LS['pct'])
    t = re.sub(r'\*+', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def prosody(cid, emotion, speed_mul):
    c = CAST[cid]
    rate = int(c['rate'].rstrip('%')) + EMO_RATE.get(emotion, 0) + round((speed_mul - 1) * 100)
    pitch = int(c['pitch'].rstrip('Hz')) + EMO_PITCH.get(emotion, 0)
    return f'{rate:+d}%', f'{pitch:+d}Hz'


def chain():
    e = (os.environ.get('TTS_ENGINE') or 'auto').lower()
    if e == 'auto':
        return (['azure'] if os.environ.get('AZURE_SPEECH_KEY') else []) + ['edge', 'piper']
    return [e] if e == 'piper' else [e, 'piper']


# ------------------------------------------------------------------ motorlar

def _azure(cid, text, rate, pitch, raw):
    import requests
    voice = CAST[cid]['voice']
    region = os.environ.get('AZURE_SPEECH_REGION') or 'westeurope'
    esc = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    body = f"<prosody rate='{rate}' pitch='{pitch}'>{esc}</prosody>"
    if 'Multilingual' in voice:
        body = f"<lang xml:lang='{LS['tts_lang']}'>{body}</lang>"
    ssml = (f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{LS['tts_lang']}'>"
            f"<voice name='{voice}'>{body}</voice></speak>")
    r = requests.post(f'https://{region}.tts.speech.microsoft.com/cognitiveservices/v1', data=ssml.encode('utf-8'),
                      timeout=30, headers={'Ocp-Apim-Subscription-Key': os.environ['AZURE_SPEECH_KEY'],
                                           'Content-Type': 'application/ssml+xml',
                                           'X-Microsoft-OutputFormat': 'riff-24khz-16bit-mono-pcm',
                                           'User-Agent': 'konusan-meyveler'})
    if r.status_code != 200 or len(r.content) < 2000:
        raise RuntimeError(f'azure {r.status_code}: {r.text[:120]}')
    raw.write_bytes(r.content)
    return raw, None


def _edge(cid, text, rate, pitch, raw):
    import asyncio
    import edge_tts
    mp3 = raw.with_suffix('.mp3')

    async def go():
        bounds = []
        com = edge_tts.Communicate(text, CAST[cid]['voice'], rate=rate, pitch=pitch, boundary='WordBoundary')
        with mp3.open('wb') as f:
            async for ch in com.stream():
                if ch['type'] == 'audio':
                    f.write(ch['data'])
                elif ch['type'] == 'WordBoundary':
                    bounds.append((ch['text'], ch['offset'] / 1e7, (ch['offset'] + ch['duration']) / 1e7))
        return bounds
    last = None
    for _ in range(3):
        try:
            bounds = asyncio.run(asyncio.wait_for(go(), timeout=40))
            if mp3.exists() and mp3.stat().st_size > 1000:
                return mp3, bounds
        except Exception as e:
            last = e
    raise RuntimeError(f'edge: {last}')


def _piper_voice(name):
    if name not in _piper:
        from piper import PiperVoice
        d = CACHE / 'piper'
        d.mkdir(parents=True, exist_ok=True)
        if not (d / f'{name}.onnx').exists():
            subprocess.run(['python', '-m', 'piper.download_voices', '--data-dir', str(d), name], check=True)
        _piper[name] = PiperVoice.load(str(d / f'{name}.onnx'))
    return _piper[name]


def _piper_synth(cid, text, rate, raw):
    from piper import SynthesisConfig
    name, _ = CAST[cid]['piper']
    v = _piper_voice(name)
    speed = 1 + int(rate.rstrip('%')) / 100
    with wave.open(str(raw), 'wb') as wf:
        v.synthesize_wav(text, wf, syn_config=SynthesisConfig(length_scale=1 / max(0.6, speed)))
    return raw, None


# ------------------------------------------------------------------ zamanlama

def syllables(word):
    return max(1, sum(1 for ch in word if ch in VOWELS))


def word_times(tokens, bounds, start, end):
    """Altyazı kelimeleri -> [{text,start,end}]. edge sınırları varsa onları eşler, yoksa hece oranıyla dağıtır."""
    clean = [re.sub(r'[^\wçğıöşüÇĞİÖŞÜ]', '', t) for t in tokens]
    if bounds:
        out, j = [], 0
        for tok, cl in zip(tokens, clean):
            if not cl:
                continue
            if j < len(bounds):
                out.append({'text': tok, 'start': bounds[j][1], 'end': bounds[j][2]}); j += 1
        if len(out) == len([c for c in clean if c]) and j == len(bounds):
            return [w for w in out]
    toks = [t for t, cl in zip(tokens, clean) if cl] or tokens
    weights = [syllables(t) + 0.6 for t in toks]
    total = sum(weights) or 1
    dur = max(0.1, end - start)
    out, cur = [], start
    for t, w in zip(toks, weights):
        d = dur * w / total
        out.append({'text': t, 'start': cur, 'end': cur + d}); cur += d
    return out


def speak(cid, text, emotion='neutral', speed_mul=1.0):
    """-> (samples float32 @48k, words [{text,start,end}] (sn, sesin başına göre))"""
    say = spoken(text)
    rate, pitch = prosody(cid, emotion, speed_mul)
    TTS_CACHE.mkdir(parents=True, exist_ok=True)
    errors = []
    for eng in chain():
        group = 'ms' if eng in ('azure', 'edge') else eng
        key = hashlib.sha1(json.dumps([group, eng if eng == 'piper' else '', CAST[cid]['voice'], say, rate, pitch,
                                       CAST[cid]['piper']]).encode()).hexdigest()[:16]
        wav_p, meta_p = TTS_CACHE / f'{key}.wav', TTS_CACHE / f'{key}.json'
        if wav_p.exists() and meta_p.exists():
            x, _ = sf.read(str(wav_p), dtype='float32')
            meta = json.loads(meta_p.read_text(encoding='utf-8'))
            return x, word_times(text.split(), meta.get('bounds'), 0, len(x) / SR)
        raw = TTS_CACHE / f'{key}.raw.wav'
        try:
            if eng == 'azure':
                src, bounds = _azure(cid, say, rate, pitch, raw)
            elif eng == 'edge':
                src, bounds = _edge(cid, say, rate, pitch, raw)
            else:
                src, bounds = _piper_synth(cid, say, rate, raw)
        except Exception as e:
            errors.append(f'{eng}: {str(e)[:150]}')
            log(f'{eng} başarısız, sıradaki motor deneniyor — {errors[-1]}')
            continue
        if errors:
            msg = f'ses yedeğe geçti ({eng}): ' + ' | '.join(errors)
            print(f'::warning::{msg}' if os.environ.get('GITHUB_ACTIONS') else f'[tts] {msg}', flush=True)
        dec = TTS_CACHE / f'{key}.dec.wav'
        subprocess.run([FFMPEG, '-y', '-v', 'error', '-i', str(src), '-ar', str(SR), '-ac', '1', str(dec)], check=True)
        src.unlink(missing_ok=True)
        x, _ = sf.read(str(dec), dtype='float32')
        dec.unlink(missing_ok=True)
        if eng == 'piper':   # perde: yeniden örnekleme (kadın/çocuk sesine yaklaştırır)
            f = CAST[cid]['piper'][1]
            if abs(f - 1) > 0.01:
                n = max(1, int(len(x) / f))
                x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
        # baş/son sessizliği kırp, kelime zamanlarını kaydır
        thr = 0.02 * (np.abs(x).max() + 1e-6)
        idx = np.where(np.abs(x) > thr)[0]
        a0 = max(0, idx[0] - int(0.03 * SR)) if len(idx) else 0
        a1 = min(len(x), idx[-1] + int(0.12 * SR)) if len(idx) else len(x)
        x = x[a0:a1]
        x = x / (np.abs(x).max() + 1e-6) * 0.92
        shift = a0 / SR
        bounds = [(w, max(0.0, s - shift), max(0.0, e - shift)) for w, s, e in (bounds or [])] or None
        sf.write(str(wav_p), x, SR)
        meta_p.write_text(json.dumps({'engine': eng, 'bounds': bounds}, ensure_ascii=False), encoding='utf-8')
        return x, word_times(text.split(), bounds, 0, len(x) / SR)
    raise RuntimeError('hiçbir ses motoru çalışmadı: ' + ' | '.join(errors))
