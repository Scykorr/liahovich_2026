# Кластерный анализ агрегированных результатов голосования по УИК

Production-ready Django-приложение для воспроизводимого кластерного анализа. Интерфейс описывает только статистические профили участков и **не** делает утверждений о нарушениях или причинах.

Стек: Python 3.12, Django 5.2 LTS, PostgreSQL 16, Redis, Celery, pandas/numpy/scipy/scikit-learn/statsmodels, Plotly, Bootstrap 5, HTMX.

## Быстрый старт (Windows)

```powershell
cd liahovich_2026
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements\dev.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

В другом окне (если не используете `CELERY_TASK_ALWAYS_EAGER=true`):

```powershell
.\.venv\Scripts\Activate.ps1
celery -A config.celery worker -l info
```

Для локального PostgreSQL/Redis укажите `DATABASE_URL` и `REDIS_URL` в `.env`. Для упрощённой разработки без Redis оставьте `config.settings.development` — кэш идёт в память; Celery eager включается переменной `CELERY_TASK_ALWAYS_EAGER=true`.

## Быстрый старт (Linux / macOS)

```bash
cd liahovich_2026
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

```bash
celery -A config.celery worker -l info
```

Первый суперпользователь получает системную роль администратора. Аналитика создавайте через «Пользователи» или `python manage.py shell`.

## Docker Compose

```bash
cp .env.example .env
# задайте DJANGO_SECRET_KEY и POSTGRES_PASSWORD
docker compose up --build
```

Сервисы: `web`, `worker`, `db`, `redis`. Контейнеры запускаются не от root.

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Локальный HTTP в Compose отключает SSL-redirect (см. `docker-compose.yml`). В настоящем production оставьте значения по умолчанию из `config.settings.production`.

## Тесты

Windows:

```powershell
pytest
pytest --cov=analytics_core --cov-fail-under=90
pytest --cov=apps --cov=analytics_core --cov-fail-under=80
ruff check .
python manage.py check --deploy --settings=config.settings.production
```

Linux:

```bash
pytest
pytest --cov=analytics_core --cov-fail-under=90
pytest --cov=apps --cov=analytics_core --cov-fail-under=80
ruff check .
DJANGO_SECRET_KEY=replace-with-long-random DJANGO_ALLOWED_HOSTS=example.test \
  python manage.py check --deploy --settings=config.settings.production
```

GitHub Actions (`.github/workflows/ci.yml`) на каждый push и pull request в `main` запускает ruff, pytest с порогами покрытия и `manage.py check --deploy`.

Фикстуры: `tests/fixtures/valid_cyrillic.csv`, `balance_error.csv`, `zero_denominators.csv`, `duplicates.csv`. Корректный XLSX собирается в интеграционном тесте импорта.

## Резервное копирование и восстановление

```bash
export DATABASE_URL=postgres://user:pass@localhost:5432/liahovich
export MEDIA_ROOT=./media
export RETENTION_DAYS=14
./scripts/backup.sh
./scripts/restore.sh ./backups/db_YYYYMMDD_HHMMSS.dump ./backups/media_YYYYMMDD_HHMMSS.tar.gz
```

Windows (Git Bash или WSL) — те же команды. Политика хранения: дампы старше `RETENTION_DAYS` удаляются. Карантинные загрузки чистятся командой:

```bash
python manage.py purge_quarantine --days 14
```

## Роли

- **Администратор** — пользователи и системный аудит.
- **Аналитик** — проекты, версии данных, запуски, публикация отчётов.
- **Наблюдатель** — только опубликованные результаты проектов, куда его добавили.

Чужой объект скрывается ответом 404. Недостаток прав у члена проекта — 403.

## Сценарий аналитика

1. Создать проект и пригласить участников.
2. Загрузить CSV/XLSX (карантин → проверка типа/размера/имени).
3. Сопоставить колонки, при необходимости поправить кодировку и разделитель, увидеть 20 строк.
4. Просмотреть качество данных, скачать CSV ошибок, подтвердить предупреждения.
5. Задать параметры запуска (они попадают в паспорт).
6. Следить за прогрессом Celery-задачи.
7. Сравнить кандидатов, выбрать модель, открыть профили и таблицу УИК.
8. Скачать назначения (CSV/XLSX), JSON паспорта, HTML/PDF-отчёт.
9. Опубликовать результат для наблюдателей.

Повтор запуска с теми же данными, конфигурацией и seed воспроизводит результат. Зафиксированный набор данных не изменяется: исправление — новая версия.
