TRANSLATIONS = {
    "tr": {
        "language_name": "Turkce",
        "select_language": "Dilinizi secin:",
        "language_changed": "Dil {language_name} olarak degistirildi.",
        "welcome": (
            "✈️ *Flight Bot'a Hos Geldin!*\n\n"
            "Ucuslarinizi takip edin, kalkis ve inis bildirimleri alin.\n\n"
            "Asagidaki menuyu kullanarak baslayabilirsiniz."
        ),
        "help": "✈️ *Flight Bot*\n\n/add `TK1234` `LTFM` — ucus ekle\n/remove — ucus sil (secimli)\n/list — takip listen\n/where — canli konum\n/menu — ana menu\n/language — dil degistir\n/about — gizlilik ve hakkimizda",
        "add_usage": "Kullanim: `/add TK1234 LTFM` — veya `/add TK1234` (otomatik bul)",
        "remove_usage": "Kullanim: `/remove TK1234` veya `/remove` ile secim yapin",
        "flight_added": "✅ `{flight}` -> *{dest}* takibe alindi!",
        "already_tracking": "ℹ️ `{flight}` zaten takibinizde.",
        "flight_removed": "✅ `{flight}` takipten cikarildi.",
        "remove_confirm": "`{flight}` takipten cikarilsin mi?",
        "remove_cancelled": "Iptal edildi.",
        "flight_not_found": "❌ `{flight}` bulunamadi.",
        "airport_not_found": "❌ `{code}` havalimani kodu bulunamadi. IATA (3 harf) veya ICAO (4 harf) kullanin.",
        "unknown_command": "❌ Bilinmeyen komut. /menu yazabilirsiniz.",
        "no_flights": "Henuz takip ettiginiz ucus yok.",
        "flight_list_header": "*Takip edilen ucuslar:*",
        "select_flight": "Bir ucus secin:",
        "select_flight_to_remove": "Silmek istediginiz ucusu secin:",
        "stats_header": "📊 *Bot Istatistikleri*",
        "stats_users": "Kullanici",
        "stats_total": "Toplam ucus",
        "stats_airborne": "Havada",
        "stats_scheduled": "Bekleyen",
        "stats_landed": "Inmis",
        "not_owner": "Bu komut sadece bot sahibi icindir.",
        "delay_warning": "⚠️ *{flight}* ucusu {delay} dakikadir havalanmadi. Bu kesin bir bilgi degil, sadece tahmindir.",
        "takeoff": "🛫 *{flight}* ucusu kalkis yapti!",
        "landing_soon": "⏰ *{flight}* ucusunun *{dest}* havalimanina inisine yaklasik {eta} dakika kaldi! (tahmini)\n📍 Konum: {lat}, {lon}\n📈 Irtifa: {alt} m | ⏱️ Hiz: {speed} km/h",
        "landing_soon_schedule": "⏰ *{flight}* ucusunun *{dest}* havalimanina yaklasik {eta} dakika icinde inmesi bekleniyor! (tahmini)",
        "landed": "✅ *{flight}* ucusu inis yapti!",
        "label_location": "Konum",
        "label_altitude": "Irtifa",
        "label_speed": "Hiz",
        "status_scheduled": "bekleyen",
        "status_airborne": "havada",
        "status_landed": "indi",
        "pref_takeoff": "Kalkis",
        "pref_30min": "30 dk kala",
        "pref_landed": "Inis",
        "pref_delay": "Gecikme",
        "pref_position": "Konum bildirimi (30 dk)",
        "pref_ask": "Hangi bildirimleri almak istersiniz?",
        "pref_saved": "Bildirim tercihleri kaydedildi.",
        "dest_unknown": "Bilinmiyor",
        "save": "Kaydet",
        "back": "Geri",
        "menu_btn": "Ana Menü",
        "add_btn": "Ucus Ekle",
        "where_btn": "Canli Konum",
        "list_btn": "Ucuslarim",
        "alerts_btn": "Bildirimler",
        "language_btn": "Dil",
        "about_btn": "Hakkimizda",
        "refresh_btn": "Yenile",
        "remove_btn": "Sil",
        "flight_actions": "`{flight}` icin islem secin:",
        "add_more_btn": "Bir tane daha ekle",
        "position_update": "📍 *{flight}* canli konum\n🌍 {country}{near}\n📏 Alt: {alt}m / {alt_ft}ft\n💨 Hiz: {speed} km/h\n🧭 Yon: {heading}°",
        "position_unavailable": "Su an konum verisi mevcut degil.",
        "where_not_airborne": "Ucus henuz havalanmadi — havada oldugunda canli konum goruntulenebilir.",
        "where_position_unavailable_active": "Ucus aktif (havada) ancak su anki veri kaynaklarindan canli konum alinamiyor.",
        "where_already_landed": "Ucus immis — canli konum verisi artik mevcut degil.",
        "where_title": "Konumunu gormek istediginiz ucusu secin:",
        "alerts_title": "Bildirim ayarlarini degistirmek istediginiz ucusu secin:",
        "your_flights": "Ucuslarin",
        "about": (
            "✈️ *Flight Bot*\n\n"
            "Canli ucus takibi — acik radar verileriyle calisir.\n\n"
            "*Toplanan veriler:* Telegram ID, kullanici adi, ucus numaralari\n"
            "*Kullanim amaci:* Ucus durumu bildirimleri gonderebilmek\n"
            "*Saklama suresi:* Ucus takipten cikarilana kadar\n"
            "*Ucuncu tarafla paylasim:* Hayir\n"
            "*Veri kaynaklari:* AirLabs, AviationStack, OpenFlights"
        ),
    },
    "en": {
        "language_name": "English",
        "select_language": "Select your language:",
        "language_changed": "Language changed to {language_name}.",
        "welcome": (
            "✈️ *Welcome to Flight Bot!*\n\n"
            "Track your flights and get takeoff & landing notifications.\n\n"
            "Use the menu below to get started."
        ),
        "help": "✈️ *Flight Bot*\n\n/add `TK1234` `LTFM` — add flight\n/remove — remove flight (with picker)\n/list — show your flights\n/where — live position\n/menu — main menu\n/language — change language\n/about — privacy & about",
        "add_usage": "Usage: `/add TK1234 LTFM` — or `/add TK1234` (auto-detect)",
        "remove_usage": "Usage: `/remove TK1234` or `/remove` to pick",
        "flight_added": "✅ `{flight}` -> *{dest}* is now being tracked!",
        "already_tracking": "ℹ️ `{flight}` is already in your list.",
        "flight_removed": "✅ `{flight}` removed from tracking.",
        "remove_confirm": "Remove `{flight}` from tracking?",
        "remove_cancelled": "Cancelled.",
        "flight_not_found": "❌ `{flight}` not found.",
        "airport_not_found": "❌ Airport code `{code}` not found. Use IATA (3-letter) or ICAO (4-letter).",
        "unknown_command": "❌ Unknown command. Use /menu.",
        "no_flights": "You have no flights tracked yet.",
        "flight_list_header": "*Tracked flights:*",
        "select_flight": "Select a flight:",
        "select_flight_to_remove": "Select a flight to remove:",
        "stats_header": "📊 *Bot Statistics*",
        "stats_users": "Users",
        "stats_total": "Total flights",
        "stats_airborne": "Airborne",
        "stats_scheduled": "Scheduled",
        "stats_landed": "Landed",
        "not_owner": "This command is only for the bot owner.",
        "delay_warning": "⚠️ *{flight}* appears to have not taken off yet ({delay} min). This is not an official delay, just an estimate.",
        "takeoff": "🛫 *{flight}* has taken off!",
        "landing_soon": "⏰ *{flight}* is about {eta} min from landing at *{dest}*! (estimate)\n📍 Location: {lat}, {lon}\n📈 Altitude: {alt} m | ⏱️ Speed: {speed} km/h",
        "landing_soon_schedule": "⏰ *{flight}* is estimated to land at *{dest}* in about {eta} minutes! (schedule-based)",
        "landed": "✅ *{flight}* has landed!",
        "label_location": "Location",
        "label_altitude": "Altitude",
        "label_speed": "Speed",
        "status_scheduled": "scheduled",
        "status_airborne": "airborne",
        "status_landed": "landed",
        "pref_takeoff": "Takeoff",
        "pref_30min": "30 min before",
        "pref_landed": "Landing",
        "pref_delay": "Delay",
        "pref_position": "Position every 30 min",
        "pref_ask": "Which notifications would you like?",
        "pref_saved": "Notification preferences saved.",
        "dest_unknown": "Unknown",
        "save": "Save",
        "back": "Back",
        "menu_btn": "Main Menu",
        "add_btn": "Add Flight",
        "where_btn": "Live Position",
        "list_btn": "My Flights",
        "alerts_btn": "Alerts",
        "language_btn": "Language",
        "about_btn": "About",
        "refresh_btn": "Refresh",
        "remove_btn": "Delete",
        "flight_actions": "Select action for `{flight}`:",
        "add_more_btn": "Add another",
        "position_update": "📍 *{flight}* live position\n🌍 {country}{near}\n📏 Alt: {alt}m / {alt_ft}ft\n💨 Speed: {speed} km/h\n🧭 Heading: {heading}°",
        "position_unavailable": "Position data not available right now.",
        "where_not_airborne": "Flight hasn't taken off yet — check back for live position once it's airborne.",
        "where_position_unavailable_active": "Flight is active (airborne) but live position is not available from current data sources.",
        "where_already_landed": "Flight has already landed — live position data is no longer available.",
        "where_title": "Select a flight to see its current location:",
        "alerts_title": "Select a flight to change its notification settings:",
        "your_flights": "Your flights",
        "about": (
            "✈️ *Flight Bot*\n\n"
            "Live flight tracking powered by open radar data.\n\n"
            "*Data collected:* Telegram ID, username, flight numbers\n"
            "*Purpose:* Send flight status notifications\n"
            "*Retention:* Until the flight is removed from tracking\n"
            "*Third-party sharing:* None\n"
            "*Data sources:* AirLabs, AviationStack, OpenFlights"
        ),
    },
}

LANGUAGE_NAMES = {code: data["language_name"] for code, data in TRANSLATIONS.items()}


def t(lang: str, key: str, **kwargs) -> str:
    msg = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)
    if kwargs:
        msg = msg.format(**kwargs)
    return msg
