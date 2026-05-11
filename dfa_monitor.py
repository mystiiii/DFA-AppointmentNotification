#!/usr/bin/env python3
"""
DFA Passport Appointment Slot Monitor
======================================
Monitors https://passport.gov.ph/appointment for available slots
in specified Metro Manila and CALABARZON sites between May 11-22, 2026.

Sends Discord webhook notifications when slots are found.

Uses undetected-chromedriver to bypass Cloudflare anti-bot protection.
"""

import os
import sys
import ssl
import time
import logging
import traceback
from datetime import datetime, date, timezone

# ── macOS SSL certificate fix ──
# Python on macOS often can't find root CAs; point it to certifi's bundle.
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
try:
    ssl._create_default_https_context = ssl.create_default_context
    ssl.create_default_context = lambda *a, **kw: ssl.create_default_context(
        *a, cafile=certifi.where(), **kw
    )
except Exception:
    pass

import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    WebDriverException,
)
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────
load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "120"))
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"

APPOINTMENT_URL = "https://passport.gov.ph/appointment"

# Target date range (inclusive)
_start_env = os.getenv("TARGET_START_DATE", "2026-05-11")
_end_env = os.getenv("TARGET_END_DATE", "2026-05-21")
try:
    TARGET_START = datetime.strptime(_start_env, "%Y-%m-%d").date()
    TARGET_END = datetime.strptime(_end_env, "%Y-%m-%d").date()
except ValueError:
    print("Invalid date format in .env. Please use YYYY-MM-DD for TARGET_START_DATE and TARGET_END_DATE.")
    sys.exit(1)

# ─── Site definitions ────────────────────────────────────────────────
_sites_env = os.getenv("TARGET_SITES")

if _sites_env:
    REGIONS_AND_SITES = {
        "CONFIGURED SITES": [s.strip() for s in _sites_env.split(",") if s.strip()]
    }
else:
    # Mapping: region dropdown value -> list of site names (exact text from dropdown)
    REGIONS_AND_SITES = {
        "ASIA PACIFIC": [
            "DFA MANILA (ASEANA)",
            "DFA NCR CENTRAL - (ROBINSONS GALLERIA ORTIGAS, QUEZON CITY)",
            "DFA NCR EAST (SM MEGAMALL, MANDALUYONG CITY)",
            "DFA NCR NORTH (ROBINSONS NOVALICHES, QUEZON CITY)",
            "DFA NCR NORTHEAST (ALI MALL CUBAO, QUEZON CITY)",
            "DFA NCR SOUTH (FESTIVAL MALL, MUNTINLUPA CITY)",
            "DFA NCR WEST (SM CITY, MANILA)",
            "SAN PABLO (SM CITY SAN PABLO)",
            "LUCENA (PACIFIC MALL, LUCENA)",
        ]
    }

# ─────────────────────────────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("dfa_monitor.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("dfa_monitor")


