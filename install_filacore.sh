#!/bin/bash

set -e

# === KONFIGURATION ===
REPO="canny86/FilaCore"
VERSION="0.1"
ZIP_NAME="filacore_release.zip"
DIR_NAME="filacore_release"

echo "🔽 Lade FilaCore Release $VERSION von GitHub..."
curl -L -o "$ZIP_NAME" "https://github.com/$REPO/releases/download/$VERSION/$ZIP_NAME"

echo "📦 Entpacke Release..."
unzip -o "$ZIP_NAME"

cd "$DIR_NAME"

echo "🧪 Erstelle Python-Umgebung..."
python3 -m venv venv

echo "🚀 Aktiviere Umgebung..."
source venv/bin/activate

echo "📚 Installiere Requirements..."
pip install --break-system-packages --no-cache-dir -r requirements.txt

echo "➕ Installiere zusätzlich flask-cors..."
pip install --break-system-packages --no-cache-dir flask-cors

echo ""
echo "✅ FilaCore wurde erfolgreich installiert!"
echo "👉 Starte mit:"
echo "   cd $DIR_NAME"
echo "   source venv/bin/activate"
echo "   ./start.sh"
