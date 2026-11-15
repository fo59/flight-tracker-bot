# ✈️ Flight Bot

**Telegram uzerinden canli ucus takip botu.** Kullanicilar ucus numaralarini ekler, bot OpenSky API uzerinden canli radar verilerini ceker ve kalkis/inis bildirimleri gonderir.

---

## 📋 Amac

Kullanicinin takip etmek istedigi bir ucusu (`TK1234`, `LH1238` gibi) Telegram uzerinden eklemesini, botun da OpenSky Network'un acik radar verilerini kullanarak su asamalarda bildirim gondermesini saglamak:

| Durum | Bildirim |
|---|---|
| Ucus radarda gorundu, havada | 🛫 "Kalkis yapti!" |
| Inise 30 dk kala | ⏰ "Inisine X dk kaldi" + konum/irtifa/hiz |
| Ucus yere indi | ✅ "Inis yapti!" |
| X dakikadir radarda gorunmuyor | ⚠️ "Olasi rotar" uyarisi |

---

## 🏗️ Mimari

```
flight_bot/
├── main.py               # Bot giris noktasi, Telegram komutlari, healthcheck
├── config.py              # Ortam degiskenlerinden ayarlar
├── database.py            # SQLite (kullanicilar, ucuslar, temizlik)
├── airports.py            # ICAO kodu -> havalimani bilgisi (cache'li)
├── opensky_client.py      # OpenSky API (async httpx + haversine hesabi)
├── scheduler.py           # APScheduler ile periyodik ucus kontrolu
├── localization.py        # TR / EN dil destegi
├── requirements.txt       # Bagimliliklar
├── Procfile               # Railway deploy icin
├── .env.example           # Ornek ortam degiskenleri
└── .gitignore
```

### Akis semasi

```
Kullanici                     Telegram Bot                     OpenSky API
   |                              |                                |
   |---- /add TK1234 LTFM ------->|                                |
   |<--- "Takibe alindi!" --------|                                |
   |                              |                                |
   |                              |---- (her 5 dk) fetch states -->|
   |                              |<--- state vectors -------------|
   |                              |                                |
   |                              |---- callsign eslestir ---------|
   |                              |                                |
   |<--- 🛫 Kalkis Yapti! -------|                                |
   |<--- ⏰ 30 dk kala -----------|                                |
   |<--- ✅ Inis Yapti! ---------|                                |
   |                              |                                |
   |                              |---- cleanup (gece 03:00) ------|
   |                              |  (24 saat gecmis ucuslari sil) |
```

---

## 🔧 Yapilan Degisiklikler (Duzeltilen Hatalar)