# ─────────────────────────────────────────────────────────────────────
# Discord Notification
# ─────────────────────────────────────────────────────────────────────
def send_discord_alert(site_name: str, available_dates: list[str]):
    """Send a rich embed to a Discord webhook when slots are found."""
    if not DISCORD_WEBHOOK_URL:
        log.warning("DISCORD_WEBHOOK_URL not set – skipping notification.")
        return

    dates_str = "\n".join(f"📅  **{d}**" for d in available_dates)

    embed = {
        "title": "🚨 DFA Passport Slot Found!",
        "description": (
            f"**Site:** {site_name}\n\n"
            f"**Available Date(s):**\n{dates_str}\n\n"
            f"[🔗 Book Now]({APPOINTMENT_URL})"
        ),
        "color": 0x00FF88,  # green
        "footer": {"text": "DFA Slot Monitor"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    payload = {
        "username": "DFA Slot Monitor",
        "embeds": [embed],
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            log.info(f"Discord alert sent for {site_name}.")
        else:
            log.error(f"Discord webhook returned {resp.status_code}: {resp.text}")
    except requests.RequestException as exc:
        log.error(f"Failed to send Discord alert: {exc}")


def send_discord_status(status: str):
    """Send a status embed (started / stopped) to Discord."""
    if not DISCORD_WEBHOOK_URL or "YOUR_WEBHOOK" in DISCORD_WEBHOOK_URL:
        return

    total_sites = sum(len(s) for s in REGIONS_AND_SITES.values())

    if status == "started":
        embed = {
            "title": "🟢 DFA Slot Monitor — Started",
            "description": (
                f"**Target Dates:** {TARGET_START} → {TARGET_END}\n"
                f"**Sites:** {total_sites} across {len(REGIONS_AND_SITES)} regions\n"
                f"**Interval:** every {CHECK_INTERVAL}s\n"
                f"**Headless:** {HEADLESS}"
            ),
            "color": 0x57F287,  # green
            "footer": {"text": "DFA Slot Monitor"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    else:
        embed = {
            "title": "🔴 DFA Slot Monitor — Stopped",
            "description": "The monitor has been shut down.",
            "color": 0xED4245,  # red
            "footer": {"text": "DFA Slot Monitor"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    payload = {"username": "DFA Slot Monitor", "embeds": [embed]}

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            log.info(f"Discord status '{status}' sent.")
        else:
            log.error(f"Discord webhook returned {resp.status_code}: {resp.text}")
    except requests.RequestException as exc:
        log.error(f"Failed to send Discord status: {exc}")


def send_discord_no_slots(cycle: int):
    """Send a status embed to Discord when no slots were found in a cycle."""
    if not DISCORD_WEBHOOK_URL or "YOUR_WEBHOOK" in DISCORD_WEBHOOK_URL:
        return

    embed = {
        "title": "🔍 Scan Complete: No Slots",
        "description": f"Cycle #{cycle} finished. Checked all sites, but no available time slots were found.",
        "color": 0x99AAB5,  # Grey
        "footer": {"text": "DFA Slot Monitor"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    payload = {"username": "DFA Slot Monitor", "embeds": [embed]}

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            log.info(f"Discord 'no slots' summary sent for cycle #{cycle}.")
    except Exception as exc:
        log.debug(f"Failed to send Discord no-slots message: {exc}")


# ─────────────────────────────────────────────────────────────────────
# Browser Helpers
# ─────────────────────────────────────────────────────────────────────
def create_driver() -> uc.Chrome:
    """Create a new undetected-chromedriver instance."""
    options = uc.ChromeOptions()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")

    driver = uc.Chrome(options=options, version_main=147)
    driver.implicitly_wait(5)
    return driver


def wait_and_click(driver, by, value, timeout=20, description="element"):
    """Wait for an element to be clickable, then click it."""
    log.debug(f"Waiting for {description}...")
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, value))
    )
    try:
        el.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", el)
    return el


def wait_for_element(driver, by, value, timeout=20, description="element"):
    """Wait for an element to be present in the DOM."""
    log.debug(f"Waiting for {description}...")
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, value))
    )


def wait_for_visible(driver, by, value, timeout=20, description="element"):
    """Wait for an element to be visible."""
    log.debug(f"Waiting for {description} to be visible...")
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((by, value))
    )


# ─────────────────────────────────────────────────────────────────────
# Core Flow
# ─────────────────────────────────────────────────────────────────────
def navigate_to_appointment_page(driver):
    """Navigate to the site and accept Terms & Conditions."""
    log.info(f"Navigating to {APPOINTMENT_URL}")
    driver.get(APPOINTMENT_URL)

    # Wait for Cloudflare challenge to resolve (if any)
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    # Extra wait for Cloudflare JS challenge
    time.sleep(5)

    # ── Accept Terms & Conditions checkbox ──
    try:
        checkbox = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='checkbox']"))
        )
        if not checkbox.is_selected():
            try:
                checkbox.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", checkbox)
            log.info("Terms & Conditions checkbox checked.")
        else:
            log.info("Terms & Conditions already checked.")
    except TimeoutException:
        log.warning("Checkbox not found – may already be past T&C page.")

    # ── Click "START INDIVIDUAL APPOINTMENT" ──
    # The actual page uses <button value="Individual"> with mixed-case text
    # and CSS text-transform: uppercase, so XPath text() won't match ALL CAPS.
    individual_selectors = [
        (By.CSS_SELECTOR, "button[value='Individual']"),
        (By.CSS_SELECTOR, "button[value='individual']"),
        (By.XPATH, "//button[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'INDIVIDUAL')]"),
        (By.XPATH, "//a[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'INDIVIDUAL')]"),
        (By.XPATH, "//*[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'START INDIVIDUAL')]"),
    ]

    clicked = False
    for by, selector in individual_selectors:
        try:
            btn = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((by, selector))
            )
            try:
                btn.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", btn)
            log.info(f"Clicked 'Start Individual Appointment' via {selector}")
            clicked = True
            break
        except TimeoutException:
            continue

    if not clicked:
        log.error("Could not find Individual Appointment button.")
        # Log available buttons for debugging
        buttons = driver.find_elements(By.TAG_NAME, "button")
        links = driver.find_elements(By.TAG_NAME, "a")
        log.error(f"Buttons on page: {[b.text.strip() for b in buttons[:10]]}")
        log.error(f"Links on page: {[a.text.strip() for a in links[:10]]}")
        raise TimeoutException("Individual Appointment button not found")

    # Let the next page load
    time.sleep(3)


