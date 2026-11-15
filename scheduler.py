from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db
from airports import get_airport
from config import (
    CHECK_INTERVAL_SECONDS,
    LANDING_THRESHOLD_MINUTES,
    DELAY_THRESHOLD_MINUTES,
    AVIATIONSTACK_API_KEY,
    AIRLABS_API_KEY,
    AIRLABS_COOLDOWN_SECONDS,
)
from localization import t as _
from opensky_client import estimate_minutes_to_arrival

logger = logging.getLogger(__name__)

AIRLABS_COOLDOWN = AIRLABS_COOLDOWN_SECONDS
AVIATIONSTACK_COOLDOWN = 12 * 3600

_aviationstack_cooldown: dict[int, float] = {}
_airlabs_cooldown: float = 0
_airlabs_seen: set[int] = set()
_airlabs_individual_cooldown: dict[int, float] = {}
AIRLABS_INDIVIDUAL_COOLDOWN = 2700  # 45 min, matches bulk cooldown

# --- helpers ---

def _user_lang(user_id: int) -> str:
    return db.get_user_language(user_id) or "en"


async def _notify(bot, user_id: int, text: str):
    try:
        await bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
    except Exception:
        logger.exception("Bildirim gonderilemedi: user_id=%s", user_id)


async def _notify_takeoff(f: dict, bot, lang: str):
    db.update_flight(f["id"], status="airborne", notified_takeoff=1)
    await _notify(bot, f["user_id"], _(lang, "takeoff", flight=f["flight_number"]))


async def _notify_landed(f: dict, bot, lang: str):
    db.update_flight(f["id"], status="landed", notified_landed=1)
    await _notify(bot, f["user_id"], _(lang, "landed", flight=f["flight_number"]))


async def _notify_landing_soon(f: dict, bot, lang: str, eta: int, pos: dict, dest_name: str):
    await _notify(bot, f["user_id"], _(
        lang, "landing_soon",
        flight=f["flight_number"], dest=dest_name, eta=eta,
        lat=f"{pos['lat']:.2f}", lon=f"{pos['lon']:.2f}",
        alt=int(pos.get("alt") or 0),
        speed=int(pos.get("speed") or 0),
    ))
    db.update_flight(f["id"], notified_30min=1)


async def _notify_landing_soon_schedule(f: dict, bot, lang: str, eta: int, dest_name: str):
    await _notify(bot, f["user_id"], _(
        lang, "landing_soon_schedule",
        flight=f["flight_number"], dest=dest_name, eta=eta,
    ))
    db.update_flight(f["id"], notified_30min=1)


def _minutes_since(iso_ts: str) -> float:
    if not iso_ts:
        return 0
    added = datetime.fromisoformat(iso_ts)
    if added.tzinfo is None:
        added = added.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - added).total_seconds() / 60


