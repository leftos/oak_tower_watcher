# Multi-stage build for VATSIM Tower Monitor (Headless)
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY headless/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Create non-root user for security
RUN groupadd -r vatsim && useradd -r -g vatsim vatsim

# Set working directory
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/vatsim/.local

# Make sure scripts in .local are usable
ENV PATH=/home/vatsim/.local/bin:$PATH

# Copy application files
COPY headless/main.py .
COPY headless/worker.py .
COPY shared/ shared/
COPY config/ config/
COPY headless/docker-entrypoint.sh .

# Make entrypoint script executable and create logs directory
RUN chmod +x docker-entrypoint.sh && \
    mkdir -p logs && \
    chown -R vatsim:vatsim /app && \
    chmod -R 755 /app

# Switch to non-root user
USER vatsim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('/tmp/vatsim_monitor_headless.lock') else 1)"

# Expose no ports (this is a monitoring service that makes outbound requests only)

# Set entrypoint and default command
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "main.py"]