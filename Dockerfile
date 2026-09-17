FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

RUN groupadd --system app && \
    useradd --system --gid app --home /app --shell /usr/sbin/nologin app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements /app/requirements
RUN pip install --no-cache-dir -r /app/requirements/prod.txt

COPY --chown=app:app . /app

RUN mkdir -p /app/media /app/staticfiles /app/logs /app/media/quarantine \
    && chown -R app:app /app/media /app/staticfiles /app/logs \
    && chmod +x /app/docker/entrypoint.sh /app/scripts/backup.sh /app/scripts/restore.sh

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health/ || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
