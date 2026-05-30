FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --no-deps vkbottle==4.3.10 && \
    pip install --no-cache-dir vkbottle_types

COPY . .

CMD ["python", "-m", "bot.main"]
