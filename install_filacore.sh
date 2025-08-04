#!/bin/bash

echo "🔽 Lade FilaCore herunter..."
curl -LO https://github.com/canny86/FilaCore/releases/download/0.1/filacore_release.zip

echo "📦 Entpacke Paket..."
unzip -o filacore_release.zip
cd filacore_release || exit 1

echo "🚀 Starte FilaCore..."
chmod +x start.sh
./start.sh
