FROM python:3.11

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_HTTP_TIMEOUT=600
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Копируем код
COPY ./app ./app
COPY main.py .
COPY ./models/models--timm--tf_efficientnetv2_m.in21k .
COPY ./pyproject.toml .
COPY uv.lock .

RUN uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
