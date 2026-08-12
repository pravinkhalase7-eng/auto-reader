pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
    timeout(time: 60, unit: 'MINUTES')
  }

  parameters {
    choice(
      name: 'DEPLOY_ENV',
      choices: ['staging', 'production'],
      description: 'Target environment for deploy'
    )
    booleanParam(
      name: 'SKIP_DEPLOY',
      defaultValue: false,
      description: 'Build and test only — skip deploy stage'
    )
    booleanParam(
      name: 'FORCE_RECREATE',
      defaultValue: false,
      description: 'Force recreate containers on deploy'
    )
    string(
      name: 'PUBLIC_API_URL',
      defaultValue: '',
      description: 'Optional override for NEXT_PUBLIC_API_URL (e.g. http://YOUR_VPS_IP:8000/api/v1). If empty, uses value from env file.'
    )
    string(
      name: 'ENV_CREDENTIAL_ID',
      defaultValue: 'aiteacher-env-file',
      description: 'Jenkins Secret file credential ID. Leave default, or set the ID you actually created.'
    )
    booleanParam(
      name: 'USE_REPO_ENV_EXAMPLE',
      defaultValue: true,
      description: 'If credential is missing, fall back to aiteacher.env.example from the repo (OK for first deploy; change secrets later).'
    )
  }

  environment {
    APP_NAME             = 'aiteacher'
    API_IMAGE            = "aiteacher-api:${env.BUILD_NUMBER}"
    API_IMAGE_LATEST     = 'aiteacher-api:latest'
    WEB_IMAGE            = "aiteacher-web:${env.BUILD_NUMBER}"
    WEB_IMAGE_LATEST     = 'aiteacher-web:latest'
    COMPOSE_PROJECT_NAME = 'aiteacher'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        sh '''
          echo "Branch: ${GIT_BRANCH:-unknown}"
          echo "Commit: ${GIT_COMMIT:-unknown}"
          git rev-parse --short HEAD || true
          echo "=== Workspace files ==="
          ls -la
          test -f docker-compose.yml || { echo "ERROR: docker-compose.yml missing"; exit 1; }
          test -f apps/api/Dockerfile || { echo "ERROR: apps/api/Dockerfile missing"; exit 1; }
          test -f apps/web/Dockerfile || { echo "ERROR: apps/web/Dockerfile missing"; exit 1; }
          test -f apps/api/requirements.txt || { echo "ERROR: apps/api/requirements.txt missing"; exit 1; }
          test -f apps/api/scripts/jenkins_smoke.py || { echo "ERROR: jenkins_smoke.py missing"; exit 1; }
        '''
      }
    }

    stage('Detect Tools') {
      steps {
        sh '''
          echo "=== Agent tools ==="
          docker --version
          docker compose version
          echo "WORKSPACE=${WORKSPACE}"
          echo "PWD=$(pwd)"
        '''
      }
    }

    stage('Prepare Env') {
      steps {
        script {
          def usedEnv = false
          def credId = (params.ENV_CREDENTIAL_ID ?: 'aiteacher-env-file').trim()

          // 1) Jenkins Secret file (ID configurable via ENV_CREDENTIAL_ID)
          try {
            withCredentials([file(credentialsId: credId, variable: 'ENV_FILE')]) {
              sh '''
                echo "Secret file path bound: $ENV_FILE"
                test -f "$ENV_FILE" || { echo "ERROR: credential file path missing"; exit 1; }
                cp -f "$ENV_FILE" .env.deploy
                echo "Copied credential file → .env.deploy"
              '''
              usedEnv = true
              echo "Loaded Jenkins credential ID: ${credId}"
            }
          } catch (err) {
            echo "WARN: Could not load credential '${credId}': ${err}"
            echo "Tip: Manage Jenkins → Credentials → Add → Kind=Secret file, ID=${credId}"
            echo "Or set build param ENV_CREDENTIAL_ID to an existing Secret file ID."
            echo "Or enable USE_REPO_ENV_EXAMPLE to use aiteacher.env.example from git."
          }

          // 2) Fallback: persistent / workspace / repo example files
          if (!usedEnv) {
            sh '''
              echo "=== Looking for fallback env files ==="
              ls -la aiteacher.env.example aiteacher.env .env \
                /var/jenkins_home/aiteacher.env /var/jenkins_home/secrets/aiteacher.env 2>/dev/null || true
            '''
            def candidates = [
              '/var/jenkins_home/secrets/aiteacher.env',
              '/var/jenkins_home/aiteacher.env',
              'aiteacher.env',
              '.env',
            ]
            if (params.USE_REPO_ENV_EXAMPLE) {
              candidates.add('aiteacher.env.example')
            }
            for (p in candidates) {
              if (fileExists(p)) {
                sh "cp -f '${p}' .env.deploy"
                usedEnv = true
                echo "Using env file: ${p} → .env.deploy"
                if (p == 'aiteacher.env.example') {
                  echo "WARNING: using repo example env. Replace YOUR_VPS_IP via PUBLIC_API_URL param, and add a real Secret file later."
                }
                break
              }
            }
          }

          if (!usedEnv) {
            // Last resort: generate a working default so first VPS deploy is not blocked
            sh '''
              cat > .env.deploy <<'EOF'
API_HOST_PORT=8000
WEB_HOST_PORT=3000
POSTGRES_USER=aiteacher
POSTGRES_PASSWORD=aiteacher
POSTGRES_DB=aiteacher
DATABASE_URL=postgresql+asyncpg://aiteacher:aiteacher@postgres:5432/aiteacher
SECRET_KEY=jenkins-auto-generated-change-me
CORS_ORIGINS=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
AI_PROVIDER=local
OCR_PROVIDER=local
TTS_PROVIDER=browser
STORAGE_PROVIDER=local
SEED_ON_STARTUP=true
OPENAI_API_KEY=
GOOGLE_AI_API_KEY=
EOF
            '''
            usedEnv = true
            echo "WARN: wrote built-in default .env.deploy (no credential / example found). Set PUBLIC_API_URL to your VPS IP:8000/api/v1"
          }

          // Optional parameter override for public API URL (browser-facing)
          if (params.PUBLIC_API_URL?.trim()) {
            def url = params.PUBLIC_API_URL.trim()
            // Derive UI origin for CORS when API looks like http://host:8000/api/v1
            def cors = ''
            def m = (url =~ /^(https?:\/\/[^:/]+)(?::8000)?(?:\/.*)?$/)
            if (m.find()) {
              cors = "${m.group(1)}:3000"
            }
            sh """
              if grep -q '^NEXT_PUBLIC_API_URL=' .env.deploy; then
                sed -i.bak 's|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=${url}|' .env.deploy
              else
                echo 'NEXT_PUBLIC_API_URL=${url}' >> .env.deploy
              fi
              if [ -n '${cors}' ]; then
                if grep -q '^CORS_ORIGINS=' .env.deploy; then
                  sed -i.bak 's|^CORS_ORIGINS=.*|CORS_ORIGINS=${cors}|' .env.deploy
                else
                  echo 'CORS_ORIGINS=${cors}' >> .env.deploy
                fi
                echo "CORS_ORIGINS set to ${cors}"
              fi
              echo "PUBLIC_API_URL override applied: ${url}"
            """
          }

          sh '''
            echo "=== .env.deploy key check (values hidden) ==="
            missing=0
            for key in SECRET_KEY NEXT_PUBLIC_API_URL CORS_ORIGINS; do
              val=$(grep -E "^${key}=" .env.deploy | head -n1 | cut -d= -f2- || true)
              if [ -n "$val" ]; then
                echo "$key=SET"
              else
                echo "$key=MISSING"
                missing=1
              fi
            done
            if [ "$missing" = "1" ] && [ "${SKIP_DEPLOY}" != "true" ]; then
              echo "ERROR: aiteacher-env-file is missing required keys (SECRET_KEY, NEXT_PUBLIC_API_URL, CORS_ORIGINS)."
              exit 1
            fi
          '''
          echo "Prepared .env.deploy for ${params.DEPLOY_ENV}"
        }
      }
    }

    stage('Docker Build') {
      steps {
        sh '''
          set -e
          set -a
          # shellcheck disable=SC1091
          . ./.env.deploy
          set +a

          echo "Building API image..."
          # IMPORTANT: do NOT bind-mount Jenkins workspace into docker run.
          # Jenkins-in-Docker cannot see /var/jenkins_home paths on the Docker host.
          docker build -t ${API_IMAGE} -t ${API_IMAGE_LATEST} ./apps/api

          echo "Building Web image (NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL})..."
          docker build \
            --build-arg "NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}" \
            -t ${WEB_IMAGE} -t ${WEB_IMAGE_LATEST} \
            ./apps/web

          docker images | grep aiteacher | head -n 20 || docker images | head -n 12
        '''
      }
    }

    stage('Smoke Test') {
      steps {
        sh '''
          set -e
          docker run --rm \
            -e PYTHONPATH=/app \
            -e SEED_ON_STARTUP=false \
            -e DATABASE_URL=sqlite+aiosqlite:///./smoke.db \
            -e SECRET_KEY=jenkins-smoke-secret \
            -e AI_PROVIDER=local \
            -e OCR_PROVIDER=local \
            ${API_IMAGE} \
            python scripts/jenkins_smoke.py
        '''
      }
    }

    stage('Deploy') {
      when {
        expression { return !params.SKIP_DEPLOY }
      }
      steps {
        sh '''
          set -e
          export IMAGE_TAG=${BUILD_NUMBER}
          export API_HOST_PORT=${API_HOST_PORT:-8000}
          export WEB_HOST_PORT=${WEB_HOST_PORT:-3000}
          cp -f .env.deploy .env

          # Export .env into this shell so compose ${VAR} substitution works
          set -a
          # shellcheck disable=SC1091
          . ./.env
          set +a

          echo "Runtime check: SECRET_KEY=${SECRET_KEY:+SET} NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}"

          echo "Freeing previous AI Teacher containers (if any)..."
          docker compose -f docker-compose.yml down --remove-orphans || true
          docker rm -f aiteacher-api aiteacher-web aiteacher-postgres aiteacher-redis 2>/dev/null || true

          free_port() {
            PORT="$1"
            CID="$(docker ps --format '{{.ID}} {{.Ports}}' | awk -v p=":${PORT}->" 'index($0,p){print $1; exit}')"
            if [ -n "$CID" ]; then
              echo "Port ${PORT} is used by container ${CID} — stopping it"
              docker stop "$CID" || true
              docker rm "$CID" || true
            fi
          }
          free_port "${API_HOST_PORT}"
          free_port "${WEB_HOST_PORT}"

          if [ "${FORCE_RECREATE}" = "true" ]; then
            docker compose -f docker-compose.yml up -d --build --force-recreate
          else
            docker compose -f docker-compose.yml up -d --build
          fi

          echo "Waiting for API healthy (via docker exec — works with Jenkins-in-Docker)..."
          for i in $(seq 1 45); do
            if docker exec aiteacher-api curl -fsS http://127.0.0.1:8000/api/v1/health >/tmp/aiteacher_health.json 2>/dev/null; then
              echo "API healthy"
              cat /tmp/aiteacher_health.json
              echo
              docker compose -f docker-compose.yml ps
              exit 0
            fi
            STATUS="$(docker inspect -f '{{.State.Health.Status}}' aiteacher-api 2>/dev/null || echo unknown)"
            echo "attempt ${i}: health=${STATUS}"
            if [ "$STATUS" = "healthy" ]; then
              docker exec aiteacher-api curl -fsS http://127.0.0.1:8000/api/v1/health || true
              echo
              exit 0
            fi
            sleep 3
          done
          echo "API health check failed"
          docker compose -f docker-compose.yml ps || true
          docker compose -f docker-compose.yml logs --tail=120
          exit 1
        '''
      }
    }

    stage('Post-Deploy Check') {
      when {
        expression { return !params.SKIP_DEPLOY }
      }
      steps {
        sh '''
          set -e
          echo "=== Container status ==="
          docker compose -f docker-compose.yml ps || true
          echo "=== API health (docker exec) ==="
          docker exec aiteacher-api curl -fsS http://127.0.0.1:8000/api/v1/health
          echo
          echo "=== API root ==="
          docker exec aiteacher-api curl -fsS http://127.0.0.1:8000/
          echo
          echo "=== Web responds ==="
          # Next may need a moment; try a few times inside the web container network via API host curl to published port is flaky from Jenkins-in-Docker
          docker exec aiteacher-web wget -qO- http://127.0.0.1:3000 >/tmp/aiteacher_web.html 2>/dev/null \
            || docker exec aiteacher-web wget -qO- http://127.0.0.1:3000/ >/tmp/aiteacher_web.html 2>/dev/null \
            || true
          if [ -s /tmp/aiteacher_web.html ]; then
            echo "web_ok bytes=$(wc -c </tmp/aiteacher_web.html)"
          else
            echo "WARN: could not fetch web HTML from inside container (image may still be starting)"
            docker logs aiteacher-web --tail=40 || true
          fi
        '''
      }
    }
  }

  post {
    success {
      echo "AI Teacher ${params.DEPLOY_ENV} build #${env.BUILD_NUMBER} succeeded"
      echo "UI: http://<VPS_HOST>:${env.WEB_HOST_PORT ?: '3000'}"
      echo "API: http://<VPS_HOST>:${env.API_HOST_PORT ?: '8000'}/docs"
    }
    failure {
      echo "AI Teacher build #${env.BUILD_NUMBER} failed — check stage logs"
      sh 'docker compose -f docker-compose.yml logs --tail=120 || true'
    }
    always {
      sh 'rm -f .env.deploy.bak || true'
    }
  }
}
