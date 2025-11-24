# Multi-stage build to reduce final image size
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies in builder stage
WORKDIR /app
COPY requirements.txt .

# Install CPU-only torch first to avoid CUDA dependencies (saves ~3GB)
# This must be installed before sentence-transformers which depends on torch
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu && \
    rm -rf /tmp/* /var/tmp/* /root/.cache/pip && \
    pip install --no-cache-dir --user -r requirements.txt && \
    # Clean up pip cache and temp files immediately after installation
    rm -rf /tmp/* /var/tmp/* /root/.cache/pip && \
    # Clean up any wheel files that might be left
    find /root/.local -name "*.whl" -delete 2>/dev/null || true

# Final stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies including Chromium for Kaleido
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    chromium \
    chromium-driver \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code (from project root)
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV PYTHONPATH=/app
# Set Chromium path for Kaleido
ENV CHROMIUM_PATH=/usr/bin/chromium
ENV DISPLAY=:99

# Expose port
EXPOSE 8080

# Use gunicorn for production WSGI server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "presentation_agent.deployment.server:app"]
