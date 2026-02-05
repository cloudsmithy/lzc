FROM python:3.11-alpine

RUN pip install --no-cache-dir feedparser requests beautifulsoup4

COPY fetch.py /app/
WORKDIR /app

CMD ["sh", "-c", "python fetch.py && while true; do sleep 3600; python fetch.py; done"]
