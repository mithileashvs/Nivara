# SmartCare backend — minimal development image.
FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal on purpose; add build-essential here if a future dependency needs compiling.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000

# `--reload` is left out of the image itself; docker-compose.yml enables it for local development
# by overriding `command` and bind-mounting the source.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
