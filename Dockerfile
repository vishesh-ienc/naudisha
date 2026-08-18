# Multi-stage Dockerfile for NauDisha Full-Stack Application (Frontend + Backend)

# Stage 1: Build Frontend Vite React Assets
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Backend + FastAPI + Static Frontend
FROM python:3.11-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Install system build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install dependencies
COPY backend/requirements.txt ./backend/requirements.txt
COPY backend/pyproject.toml ./backend/pyproject.toml
RUN pip install --no-cache-dir -r ./backend/requirements.txt
RUN pip install --no-cache-dir -e ./backend

# Copy application source code and built frontend assets
COPY backend/ ./backend/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn naudisha.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
