# Как запустить проект локально

Два способа: **простой** (SQLite, без PostgreSQL и Redis) и **полный** (Docker Compose, как в production).

Локальный вход: создайте суперпользователя командой `python manage.py createsuperuser` и войдите этими данными.

Сервер: http://127.0.0.1:8000/

---

## 1. Простой запуск на Windows (рекомендуется)

Нужен Python 3.11 или 3.12.

Откройте PowerShell в папке проекта:

```powershell
cd $HOME\Documents\GitHub\liahovich_2026
```

### 1.1. Виртуальное окружение и пакеты

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements\dev.txt
```

Если политика выполнения скриптов запрещает activate:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 1.2. Файл `.env`

Скопируйте пример и поправьте базу на SQLite (PostgreSQL для простого режима не нужен):

```powershell
copy .env.example .env
```

В `.env` оставьте или поставьте:

```
DJANGO_SETTINGS_MODULE=config.settings.development
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=local-dev-key-not-for-production
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
DATABASE_URL=sqlite:///db.sqlite3
CELERY_TASK_ALWAYS_EAGER=true
```

`CELERY_TASK_ALWAYS_EAGER=true` считает анализ внутри веб-процесса, отдельный Celery/Redis не нужен.

### 1.3. База, пользователь, сервер

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Команда `createsuperuser` спросит имя, email и пароль. Первый суперпользователь получает роль администратора.

Откройте в браузере: http://127.0.0.1:8000/

Проверка живности: http://127.0.0.1:8000/health/

Остановка сервера: в окне PowerShell нажмите `Ctrl+C`.

### 1.4. Что делать в интерфейсе

1. Войти учётной записью, которую создали через `createsuperuser`.
2. Создать проект.
3. Импортировать `tests\fixtures\valid_cyrillic.csv`.
4. Сопоставить колонки и проверить качество данных.
5. Запустить анализ (при eager-режиме прогресс завершится в том же процессе).
6. Открыть кандидатов, профиль модели и скачать назначения.

---

## 2. Linux / macOS (простой режим)

```bash
cd ~/Documents/GitHub/liahovich_2026
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env
```

В `.env` те же значения, что в разделе 1.2 (`DATABASE_URL=sqlite:///db.sqlite3` и `CELERY_TASK_ALWAYS_EAGER=true`).

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

---

## 3. Полный стек через Docker Compose

Нужны Docker Desktop и файл `.env` (можно из `.env.example`). Задайте `DJANGO_SECRET_KEY` и `POSTGRES_PASSWORD`.

```powershell
copy .env.example .env
docker compose up --build
```

В другом окне:

```powershell
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Сервисы: `web` (порт 8000), `worker` (Celery), `db` (PostgreSQL 16), `redis`.

Остановка:

```powershell
docker compose down
```

---

## 4. Частые проблемы

| Симптом | Что сделать |
| --- | --- |
| `Couldn't import Django` | Активируйте `.venv` и установите `requirements\dev.txt` |
| Ошибка подключения к PostgreSQL | Для простого режима в `.env` укажите `DATABASE_URL=sqlite:///db.sqlite3` |
| Анализ «висит» в очереди | Включите `CELERY_TASK_ALWAYS_EAGER=true` или запустите worker: `celery -A config.celery worker -l info` |
| Порт 8000 занят | `python manage.py runserver 127.0.0.1:8001` |
| `createsuperuser` пишет, что пользователь есть | Входите существующим `admin` или создайте другого через `/accounts/users/` |
| Не открывается сайт | Проверьте, что `runserver` запущен и открыт именно http://127.0.0.1:8000/ |

Тесты:

```powershell
.\.venv\Scripts\Activate.ps1
pytest
```