def select_region(driver, region_text: str) -> bool:
    """
    Select a region from the location/region dropdown.
    Returns True if selection succeeded.
    """
    try:
        # Wait for a <select> element that contains region options
        region_select_el = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "select#region, select[name='region'], select.region-select, select")
            )
        )
        select = Select(region_select_el)

        # Try exact match first, then partial match
        matched = False
        for option in select.options:
            option_text = option.text.strip()
            if region_text.upper() in option_text.upper() or option_text.upper() in region_text.upper():
                select.select_by_visible_text(option_text)
                log.info(f"Selected region: {option_text}")
                matched = True
                break

        if not matched:
            # Try by value attribute
            for option in select.options:
                val = option.get_attribute("value") or ""
                if region_text.upper() in val.upper():
                    select.select_by_value(val)
                    log.info(f"Selected region by value: {val}")
                    matched = True
                    break

        if not matched:
            log.warning(f"Region '{region_text}' not found in dropdown. Available: "
                        f"{[o.text.strip() for o in select.options]}")
            return False

        time.sleep(2)  # Allow site dropdown to populate
        return True

    except TimeoutException:
        log.warning(f"Region dropdown not found when selecting '{region_text}'.")
        return False
    except Exception as exc:
        log.error(f"Error selecting region '{region_text}': {exc}")
        return False


def select_site(driver, site_name: str) -> bool:
    """
    Select a specific site from the site/location dropdown.
    Returns True if selection succeeded.
    """
    try:
        # Look for site/location <select>
        selects = driver.find_elements(By.TAG_NAME, "select")

        site_select_el = None
        for sel in selects:
            sel_options = sel.find_elements(By.TAG_NAME, "option")
            for opt in sel_options:
                opt_text = opt.text.strip().upper()
                if "DFA" in opt_text or "MANILA" in opt_text or "ASEANA" in opt_text:
                    site_select_el = sel
                    break
            if site_select_el:
                break

        if not site_select_el:
            # Fallback: try the second <select> on page (first is region)
            if len(selects) >= 2:
                site_select_el = selects[1]
            else:
                log.warning(f"Site dropdown not found for '{site_name}'.")
                return False

        select = Select(site_select_el)

        # Match site name
        for option in select.options:
            option_text = option.text.strip()
            normalized_site = "".join(site_name.upper().split())
            normalized_opt = "".join(option_text.upper().split())
            if normalized_site in normalized_opt:
                val = option.get_attribute("value")
                if val:
                    select.select_by_value(val)
                else:
                    driver.execute_script("arguments[0].selected = true; arguments[0].dispatchEvent(new Event('change', {bubbles: true}));", option)
                log.info(f"Selected site: {option_text}")
                time.sleep(2)  # Allow page to update
                return True

        log.warning(f"Site '{site_name}' not found. Available: "
                    f"{[o.text.strip() for o in select.options]}")
        return False

    except Exception as exc:
        log.error(f"Error selecting site '{site_name}': {exc}")
        return False


