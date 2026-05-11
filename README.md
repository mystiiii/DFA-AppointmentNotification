# DFA Passport Appointment Slot Monitor 🇵🇭

Automated monitor for [passport.gov.ph](https://passport.gov.ph/appointment) that checks for available appointment slots and sends **Discord notifications** when openings are found.

## Features

- **Cloudflare Bypass** — Uses `undetected-chromedriver` to avoid anti-bot blocks
- **Multi-Site Monitoring** — Checks 9 DFA sites across NCR and CALABARZON
- **Smart Calendar Parsing** — Detects non-disabled/non-full dates in the target range
- **Discord Alerts** — Rich embed notifications with site name, dates, and booking link
- **Auto-Retry** — Recovers from errors and continues monitoring in a loop

## Target Sites

### Metro Manila (NCR)
| # | Site |
|---|------|
| 1 | DFA MANILA (ASEANA) |
| 2 | DFA NCR CENTRAL – (ROBINSONS GALLERIA ORTIGAS, QUEZON CITY) |
| 3 | DFA NCR EAST (SM MEGAMALL, MANDALUYONG CITY) |
| 4 | DFA NCR NORTH (ROBINSONS NOVALICHES, QUEZON CITY) |
| 5 | DFA NCR NORTHEAST (ALI MALL CUBAO, QUEZON CITY) |
| 6 | DFA NCR SOUTH (FESTIVAL MALL, MUNTINLUPA CITY) |
| 7 | DFA NCR WEST (SM CITY, MANILA) |

### CALABARZON (Region IV-A)
| # | Site |
|---|------|
| 1 | DFA SAN PABLO |
| 2 | DFA LUCENA |

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
