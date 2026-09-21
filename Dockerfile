FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY ai_service ./ai_service
COPY tests ./tests
COPY etl ./etl

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
