# Lac Manitou — Architecture

Full technical documentation for the **Lac Manitou temperature & weather dashboard**
(live at **https://lmt.bcourchesne.com**). This document describes the whole system:
sensors → Home Assistant → Firebase → web app, plus the legacy Google-stack it
replaced.

---

## 1. Overview

A public web dashboard showing **real-time and historical water, air, and weather
conditions** for Lac Manitou (Ivry-sur-le-Lac, QC — ~46.06°N, −74.37°W, ~390 m
elevation). It is a static single-page app that reads from a Firebase Realtime
Database, which is fed every 5 minutes by Home Assistant from three independent
sensor systems.

**Design principles**
- **Serverless & free.** No Cloud Functions, no always-on backend. Runs entirely on
  the Firebase Spark (free) plan. Home Assistant does all the data collection and
  aggregation.
- **Static frontend.** Plain HTML/CSS/JS on Firebase Hosting; all charting and
  downsampling happen client-side.
- **Public read, authenticated write.** Anyone can view; only the Home Assistant
  writer account can write.

---

## 2. System architecture

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                          SENSOR LAYER                                  │
  │                                                                        │
  │  ① Olimex ESP32-POE-ISO (ESPHome)      ② Veranda sensor    ③ Ecowitt   │
  │     3× DS18B20 on 1-Wire (GPIO13)         (Zigbee/RF)         WS69 +    │
  │     • water surface                       • temperature      GW3000    │
  │     • water 4 ft deep                      (airv)            gateway    │
  │     • dock air (archived only)            • humidity (hum)   • wind/gust│
  │     Wired PoE Ethernet (LAN8720)                             • rain     │
  │                                                             • UV/solar  │
  │                                                             • pressure  │
  └───────────────┬───────────────────────┬─────────────────────┬─────────┘
                  │  ESPHome native API    │  (integration)      │ (integration)
                  ▼                        ▼                     ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    HOME ASSISTANT  (192.168.11.3:8123)                 │
  │                                                                        │
  │  • Every 5 min automation:                                             │
  │      1. sign in to Firebase Auth  → fresh idToken (1 h)                │
  │      2. PUT /readings/{epoch_ms}  (authenticated)                     │
  │  • Hourly script: aggregate completed days → /daily (self-healing)     │
  │  • (Sheets dual-write retired 2026-07-11 — Firebase is now sole target)│
  └───────────────┬──────────────────────────────────────┬────────────────┘
                  │ REST (PUT, auth token)
                  ▼
  ┌───────────────────────────────────┐      ┌──────────────────────────────┐
  │  FIREBASE Realtime Database        │      │  GOOGLE APPS SCRIPT + SHEETS │
  │  project: lac-manitou-temperatures │      │  (LEGACY — not written to)   │
  │  /readings/{ms}  raw 5-min samples │      │  • Temperatures sheet (frozen)│
  │  /daily/{utcMidnightMs} daily means│      │  • Visiteurs sheet (frozen)  │
  │  rules: read=public, write=ha-only │      │  • doGet → redirect to app   │
  └───────────────┬───────────────────┘      └──────────────────────────────┘
                  │ public REST (GET, no auth)
                  ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │        FIREBASE HOSTING  →  https://lmt.bcourchesne.com               │
  │        index.html (static SPA)                                        │
  │  • fetch /readings (24h/7d/30d) + client downsampling                 │
  │  • fetch /daily (season/year)                                         │
  │  • Chart.js line charts, current-condition cards, stats               │
  │  • External: Environment Canada forecast, Windy radar, SunCalc, GA4   │
  └──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Sensor layer

### ① Water & air probes — Olimex ESP32-POE-ISO (ESPHome)
Config: [`../sondes.yaml`](../sondes.yaml) · device name `sondes-quai-lac-manitou`

- **Board:** Olimex `esp32-poe-iso`, Arduino framework.
- **Networking:** **wired PoE Ethernet** (LAN8720 PHY) — no Wi-Fi. Powered and
  networked over a single Ethernet cable at the dock.
- **Bus:** 3× **DS18B20** (`dallas_temp`) digital temperature probes on a shared
  1-Wire bus (GPIO13), 12-bit resolution, 5-min update interval:
  - **`temp_surface`** — water surface  → the "Eau surface" tile / `surface` field
  - **`temp_4pi`** — water at 4 feet deep → the "Eau 4 pieds" tile / `depth` field
  - **`temp_air`** — air at the dock → `air` field (**archived only, not displayed**;
    the dock probe sits too close to the water surface, which hurts its precision — its
    reading is pulled toward the water temperature rather than reflecting true air
    temperature. The UI uses the veranda sensor instead — see ②).
- **Derived (template) sensors, on-device:**
  - Delta surface − 4 ft (thermal stratification)
  - Delta surface − air (fog / condensation indicator)
- **Link to HA:** native ESPHome API (encrypted). The three DS18B20 addresses in
  `sondes.yaml` are placeholders (`0x0000…`) and are set to the real probe addresses
  on the running device.

> The two **water** sensors (surface + 4 ft) are the heart of the app; the dock air
> probe is retained in storage but superseded on-screen by the veranda sensor.

### ② Ambient air & humidity — Veranda sensor
HA entities `sensor.remote_veranda_salle_a_manger_temperature` / `_humidity`.

Provides the UI's **"Air ambiant" (`airv`)** and **"Humidité" (`hum`)**. It lives in a
screened porch (transparent roof) that is representative of outdoor air but can read a
few °C high midday from radiant heating. **It replaced the dock air probe as the
displayed air temperature** because the dock probe, being too close to the water, lost
precision (its readings tracked the water rather than the air).

### ③ Weather station — Ecowitt WS69 + GW3000 gateway
HA entities `sensor.gw3000b_*`. Contributes wind, rain, sky, and pressure:

| Field  | HA entity                          | Notes |
|--------|------------------------------------|-------|
| `wind` | `gw3000b_wind_speed` (km/h)        | |
| `gust` | `gw3000b_wind_gust` (km/h)         | daily max stored as `gustmax` in /daily |
| `wdir` | `gw3000b_wind_direction` (°)       | |
| `rrate`| `gw3000b_rain_rate` (mm/h)         | |
| `rday` | `gw3000b_daily_rain` (mm)          | daily max in /daily |
| `uv`   | `gw3000b_uv_index`                 | |
| `solar`| `gw3000b_solar_radiation` (W/m²)   | |
| `press`| `gw3000b_relative_pressure` (hPa)  | **sea-level (relative) pressure** — see §11 |

Details on the Ecowitt integration and HA entity discovery are in
[`ECOWITT_HANDOFF.md`](ECOWITT_HANDOFF.md). A `WN32` outdoor temp/humidity sensor
(`airb`/`humb`) is provisioned in the payload but commented out until the entity exists.

---

## 4. Data pipeline (Home Assistant)

Config: [`home_assistant.yaml`](home_assistant.yaml) (gitignored on the live HA host;
the copy here is the reference).

### 4.1 Every-5-minute write automation
Trigger: `time_pattern` every 5 min. Skips if the ESP32 water/air probes are
`unavailable`.

1. **`firebase_signin`** → POST to Firebase Auth `signInWithPassword` with the
   `ha-writer@manitou.local` account → returns a fresh **idToken** (valid 1 h). The
   token is ~900 chars — too long to store in an `input_text` — so HA signs in fresh
   every cycle rather than caching it.
2. **`manitou_firebase`** → `PUT /readings/{epoch_ms}.json?auth={token}` with the full
   payload (all sensor fields). **Key = timestamp in ms** → free chronological
   ordering + idempotency. A `num()` Jinja macro writes `null` (not `0`) when a sensor
   is `unavailable`, so missing data doesn't pollute averages.

A persistent notification fires on Firebase auth or write failure.

> **Retired (2026-07-11):** the automation used to also POST to the legacy Google
> Apps Script endpoint (`manitou_temperatures`) as a dual-write to Sheets. That step
> has been removed — Firebase is the sole write target. See §8 for what this means
> for the GAS backend.

### 4.2 Hourly `/daily` aggregation (Option A)
Script `script.manitou_aggregate_daily`, triggered hourly and at HA start.
**Idempotent & self-healing:** for each of the **last 10 completed UTC days** missing
from `/daily`, it GETs that day's raw `/readings` and PUTs a bucket keyed by
UTC-midnight ms.

- Means: `air, surface, depth, airv, hum, airb, humb, wind, uv, solar, press`
- Maxes: `gustmax` (from `gust`), `rday`
- **Vector mean:** `wdirdom` — dominant wind direction in degrees, from `wdir`.
  Wind direction is circular, so this is a **vector** mean (sum the sin/cos
  components, then `atan2`), never an arithmetic one — averaging 350° and 10°
  arithmetically gives 180°, the exact opposite of the truth. When the resultant
  magnitude is below 0.2 (wind swung all over the day) it writes `null` rather
  than the misleading 0°=North that `atan2(0,0)` would return.
- Count: `n` (number of raw samples that day)

> **Adding a field to `/daily` touches TWO reload domains.** The value is computed
> in the `data:` block of `script.manitou_aggregate_daily`, but the JSON key lives in
> `rest_command.firebase_put_daily.payload` (configuration.yaml). *Reload Scripts does
> not reload REST commands* — reload both, or restart. A field present in one and not
> the other fails **silently**: a missing key just writes a shorter bucket, and an
> undefined variable in the payload renders empty, producing invalid JSON that kills
> the whole write. Use `{{ field | default("null") }}` in the payload so the two can
> be deployed in either order. This cost a full debugging session on `wdirdom`
> (added 2026-07-17, actually live 2026-07-22).
>
> **Adding a new field to `/daily` does not backfill history.** The script skips
> any day already present (`dayms not in existing`), so a new field only appears
> on days aggregated from then on. To rebuild history: temporarily widen
> `for_each: range(1, 11)` to cover every day since the start of record, delete
> `/daily`, run the script, then restore the 10-day window. Deleting `/daily`
> *without* widening the range permanently drops every bucket older than 10 days
> (the season/year views read `/daily`).
- "Option A" = **completed days only.** Today never appears in /daily; the 24 h raw
  view covers the current day. Nobody views a yearly chart expecting the last 3 hours,
  so this is sufficient and avoids Cloud Functions entirely.

---

## 5. Data storage — Firebase Realtime Database

- **Project:** `lac-manitou-temperatures-d284a`
- **URL:** `https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com/`

### 5.1 `/readings/{epoch_ms}` — raw 5-minute samples
```json
{
  "air": 14.06, "surface": 22.94, "depth": 23.12,   // ESP32 water/dock probes (°C)
  "airv": 15.36, "hum": 91.52,                       // veranda temp (°C) / humidity (%)
  "wind": 0.7, "gust": 1.8, "wdir": 302,             // Ecowitt wind
  "rrate": 0.0, "rday": 0.0,                          // Ecowitt rain (mm/h, mm)
  "uv": 0, "solar": 32,                               // Ecowitt sky
  "press": 1009                                       // sea-level pressure (hPa)
}
```
Fields may be absent on older records (sensors were added over time — pressure/wind/UV
only exist from ~Jul 7 2026; `airv`/`hum` from ~Jul 6 2026).

### 5.2 `/daily/{utc_midnight_ms}` — daily aggregates
```json
{ "air": 19.52, "surface": 24.0, "depth": 24.14, "airv": 20.17, "hum": 86.39,
  "wind": 0.5, "gustmax": 13.0, "wdirdom": 271, "rday": 10.7, "uv": 0.2,
  "solar": 45, "press": 964.2, "n": 288 }
```

### 5.3 Security rules — [`database.rules.json`](database.rules.json)
```json
{ "rules": {
    ".read": false,
    ".write": "auth.uid === '51jJyJAiWGTnUJZAaK9FgbzH6sA2'",
    "readings": { ".read": true },
    "daily":    { ".read": true }
}}
```
Public read on `/readings` and `/daily` (so the browser can fetch without auth);
writes require the `ha-writer` account UID. Verified: anonymous write → 401.

---

## 6. Frontend — the web app

Single file: [`index.html`](index.html) (~1800 lines, vanilla JS, no build step).
Served as static content by Firebase Hosting.

### 6.1 Views & data granularity
| Period      | Source              | Downsampling |
|-------------|---------------------|--------------|
| 24 h        | `/readings`         | raw (client)  |
| 7 d / 30 d  | `/readings`         | client-side hourly averaging |
| Saison (180 d) / Année (365 d) | `/daily` | pre-aggregated, no client bucketing |

Reading `/daily` for long ranges keeps payloads at ~15–35 KB instead of 5–9 MB of raw
data. `/daily` excludes the current incomplete day, avoiding a misleading partial-day
average.

### 6.2 What's displayed
- **Condition cards:** Air, Humidité, Pression, Eau surface, Eau 4 pieds — each with a
  value and a trend arrow. Pressure trend colors a *falling* reading orange as a
  storm-approaching cue.
- **Chart:** Chart.js multi-series line chart with dual °C (left) / °F (right) axes.
  Legend items are checkboxes toggling series (temps grouped; Humidité and other
  weather metrics — pressure/wind/rain/UV/solar — are exclusive vs the temp group and
  swap the y-axis unit).
- **Stats:** Min / Avg / Max per series for the selected period.
- **Forecast row:** Windy radar embed + Environment Canada 7-day forecast.
- **Sun/Moon:** SunCalc computes moon phase and sun times client-side.
- **i18n:** full FR/EN toggle; preferences (`lm_lang`, `lm_unit_*`) in `localStorage`
  (reliable now on the stable Firebase domain — the original reason for leaving GAS).

### 6.3 Client libraries (all via CDN)
- **Chart.js 4.4** + `chartjs-adapter-date-fns` 3.0 (time axis)
- **SunCalc 1.9** (sun/moon)
- **Tabler Icons** 3.11 (webfont) · **Inter** font
- **Google Analytics 4** — measurement id `G-DPZEL02P7N` (client gtag; works on the
  Firebase domain, unlike the old GAS iframe).

---

## 7. External integrations

| Service | Use | Endpoint |
|---------|-----|----------|
| **Environment Canada** | 7-day forecast (station Sainte-Agathe, `qc-33`); also carries current conditions incl. sea-level pressure | `api.weather.gc.ca/collections/citypageweather-realtime/items/qc-33` |
| **Windy** | Embedded weather radar iframe | `embed.windy.com/embed2.html` |
| **SunCalc** | Moon phase & sun times (client, offline) | — |
| **Google Analytics 4** | Visitor analytics | `G-DPZEL02P7N` |

Forecast refreshes hourly; the current conditions ~5-min data refreshes on the same
interval as the readings. The forecast card fails silently (hides) if the API is
unreachable.

---

## 8. Legacy Google stack (mostly dormant)

Code: [`Code.gs`](Code.gs) · manifest [`appsscript.json`](appsscript.json) ·
Spreadsheet `1-bCZDpK7PwrMPeG7KcUEcpXs1LcsND7C4tnJMInwnoo`.

The app **originated** as a Google Apps Script web app reading from Google Sheets. It
was migrated to Firebase (see the migration history in the project notes). Current
state:

- **`doPost`** — the HA dual-write that used to call this was **removed on
  2026-07-11** (Firebase is now the sole write target). `doPost` itself is still
  present in `Code.gs` (token-guarded, range-validated) but is no longer invoked by
  anything — it's dead code kept for now, not an active pipeline step. Safe to delete
  outright in a follow-up if the Sheets copy is no longer needed.
- **`doGet`** — no longer serves the app; returns a **"site moved" redirect** page to
  `lmt.bcourchesne.com` (the original data-serving `doGet` is preserved in a commented
  `ANCIEN CODE` block for rollback).
- **`migrateSheetToFirebase()`** — one-shot historical import (Sheets → `/readings`),
  auto-detects the cutoff = earliest live Firebase key so it never duplicates. Already
  run; would now fail if re-run (writes unauthenticated) — migration is complete.
- **Visitor tracking / GA4 Measurement Protocol** — legacy server-side analytics in the
  Sheets `Visiteurs` tab; superseded by client-side GA4.

---

## 9. Hosting & domain

- **Firebase Hosting** ([`firebase.json`](firebase.json)) serves the repo root as
  static content. The `ignore` list keeps sources out of the deploy (`*.gs`, `*.yaml`,
  `*.py`, `*.md`, source images, `wireframes.html`, `appsscript.json`).
- **Custom domain:** `lmt.bcourchesne.com` → CNAME `lmt` →
  `lac-manitou-temperatures-d284a.web.app.` (DNS at ZoneEdit). SSL auto-provisioned.
- **`.firebaserc`** pins the default project to `lac-manitou-temperatures-d284a`.

---

## 10. Tech stack summary

| Layer            | Technology |
|------------------|------------|
| Water/air probes | Olimex **ESP32-POE-ISO** + **ESPHome**, 3× DS18B20 (1-Wire), wired PoE |
| Weather station  | **Ecowitt WS69** + **GW3000** Wi-Fi gateway |
| Ambient sensor   | Veranda temp/humidity (via Home Assistant) |
| Hub / ETL        | **Home Assistant** (REST commands + automations + scripts, Jinja) |
| Auth             | **Firebase Authentication** (email/password writer account) |
| Database         | **Firebase Realtime Database** (`/readings`, `/daily`) |
| Hosting          | **Firebase Hosting** (static, custom domain) |
| Frontend         | Vanilla **HTML/CSS/JS**, **Chart.js**, SunCalc, Tabler Icons, Inter |
| Analytics        | **Google Analytics 4** (gtag) |
| Legacy backend   | **Google Apps Script** + **Google Sheets** (redirect only — dual-write retired) |
| Deploy tooling   | Firebase CLI (hosting/db) · **clasp** (GAS) |

---

## 11. Operational notes & gotchas

- **Pressure is sea-level (relative), not absolute.** The station sits at ~390 m, so
  its *absolute* pressure is ~47 hPa below sea-level pressure. The gateway's
  **"Altitude for REL"** must be set to the site elevation (~**1280 ft**) so
  `relative_pressure` reports true MSLP (~1011 hPa) comparable to weather services.
  When that setting was 0, "relative" pressure equalled absolute (~964 hPa) — a
  ~47 hPa low reading. Historical `/readings` and `/daily` recorded before the fix
  were corrected by adding the gateway's observed offset (+45 hPa) via
  [`fix_pressure_offset.py`](fix_pressure_offset.py) (value-thresholded → idempotent,
  won't double-apply).
- **Secrets** (Firebase writer password, Firebase Web API key, ESPHome API/OTA keys,
  GAS `POST_TOKEN`, `GA4_API_SECRET`) live in gitignored HA YAML, ESPHome config, and
  GAS Script Properties — not in the deployed app, and not committed here. The web API
  key is restricted to Identity Toolkit API only (rotated 2026-07-11); corrupting or
  losing it breaks both the 5-min write and aggregation, since HA re-authenticates with
  it every cycle.
- **Firebase Hosting caching:** verify frontend changes in an incognito window; a hard
  refresh alone can serve a stale build.
- **Maintenance scripts** (Python, gitignored secrets via `backfill_veranda.py`):
  `backfill_ecowitt.py`, `backfill_veranda.py`, `catchup.py`, `clear_phantom_rain.py`,
  `fix_pressure_offset.py` — one-off backfills/corrections that reuse the HA writer
  credentials to PATCH Firebase.

---

## 12. Repository layout

```
ESPHome/
├─ sondes.yaml              ESPHome config for the ESP32-POE water/air probes
└─ manitou/
   ├─ index.html            the web app (deployed)
   ├─ Code.gs               legacy GAS backend (dormant doPost + redirect)
   ├─ home_assistant.yaml   HA rest_commands / automations / aggregation (reference)
   ├─ database.rules.json   Firebase RTDB security rules
   ├─ firebase.json         Firebase Hosting + DB config
   ├─ .firebaserc           Firebase project alias
   ├─ appsscript.json       GAS manifest
   ├─ ECOWITT_HANDOFF.md    Ecowitt/weather-station integration notes
   ├─ ARCHITECTURE.md       (this document)
   ├─ PLAN.md               project planning notes — source of truth for backlog/status
   ├─ TIME_TRAVEL_SPEC.md   detailed spec for the chart's time-travel navigation feature
   └─ *.py                  backfill / correction maintenance scripts
```
