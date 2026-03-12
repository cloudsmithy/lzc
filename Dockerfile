FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir feedparser requests beautifulsoup4

WORKDIR /app
COPY fetch.py .
COPY entrypoint.sh .
COPY nginx.conf /etc/nginx/sites-enabled/default
COPY style.css /data/style.css

RUN chmod +x entrypoint.sh && \
    mkdir -p /data/articles

EXPOSE 80

ENTRYPOINT ["/app/entrypoint.sh"]
