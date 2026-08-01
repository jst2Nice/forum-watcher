#!/usr/bin/env python3
"""
Forum-Watcher fuer forum.gta5majestic.com

Prueft ein XenForo-Unterforum auf neue Themen und benachrichtigt bei
neuen Beitraegen per:
  - Discord Webhook (mit Ping/Mention)
  - ntfy.sh Push-Benachrichtigung

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

# ---------------------------------------------------------------------------
# Konfiguration ueber Umgebungsvariablen (siehe README.md)
# ---------------------------------------------------------------------------
FORUM_URL = os.environ.get(
    "FORUM_URL",
    "https://forum.gta5majestic.com/forums/beschwerden-uber-spieler.88/",
)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DISCORD_PING = os.environ.get("DISCORD_PING", "")  # z.B. "<@&ROLLEN_ID>" oder "@everyone"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")       # z.B. "valentin-gta-beschwerden-7x2k"
NTFY_URL = os.environ.get("NTFY_URL", "https://ntfy.sh")

FORUM_USERNAME = os.environ.get("FORUM_USERNAME", "")
FORUM_PASSWORD = os.environ.get("FORUM_PASSWORD", "")
FORUM_LOGIN_URL = os.environ.get("FORUM_LOGIN_URL", "https://forum.gta5majestic.com/login/")

STATE_FILE = Path(__file__).parent / "seen_threads.json"

HEADERS = {
    # Realistischer User-Agent, damit die Anfrage nicht sofort als Bot erkannt wird
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
}

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


def make_session() -> requests.Session:
    """Erstellt eine requests-Session und loggt sich (falls Zugangsdaten
    gesetzt sind) per Standard-XenForo-Loginformular ein."""
    session = requests.Session()
    session.headers.update(HEADERS)

    if not (FORUM_USERNAME and FORUM_PASSWORD):
        return session

    login_page = session.get(FORUM_LOGIN_URL, timeout=30)
    login_page.raise_for_status()
    soup = BeautifulSoup(login_page.text, "html.parser")

    form = soup.find("form", attrs={"action": True})
    # Das Formular mit dem Passwortfeld ist das eigentliche Login-Formular
    for candidate in soup.find_all("form"):
        if candidate.find("input", attrs={"name": "password"}):
            form = candidate
            break

    if form is None:
        print(
            "WARNUNG: Login-Formular wurde nicht gefunden. Eventuell hat das "
            "Forum ein anderes Login-Formular als Standard-XenForo. Melde dich, "
            "dann passen wir das an.",
            file=sys.stderr,
        )
        return session

    action = requests.compat.urljoin(FORUM_LOGIN_URL, form.get("action") or FORUM_LOGIN_URL)

    payload = {}
    for field in form.find_all(["input", "textarea"]):
        name = field.get("name")
        if not name:
            continue
        payload[name] = field.get("value", "")

    # Standard-Feldnamen von XenForo 2 fuer Benutzername/Passwort
    payload["login"] = FORUM_USERNAME
    payload["password"] = FORUM_PASSWORD
    payload.setdefault("remember", "1")

    resp = session.post(action, data=payload, timeout=30)
    resp.raise_for_status()

    # grobe Erfolgspruefung: nach erfolgreichem Login sollte auf der
    # eigentlichen Forumsseite kein Passwortfeld mehr auftauchen
    check = session.get(FORUM_URL, timeout=30)
    check_soup = BeautifulSoup(check.text, "html.parser")
    if check_soup.find("input", attrs={"name": "password"}):
        print(
            "WARNUNG: Login war vermutlich NICHT erfolgreich (Passwortfeld "
            "immer noch sichtbar). Bitte Benutzername/Passwort in den "
            "GitHub Secrets pruefen.",
            file=sys.stderr,
        )
    else:
        print("Login erfolgreich.")

    return session


def fetch_threads() -> list[dict]:
    """Ruft die Forumsseite ab und gibt eine Liste von Threads zurueck."""
    session = make_session()
    resp = session.get(FORUM_URL, timeout=30)
    resp.raise_for_status()
    html = resp.text

    # Debug-Hilfe: erkennen, ob wir nur eine Sperr-/Login-Seite bekommen haben
    if len(html) < 3000 and ("JavaScript" in html or "Cloudflare" in html or "Attention Required" in html):
        print(
            "WARNUNG: Die Antwort sieht nach einer Sperrseite aus (Cloudflare-"
            "Challenge oder fehlender Login). Siehe README.md, Abschnitt "
            "'Falls das Forum weiterhin blockiert'.",
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
