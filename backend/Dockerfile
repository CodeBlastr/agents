FROM python:3.12-slim-bookworm

WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

EXPOSE 8000
CMD ["bash", "-lc", "cd /app && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