def check_calendar_for_slots(driver, site_name: str) -> list[str]:
    """
    Inspect the calendar widget for available (non-disabled, non-full) dates
    within the target range (May 11-22, 2026).

    Returns a list of date strings that appear available.
    """
    available_dates = []

    try:
        # Wait for calendar to render
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".calendar, .datepicker, table.calendar, .ui-datepicker, "
                                   "#calendar, .fc-view, .flatpickr-calendar, .appointment-calendar")
            )
        )
    except TimeoutException:
        log.warning(f"Calendar did not load for {site_name}.")
        return available_dates

    month_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    current_date = TARGET_START.replace(day=1)
    target_months = []
    while current_date <= TARGET_END.replace(day=1):
        target_months.append((current_date.month, current_date.year))
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)

    for (t_month, t_year) in target_months:
        t_month_name = month_names[t_month - 1]
        
        # Navigate to target month
        _navigate_calendar(driver, t_month_name, str(t_year))

        # ── Scan day cells ──
        try:
            day_selectors = [
                "td.day", "td[data-date]", ".datepicker td", ".ui-datepicker td a",
                ".flatpickr-day", "td.fc-day", ".calendar td:not(.empty)",
                "td a.ui-state-default", "table td[class]"
            ]

            day_cells = []
            for selector in day_selectors:
                day_cells = driver.find_elements(By.CSS_SELECTOR, selector)
                if day_cells:
                    log.debug(f"Found {len(day_cells)} calendar cells with selector: {selector}")
                    break

            if not day_cells:
                all_tds = driver.find_elements(By.CSS_SELECTOR, "table td")
                day_cells = [td for td in all_tds if td.text.strip().isdigit()]

            for cell in day_cells:
                try:
                    cell_text = cell.text.strip()
                    if not cell_text or not cell_text.isdigit():
                        continue

                    day_num = int(cell_text)
                    try:
                        cell_date = date(t_year, t_month, day_num)
                    except ValueError:
                        continue
                        
                    if cell_date < TARGET_START or cell_date > TARGET_END:
                        continue

                    # Check if this cell is disabled/full
                    cell_classes = (cell.get_attribute("class") or "").lower()
                    cell_title = (cell.get_attribute("title") or "").lower()
                    cell_aria = (cell.get_attribute("aria-disabled") or "").lower()
                    cell_data = (cell.get_attribute("data-status") or "").lower()

                    parent = cell.find_element(By.XPATH, "..") if cell.tag_name in ("a", "span") else cell
                    parent_classes = (parent.get_attribute("class") or "").lower()

                    disabled_indicators = [
                        "disabled", "unavailable", "full", "inactive",
                        "off", "old", "new", "blocked", "closed",
                        "past", "booked", "no-slot", "noslot", "not-available",
                    ]

                    is_disabled = any(
                        indicator in combined
                        for combined in [cell_classes, parent_classes, cell_title, cell_aria, cell_data]
                        for indicator in disabled_indicators
                    )

                    if not is_disabled:
                        try:
                            driver.execute_script("arguments[0].click();", cell)
                            time.sleep(2)  # Wait for time slots to load
                            
                            available_times = []
                            radios = driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                            
                            for radio in radios:
                                if not radio.get_attribute("disabled"):
                                    try:
                                        label = radio.find_element(By.XPATH, "../..")
                                        t_text = label.text.replace('\n', ' ').replace("Available", "").strip()
                                        if t_text:
                                            available_times.append(t_text)
                                        else:
                                            available_times.append("Slot")
                                    except:
                                        available_times.append("Slot")
                                        
                            if not radios:
                                time_els = driver.find_elements(By.XPATH, "//*[contains(text(), ':00') or contains(text(), ':30')]")
                                for el in time_els:
                                    txt = el.text.upper()
                                    if "FULLY BOOKED" not in txt and len(txt) < 30:
                                        available_times.append(el.text.strip())
                                        
                            available_times = list(dict.fromkeys(available_times))
                            
                            if available_times:
                                date_str = f"{month_names[t_month-1].capitalize()} {day_num}, {t_year} ({', '.join(available_times)})"
                                available_dates.append(date_str)
                                log.info(f"🎯 SLOT FOUND → {site_name} on {date_str}")
                            else:
                                log.info(f"Date {month_names[t_month-1].capitalize()} {day_num} selectable, but all timeslots are fully booked.")
                                
                        except Exception as e:
                            log.debug(f"Error checking timeslots for {month_names[t_month-1].capitalize()} {day_num}: {e}")

                except StaleElementReferenceException:
                    continue
                except Exception as exc:
                    log.debug(f"Error reading cell: {exc}")
                    continue

        except Exception as exc:
            log.error(f"Error scanning calendar for {site_name} in {t_month_name} {t_year}: {exc}")

    return available_dates


