# Deploy to VPS (Jenkins)

This project follows the same Jenkins → Docker Compose pattern as **Option-Trading / NiftySense**.

## What Jenkins does

1. Checkout repo
2. Load secrets from Jenkins credential `aiteacher-env-file`
3. Build `aiteacher-api` and `aiteacher-web` images
4. Run API smoke test (`scripts/jenkins_smoke.py`)
5. `docker compose up -d` on the VPS agent
6. Health-check API via `docker exec aiteacher-api curl .../api/v1/health`

## Jenkins setup

1. Install Docker + Docker Compose on the Jenkins agent (or use Jenkins-in-Docker with Docker socket mount — same as NiftySense).
2. Create a Pipeline job pointing at this repo’s `Jenkinsfile`.
3. Create credential:
   - **Kind:** Secret file  
   - **ID:** `aiteacher-env-file` (exact)  
   - **Contents:** filled copy of [`aiteacher.env.example`](../aiteacher.env.example)
4. Set in that file:
   - `SECRET_KEY`
   - `POSTGRES_PASSWORD` / matching `DATABASE_URL`
   - `CORS_ORIGINS=http://doxstation.com,http://doxstation.com:3000,http://YOUR_VPS_IP:3000`
   - `NEXT_PUBLIC_API_URL=http://doxstation.com/api/v1` (via nginx on port 80)
   - `TWILIO_WEBHOOK_BASE_URL=http://doxstation.com`
   - `GOOGLE_AI_API_KEY` (required for story pictures; not `GOOGLE_API_KEY`)
5. Open the VPS firewall for **80** (nginx), and optionally **3000** / **8000** for direct debug.
6. Run the job. Optional parameters:
   - `SKIP_DEPLOY` — build + smoke only
   - `FORCE_RECREATE` — recreate containers
   - `RESET_POSTGRES` — **leave unchecked**. Checking it deletes the Postgres volume and wipes users, lessons, and reminders. Use only after a password/`InvalidPasswordError` reset when you want an empty database.
   - `PUBLIC_API_URL` — override browser API URL for this build (also refreshes CORS / Twilio base)

## After deploy

| Service | URL |
|---------|-----|
| UI (recommended) | `http://doxstation.com/` or `http://YOUR_VPS_IP/` |
| UI (direct) | `http://YOUR_VPS_IP:3000` |
| API via nginx | `http://doxstation.com/api/v1/health` |
| API docs (direct) | `http://YOUR_VPS_IP:8000/docs` |
| Health | `http://YOUR_VPS_IP:8000/api/v1/health` |

Demo login (if seed enabled): `demo@example.com` / `demo1234`

## Nginx

Compose service `nginx` (`aiteacher-nginx`) listens on **`NGINX_HOST_PORT` (default 80)**:

- `/` → `web:3000`
- `/api/` → `api:8000`

Config is baked into image `aiteacher-nginx` from [`deploy/nginx/`](../deploy/nginx/) (no host bind mount — required when Jenkins uses the host Docker socket). No TLS yet — add certificates later (Caddy/certbot) if you want `https://`.

## Manual deploy (without Jenkins)

```bash
cp aiteacher.env.example .env
# edit .env — set YOUR_VPS_IP / secrets

export IMAGE_TAG=manual
docker compose build
docker compose up -d
docker compose ps
docker exec aiteacher-api curl -fsS http://127.0.0.1:8000/api/v1/health
```

## Notes

- `NEXT_PUBLIC_API_URL` is baked into the **web image at build time**. Change it → rebuild web (Jenkins does this every run).
- OCR needs Tesseract in the API image (already installed in `apps/api/Dockerfile`).
- Do not bind-mount Jenkins workspace paths into containers when Jenkins runs inside Docker (same constraint as Option-Trading).
