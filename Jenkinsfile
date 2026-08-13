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
    booleanParam(
      name: 'RESET_POSTGRES',
      defaultValue: false,
      description: 'Delete Postgres data (users, lessons, reminders). Leave OFF so accounts survive deploys. Turn ON only if you need a fresh empty database.'
    )
    string(
      name: 'PUBLIC_API_URL',
      defaultValue: 'http://187.127.138.86:8000/api/v1',
      description: 'Browser-facing API URL baked into the web image'
    )
    string(
      name: 'ENV_CREDENTIAL_ID',
      defaultValue: 'aiteacher-env-file',
      description: 'Jenkins Secret file credential ID (only used when USE_ENV_CREDENTIAL=true)'
    )
    booleanParam(
      name: 'USE_ENV_CREDENTIAL',
      defaultValue: false,
      description: 'OFF by default. Turn ON only after you create the Jenkins Secret file credential.'
    )
    booleanParam(
      name: 'USE_REPO_ENV_EXAMPLE',
      defaultValue: true,
      description: 'Use aiteacher.env.example from the repo when no credential is loaded'
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
      when {
        expression { return !params.SKIP_DEPLOY }
      }
      steps {
        script {
          def usedEnv = false

          // 1) Jenkins Secret file — ID must be exactly: aiteacher-env-file
          try {
            withCredentials([file(credentialsId: 'aiteacher-env-file', variable: 'ENV_FILE')]) {
              sh '''
                echo "Secret file path bound: $ENV_FILE"
                test -f "$ENV_FILE" || { echo "ERROR: credential file path missing"; exit 1; }
                cp -f "$ENV_FILE" .env.deploy
                echo "Copied aiteacher-env-file → .env.deploy"
              '''
              usedEnv = true
            }
          } catch (err) {
            echo "Could not load credential aiteacher-env-file: ${err}"
            echo "Check: Manage Jenkins → Credentials → ID is exactly aiteacher-env-file (Secret file), scope Global, accessible to this job."
          }

          // 2) Fallback: persistent / workspace files
          if (!usedEnv) {
            sh '''
              echo "=== Looking for fallback env files ==="
              ls -la aiteacher.env .env /var/jenkins_home/aiteacher.env /var/jenkins_home/secrets/aiteacher.env 2>/dev/null || true
            '''
            def candidates = [
              '/var/jenkins_home/secrets/aiteacher.env',
              '/var/jenkins_home/aiteacher.env',
              'aiteacher.env',
              '.env',
            ]
            for (p in candidates) {
              if (fileExists(p)) {
                sh "cp -f '${p}' .env.deploy"
                usedEnv = true
                echo "Using env file: ${p} → .env.deploy"
                break
              }
            }
          }

          if (!usedEnv) {
            error('''No env source found.
Create Jenkins credential:
  Kind: Secret file
  ID: aiteacher-env-file
  Scope: Global
Then rebuild.''')
          }

          sh '''
            set -e
            python3 scripts/normalize_deploy_env.py .env.deploy
            if [ -n "$PUBLIC_API_URL" ]; then
              python3 scripts/normalize_deploy_env.py .env.deploy --public-api-url "$PUBLIC_API_URL"
            fi
            echo "=== DATABASE_URL from .env.deploy ==="
            grep DATABASE_URL .env.deploy || true
            echo "=== POSTGRES_PASSWORD from .env.deploy ==="
            grep POSTGRES_PASSWORD .env.deploy || true
          '''
          echo "Prepared .env.deploy for ${params.DEPLOY_ENV}"
        }
      }
    }



    stage('Clean') {
      steps {
        script {
          sh '''
            set +e
            echo "=== Stop previous AI Teacher containers ==="
            docker compose -f docker-compose.yml down --remove-orphans || true
            docker rm -f aiteacher-api aiteacher-web aiteacher-postgres aiteacher-redis aiteacher-celery-worker aiteacher-celery-beat 2>/dev/null || true
            docker rmi -f aiteacher-api:latest aiteacher-web:latest 2>/dev/null || true
            echo "=== Remaining aiteacher images ==="
            docker images | grep aiteacher || echo none
            echo "=== Docker volumes ==="
            docker volume ls
          '''
          if (params.RESET_POSTGRES) {
            sh '''
              set +e
              echo "RESET_POSTGRES=true — deleting Postgres volume (this wipes users and lessons)"
              docker volume rm -f aiteacher_pgdata aiteacher_aiteacher_pgdata 2>/dev/null || true
              echo "=== Docker volumes after Postgres reset ==="
              docker volume ls
            '''
          } else {
            echo "Keeping Postgres volume aiteacher_pgdata so users and lessons survive this deploy"
          }
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

          echo "Building API image (no cache so lesson-save fix is actually in the image)..."
          docker build --no-cache -t ${API_IMAGE} -t ${API_IMAGE_LATEST} ./apps/api

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

          set -a
          # shellcheck disable=SC1091
          . ./.env
          set +a

          echo "=== DATABASE_URL after bash source ==="
          echo "DATABASE_URL=${DATABASE_URL}"
          echo "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}"
          echo "=== .env file lines ==="
          grep DATABASE_URL .env || true
          grep POSTGRES_PASSWORD .env || true
          echo "=== docker compose resolved env ==="
          docker compose -f docker-compose.yml config | grep DATABASE_URL || true
          docker compose -f docker-compose.yml config | grep POSTGRES_PASSWORD || true

          echo "Freeing previous AI Teacher containers (if any)..."
          docker compose -f docker-compose.yml down --remove-orphans || true
          docker rm -f aiteacher-api aiteacher-web aiteacher-postgres aiteacher-redis aiteacher-celery-worker aiteacher-celery-beat 2>/dev/null || true

          echo "Starting Postgres first..."
          docker compose -f docker-compose.yml up -d --no-build postgres

          echo "Waiting for Postgres..."
          PG_USER="${POSTGRES_USER:-aiteacher}"
          ready=0
          i=1
          while [ "$i" -le 30 ]; do
            if docker exec aiteacher-postgres pg_isready -U "$PG_USER" >/dev/null 2>&1; then
              echo "Postgres ready"
              ready=1
              break
            fi
            echo "attempt ${i}: postgres starting"
            i=$((i + 1))
            sleep 2
          done
          if [ "$ready" != "1" ]; then
            echo "Postgres did not become ready"
            docker compose -f docker-compose.yml logs postgres --tail=80
            exit 1
          fi

          echo "Starting API, web, Redis, and Pavi Celery workers from the images just built..."
          docker compose -f docker-compose.yml up -d --no-build --force-recreate redis api web celery-worker celery-beat
          echo "=== aiteacher-api DATABASE_URL inside container ==="
          docker exec aiteacher-api printenv DATABASE_URL || true
          echo "=== aiteacher-postgres POSTGRES_PASSWORD inside container ==="
          docker exec aiteacher-postgres printenv POSTGRES_PASSWORD || true

          echo "Waiting for API healthy via docker exec..."
          i=1
          while [ "$i" -le 45 ]; do
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
            i=$((i + 1))
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
      echo "UI: http://187.127.138.86:3000"
      echo "API: http://187.127.138.86:8000/docs"
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
