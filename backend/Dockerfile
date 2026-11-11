# --- build: compile wheels with the full toolchain ---
FROM python:3.12-slim AS build
WORKDIR /src
COPY requirements.txt .
RUN pip wheel --no-cache-dir --require-hashes --wheel-dir /wheels -r requirements.txt   # pinned + hash-checked

# --- run: slim image, no compilers, non-root ---
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY --chown=app:app app ./app
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app alembic.ini boards.txt skills.txt places.txt ./
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/health').status != 200)"
# No --proxy-headers: X-Forwarded-For is client-controlled. Real IPs come from CF-Connecting-IP (TRUST_CF_CONNECTING_IP).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
