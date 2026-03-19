FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user and prepare the data directory before dropping privileges
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data && \
    chown appuser:appuser /app/data

COPY . .

ENV DATABASE_URL="sqlite:///./data/lan_dashboard.db"

# Drop to non-root for runtime
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
