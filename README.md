# Padel Time

Padel court availability aggregator.

## Docker

**Local or VPS:**

```bash
# Build and run with Compose
docker compose up --build

# Or build and run manually
docker build -t padel-time .
docker run -p 8000:8000 padel-time
```

App is at **http://localhost:8000**.

For Coolify: use the same Dockerfile (build context = repo root, no compose needed).
