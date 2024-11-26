FROM python:3.11-slim-bullseye as base
WORKDIR /app

# Установка необходимых системных библиотек
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY Pipfile Pipfile.lock /app/
RUN pip install pipenv \
 && pipenv --python 3.11 \
 && pipenv install --system --deploy

# Копирование всего приложения
COPY app /app/

FROM base as fastapi
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
