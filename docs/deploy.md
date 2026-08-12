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
   - `CORS_ORIGINS=http://YOUR_VPS_IP:3000`
   - `NEXT_PUBLIC_API_URL=http://YOUR_VPS_IP:8000/api/v1`
5. Run the job. Optional parameters:
   - `SKIP_DEPLOY` — build + smoke only
   - `FORCE_RECREATE` — recreate containers
   - `PUBLIC_API_URL` — override browser API URL for this build

## After deploy

| Service | URL |
|---------|-----|
| UI | `http://YOUR_VPS_IP:3000` |
| API docs | `http://YOUR_VPS_IP:8000/docs` |
| Health | `http://YOUR_VPS_IP:8000/api/v1/health` |

Demo login (if seed enabled): `demo@example.com` / `demo1234`

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
