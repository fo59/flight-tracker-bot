import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

import config
import database as db
from airports import get_airport
from localization import TRANSLATIONS, LANGUAGE_NAMES, t as _
from scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass


def _start_healthcheck(port: str):
    server = HTTPServer(("0.0.0.0", int(port)), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Healthcheck -> :%s", port)


def _get_lang(context, user_id: int) -> Optional[str]:
    lang = context.user_data.get("lang")
    if not lang:
        lang = db.get_user_language(user_id)
        if lang:
            context.user_data["lang"] = lang
    return lang or None


def _flight_rows(user_id: int, lang: str):
    flights = db.list_flights(user_id)
    rows = []
    emoji_map = {"scheduled": "📅", "airborne": "🛫", "landed": "✅"}
    for f in flights:
        dest_name = f["destination_icao"] or _(lang, "dest_unknown")
        emoji = emoji_map.get(f["status"], "❓")
        label = f"{emoji} {f['flight_number']} → {dest_name}"
        rows.append([InlineKeyboardButton(label, callback_data=f"where_{f['id']}")])
    return rows


async def _show_pref_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE, flight_id: int, lang: str, edit: bool = False):
    flight = db.get_flight(flight_id)
    if not flight:
        return

    rows = []
    for pref in PREF_KEYS:
        val = flight[pref]
        emoji = PREF_LABELS[pref]
        name = _(lang, pref)
        status = "✅" if val else "⬜"
        rows.append([InlineKeyboardButton(
            f"{emoji} {name}: {status}",
            callback_data=f"p_{flight_id}_{pref}",
        )])
    rows.append([InlineKeyboardButton(f"💾 {_(lang, 'save')}", callback_data=f"p_{flight_id}_save")])

    text = f"✈️ `{flight['flight_number']}` — {_(lang, 'pref_ask')}"
    kwargs = dict(text=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))

    if edit:
        await update.callback_query.edit_message_text(**kwargs)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, **kwargs)


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _get_lang(context, update.effective_user.id) or "en"
    await _show_menu(update, context, lang)


