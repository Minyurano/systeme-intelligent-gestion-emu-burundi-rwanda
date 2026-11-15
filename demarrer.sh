#!/usr/bin/env sh
# UMURAGE — démarrage en un clic (Linux, macOS). Utilisation : sh demarrer.sh
set -e
RACINE="$(cd "$(dirname "$0")" && pwd)"
cd "$RACINE/backend"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install --quiet -r requirements.txt
python manage.py migrate --noinput
python manage.py seed_demo
python manage.py seed_metier
cd "$RACINE/frontend"
[ -d node_modules ] || npm install --no-audit --no-fund
npm run build
cd "$RACINE/backend"
echo "UMURAGE : http://localhost:8000"
python manage.py runserver 8000
