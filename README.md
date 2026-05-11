# DFA Passport Appointment Slot Monitor 🇵🇭

Automated monitor for [passport.gov.ph](https://passport.gov.ph/appointment) that checks for available appointment slots and sends **Discord notifications** when openings are found.

## Features

- **Cloudflare Bypass** — Uses `undetected-chromedriver` to avoid anti-bot blocks
- **Multi-Site Monitoring** — Checks 9 DFA sites across NCR and CALABARZON
- **Smart Calendar Parsing** — Detects non-disabled/non-full dates in the target range
- **Discord Alerts** — Rich embed notifications with site name, dates, and booking link
- **Auto-Retry** — Recovers from errors and continues monitoring in a loop

## Target Sites

Here is the complete list of available sites you can use for your `TARGET_SITES` configuration in `.env`. Please make sure to copy the exact text (or at least exactly without worrying about extra spaces).

### Metro Manila (NCR)
| Site |
|------|
| DFA MANILA (ASEANA) |
| DFA NCR CENTRAL - (ROBINSONS GALLERIA ORTIGAS, QUEZON CITY) |
| DFA NCR EAST (SM MEGAMALL, MANDALUYONG CITY) |
| DFA NCR NORTH (ROBINSONS NOVALICHES, QUEZON CITY) |
| DFA NCR NORTHEAST (ALI MALL CUBAO, QUEZON CITY) |
| DFA NCR SOUTH (FESTIVAL MALL, MUNTINLUPA CITY) |
| DFA NCR WEST (SM CITY, MANILA) |

### Provincial Sites
| Site |
|------|
| ANGELES (SM CITY CLARK, ANGELES CITY) |
| ANTIPOLO (SM CENTER, ANTIPOLO CITY, RIZAL) |
| ANTIQUE (CITYMALL ANTIQUE) |
| BACOLOD (ROBINSONS BACOLOD) |
| BAGUIO (SM CITY BAGUIO) |
| BALANGA (THE BUNKER BUILDING, CAPITOL COMPOUND) |
| BUTUAN (ROBINSONS BUTUAN) |
| CAGAYAN DE ORO (BPO TOWER SM DOWNTOWN PREMIER) |
| CALASIAO (ROBINSONS CALASIAO, PANGASINAN) |
| CANDON (CANDON CITY ARENA) |
| CEBU (ROBINSONS GALLERIA , CEBU CITY ) |
| CLARIN (TOWN CENTER,,CLARIN, MISAMIS OCC) |
| DASMARIÑAS ( SM CITY DASMARIÑAS) |
| DAVAO (SM CITY DAVAO) |
| DUMAGUETE (ROBINSONS DUMAGUETE) |
| GENERAL SANTOS (ROBINSONS GEN. SANTOS CITY) |
| ILOCOS NORTE (ROBINSONS PLACE, SAN NICOLAS) |
| ILOILO (ROBINSONS ILOILO) |
| KIDAPAWAN ( KIDAPAWAN CITY ) |
| LA UNION (CSI MALL SAN FERNANDO, LA UNION) |
| LEGAZPI (PACIFIC MALL LEGAZPI) |
| LIPA (ROBINSONS LIPA) |
| LUCENA (PACIFIC MALL, LUCENA) |
| MALOLOS (CTTCH.,XENTRO MALL, MALOLOS CITY) |
| OLONGAPO (SM CITY OLONGAPO CENTRAL) |
| PAGADIAN (C3 MALL, PAGADIAN CITY) |
| PAMPANGA (ROBINSONS STARMILLS SAN FERNANDO) |
| PANIQUI, TARLAC (WALTERMART) |
| PUERTO PRINCESA (ROBINSONS PALAWAN) |
| SAN PABLO ( SM CITY SAN PABLO) |
| SANTIAGO, ISABELA (ROBINSONS PLACE SANTIAGO) |
| TACLOBAN (ROBINSONS N. ABUCAY, TAC. CITY) |
| TAGBILARAN (ALTURAS MALL, TAGBILARAN CITY) |
| TAGUM (ROBINSONS PLACE OF TAGUM) |
| TUGUEGARAO (REG. GOVT CENTER, TUGUEGARAO CITY) |
| ZAMBOANGA (GO-VELAYO BLDG. VET. AVE. ZAMBO) |

## Setup

### 1. Clone & Install

```bash
cd /Users/lei/PROJECTS/DFAWebhook
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

Edit `.env` (you can copy from `.env.example` if it exists, or create a new one) with your settings:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123456/abcdef
CHECK_INTERVAL=120
HEADLESS=false

# Target Date Range (Format: YYYY-MM-DD)
TARGET_START_DATE=2026-05-11
TARGET_END_DATE=2026-05-21

# Target Sites (Comma-separated list of site names)
# Leave empty to use the default hardcoded sites in the script.
TARGET_SITES="DFA MANILA (ASEANA), DFA NCR CENTRAL - (ROBINSONS GALLERIA ORTIGAS, QUEZON CITY)"
```

### 3. Run

```bash
python dfa_monitor.py
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_WEBHOOK_URL` | — | Your Discord webhook URL (required for alerts) |
| `CHECK_INTERVAL` | `120` | Seconds between check cycles |
| `HEADLESS` | `false` | Run Chrome without GUI (`true` for servers) |
| `TARGET_START_DATE`| `2026-05-11` | The start date for checking availability (YYYY-MM-DD) |
| `TARGET_END_DATE` | `2026-05-21` | The end date for checking availability (YYYY-MM-DD) |
| `TARGET_SITES` | Default sites | Comma-separated list of specific sites to monitor |

## How It Works

1. Opens Chrome with `undetected-chromedriver` to bypass Cloudflare
2. Navigates to the DFA appointment portal
3. Accepts Terms & Conditions and clicks "Start Individual Appointment"
4. For each region (NCR, CALABARZON):
   - Selects the region from the dropdown
   - For each target site, selects it and inspects the calendar
5. Scans calendar cells within your configured date range — any date not marked as disabled/full triggers an alert
6. Sends a rich Discord embed with site name, available dates, and a booking link
7. Sleeps and repeats
