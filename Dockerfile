# UMURAGE — image de production : interface construite + API Django servies par Gunicorn
# Construction : docker build -t umurage .

# 1) Construction de l'interface
FROM node:20-alpine AS interface
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# 2) Application Python
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_DEBUG=0 FRONTEND_DIST=/app/frontend/dist
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-fra \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=interface /app/frontend/dist /app/frontend/dist
# Valeurs fictives, seulement pour préparer les fichiers statiques pendant la construction
RUN DJANGO_SECRET_KEY=construction-de-l-image-uniquement-pas-un-vrai-secret DJANGO_ALLOWED_HOSTS=construction \
    python manage.py collectstatic --noinput
RUN useradd --create-home umurage && mkdir -p media sauvegardes ia_modeles && chown -R umurage /app/backend
USER umurage
EXPOSE 8000
# Contrôle de santé : base joignable et migrations appliquées (voir /api/sante/)
HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 CMD python -c "import os,urllib.request as u; h=os.environ.get('DJANGO_ALLOWED_HOSTS','localhost').split(',')[0]; u.urlopen(u.Request('http://127.0.0.1:8000/api/sante/', headers={'Host': h}), timeout=8)" || exit 1
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3} --timeout 120"]
