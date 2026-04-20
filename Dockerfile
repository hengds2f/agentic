# Multi-stage build: Node.js for frontend, Python for backend
# ── Stage 1: Build frontend ────────────────────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

# ── Stage 2: Python backend + built frontend ───────────────────────────────────
FROM python:3.11-slim

# Create non-root user (HuggingFace Spaces requirement)
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install system deps for weasyprint (optional PDF export)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
        libffi-dev libcairo2 && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/pyproject.toml backend/
RUN pip install --no-cache-dir -e backend/

# Copy backend source
COPY backend/ backend/

# Copy built frontend into the location the backend expects
COPY --from=frontend-build /build/dist backend/frontend/dist

# Adjust frontend dist path for Docker layout
# The main.py looks for ../../frontend/dist relative to app/main.py
# In Docker this becomes /app/backend/frontend/dist
# We symlink to make it discoverable
RUN ln -sf /app/backend/frontend /app/frontend

# Create writable directories
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

# HuggingFace Spaces uses port 7860
EXPOSE 7860

ENV PYTHONUNBUFFERED=1
ENV HP_DATABASE_URL="sqlite+aiosqlite:///./data/holidaypilot.db"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--app-dir", "/app/backend"]
