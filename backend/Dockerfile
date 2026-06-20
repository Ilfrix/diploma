# backend/Dockerfile
FROM python:3.11
# FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

# Устанавливаем системные зависимости (исправленные пакеты)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*
# RUN apt-get update && apt-get install -y \
#     python3.11 \
#     python3-pip \
#     libgl1 \
#     libglib2.0-0 \
#     && rm -rf /var/lib/apt/lists/*
# Устанавливаем uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_HTTP_TIMEOUT=600
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Копируем код
COPY . .

# Устанавливаем зависимости
RUN uv sync --no-dev --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
