# ── Stage 1: build ────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Build tools needed by bcrypt (C extension) and any future packages
# that require compilation. Cleaned in this layer via rm to minimise stage size.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt \
    && pip uninstall -y Jinja2 MarkupSafe 2>/dev/null; true \
    && find /venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true \
    && find /venv -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null; true \
    && find /venv -name "*.pyi" -delete 2>/dev/null; true \
    && find /venv -name "py.typed" -delete 2>/dev/null; true \
    && pip uninstall -y pip setuptools 2>/dev/null; true

# ── Stage 2: runtime ──────────────────────────────────────────────────────
FROM python:3.12-slim

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy only the compiled virtualenv — no gcc or headers in the final image
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"

COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/

RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