def _parse_iso(iso_ts: str):
    if not iso_ts:
        return None
    dt = datetime.fromisoformat(iso_ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _get_destination(f: dict) -> tuple:
    """Return (dest_info, dest_name) for a flight."""
    dest = get_airport(f["destination_icao"]) if f.get("destination_icao") else None
    dest_name = dest["name"] if dest else (f.get("destination_icao") or "??")
    return dest, dest_name


def _estimate_eta(pos: dict, dest: dict) -> int | None:
    """Returns minutes to arrival, or None if cannot compute."""
    eta = estimate_minutes_to_arrival(pos["lat"], pos["lon"], pos["speed"] or 0, dest["lat"], dest["lon"])
    return int(eta) if eta is not None else None


def _should_notify_30min(f: dict) -> bool:
    return f["status"] == "airborne" and not f["notified_30min"] and f["pref_30min"]


# --- Phase 1: AirLabs bulk ---

async def _airlabs_bulk(flights: list, bot) -> set[int]:
    """Check all flights via AirLabs /flights. Returns set of matched flight IDs."""
    global _airlabs_cooldown, _airlabs_seen

    if not AIRLABS_API_KEY:
        return set()

    now = time.time()
    if now - _airlabs_cooldown < AIRLABS_COOLDOWN:
        return set()

    from airlabs_client import fetch_all_active_flights, extract_position as al_pos

    all_al = await fetch_all_active_flights()
    if all_al is None:
        return set()

    _airlabs_cooldown = now
    matched: set[int] = set()
    current_seen: set[int] = set()

    for f in flights:
        al_data = all_al.get(f["flight_number"])
        if not al_data:
            continue

        matched.add(f["id"])
        current_seen.add(f["id"])
        lang = _user_lang(f["user_id"])
        status = al_data.get("status", "")
        pos = al_pos(al_data)

        # takeoff
        if status == "en-route" and f["status"] == "scheduled" and f["pref_takeoff"]:
            f["status"] = "airborne"
            await _notify_takeoff(f, bot, lang)

        # landed (explicit from API)
        if status == "landed" and f["status"] == "airborne" and f["pref_landed"]:
            f["status"] = "landed"
            await _notify_landed(f, bot, lang)
            continue

        # 30 min before landing
        if _should_notify_30min(f) and pos:
            dest, dest_name = _get_destination(f)
            if dest:
                eta = _estimate_eta(pos, dest)
                if eta is not None and eta <= LANDING_THRESHOLD_MINUTES:
                    await _notify_landing_soon(f, bot, lang, eta, pos, dest_name)

    # landing detection: vanished from AirLabs radar
    vanished = _airlabs_seen - current_seen
    _airlabs_seen = current_seen
    for fid in vanished:
        f = next((x for x in flights if x["id"] == fid), None)
        if f and f["status"] == "airborne" and f["pref_landed"]:
            await _notify_landed(f, bot, _user_lang(f["user_id"]))

    return matched


# --- Phase 2: AviationStack fallback ---

def _update_db_schedule(f: dict, schedule: dict):
    updates = {}
    if schedule.get("dep_scheduled"):
        updates["sched_departure"] = schedule["dep_scheduled"]
    if schedule.get("arr_scheduled"):
        updates["sched_arrival"] = schedule["arr_scheduled"]
    if schedule.get("dep_icao"):
        updates["dep_icao"] = schedule["dep_icao"]
    if updates:
        db.update_flight(f["id"], **updates)
        f.update(updates)


async def _as_handle_takeoff(f: dict, bot, lang: str, flight_status: str):
    if flight_status == "active" and f["status"] == "scheduled" and f["pref_takeoff"]:
        await _notify_takeoff(f, bot, lang)


async def _as_handle_landed(f: dict, bot, lang: str, flight_status: str):
    if flight_status == "landed" and f["status"] == "airborne" and f["pref_landed"]:
        await _notify_landed(f, bot, lang)


async def _as_handle_30min(f: dict, bot, lang: str, data: dict, schedule: dict):
    if not _should_notify_30min(f):
        return

    from aviationstack_client import extract_position as as_pos

    pos = as_pos(data)
    if pos:
        dest, dest_name = _get_destination(f)
        if dest:
            eta = _estimate_eta(pos, dest)
            if eta is not None and eta <= LANDING_THRESHOLD_MINUTES:
                await _notify_landing_soon(f, bot, lang, eta, pos, dest_name)
                return

    arrival_time = schedule.get("arr_estimated") or schedule.get("arr_scheduled")
    if not arrival_time:
        return

    arr_dt = _parse_iso(arrival_time)
    if not arr_dt:
        return

    remaining = (arr_dt - datetime.now(timezone.utc)).total_seconds() / 60
    if 0 < remaining <= LANDING_THRESHOLD_MINUTES:
        _, dest_name = _get_destination(f)
        await _notify_landing_soon_schedule(f, bot, lang, int(remaining), dest_name)


async def _check_one_al_individual(f: dict, bot) -> bool:
    """Check a single flight via AirLabs individual /flight endpoint. Returns True if matched."""
    flight_id = f["id"]
    now = time.time()
    last = _airlabs_individual_cooldown.get(flight_id, 0)
    if now - last < AIRLABS_INDIVIDUAL_COOLDOWN:
        return False

    from airlabs_client import lookup_flight, extract_position as al_pos

    _airlabs_individual_cooldown[flight_id] = now
    data = await lookup_flight(f["flight_number"])
    if not data:
        return False

    lang = _user_lang(f["user_id"])
    status = data.get("status", "")
    pos = al_pos(data)

    if status == "en-route" and f["status"] == "scheduled" and f["pref_takeoff"]:
        f["status"] = "airborne"
        await _notify_takeoff(f, bot, lang)

    if status == "landed" and f["status"] == "airborne" and f["pref_landed"]:
        f["status"] = "landed"
        await _notify_landed(f, bot, lang)
        return True

    if _should_notify_30min(f) and pos:
        dest, dest_name = _get_destination(f)
        if dest:
            eta = _estimate_eta(pos, dest)
            if eta is not None and eta <= LANDING_THRESHOLD_MINUTES:
                await _notify_landing_soon(f, bot, lang, eta, pos, dest_name)

    return True


async def _check_one_as(f: dict, bot):
    """Check a single flight via AviationStack."""
    from aviationstack_client import lookup_flight, extract_schedule

    flight_id = f["id"]
    now_ts = time.time()
    last = _aviationstack_cooldown.get(flight_id, 0)

    if now_ts - last < AVIATIONSTACK_COOLDOWN:
        return

    _aviationstack_cooldown[flight_id] = now_ts
    data = await lookup_flight(f["flight_number"])
    if not data:
        return

    schedule = extract_schedule(data)
    if not schedule:
        return

    lang = _user_lang(f["user_id"])
    flight_status = schedule.get("flight_status", "")

    _update_db_schedule(f, schedule)
    await _as_handle_takeoff(f, bot, lang, flight_status)
    await _as_handle_30min(f, bot, lang, data, schedule)
    await _as_handle_landed(f, bot, lang, flight_status)


async def _aviationstack_fallback(flights: list, already_matched: set[int], bot):
    for f in flights:
        if f["id"] not in already_matched:
            matched_individual = await _check_one_al_individual(f, bot)
            if not matched_individual:
                await _check_one_as(f, bot)
        await _check_delay(f, bot, _user_lang(f["user_id"]))


# --- Delay detection ---

async def _check_delay(f: dict, bot, lang: str):
    if f["status"] != "scheduled" or f["notified_delay"] or not f["pref_delay"]:
        return
    if f.get("sched_departure"):
        sched = _parse_iso(f["sched_departure"])
        if sched and datetime.now(timezone.utc) > sched + timedelta(minutes=DELAY_THRESHOLD_MINUTES):
            db.update_flight(f["id"], notified_delay=1)
            await _notify(bot, f["user_id"], _(lang, "delay_warning", flight=f["flight_number"], delay=DELAY_THRESHOLD_MINUTES))
    else:
        if _minutes_since(f["added_date"]) >= DELAY_THRESHOLD_MINUTES:
            db.update_flight(f["id"], notified_delay=1)
            await _notify(bot, f["user_id"], _(lang, "delay_warning", flight=f["flight_number"], delay=DELAY_THRESHOLD_MINUTES))


# --- Position updates ---

POSITION_UPDATE_INTERVAL = 30  # minutes

async def _position_updates(flights: list, bot):
    """Send periodic position updates for flights with pref_position=1."""
    from airlabs_client import extract_position as al_pos
    from geocode import get_country
    from airports import find_nearest_airport

    now = time.time()

    for f in flights:
        if f["status"] != "airborne" or not f.get("pref_position"):
            continue

        last_notif = f.get("last_position_notification")
        if last_notif:
            last_ts = _parse_iso(last_notif)
            if last_ts:
                elapsed = (datetime.now(timezone.utc) - last_ts).total_seconds() / 60
                if elapsed < POSITION_UPDATE_INTERVAL:
                    continue

        flight_id = f["id"]

        from airlabs_client import lookup_flight
        data = await lookup_flight(f["flight_number"])
        if not data:
            continue

        pos = al_pos(data)
        if not pos:
            continue

        lang = _user_lang(f["user_id"])
        country = get_country(pos["lat"], pos["lon"])
        nearest = find_nearest_airport(pos["lat"], pos["lon"])

        near_text = ""
        if nearest:
            near_city = nearest.get("city") or nearest.get("name") or "??"
            dist = nearest["distance_km"]
            if dist <= 30:
                near_text = f" — near *{near_city}*"
            else:
                near_text = f" — near *{near_city}* area ({int(dist)}km)"

        alt_m = int(pos.get("alt") or 0)
        alt_ft = int(alt_m * 3.28084)
        speed = int(pos.get("speed") or 0)
        heading = int(pos.get("direction") or 0)

        text = _(
            lang, "position_update",
            flight=f["flight_number"],
            country=country or "??",
            near=near_text,
            alt=alt_m,
            alt_ft=alt_ft,
            speed=speed,
            heading=heading,
        )

        await _notify(bot, f["user_id"], text)
        db.update_position_notification_time(flight_id)


# --- Orchestrator ---

async def check_all_flights(bot):
    flights = db.get_all_tracked_flights()
    if not flights:
        return

    matched = await _airlabs_bulk(flights, bot)

    if AVIATIONSTACK_API_KEY:
        await _aviationstack_fallback(flights, matched, bot)
    else:
        for f in flights:
            if f["id"] not in matched:
                await _check_delay(f, bot, _user_lang(f["user_id"]))

    await _position_updates(flights, bot)


# --- Cleanup & scheduler ---

async def cleanup_old_flights_job():
    count = db.cleanup_old_flights()
    if count:
        logger.info("Temizlik: %s ucus silindi.", count)


def start_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_all_flights,
        "interval",
        seconds=CHECK_INTERVAL_SECONDS,
        args=[bot],
        next_run_time=datetime.now(),
    )
    scheduler.add_job(
        cleanup_old_flights_job,
        "cron",
        hour=3,
        minute=0,
    )
    scheduler.start()
    return scheduler
