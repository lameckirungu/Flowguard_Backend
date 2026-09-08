# Multi-stage Docker build for Flowguard Backend
FROM python:3.13-slim AS builder

WORKDIR /app

# Copy requirement files first for optimal Docker layer caching
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

COPY . /app

FROM python:3.13-slim AS runtime

RUN useradd --create-home --uid 1000 flowgard
WORKDIR /app

# Copy installed site-packages and app source
COPY --from=builder /install /usr/local
COPY --from=builder --chown=flowgard:flowgard /app /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER flowgard

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
