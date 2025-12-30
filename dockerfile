FROM python:3.11-slim AS builder

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN useradd -m -u 1000 appuser && mkdir /app && chown -R appuser:appuser /app
WORKDIR /app

COPY --chown=appuser:appuser requirements.txt .
USER appuser
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim

LABEL maintainer="mati@waichatt.com"

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PATH="/home/appuser/.local/bin:$PATH"
ENV WORKERS=4

# Instala curl para el healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser && mkdir /app && chown -R appuser:appuser /app
WORKDIR /app

COPY --from=builder --chown=appuser:appuser /home/appuser/.local /home/appuser/.local
COPY --chown=appuser:appuser . .

EXPOSE 8000
USER appuser

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${WORKERS}"]