async def _show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    keyboard = [
        [InlineKeyboardButton(f"➕ {_(lang, 'add_btn')}", callback_data="add"),
         InlineKeyboardButton(f"📍 {_(lang, 'where_btn')}", callback_data="where")],
        [InlineKeyboardButton(f"📋 {_(lang, 'list_btn')}", callback_data="list"),
         InlineKeyboardButton(f"🔔 {_(lang, 'alerts_btn')}", callback_data="al")],
        [InlineKeyboardButton(f"🌍 {_(lang, 'language_btn')}", callback_data="lang_picker"),
         InlineKeyboardButton(f"ℹ️ {_(lang, 'about_btn')}", callback_data="about")],
    ]
    text = _(lang, "welcome")
    if hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(v["language_name"], callback_data=f"lang_{k}")]
        for k, v in TRANSLATIONS.items()
    ]
    lang = _get_lang(context, update.effective_user.id) or "en"
    await update.message.reply_text(
        _(lang, "select_language"),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "lang_picker":
        lang = _get_lang(context, query.from_user.id) or "en"
        keyboard = [
            [InlineKeyboardButton(v["language_name"], callback_data=f"lang_{k}")]
            for k, v in TRANSLATIONS.items()
        ]
        await query.edit_message_text(_(lang, "select_language"), reply_markup=InlineKeyboardMarkup(keyboard))
        return
    lang = data.split("_", 1)[1]
    user_id = query.from_user.id
    db.set_language(user_id, lang)
    context.user_data["lang"] = lang
    name = LANGUAGE_NAMES.get(lang, lang)
    await query.edit_message_text(
        _(lang, "language_changed", language_name=name) + "\n\n" + _(lang, "welcome"),
        parse_mode="Markdown",
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username)
    lang = _get_lang(context, user.id)

    if lang:
        await _show_menu(update, context, lang)
    else:
        keyboard = [
            [InlineKeyboardButton(v["language_name"], callback_data=f"lang_{k}")]
            for k, v in TRANSLATIONS.items()
        ]
        await update.message.reply_text(
            "Select your language / Dilinizi seçin / Wybierz język:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _get_lang(context, update.effective_user.id) or "en"
    await update.message.reply_text(_(lang, "help"), parse_mode="Markdown")


_KNOWN_COMMANDS = {"start", "help", "add", "remove", "list", "language", "about", "stats", "where", "menu"}


async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmd = update.message.text.split()[0].lower().lstrip("/").split("@")[0]
    if cmd in _KNOWN_COMMANDS:
        return
    lang = _get_lang(context, update.effective_user.id) or "en"
    await update.message.reply_text(_(lang, "unknown_command"))


async def cmd_where(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    flights = db.list_flights(user.id)
    if not flights:
        lang = _get_lang(context, user.id) or "en"
        await update.message.reply_text(_(lang, "no_flights"))
        return
    lang = _get_lang(context, user.id) or "en"
    rows = _flight_rows(user.id, lang)
    rows.append([InlineKeyboardButton(f"◀️ {_(lang, 'menu_btn')}", callback_data="menu")])
    await update.message.reply_text(
        _(lang, "where_title"),
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _get_lang(context, update.effective_user.id) or "en"
    if not context.args:
        await update.message.reply_text(_(lang, "add_usage"))
        return

    user = update.effective_user
    db.upsert_user(user.id, user.username)

    flight = context.args[0].upper()
    dest = context.args[1].upper() if len(context.args) > 1 else None
    origin = context.args[2].upper() if len(context.args) > 2 else None

    dest_name = None
    if not dest:
        dest_name = _(lang, "dest_unknown")
        dest = ""
        dest_auto = 1
    else:
        dest_info = get_airport(dest)
        if not dest_info:
            await update.message.reply_text(_(lang, "airport_not_found", code=dest))
            return
        dest_name = dest_info["name"]
        dest_auto = 0

    if origin:
        origin_info = get_airport(origin)
        if not origin_info:
            await update.message.reply_text(_(lang, "airport_not_found", code=origin))
            return

    flight_id = db.add_flight(user.id, flight, dest or "", origin, dest_auto)
    if flight_id:
        await update.message.reply_text(
            _(lang, "flight_added", flight=flight, dest=dest_name),
            parse_mode="Markdown",
        )
        await _show_pref_keyboard(update, context, flight_id, lang)
        keyboard = [
            [InlineKeyboardButton(f"📍 {_(lang, 'where_btn')}", callback_data=f"where_{flight_id}"),
             InlineKeyboardButton(f"🔔 {_(lang, 'alerts_btn')}", callback_data=f"al_{flight_id}")],
            [InlineKeyboardButton(f"➕ {_(lang, 'add_more_btn')}", callback_data="add"),
             InlineKeyboardButton(f"🏠 {_(lang, 'menu_btn')}", callback_data="menu")],
        ]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=_(lang, "flight_actions", flight=flight),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await update.message.reply_text(_(lang, "already_tracking", flight=flight))


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _get_lang(context, update.effective_user.id) or "en"
    if context.args:
        flight = context.args[0].upper()
        ok = db.remove_flight(update.effective_user.id, flight)
        if ok:
            await update.message.reply_text(_(lang, "flight_removed", flight=flight))
        else:
            flights = db.list_flights(update.effective_user.id)
            if flights:
                await _show_remove_list(update, context, lang)
            else:
                await update.message.reply_text(_(lang, "flight_not_found", flight=flight))
        return

    flights = db.list_flights(update.effective_user.id)
    if not flights:
        await update.message.reply_text(_(lang, "no_flights"))
        return
    await _show_remove_list(update, context, lang)


async def _show_remove_list(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    flights = db.list_flights(update.effective_user.id)
    rows = []
    emoji_map = {"scheduled": "📅", "airborne": "🛫", "landed": "✅"}
    for f in flights:
        emoji = emoji_map.get(f["status"], "❓")
        rows.append([InlineKeyboardButton(
            f"{emoji} {f['flight_number']}",
            callback_data=f"rm_{f['flight_number']}",
        )])
    rows.append([InlineKeyboardButton(f"◀️ {_(lang, 'menu_btn')}", callback_data="menu")])
    if hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.edit_message_text(
            _(lang, "select_flight_to_remove"),
            reply_markup=InlineKeyboardMarkup(rows),
        )
    else:
        await update.message.reply_text(
            _(lang, "select_flight_to_remove"),
            reply_markup=InlineKeyboardMarkup(rows),
        )


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _get_lang(context, update.effective_user.id) or "en"
    flights = db.list_flights(update.effective_user.id)
    if not flights:
        await update.message.reply_text(_(lang, "no_flights"))
        return

    status_map = {"scheduled": _(lang, "status_scheduled"), "airborne": _(lang, "status_airborne"), "landed": _(lang, "status_landed")}
    emoji_map = {"scheduled": "📅", "airborne": "🛫", "landed": "✅"}

    lines = [_(lang, "flight_list_header")]
    rows = []
    for f in flights:
        dest_name = _(lang, "dest_unknown")
        if f["destination_icao"]:
            dest = get_airport(f["destination_icao"])
            dest_name = dest["name"] if dest else f["destination_icao"]
        emoji = emoji_map.get(f["status"], "❓")
        label = status_map.get(f["status"], f["status"])
        lines.append(f"{emoji} `{f['flight_number']}` -> {dest_name} ({label})")
        rows.append([
            InlineKeyboardButton(f"📍", callback_data=f"lw_{f['id']}"),
            InlineKeyboardButton(f"🔔", callback_data=f"lal_{f['id']}"),
            InlineKeyboardButton(f"🗑", callback_data=f"lrm_{f['id']}"),
        ])

    rows.append([InlineKeyboardButton(f"➕ {_(lang, 'add_btn')}", callback_data="add"),
                 InlineKeyboardButton(f"🏠 {_(lang, 'menu_btn')}", callback_data="menu")])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows),
    )


PREF_LABELS = {
    "pref_takeoff": "🛫",
    "pref_30min": "⏰",
    "pref_landed": "✅",
    "pref_delay": "⚠️",
    "pref_position": "📍",
}

PREF_KEYS = ["pref_takeoff", "pref_30min", "pref_landed", "pref_delay", "pref_position"]


async def pref_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split("_", 2)
    if len(parts) < 3:
        return
    flight_id = int(parts[1])
    pref = parts[2]

    lang = _get_lang(context, query.from_user.id) or "en"

    if pref == "save":
        flight = db.get_flight(flight_id)
        fn = flight["flight_number"] if flight else "??"
        keyboard = [[
            InlineKeyboardButton(f"📍 {_(lang, 'where_btn')}", callback_data=f"where_{flight_id}"),
            InlineKeyboardButton(f"🗑 {_(lang, 'remove_btn')}", callback_data=f"rm_{fn}"),
        ], [
            InlineKeyboardButton(f"🏠 {_(lang, 'menu_btn')}", callback_data="menu"),
        ]]
        await query.edit_message_text(
            f"✈️ `{fn}` — {_(lang, 'pref_saved')}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    flight = db.get_flight(flight_id)
    if not flight:
        await query.edit_message_text("Flight not found.")
        return

    new_val = 0 if flight[pref] else 1
    db.update_pref(flight_id, pref, new_val)
    flight[pref] = new_val

    rows = []
    for p in PREF_KEYS:
        val = flight[p]
        emoji = PREF_LABELS[p]
        name = _(lang, p)
        status = "✅" if val else "⬜"
        rows.append([InlineKeyboardButton(
            f"{emoji} {name}: {status}",
            callback_data=f"p_{flight_id}_{p}",
        )])
    rows.append([InlineKeyboardButton(f"💾 {_(lang, 'save')}", callback_data=f"p_{flight_id}_save")])

    await query.edit_message_text(
        f"✈️ `{flight['flight_number']}` — {_(lang, 'pref_ask')}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def where_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    flight_id = int(query.data.split("_", 1)[1])
    flight = db.get_flight(flight_id)
    if not flight:
        await query.edit_message_text("Flight not found.")
        return

    fn = flight["flight_number"]
    lang = _get_lang(context, query.from_user.id) or "en"
    await query.edit_message_text(f"🔍 Looking up `{fn}`...", parse_mode="Markdown")

    from aviationstack_client import lookup_flight as as_lookup, extract_position as as_pos, extract_schedule
    from airlabs_client import lookup_flight as al_lookup, extract_position as al_pos
    from geocode import get_country

    as_data = await as_lookup(fn)
    pos = as_pos(as_data) if as_data else None
    schedule = extract_schedule(as_data) if as_data else None
    source = "AviationStack"

    if not pos:
        al_data = await al_lookup(fn)
        pos = al_pos(al_data) if al_data else None
        if pos:
            source = "AirLabs"

    keyboard = [[
        InlineKeyboardButton(f"🔄 {_(lang, 'refresh_btn')}", callback_data=f"ref_{flight_id}"),
        InlineKeyboardButton(f"🗑 {_(lang, 'remove_btn')}", callback_data=f"rm_{fn}"),
    ], [
        InlineKeyboardButton(f"🔔 {_(lang, 'alerts_btn')}", callback_data=f"al_{flight_id}"),
        InlineKeyboardButton(f"🏠 {_(lang, 'menu_btn')}", callback_data="menu"),
    ]]

    if pos:
        country = get_country(pos["lat"], pos["lon"])
        from airports import find_nearest_airport
        nearest = find_nearest_airport(pos["lat"], pos["lon"])

        parts = [f"✈️ `{fn}`"]
        if country:
            if nearest:
                near_city = nearest.get("city") or nearest.get("name") or "??"
                dist = nearest["distance_km"]
                if dist <= 30:
                    label = f"*{near_city}*"
                else:
                    label = f"*{near_city}* area ({int(dist)}km)"
                parts.append(f"🌍 Over: {country} — near {label}")
            else:
                parts.append(f"🌍 Over: *{country}*")
        if pos.get("alt") is not None:
            alt_ft = int(pos["alt"] * 3.28084)
            parts.append(f"📏 Alt: {int(pos['alt'])}m / {alt_ft}ft")
        if pos.get("speed") is not None:
            kmh = int(pos["speed"])
            knots = int(kmh * 0.539957)
            parts.append(f"💨 Speed: {kmh} km/h / {knots} kts")
        if pos.get("direction") is not None:
            parts.append(f"🧭 Heading: {int(pos['direction'])}°")
        parts.append(f"\n_Data: {source}_")

        await query.edit_message_text("\n".join(parts), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if schedule and schedule.get("flight_status"):
        status = schedule["flight_status"]
        dep_iata = schedule.get("dep_iata") or "??"
        arr_iata = schedule.get("arr_iata") or "??"
        dep_sched = schedule.get("dep_scheduled") or ""
        arr_sched = schedule.get("arr_scheduled") or ""

        parts = [f"✈️ `{fn}`"]
        parts.append(f"📋 Status: *{status}*")
        parts.append(f"🛫 {dep_iata}  →  {arr_iata}")
        if dep_sched:
            parts.append(f"⏰ Dep: {dep_sched[:16].replace('T', ' ')}")
        if arr_sched:
            parts.append(f"⏰ Arr: {arr_sched[:16].replace('T', ' ')}")
        parts.append(f"\n_Data: AviationStack_")

        if status == "active":
            parts.append(f"\n💡 {_(lang, 'where_position_unavailable_active')}")
        elif status == "scheduled":
            parts.append(f"\n💡 {_(lang, 'where_not_airborne')}")
        elif status == "landed":
            parts.append(f"\n💡 {_(lang, 'where_already_landed')}")
        else:
            parts.append(f"\n💡 {_(lang, 'position_unavailable')}")

        await query.edit_message_text("\n".join(parts), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    await query.edit_message_text(
        f"✈️ `{fn}`\n\n{_(lang, 'position_unavailable')}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _get_lang(context, update.effective_user.id) or "en"
    await update.message.reply_text(_(lang, "about"), parse_mode="Markdown")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = _get_lang(context, update.effective_user.id) or "en"
    if config.OWNER_ID and update.effective_user.id != config.OWNER_ID:
        await update.message.reply_text(_(lang, "not_owner"))
        return

    s = db.get_stats()
    await update.message.reply_text(
        f"{_(lang, 'stats_header')}\n\n"
        f"👤 {_(lang, 'stats_users')}: {s['users']}\n"
        f"✈️ {_(lang, 'stats_total')}: {s['total_flights']}\n"
        f"🛫 {_(lang, 'stats_airborne')}: {s['airborne']}\n"
        f"📅 {_(lang, 'stats_scheduled')}: {s['scheduled']}\n"
        f"✅ {_(lang, 'stats_landed')}: {s['landed']}",
        parse_mode="Markdown",
    )


# ── Callback handlers ──────────────────────────────────────────────

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _get_lang(context, query.from_user.id) or "en"
    await _show_menu(update, context, lang)


async def add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _get_lang(context, query.from_user.id) or "en"
    await query.edit_message_text(_(lang, "add_usage"))


async def where_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    lang = _get_lang(context, user.id) or "en"
    flights = db.list_flights(user.id)
    if not flights:
        await query.edit_message_text(_(lang, "no_flights"))
        return
    rows = _flight_rows(user.id, lang)
    rows.append([InlineKeyboardButton(f"◀️ {_(lang, 'menu_btn')}", callback_data="menu")])
    await query.edit_message_text(
        _(lang, "where_title"),
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def alerts_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    lang = _get_lang(context, user.id) or "en"
    flights = db.list_flights(user.id)
    if not flights:
        await query.edit_message_text(_(lang, "no_flights"))
        return
    rows = []
    emoji_map = {"scheduled": "📅", "airborne": "🛫", "landed": "✅"}
    for f in flights:
        emoji = emoji_map.get(f["status"], "❓")
        rows.append([InlineKeyboardButton(
            f"{emoji} {f['flight_number']}",
            callback_data=f"al_{f['id']}",
        )])
    rows.append([InlineKeyboardButton(f"◀️ {_(lang, 'menu_btn')}", callback_data="menu")])
    await query.edit_message_text(
        _(lang, "alerts_title"),
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def alerts_flight_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    flight_id = int(query.data.split("_", 1)[1])
    lang = _get_lang(context, query.from_user.id) or "en"
    await _show_pref_keyboard(update, context, flight_id, lang, edit=True)


async def remove_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fn = query.data.split("_", 1)[1]
    lang = _get_lang(context, query.from_user.id) or "en"

    keyboard = [[
        InlineKeyboardButton(f"✅ {_(lang, 'remove_btn')}", callback_data=f"rmf_{fn}"),
        InlineKeyboardButton(f"◀️ {_(lang, 'back')}", callback_data="menu"),
    ]]
    await query.edit_message_text(
        _(lang, "remove_confirm", flight=fn),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def remove_final_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fn = query.data.split("_", 1)[1]
    user_id = query.from_user.id
    lang = _get_lang(context, user_id) or "en"

    ok = db.remove_flight(user_id, fn)
    if ok:
        text = _(lang, "flight_removed", flight=fn)
    else:
        text = _(lang, "flight_not_found", flight=fn)

    keyboard = [[
        InlineKeyboardButton(f"➕ {_(lang, 'add_btn')}", callback_data="add"),
        InlineKeyboardButton(f"🏠 {_(lang, 'menu_btn')}", callback_data="menu"),
    ]]
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    flight_id = int(query.data.split("_", 1)[1])
    query.data = f"where_{flight_id}"
    await where_callback(update, context)


async def list_where_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    flight_id = int(query.data.split("_", 1)[1])
    query.data = f"where_{flight_id}"
    await where_callback(update, context)


async def list_alerts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    flight_id = int(query.data.split("_", 1)[1])
    query.data = f"al_{flight_id}"
    await alerts_flight_callback(update, context)


async def list_remove_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    flight = db.get_flight(int(query.data.split("_", 1)[1]))
    if not flight:
        return
    query.data = f"rm_{flight['flight_number']}"
    await remove_confirm_callback(update, context)


async def about_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = _get_lang(context, query.from_user.id) or "en"
    user = db.get_user(query.from_user.id)
    total = "---"
    if user:
        cnt = db.get_user_flight_count(query.from_user.id)
        total = str(cnt)
    text = _(lang, "about") + f"\n\n✈️ {_(lang, 'your_flights')}: {total}"
    keyboard = [[InlineKeyboardButton(f"◀️ {_(lang, 'menu_btn')}", callback_data="menu")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


# ── Main ────────────────────────────────────────────────────────────

async def async_main():
    db.init_db()
    logger.info("DB ready.")

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("language", cmd_language))
    app.add_handler(CommandHandler("about", cmd_about))
    app.add_handler(CommandHandler("where", cmd_where))
    app.add_handler(CommandHandler("menu", cmd_menu))

    app.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(pref_callback, pattern="^p_"))
    app.add_handler(CallbackQueryHandler(where_callback, pattern="^where_"))
    app.add_handler(CallbackQueryHandler(refresh_callback, pattern="^ref_"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(add_callback, pattern="^add$"))
    app.add_handler(CallbackQueryHandler(where_menu_callback, pattern="^where$"))
    app.add_handler(CallbackQueryHandler(alerts_menu_callback, pattern="^al$"))
    app.add_handler(CallbackQueryHandler(alerts_flight_callback, pattern="^al_"))
    app.add_handler(CallbackQueryHandler(remove_confirm_callback, pattern="^rm_")),
    app.add_handler(CallbackQueryHandler(remove_final_callback, pattern="^rmf_"))
    app.add_handler(CallbackQueryHandler(list_where_callback, pattern="^lw_"))
    app.add_handler(CallbackQueryHandler(list_alerts_callback, pattern="^lal_"))
    app.add_handler(CallbackQueryHandler(list_remove_callback, pattern="^lrm_"))
    app.add_handler(CallbackQueryHandler(about_callback, pattern="^about$"))
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))

    await app.initialize()
    await app.updater.start_polling()
    await app.start()

    start_scheduler(app.bot)

    if config.PORT:
        _start_healthcheck(config.PORT)

    logger.info("Bot running!")

    stop = asyncio.Event()
    await stop.wait()


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
