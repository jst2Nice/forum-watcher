# Forum Watcher – Setup-Anleitung

(Full Vibecoded mit Claude, bitte nicht haten)

Prüft alle 5 Minuten automatisch (via GitHub Actions, kostenlos), ob im
Unterforum "Beschwerden über Spieler" ein neues Thema erstellt wurde, und
schickt dir dann:
- einen Discord-Ping über deinen Webhook
- eine Push-Benachrichtigung aufs Handy über ntfy.sh

Das Skript nutzt einen echten (unsichtbaren) Chromium-Browser via
Playwright, weil das Forum durch einen Anti-Bot-Schutz (React Labs)
abgesichert ist, der einfache Anfragen ohne JavaScript blockiert.
Zusätzlich loggt es sich mit einem Forum-Account ein, da das Unterforum
nur eingeloggten Nutzern angezeigt wird.

## 1. Repo anlegen

1. Erstelle ein **neues, öffentliches (public)** GitHub-Repository (z.B.
   `forum-watcher`). Public ist hier wichtig: GitHub Actions ist bei
   öffentlichen Repos unbegrenzt kostenlos nutzbar, bei privaten Repos gibt
   es nur ein begrenztes Minuten-Kontingent pro Monat – das würde bei einem
   Playwright-Browser im 5-Minuten-Takt nicht reichen. Deine Zugangsdaten
   (Schritt 5) bleiben trotzdem als verschlüsseltes Secret unsichtbar, nur
   der Code selbst ist dann öffentlich einsehbar (unproblematisch, da nichts
   Sensibles im Code steht).
2. Lade die Dateien aus diesem Ordner dort hoch (`forum_watcher.py`,
   `requirements.txt`, `.github/workflows/check.yml`).
   Am einfachsten per Drag & Drop im Browser (**Add file → Upload files**,
   kompletten Ordner reinziehen) oder mit:
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
verschlüsseltes Secret ins Repo (Schritt 5), sind also nicht öffentlich
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

Diese Secrets sind auch bei einem öffentlichen Repo nicht einsehbar – weder
für andere Nutzer noch in den Actions-Logs (GitHub blendet sie automatisch
aus).

## 6. Testen

Gehe im Repo auf **Actions → Forum Watcher → Run workflow**, um es einmal
manuell zu starten, statt 5 Minuten auf den nächsten Cron-Lauf zu warten.

- **Erster Lauf:** Es werden nur alle aktuell vorhandenen Threads gespeichert
  (Datei `seen_threads.json` wird im Repo angelegt und automatisch
  committet). Es kommt bewusst noch KEINE Benachrichtigung, sonst würdest du
  beim ersten Start für jedes bestehende Thema einen Ping bekommen.
- **Ab dem zweiten Lauf:** Nur wirklich neue Themen lösen Discord-Ping +
  Push aus.

Schau dir nach dem ersten Lauf das Log an (Actions → der Lauf → "Forum
prüfen"):

- Steht dort "Login war vermutlich NICHT erfolgreich" → Benutzername/Passwort
  in den Secrets prüfen (Tippfehler? E-Mail statt Benutzername nötig?).
- Steht dort weiterhin eine Warnung über eine Sperrseite → melde dich mit
  einem Screenshot, dann schauen wir gezielt weiter.
- Steht dort z.B. "Erster Lauf: 20 bestehende Threads werden gespeichert" →
  alles funktioniert. Prüf danach im Tab **Code** in der Commit-Historie,
  ob ein Commit "Zustand aktualisieren" erschienen ist – falls ja, wird der
  Zustand korrekt gespeichert und ab jetzt läuft alles automatisch im
  Hintergrund.

## Intervall ändern

In `.github/workflows/check.yml` steht `cron: "*/5 * * * *"` – alle 5
Minuten. Kleinstes sinnvolles Intervall bei GitHub Actions ist etwa 5
Minuten (kürzer wird von GitHub nicht garantiert zuverlässig ausgeführt).
