# ============================================================================
# Stage 1: Build React 19 + Tailwind CSS Frontend Bundle
# ============================================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ============================================================================
# Stage 2: Production Python FastAPI Multi-Cloud Control Plane
# ============================================================================
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Copy project configuration and source
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY services/ ./services/

# Install FastAPI Control Plane + Snowflake + Cloud SDKs
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . boto3 requests

# Copy compiled frontend static assets from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8000

CMD ["sh", "-c", "uvicorn sf_dr_controller.api:app --host 0.0.0.0 --port ${PORT:-8000}"]