| # | Sorun | Cozum |
|---|---|---|
| 1 | `opensky_client.py` tamamen `airports.py`'nin kopyasiydi, `fetch_states()` / `match_callsign()` / `estimate_minutes_to_arrival()` yoktu | Gercek OpenSky API istemcisi yazildi |
| 2 | `fetch_states()` sync `requests` ile async loop'u blokluyordu | `httpx.AsyncClient` ile asenkron yapildi |
| 3 | Bildirimde "km/s" yaziyordu (yanlis) | "km/h" olarak duzeltildi |
| 4 | Bot handler'lari (main.py) tamamen eksikti, bot calismazdi | Olusturuldu: /start, /add, /remove, /list, /stats, /language |
| 5 | Python 3.9`da `str \| None` syntax hatasi | `Optional[str]` ile degistirildi |
| 6 | Veritabani sismesi (`landed` ucuslar birikiyor) | `cleanup_old_flights()` eklendi, gece 03:00'te calisir |
| 7 | Dil secenegi yoktu | TR/EN destegi eklendi |

---

## 🤖 Bot Kullanimi

### /start — Baslangic

İlk kez baslatan kullaniciya dil secim ekrani gelir:

```
[ Turkce ]  [ English ]
```

Secim yapildiktan sonra hos geldin mesaji ve komut listesi gonderilir.

### /add — Ucus Ekle

```
/add TK1234 LTFM
```

- `TK1234` = ucus numarasi
- `LTFM` = varis havalimani ICAO kodu (Istanbul Havalimani)
- Istege bagli 3. parametre: kalkis havalimani

```
/add TK1234 LTFM LTBA
```

Havalimani ICAO kodu gecersizse bot uyarir.

### /remove — Ucus Sil

```
/remove TK1234
```

### /list — Takip Listesi

Takip ettiginiz tum ucuslari durumlariyla gosterir:

```
📅 `TK1234` -> Istanbul Havalimani (bekleyen)
🛫 `LH1238` -> Frankfurt Havalimani (havada)
✅ `TK4567` -> Ankara Esenboga (indi)
```

### /stats — Istatistikler (Admin)

Sadece `.env`'de `OWNER_ID` tanimlanmissa calisir:

```
📊 Bot Istatistikleri
👤 Kullanici: 12
✈️ Toplam ucus: 34
🛫 Havada: 2
📅 Bekleyen: 28
✅ Inmis: 4
```

### /language — Dil Degistir

Dil secim menusunu tekrar acar.

---

## 🖼️ Bota Resim / Medya Ekleme

Su an bot sadece metin mesaji gonderiyor. Asagidaki yontemlerle resim ekleyebilirsin:

### Yontem 1: `send_photo` ile dogrudan resim

En basit yontem. Ornegin `scheduler.py`'daki `_notify` fonksiyonuna alternatif:

```python
async def _notify_with_photo(bot, user_id: int, text: str, photo_url: str):
    try:
        await bot.send_photo(
            chat_id=user_id,
            photo=photo_url,
            caption=text,
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("Fotograf gonderilemedi: user_id=%s", user_id)
```

Kullanimi:

```python
# Kalkis bildiriminde ucak resmi
await _notify_with_photo(
    bot, user_id,
    "🛫 *TK1234* kalkis yapti!",
    "https://example.com/plane_takeoff.png",
)
```

### Yontem 2: `InputMediaPhoto` ile album (birden cok resim)

```python
from telegram import InputMediaPhoto

media = [
    InputMediaPhoto(media="https://example.com/photo1.jpg"),
    InputMediaPhoto(media="https://example.com/photo2.jpg"),
]
await bot.send_media_group(chat_id=user_id, media=media)
```

### Yontem 3: Yerel dosyadan gonderme

```python
with open("assets/welcome.jpg", "rb") as f:
    await bot.send_photo(chat_id=user_id, photo=f, caption="Hos geldiniz!")
```

### Onerilen yapı

1. `assets/` klasoru olustur
2. Icerisine `takeoff.png`, `landing.png`, `warning.png`, `welcome.png` gibi resimler koy
3. `config.py`'ye `ASSETS_DIR = "assets"` ekle
4. Bildirimlerde `send_photo` + `caption` kullan

Ornek `main.py`'de `/start` komutuna resim ekleme:

```python
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username)
    lang = _get_lang(context, user.id) or "en"

    with open("assets/welcome.jpg", "rb") as f:
        await update.message.reply_photo(
            photo=f,
            caption=_(lang, "welcome"),
            parse_mode="Markdown",
        )
```

---

## 🚀 Railway'a Deployment

### 1. GitHub'a Yukle

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/KULLANICI_ADIN/flight-bot.git
git push -u origin main
```

### 2. Railway'de Ac

1. [Railway.app](https://railway.app)'e gir
2. **New Project** -> **Deploy from GitHub repo**
3. Repository'ni sec
4. **Variables** sekmesine `.env.example`'daki degiskenleri ekle:

| Variable | Zorunlu | Aciklama |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Evet | @BotFather'dan al |
| `OPENSKY_USERNAME` | Hayir | OpenSky uyelik (rate-limit icin) |
| `OPENSKY_PASSWORD` | Hayir | OpenSky sifre |
| `OWNER_ID` | Hayir | Telegram ID'n (/stats icin) |

5. **Deploy** otomatik baslar

### 3. Veritabani Kaliciligi

Railway ephemeral disk kullanir (`flights.db` her restartta silinir). Kalici depolama icin:

- **Railway Volume** ekle (Project -> Volume -> `/app` mount)
- Veya `DB_PATH`'i volume dizinine yonlendir

---

## ⚙️ Lokal Calistirma

```bash
git clone <repo-url>
cd flight_bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env'yi duzenle: TELEGRAM_BOT_TOKEN ekle

python main.py
```

---

## 🧩 Bagimliliklar

| Kutuphane | Kullanim |
|---|---|
| `python-telegram-bot>=20` | Telegram Bot API (async) |
| `apscheduler>=3.10` | Periyodik gorevler |
| `requests>=2.28` | OpenFlights verisi (`airports.py`) |
| `httpx>=0.24` | OpenSky API (async) |
| `python-dotenv>=1.0` | `.env` okuma |

---

## 📝 Notlar

- **OpenSky rate-limit**: Anonim kullanimda 10 request / 10 dk. `OPENSKY_USERNAME`/`PASSWORD` tanimlanirsa 1000 request / 10 dk.
- **Dil dosyasi**: `localization.py`'deki `TRANSLATIONS` sozlugune yeni dil ekleyebilirsin. Anahtarlarin tamami her dilde bulunmalidir.
