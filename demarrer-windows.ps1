# UMURAGE — démarrage en un clic sous Windows
# Utilisation (dans PowerShell, depuis ce dossier) :
#   powershell -ExecutionPolicy Bypass -File .\demarrer-windows.ps1
# Le script installe ce qui manque, met à jour la base, construit l'interface,
# puis ouvre l'application sur http://localhost:8000 (un seul serveur).
$ErrorActionPreference = "Stop"
$racine = $PSScriptRoot

Write-Host "1/4  Python et bibliothèques..." -ForegroundColor Green
Set-Location "$racine\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
$py = "$racine\backend\.venv\Scripts\python.exe"
& $py -m pip install --quiet --disable-pip-version-check -r requirements.txt

Write-Host "2/4  Base de données..." -ForegroundColor Green
& $py manage.py migrate --noinput
& $py manage.py seed_demo   # ne fait rien si des données existent déjà
& $py manage.py seed_metier # démonstration des modules métier (installations de démonstration uniquement)

Write-Host "3/4  Interface..." -ForegroundColor Green
Set-Location "$racine\frontend"
if (-not (Test-Path "node_modules") -or ((Get-Item "package.json").LastWriteTime -gt (Get-Item "node_modules").LastWriteTime)) {
    npm install --no-audit --no-fund
}
npm run build

Write-Host "4/4  Démarrage : http://localhost:8000  (Ctrl+C pour arrêter)" -ForegroundColor Green
Set-Location "$racine\backend"
Start-Process "http://localhost:8000"
& $py manage.py runserver 8000
