# Padel Time

Padel court availability aggregator.

## Docker

**Local or VPS:**

```bash
# Option 1: Use .env file (recommended)
cp .env.example .env
# Edit .env and set GOOGLE_ANALYTICS_ID=G-XXXXXXXXXX
docker compose up --build

# Option 2: Set env var directly
GOOGLE_ANALYTICS_ID=G-XXXXXXXXXX docker compose up --build

# Option 3: Build and run manually
docker build -t padel-time .
docker run -p 8000:8000 -e GOOGLE_ANALYTICS_ID=G-XXXXXXXXXX padel-time
```

App is at **http://localhost:8000**.

**For Coolify:** Add `GOOGLE_ANALYTICS_ID` as an environment variable in the Coolify app settings (no .env file needed).
