FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.3.1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Если на Py 3.14 у зависимостей не окажется wheels, понадобится сборка.
# build-essential + libpq-dev часто нужны для asyncpg/psycopg и т.п.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir "poetry==${POETRY_VERSION}"

# Кешируем слой зависимостей
COPY pyproject.toml poetry.lock /app/

# Ставим только main-зависимости, без установки "самого проекта" как пакета
RUN poetry install --no-ansi --only main --no-root

# Код
COPY app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
