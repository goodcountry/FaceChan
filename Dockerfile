# syntax=docker/dockerfile:1
FROM python:3.12-slim

# System deps — psycopg2 needs libpq, Pillow needs libjpeg/zlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files at build time
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Daphne: ASGI server handling both HTTP and WebSocket connections.
# Workers are managed by Daphne internally; WEB_CONCURRENCY sets thread count.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed --threads 100 --max-replies 40 && daphne -b 0.0.0.0 -p 8000 facechan.asgi:application"]
