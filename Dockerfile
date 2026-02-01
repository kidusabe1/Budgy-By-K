FROM python:3.11-slim

WORKDIR /app

# System deps for matplotlib (native extensions)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV USE_FIRESTORE=true

CMD ["python", "entrypoint.py"]
