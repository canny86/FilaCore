## Filacore

<p align="center">
  <img src="https://github.com/user-attachments/assets/cd038398-d1cd-4f2b-b4a8-8715221414ee" width="45%">
  <img src="https://github.com/user-attachments/assets/4f345f13-8b0d-432c-b327-ce0e59f8b525" width="45%">
</p>
<p align="center">
  <img src="https://github.com/user-attachments/assets/85e1da31-b601-4eb0-9912-39a583ad051a" width="45%">
  <img src="https://github.com/user-attachments/assets/edf124ec-b959-48a4-94c9-24b716e1e193" width="45%">
</p>

Leichtgewichtiges, lokales Filament- und Drucker-Management für Bambu A1 (u.a.).  
Bedienoberfläche im Browser, keine Cloud, fokus auf „schnell & klar“.

## Features
- Filamentlager mit Visitenkarten-UI (Hersteller, Profil, Core-ID, Temp min/max, TD, Preis)
- Druckerstatus inkl. AMS (lokal)
- Filament laden per MQTT-Bridge
- Offline-first, läuft in LXC/Docker oder direkt auf Linux

## Installation (Release)
1. **Release-ZIP laden:** `Releases → 0.2 → filacore_release.zip`
2. Entpacken, in Ordner wechseln
3. `./start.sh` ausführen (legt venv an, installiert requirements, startet `app.py`)
4. (optional) systemd Unit nutzen

## Konfiguration
- `static/printers/<NAME>/` (Zertifikat `blcert.pem`, Drucker-IPs, Access Codes)
- `printers.json` (mehrere Drucker, `active: true/false`)
- `static/filament_print_details.json` (Profil/Temperaturen/Dichte)
- `static/filacore_spools.json` (Filamente)

## Roadmap
- Dockerfile & Compose
- Export/Import für Spools