def _navigate_calendar(driver, target_month_name: str, target_year_str: str):
    """
    If the calendar is not already showing the target month/year, click 'next' until it does.
    """
    max_clicks = 12  # Safety limit
    for _ in range(max_clicks):
        try:
            # Check current month/year displayed
            header_selectors = [
                ".datepicker-switch",           # bootstrap-datepicker
                ".ui-datepicker-title",         # jQuery UI
                ".flatpickr-current-month",     # flatpickr
                ".calendar-header",             # custom
                ".fc-toolbar-title",            # FullCalendar
                "th.month",                     # generic
                ".month-year",                  # custom
            ]

            header_text = ""
            for selector in header_selectors:
                try:
                    header = driver.find_element(By.CSS_SELECTOR, selector)
                    header_text = header.text.strip().upper()
                    if header_text:
                        break
                except NoSuchElementException:
                    continue

            if not header_text:
                # Try any <th> with colspan
                try:
                    headers = driver.find_elements(By.CSS_SELECTOR, "th[colspan]")
                    for h in headers:
                        text = h.text.strip().upper()
                        if any(m in text for m in ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                                                     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]):
                            header_text = text
                            break
                except Exception:
                    pass

            if target_month_name in header_text and target_year_str in header_text:
                log.debug(f"Calendar is on {target_month_name} {target_year_str}.")
                return

            # Click next month button
            next_selectors = [
                ".next",                        # bootstrap-datepicker
                ".ui-datepicker-next",          # jQuery UI
                ".flatpickr-next-month",        # flatpickr
                "button.next",                  # generic
                ".fc-next-button",              # FullCalendar
                "th.next",                      # generic
                "[aria-label='Next']",          # accessibility
                ".calendar-next",               # custom
            ]

            clicked = False
            for selector in next_selectors:
                try:
                    next_btn = driver.find_element(By.CSS_SELECTOR, selector)
                    next_btn.click()
                    clicked = True
                    time.sleep(1)
                    break
                except (NoSuchElementException, ElementClickInterceptedException):
                    continue

            if not clicked:
                # Try arrow icon / chevron
                try:
                    arrows = driver.find_elements(By.CSS_SELECTOR, "[class*='right'], [class*='forward'], [class*='next']")
                    for arrow in arrows:
                        if arrow.is_displayed():
                            arrow.click()
                            time.sleep(1)
                            break
                except Exception:
                    pass

                log.debug("Could not find next-month button.")
                return

        except Exception as exc:
            log.debug(f"Calendar navigation error: {exc}")
            return


