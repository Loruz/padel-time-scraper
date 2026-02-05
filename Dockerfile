# Use Python 3.12 (3.14 not in official images yet; app is compatible)
FROM python:3.12-slim

WORKDIR /app

# Install dependencies (matches pyproject.toml)
RUN pip install --no-cache-dir \
    "fastapi[standard]>=0.128.0" \
    "httpx>=0.27.0" \
    "beautifulsoup4>=4.12.0" \
    "lxml>=5.0.0" \
    "cachetools>=5.3.0"

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
