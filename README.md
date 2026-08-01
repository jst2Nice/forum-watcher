# Forum Watcher – Setup-Anleitung

Prüft alle 5 Minuten automatisch (via GitHub Actions, kostenlos), ob im
Unterforum "Beschwerden über Spieler" ein neues Thema erstellt wurde, und
schickt dir dann:
- einen Discord-Ping über deinen Webhook
- eine Push-Benachrichtigung aufs Handy über ntfy.sh

## 1. Repo anlegen

1. Erstelle ein **neues, privates** GitHub-Repository (z.B. `forum-watcher`).
2. Lade die Dateien aus diesem Ordner dort hoch (`forum_watcher.py`,
   `requirements.txt`, `.github/workflows/check.yml`).
   Am einfachsten per Drag & Drop im Browser oder mit:
   ```
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/DEIN-USERNAME/forum-watcher.git
   git push -u origin main
   ```

## 2. ntfy.sh einrichten (Push aufs Handy)

1. Installiere die **ntfy** App (iOS App Store / Google Play).
2. Denk dir ein einzigartiges "Topic" aus – das ist quasi dein privater
   Kanalname. Nimm etwas Zufälliges, damit niemand sonst mitliest, z.B.
   `valentin-gta-beschwerden-a8x2k`.
3. In der App: "+" → dieses Topic abonnieren.
4. Fertig – keine Registrierung, kein Account nötig.

## 3. Forum-Account für den Bot

Das Forum verlangt einen Login, um die Beiträge zu sehen. Erstell dir dafür
am besten einen **zweiten, separaten Account** im Forum (nicht deinen
Haupt-Account) – nur für dieses Skript. Die Zugangsdaten kommen als
verschlüsselte Secrets ins Repo (Schritt 5), sind also nicht öffentlich
einsehbar, aber ein zweiter Account ist trotzdem die sauberere Lösung.

## 4. Discord-Webhook einrichten

Du hast schon einen – trag ihn unten bei den Secrets ein. Falls du zusätzlich
eine Rolle oder dich selbst pingen willst, brauchst du die Rollen-ID bzw.
User-ID (Rechtsklick auf Rolle/Nutzer → "ID kopieren", Entwicklermodus muss
in Discord aktiviert sein unter Einstellungen → Erweitert).
- Rolle pingen: `<@&123456789012345678>`
- Person pingen: `<@123456789012345678>`
- Alle pingen: `@everyone` (Vorsicht, weckt wirklich alle)

## 5. GitHub Secrets eintragen

Im Repo: **Settings → Secrets and variables → Actions → New repository secret**

| Name | Wert |
|---|---|
| `FORUM_USERNAME` | Benutzername/E-Mail des Bot-Accounts aus Schritt 3 |
| `FORUM_PASSWORD` | Passwort des Bot-Accounts aus Schritt 3 |
| `DISCORD_WEBHOOK_URL` | dein Discord-Webhook-Link |
| `DISCORD_PING` | z.B. `<@&ROLLEN_ID>` oder `@everyone` (optional, kann auch leer bleiben) |
| `NTFY_TOPIC` | das Topic aus Schritt 2, z.B. `valentin-gta-beschwerden-a8x2k` |

## 6. Testen

Gehe im Repo auf **Actions → Forum Watcher → Run workflow**, um es einmal
manuell zu starten, statt 5 Minuten auf den nächsten Cron-Lauf zu warten.

- **Erster Lauf:** Es werden nur alle aktuell vorhandenen Threads gespeichert
  (Datei `seen_threads.json` wird im Repo angelegt). Es kommt bewusst noch
  KEINE Benachrichtigung, sonst würdest du beim ersten Start für jedes
  bestehende Thema einen Ping bekommen.
- **Ab dem zweiten Lauf:** Nur wirklich neue Themen lösen Discord-Ping +
  Push aus.

Schau dir nach dem ersten Lauf das Log an (Actions → der Lauf → "Forum
prüfen"):

- Steht dort "Login war vermutlich NICHT erfolgreich" → Benutzername/Passwort
  in den Secrets prüfen (Tippfehler? E-Mail statt Benutzername nötig?).
- Steht dort weiterhin eine Warnung über eine Sperrseite → siehe Abschnitt
  "Falls das Forum weiterhin blockiert" unten.
- Steht dort z.B. "Erster Lauf: 20 bestehende Threads werden gespeichert" →
  alles funktioniert, ab jetzt läuft es automatisch im Hintergrund.

## Falls das Forum weiterhin blockiert

Das Skript ruft die Seite jetzt per einfachem eingeloggten HTTP-Request ab
(kein Browser mehr nötig, dafür deutlich schneller und schont dein
Actions-Minuten-Kontingent). Falls im Log trotzdem wieder die Warnung
"sieht nach einer Sperrseite aus" bzw. `Keine Threads gefunden` erscheint,
kann das zwei Gründe haben:

- Der Login hat nicht geklappt (siehe Warnung "Login war vermutlich NICHT
  erfolgreich" oben) → Zugangsdaten in den Secrets prüfen.
- Das Forum setzt doch eine aktive Cloudflare-Challenge (Captcha/Turnstile)
  ein, die ein einfacher Request nicht lösen kann. Melde dich dann mit
  einem Screenshot vom Actions-Log, dann bauen wir die Playwright-Variante
  (echter Headless-Browser) wieder ein – die kostet dann etwas mehr
  Actions-Minuten, ist aber weiterhin die zuverlässigere Rückfalllösung.

## Intervall ändern

In `.github/workflows/check.yml` steht `cron: "*/5 * * * *"` – alle 5
Minuten. Kleinstes sinnvolles Intervall bei GitHub Actions ist etwa 5
Minuten (kürzer wird von GitHub nicht garantiert zuverlässig ausgeführt).
