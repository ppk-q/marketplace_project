# Marketplace Blog API

Backend-сервис блога маркетплейса на FastAPI.

## Что реализовано

- Регистрация и авторизация пользователя
- JWT-аутентификация через HttpOnly cookie
- Подтверждение email
- Refresh/logout с ротацией refresh-токенов
- Категории и статьи (CRUD)
- Публичные read-эндпоинты блога
- Полнотекстовый поиск статей на PostgreSQL
- Soft-delete статей в таблицу `deleted_articles`
- Presigned URL для загрузки/чтения изображений через MinIO/S3

## Стек

- Python 3.14
- FastAPI
- SQLAlchemy + Alembic
- PostgreSQL
- Redis
- RabbitMQ
- Celery
- MinIO
- Poetry
- Ruff
- Pytest

## Структура проекта

- `app/` - API
- `worker/` - Celery-воркер и задачи
- `alembic/` - миграции БД
- `tests/` - тесты
- `docker-compose.yml` - локальный стек

## Требования

- Docker + Docker Compose (рекомендуется)
- или Python 3.14 + Poetry
- `jq` (опционально, удобно для примеров)
- `HTTPie` для примеров без `curl` (`http` команда)

Установка HTTPie (любой вариант):

```bash
pipx install httpie
```

или

```bash
python -m pip install --user httpie
```

## Быстрый старт (Docker)

1. Создайте локальный env-файл:

```bash
cp .env.example .env
```

2. Поднимите сервисы:

```bash
docker compose up -d --build --wait --wait-timeout 180
docker compose ps
```

3. OpenAPI/Swagger:

- `http://127.0.0.1:8000/openapi.json`
- `http://127.0.0.1:8000/docs`

4. Миграции в Docker применяются при старте API автоматически. При необходимости:

```bash
docker compose exec -T api alembic upgrade head
```

5. Остановка:

```bash
docker compose down
```

## Локальный запуск (Poetry)

Нужны доступные инфраструктурные сервисы: PostgreSQL, Redis, RabbitMQ, MinIO.
Проще всего поднять их Docker Compose, а API/worker запускать локально.

1. Установите зависимости:

```bash
poetry install
```

2. Экспортируйте переменные из `.env`:

```bash
set -a
source .env
set +a
```

3. Задайте `DATABASE_URL` для локального хоста и примените миграции:

```bash
export DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/app
poetry run alembic upgrade head
```

4. Запустите API:

```bash
poetry run uvicorn app.main:app --reload
```

5. Запустите worker:

```bash
poetry run celery -A worker.celery_app:celery_app worker -l INFO
```

## Ключевые переменные окружения

- `DATABASE_URL` - URL БД (обязателен)
- `JWT_SECRET` - секрет подписи JWT
- `JWT_ACCESS_TTL_MINUTES` - TTL access-токена
- `JWT_REFRESH_TTL_MINUTES` - TTL refresh-токена
- `AUTH_REQUIRE_EMAIL_CONFIRMED` - требовать подтверждение email при логине
- `AUTH_REFRESH_STORE_BACKEND` - `db` / `memory` / `redis`
- `AUTH_REDIS_URL` - URL Redis для refresh-store
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`

## Quality Gates

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run pytest -q
```

## Интеграционный тест

По умолчанию integration-тесты пропускаются.

```bash
RUN_INTEGRATION_TESTS=1 \
DATABASE_URL=postgresql+asyncpg://app:app@127.0.0.1:5432/app \
poetry run pytest -q -m integration
```

## Примеры API без curl (через HTTPie)

Подготовьте переменные:

```bash
BASE_URL="http://127.0.0.1:8000"
SESSION="/tmp/marketplace_httpie_session.json"
EMAIL="user_$(date +%s)@example.com"
PASSWORD="StrongPass123"
```

### 1) Регистрация

