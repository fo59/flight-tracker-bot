<p align="center">
  <img src="flight_check_logo.png" width="140" alt="Flight Tracker Bot logo">
</p>

# Flight Tracker Bot

A Telegram bot that follows a flight for you and messages you when something happens: takeoff, 30 minutes before landing, landing, or a likely delay. You send a flight number, the bot does the rest.

I built it because refreshing flight radar apps while waiting to pick someone up from the airport gets old fast. Telegram was the obvious place for it: the message just arrives on your phone.

## What it does

- **Track any flight by number:** `/add TK1785`, optionally with destination and origin airports (`/add TK1785 EKCH LTFM`).
- **Choose notifications per flight:** takeoff, landing soon, landed, delay warning, and optional position updates every 30 minutes.
- **See where the plane is:** the country it's flying over and the nearest city (*Romania, near Constanța area (40km)*), plus altitude, speed and heading.
- **Button menus:** everything works with inline buttons; commands are there if you prefer typing.
- **Turkish and English:** each user picks a language on first start.

## How it works

Free flight APIs have tight monthly limits, so most of the logic is about getting accurate data without burning through the quota.

```
every 5 min
   │
   ├─ 1. AirLabs bulk request ──── one call returns all live flights,
   │                               matched against every tracked flight
   │
   ├─ 2. AirLabs single lookup ─── only for flights the bulk call missed
   │                               (45 min cooldown per flight)
   │
   ├─ 3. AviationStack ─────────── last resort; has schedules even before
   │                               takeoff (12 h cooldown per flight)
   │
   └─ 4. Delay check ───────────── still not airborne 45 min after scheduled
                                   departure → "possible delay" warning
```

- **Landing ETA** is calculated from the plane's live position and ground speed using the haversine formula. If no position is available, the bot falls back to the scheduled arrival time.
- **Landing detection** uses the status from the API, and also catches flights that disappear from live data while airborne.
- **Country lookup** runs offline against a bundled GeoJSON file of country borders. It samples a few nearby points when the plane is near a coastline, so it isn't wrongly reported as over water. No geocoding API needed.
- **Nearest city** comes from the OpenFlights airport dataset, downloaded once and cached locally.
- **Cleanup:** a nightly job deletes flights that landed more than a day ago.

## Tech stack

- Python 3.9+ with `asyncio`
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v20
- APScheduler for the polling and cleanup jobs
- httpx for async API requests
- SQLite for users, flights and notification preferences
- Deployed on Railway, with a small HTTP health check endpoint

## Project structure

```
main.py                  Telegram handlers, menus, health check, entry point
scheduler.py             Polling loop: data source fallback, notifications, delay checks
database.py              SQLite schema, migrations and queries
airlabs_client.py        AirLabs API (bulk + single flight)
aviationstack_client.py  AviationStack API (schedules)
opensky_client.py        Haversine distance and ETA calculation
airports.py              OpenFlights airport data, ICAO lookup, nearest airport
geocode.py               Offline lat/lon → country lookup
localization.py          Turkish and English texts
config.py                Settings from environment variables
```

## Running locally

```bash
git clone https://github.com/fo59/flight-tracker-bot.git
cd flight-tracker-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env     # then fill in your keys
python main.py
```

You need a bot token from [@BotFather](https://t.me/BotFather). Both flight data APIs have free plans.

| Variable | Required | Notes |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | From @BotFather |
| `AIRLABS_API_KEY` | recommended | Live positions and flight status ([airlabs.co](https://airlabs.co)) |
| `AVIATIONSTACK_API_KEY` | optional | Schedules, used as fallback ([aviationstack.com](https://aviationstack.com)) |
| `OWNER_ID` | optional | Your Telegram user ID; enables the `/stats` command |
| `CHECK_INTERVAL_SECONDS` | optional | Polling interval, default `300` |
| `LANDING_THRESHOLD_MINUTES` | optional | When to send "landing soon", default `30` |
| `DELAY_THRESHOLD_MINUTES` | optional | When to warn about a delay, default `45` |

Without any flight API key the bot still runs, but it can only send delay warnings.

## Deploying

The repo includes a `Procfile`, so it deploys to Railway (or a similar platform) as is: connect the repo and add the environment variables. Railway's disk is reset on every deploy, so attach a volume and point `DB_PATH` to it if tracked flights should survive restarts.

## Commands

| Command | |
|---|---|
| `/start` | Choose a language and open the menu |
| `/add <flight> [dest] [origin]` | Start tracking a flight |
| `/list` | Your tracked flights and their status |
| `/where` | Current position of a flight |
| `/remove <flight>` | Stop tracking a flight |
| `/language` | Change language |
| `/about` | What data the bot stores and why |
