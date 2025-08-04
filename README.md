# FilaCore

Minimalversion zur lokalen Installation (z. B. auf Raspberry Pi, Server oder Docker-Host)

## Voraussetzungen

- Python 3.9 oder höher
- unzip
- optional: virtualenv (wird automatisch erstellt)

## Installation & Start

1. ZIP entpacken
2. Terminal öffnen und in den Ordner wechseln
3. Startskript ausführen:

    unzip filacore_release.zip  
    cd filacore_release  
    chmod +x start.sh  
    ./start.sh  

Dann im Browser öffnen:  
http://localhost:5000  
oder  
http://<deine-ip>:5000

## Struktur

- app.py – Hauptlogik
- static/ – enthält Filamentdaten, Druckprofile und UI
- requirements.txt – Python-Abhängigkeiten
- start.sh – Startscript
