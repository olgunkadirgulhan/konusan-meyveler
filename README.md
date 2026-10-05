# Konuşan Meyveler — otomatik komik meyve Shorts kanalı (TR)

Dex and Friends'in altyapısıyla çalışır. Her şey GitHub Actions'ta döner (`.github/workflows/videos.yml`); bilgisayar kapalıyken de video çıkar.

```
senaryo (Gemini yazar + Gemini hakem ≥7, bilgi doğruluğu kontrolü; yoksa bank/)
  → Türkçe sesler (Azure → edge-tts → Piper; karakter başına ses/perde/hız, duyguya göre ayar)
  → cairo animasyon (gölgeli 3B görünümlü meyveler, iri gözler, dudak senkronu, kamera, BİLGİ kartları, efektler)
  → prosedürel müzik/SFX → ffmpeg → YouTube (+ Telegram bildirimi)
```

**Takvim:** Günde 3 Shorts, TR 12:00 · 17:00 · 20:30. Saatlik tetiklenir; `.github/slot_guard.py` sadece zamanı gelmiş slot varsa üretir.

**Kadro** (`meyve/cast.py`): Limon, Domates, Muz, Karpuz, Çilek, Soğan, Ananas (aksanlı), Avokado (aksanlı), Portakal, Acı Biber, Salatalık. Hepsi kodla çizilir, telif yok.

**Formatlar** (`meyve/writer.py`): meyve anlatıyor (gerçek bilgilerle) · kavga · kimlik krizi · buzdolabı draması · ters köşe · tipler.
Bilgi içeren repliklerde ekranda sarı **BİLGİ** kartı çıkar, bilgiler YouTube açıklamasına da yazılır.

**Sahneler** (`meyve/backgrounds.py`): mutfak tezgâhı, buzdolabı içi, pazar tezgâhı, kesme tahtası, yemek masası, bahçe, plaj, blender'lı mutfak.

**Aksiyonlar:** tokat, bayılma, kaçma, yuvarlanıp kaçma, zıplama, dönme, titreme, ezilme, dramatik zoom, ba-dum-tss, dev insan elinin meyveyi kapması.

## Kurulum (bir kez)

1. GitHub'da `konusan-meyveler` reposunu aç, bu klasörü push et.
2. YouTube'da yeni kanalı aç, sonra bağla (diğer kanallarındaki `client_secret.json` kullanılabilir):
   `python auth_setup.py --repo olgunkadirgulhan/konusan-meyveler --expect Meyve`
3. **Secrets:** `GEMINI_API_KEY` (Dex'tekiyle aynı olabilir); opsiyonel `AZURE_SPEECH_KEY` (Fenek'tekiyle aynı),
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
4. **Variables:** `YT_PRIVACY=private` (ilk günler kontrol için, sonra `public`); opsiyonel `AZURE_SPEECH_REGION`,
   `MAX_PER_DAY` (varsayılan 3), `SCRIPT_SOURCE=bank` (sadece hazır senaryolar).
5. Actions → videos → *Run workflow* (`no_upload` işaretli) ile ilk videoyu artifact olarak indirip izle.

## Yerel test

```
pip install -r requirements.txt          # + ffmpeg ve cairo
python run.py --script bank/001_domates_kimlik.json --no-upload   # output/<id>/video.mp4
python run.py --no-upload                                          # Gemini ile yeni senaryo (anahtar gerekir)
```

## Yeni senaryo / karakter eklemek

- `bank/` içine aynı şemada JSON ekle (Gemini çalışmazsa sırayla bunlar kullanılır, Gemini'ye örnek olarak da gösterilir).
- Yeni meyve: `meyve/cast.py`'ye kayıt + gerekirse `meyve/fruit.py`'de biçim (`_polar` / `_spine`), doku ve aksesuar.
