#!/usr/bin/env python3
"""
Forum-Watcher fuer forum.gta5majestic.com

Prueft ein XenForo-Unterforum auf neue Themen und benachrichtigt bei
neuen Beitraegen per:
  - Discord Webhook (mit Ping/Mention)
  - ntfy.sh Push-Benachrichtigung

Nutzt einen echten (headless) Chromium-Browser via Playwright, weil das
Forum hinter einem Anti-Bot-Schutz (React Labs) liegt, der einfache
HTTP-Requests ohne JavaScript-Ausfuehrung blockiert. Zusaetzlich wird ein
Login durchgefuehrt, da das Unterforum nur eingeloggten Nutzern angezeigt
wird.

Der Skript-Zustand (welche Threads schon bekannt sind) wird in einer
JSON-Datei (STATE_FILE) gespeichert, damit bei jedem Lauf nur wirklich
NEUE Threads gemeldet werden.
"""

import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# Konfiguration ueber Umgebungsvariablen (siehe README.md)
# ---------------------------------------------------------------------------
FORUM_URL = os.environ.get(
    "FORUM_URL",
    "https://forum.gta5majestic.com/forums/beschwerden-uber-spieler.88/",
)
FORUM_LOGIN_URL = os.environ.get("FORUM_LOGIN_URL", "https://forum.gta5majestic.com/login/")
FORUM_USERNAME = os.environ.get("FORUM_USERNAME", "")
FORUM_PASSWORD = os.environ.get("FORUM_PASSWORD", "")

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DISCORD_PING = os.environ.get("DISCORD_PING", "")  # z.B. "<@&ROLLEN_ID>" oder "@everyone"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")       # z.B. "valentin-gta-beschwerden-7x2k"
NTFY_URL = os.environ.get("NTFY_URL", "https://ntfy.sh")

STATE_FILE = Path(__file__).parent / "seen_threads.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# XenForo-Thread-URLs sehen immer so aus: /threads/irgendein-titel.12345/
THREAD_LINK_RE = re.compile(r"/threads/[^/\"'#]+\.(\d+)/?$")


def load_seen_ids() -> set[str]:
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return set()
    return set()


def save_seen_ids(ids: set[str]) -> None:
    STATE_FILE.write_text(json.dumps(sorted(ids)), encoding="utf-8")


def login(page) -> None:
    """Loggt sich per Standard-XenForo-Loginformular ein."""
    page.goto(FORUM_LOGIN_URL, timeout=45000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    try:
        page.fill('input[name="login"]', FORUM_USERNAME, timeout=10000)
        page.fill('input[name="password"]', FORUM_PASSWORD, timeout=10000)
    except Exception:
        print(
            "WARNUNG: Login-Formularfelder wurden nicht gefunden. Eventuell "
            "hat das Forum ein anderes Login-Formular als Standard-XenForo. "
            "Melde dich, dann passen wir die Feld-Selektoren an.",
            file=sys.stderr,
        )
        return

    try:
        page.click('button[type="submit"]', timeout=10000)
    except Exception:
        page.press('input[name="password"]', "Enter")

    page.wait_for_timeout(4000)

    if page.locator('input[name="password"]').count() > 0:
        print(
            "WARNUNG: Login war vermutlich NICHT erfolgreich (Passwortfeld "
            "immer noch sichtbar). Bitte Benutzername/Passwort in den "
            "GitHub Secrets pruefen.",
            file=sys.stderr,
        )
    else:
        print("Login erfolgreich.")


def fetch_html_via_browser() -> str:
    """Loggt sich (falls Zugangsdaten gesetzt sind) ein und laedt dann die
    Forumsseite mit einem echten (headless) Chromium-Browser."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="de-DE",
            viewport={"width": 1366, "height": 900},
        )
        page = context.new_page()

        if FORUM_USERNAME and FORUM_PASSWORD:
            login(page)

        page.goto(FORUM_URL, timeout=45000, wait_until="domcontentloaded")
        # kurz warten, falls im Hintergrund noch eine JS-Pruefung laeuft
        page.wait_for_timeout(4000)
        html = page.content()
        browser.close()
        return html


def fetch_threads() -> list[dict]:
    """Ruft die Forumsseite ab und gibt eine Liste von Threads zurueck."""
    html = fetch_html_via_browser()

    if len(html) < 3000 and ("JavaScript" in html or "Attention Required" in html):
        print(
            "WARNUNG: Die Antwort sieht immer noch nach einer Sperrseite aus. "
            "Melde dich mit einem Screenshot vom Log, falls das oefter "
            "vorkommt.",
            file=sys.stderr,
        )

    soup = BeautifulSoup(html, "html.parser")

    threads = {}
    for a in soup.find_all("a", href=True):
        match = THREAD_LINK_RE.search(a["href"])
        if not match:
            continue
        thread_id = match.group(1)
        title = a.get_text(strip=True)
        # Es gibt pro Thread mehrere Links (Titel, "neuester Beitrag" etc.) -
        # wir behalten den mit dem laengsten (aussagekraeftigsten) Titeltext.
        if thread_id not in threads or len(title) > len(threads[thread_id]["title"]):
            threads[thread_id] = {
                "id": thread_id,
                "title": title,
                "url": requests.compat.urljoin(FORUM_URL, a["href"]),
            }

    return list(threads.values())


def notify_discord(thread: dict) -> None:
    if not DISCORD_WEBHOOK_URL:
        return
    content = f"{DISCORD_PING} Neuer Beitrag im Forum!".strip()
    payload = {
        "content": content,
        "embeds": [
            {
                "title": thread["title"] or "Neues Thema",
                "url": thread["url"],
                "description": "Ein neues Thema wurde im Unterforum erstellt.",
                "color": 0xE74C3C,
            }
        ],
    }
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
    if r.status_code >= 300:
        print(f"Discord-Webhook Fehler: {r.status_code} {r.text}", file=sys.stderr)


def notify_ntfy(thread: dict) -> None:
    if not NTFY_TOPIC:
        return
    url = f"{NTFY_URL.rstrip('/')}/{NTFY_TOPIC}"
    r = requests.post(
        url,
        data=(thread["title"] or "Neues Thema erstellt").encode("utf-8"),
        headers={
            "Title": "Neuer Forumsbeitrag".encode("utf-8"),
            "Priority": "high",
            "Tags": "warning",
            "Click": thread["url"],
        },
        timeout=15,
    )
    if r.status_code >= 300:
        print(f"ntfy Fehler: {r.status_code} {r.text}", file=sys.stderr)


def main() -> int:
    threads = fetch_threads()

    if not threads:
        print(
            "Keine Threads gefunden. Entweder ist das Forum leer (unwahrscheinlich) "
            "oder das Parsen/Abrufen funktioniert nicht wie erwartet.",
            file=sys.stderr,
        )
        return 1

    seen_ids = load_seen_ids()
    is_first_run = len(seen_ids) == 0

    new_threads = [t for t in threads if t["id"] not in seen_ids]

    if is_first_run:
        # Beim allerersten Lauf nur den Zustand speichern, NICHT für jeden
        # bestehenden Thread eine Benachrichtigung verschicken.
        print(f"Erster Lauf: {len(threads)} bestehende Threads werden gespeichert, keine Benachrichtigung.")
    else:
        for thread in new_threads:
            print(f"Neuer Thread erkannt: {thread['title']} ({thread['url']})")
            notify_discord(thread)
            notify_ntfy(thread)

    all_ids = seen_ids | {t["id"] for t in threads}
    save_seen_ids(all_ids)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
