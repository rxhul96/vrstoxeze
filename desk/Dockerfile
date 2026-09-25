# Stage 1: build the UI into the Python package's static dir
FROM node:22-alpine AS ui
WORKDIR /build/ui
COPY ui/package*.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
RUN mkdir -p /build/src/optionsdesk && npm run build

# Stage 2: Python runtime
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DESK_DB_PATH=/data/desk.sqlite3
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY --from=ui /build/src/optionsdesk/static ./src/optionsdesk/static
RUN pip install --no-cache-dir ".[kite,server]"
VOLUME ["/data"]
EXPOSE 8000
CMD ["uvicorn", "--factory", "optionsdesk.app:create_app", "--host", "0.0.0.0", "--port", "8000"]
