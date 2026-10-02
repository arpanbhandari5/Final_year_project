FROM python:3.11-slim

WORKDIR /app

# Install system dependencies: curl for healthcheck, gcc for some pip builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user and set up directories
RUN useradd -m -u 1000 prayash && \
    chown -R prayash:prayash /app && \
    mkdir -p /app/ml_models /app/instance && \
    chmod -R 755 /app/start.sh

USER prayash

# Train model during the build so the container is ready to serve immediately
RUN python train_model.py

# Health check verifies the ML pipeline is operational
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=5s \
    CMD python -c "import joblib, sys; joblib.load('ml_models/model.pkl'); joblib.load('ml_models/courses.pkl'); sys.exit(0)" \
    || curl -f http://localhost:5000/healthz || exit 1

EXPOSE 5000

CMD ["python", "app.py"]