```bash
http POST "$BASE_URL/api/v1/auth/register" \
  email="$EMAIL" \
  password="$PASSWORD"
```

После регистрации worker печатает ссылку подтверждения email в лог:

```bash
docker compose logs worker --tail=300 | grep "$EMAIL"
```

Скопируйте ссылку `confirm-email?...` в переменную и подтвердите:

```bash
CONFIRM_LINK="http://127.0.0.1:8000/api/v1/auth/confirm-email?token=..."
http GET "$CONFIRM_LINK"
```

### 2) Логин (cookie сохраняются в session)

```bash
http --session="$SESSION" POST "$BASE_URL/api/v1/auth/login" \
  email="$EMAIL" \
  password="$PASSWORD"
```

### 3) Refresh

```bash
http --session="$SESSION" POST "$BASE_URL/api/v1/auth/refresh"
```

### 4) Logout

```bash
http --session="$SESSION" POST "$BASE_URL/api/v1/auth/logout"
```

### 5) Создание категории (protected)

```bash
CATEGORY_ID=$(
  http --session="$SESSION" --print=b POST "$BASE_URL/api/v1/categories" \
    title="Tech" \
  | jq -r '.id'
)
echo "$CATEGORY_ID"
```

### 6) Создание статьи (protected, `image_key` обязателен)

```bash
ARTICLE_ID=$(
  http --session="$SESSION" --print=b POST "$BASE_URL/api/v1/articles" \
    title="Первая статья" \
    text="Текст статьи" \
    category_id:="$CATEGORY_ID" \
    image_key="articles/first.png" \
  | jq -r '.id'
)
echo "$ARTICLE_ID"
```

### 7) Список статей (public)

```bash
http GET "$BASE_URL/api/v1/articles" \
  page_number==1 \
  page_size==20
```

С фильтрами:

```bash
http GET "$BASE_URL/api/v1/articles" \
  search=="телефон" \
  category_id=="$CATEGORY_ID" \
  page_number==1 \
  page_size==10
```

### 8) Деталь статьи (public)

```bash
http GET "$BASE_URL/api/v1/articles/$ARTICLE_ID"
```

### 9) Обновление статьи (protected)

```bash
http --session="$SESSION" PATCH "$BASE_URL/api/v1/articles/$ARTICLE_ID" \
  title="Обновлённый заголовок"
```

### 10) Удаление статьи (soft-delete, protected)

```bash
http --session="$SESSION" DELETE "$BASE_URL/api/v1/articles/$ARTICLE_ID"
```

### 11) Presigned URL на загрузку изображения (protected)

```bash
UPLOAD_JSON=$(
  http --session="$SESSION" --print=b POST "$BASE_URL/api/v1/media/presign-upload" \
    file_name="cover.png" \
    content_type="image/png" \
    file_size:=1024
)
echo "$UPLOAD_JSON"

UPLOAD_URL=$(printf '%s' "$UPLOAD_JSON" | jq -r '.upload_url')
IMAGE_KEY=$(printf '%s' "$UPLOAD_JSON" | jq -r '.image_key')
```

Загрузка файла в MinIO/S3 по `UPLOAD_URL`:

```bash
http PUT "$UPLOAD_URL" Content-Type:image/png < ./cover.png
```

### 12) Presigned URL на скачивание изображения (protected)

```bash
http --session="$SESSION" GET "$BASE_URL/api/v1/media/presign-download" \
  image_key=="$IMAGE_KEY"
```

## Частые проблемы

### Ошибка `DATABASE_URL is not set`

Используйте один из вариантов:

```bash
docker compose exec -T api alembic upgrade head
```

или

```bash
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/app \
poetry run alembic upgrade head
```

### `401 Not authenticated`

- Для protected-эндпоинтов нужен логин.
- В HTTPie используйте `--session="$SESSION"` после успешного логина.

### Integration-тест пропускается

- Запускайте с `RUN_INTEGRATION_TESTS=1`.