def run_check_cycle(driver):
    """
    Run one full check cycle: navigate to appointment page,
    iterate through all regions/sites, check calendars.
    """
    total_found = 0

    for region, sites in REGIONS_AND_SITES.items():
        log.info(f"─── Checking region: {region} ───")

        for site_name in sites:
            try:
                # 1. Navigate from scratch for each site to ensure clean state
                navigate_to_appointment_page(driver)
                
                # Skip region selection entirely, go straight to site
                
                # 5. find locations
                if not select_site(driver, site_name):
                    log.warning(f"Skipping site {site_name} – could not select.")
                    continue
                
                # 6. click I confirm checkbox
                try:
                    checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
                    clicked_cb = False
                    for cb in checkboxes:
                        if not cb.is_selected():
                            driver.execute_script("arguments[0].click();", cb)
                            clicked_cb = True
                    if clicked_cb:
                        log.info("Site confirm checkbox checked.")
                except Exception as e:
                    log.warning(f"Could not click site confirm checkbox: {e}")
                
                time.sleep(1)

                # 7. click next
                try:
                    next_selectors = [
                        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')]",
                        "//input[translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='next']",
                        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')]"
                    ]
                    next_clicked = False
                    for sel in next_selectors:
                        elements = driver.find_elements(By.XPATH, sel)
                        if elements:
                            # Use the last one or the first visible one
                            for el in elements:
                                if el.is_displayed():
                                    driver.execute_script("arguments[0].click();", el)
                                    next_clicked = True
                                    break
                        if next_clicked:
                            break
                    if next_clicked:
                        log.info("Clicked NEXT button.")
                    else:
                        log.warning("Could not find NEXT button.")
                except Exception as e:
                    log.warning(f"Error clicking NEXT: {e}")

                # Wait for calendar page to load
                time.sleep(3)

                # 8. check dates
                available = check_calendar_for_slots(driver, site_name)

                if available:
                    total_found += len(available)
                    send_discord_alert(site_name, available)
                else:
                    log.info(f"No slots for {site_name} in target range.")

            except Exception as exc:
                log.error(f"Error checking {site_name}: {exc}")
                log.debug(traceback.format_exc())
                # Abort the cycle if the browser window was closed
                if "no such window" in str(exc).lower() or "chrome not reachable" in str(exc).lower():
                    log.error("Browser window was closed or is unreachable. Aborting current cycle.")
                    raise
                continue

    return total_found


# ─────────────────────────────────────────────────────────────────────
# Main Loop
# ─────────────────────────────────────────────────────────────────────
def main():
    if not DISCORD_WEBHOOK_URL or "YOUR_WEBHOOK" in DISCORD_WEBHOOK_URL:
        log.warning(
            "⚠️  DISCORD_WEBHOOK_URL is not configured. "
            "Set it in .env to receive notifications."
        )

    log.info("=" * 60)
    log.info("DFA Passport Appointment Slot Monitor")
    log.info(f"Target dates  : {TARGET_START} → {TARGET_END}")
    log.info(f"Check interval: {CHECK_INTERVAL}s")
    log.info(f"Headless mode : {HEADLESS}")
    log.info(f"Regions       : {list(REGIONS_AND_SITES.keys())}")
    total_sites = sum(len(s) for s in REGIONS_AND_SITES.values())
    log.info(f"Sites         : {total_sites}")
    log.info("=" * 60)

    send_discord_status("started")

    cycle = 0
    while True:
        cycle += 1
        driver = None
        try:
            log.info(f"\n{'━' * 50}")
            log.info(f"Cycle #{cycle} starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            log.info(f"{'━' * 50}")

            driver = create_driver()
            found = run_check_cycle(driver)

            if found:
                log.info(f"✅ Cycle #{cycle} complete — {found} slot(s) found and notified!")
            else:
                log.info(f"Cycle #{cycle} complete — no slots found.")
                send_discord_no_slots(cycle)

        except WebDriverException as exc:
            log.error(f"WebDriver error in cycle #{cycle}: {exc}")
            log.debug(traceback.format_exc())
        except KeyboardInterrupt:
            log.info("Interrupted by user. Shutting down.")
            send_discord_status("stopped")
            break
        except Exception as exc:
            log.error(f"Unexpected error in cycle #{cycle}: {exc}")
            log.debug(traceback.format_exc())
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

        log.info(f"Sleeping {CHECK_INTERVAL}s before next cycle...")
        try:
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            log.info("Interrupted during sleep. Shutting down.")
            send_discord_status("stopped")
            break


if __name__ == "__main__":
    main()
