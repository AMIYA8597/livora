#!/usr/bin/env bash
# Runs on the free-tier VM, called over SSH by .github/workflows/free-tier-deploy.yml after it has
# copied docker-compose.yml, Caddyfile, api.env and this file to /opt/flatmate.
#
#   API_IMAGE=ghcr.io/owner/flatmate-api:<sha> API_DOMAIN=api.example.com ACME_EMAIL=you@example.com \
#     bash /opt/flatmate/deploy.sh  < registry-token-on-stdin (optional)
#
# Starts the new image, waits until the API answers through Caddy over HTTPS, and otherwise puts
# the previous image back and fails. A registry token on stdin is used for the pull and then
# forgotten (docker logout), so no long-lived credential stays on the VM.
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/flatmate}
: "${API_IMAGE:?API_IMAGE is required}"
: "${API_DOMAIN:?API_DOMAIN is required}"
: "${ACME_EMAIL:?ACME_EMAIL is required}"
REGISTRY=${REGISTRY:-ghcr.io}
REGISTRY_USER=${REGISTRY_USER:-}
WAIT_SECONDS=${WAIT_SECONDS:-180}
# Tests only (.github/workflows/free-tier-stack.yml): Caddy's own certificate for localhost.
HEALTH_INSECURE_TLS=${HEALTH_INSECURE_TLS:-0}

cd "$APP_DIR"
umask 077
chmod 600 api.env

grep -q '^REDIS_PASSWORD=.' .env || { echo "::error::$APP_DIR/.env has no REDIS_PASSWORD (cloud-init creates it)"; exit 1; }

set_env() {  # set_env KEY VALUE: replace or add a line in .env
  local key=$1 value=$2
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}

previous=$(sed -n 's/^API_IMAGE=//p' .env || true)
set_env API_DOMAIN "$API_DOMAIN"
set_env ACME_EMAIL "$ACME_EMAIL"
set_env API_IMAGE "$API_IMAGE"

compose() { docker compose --project-directory "$APP_DIR" "$@"; }

token=""
if [ ! -t 0 ]; then token=$(cat || true); fi
if [ -n "$token" ] && [ -n "$REGISTRY_USER" ]; then
  printf '%s' "$token" | docker login "$REGISTRY" -u "$REGISTRY_USER" --password-stdin >/dev/null
fi
pull_ok=0
compose pull --quiet api worker && pull_ok=1
[ -n "$token" ] && docker logout "$REGISTRY" >/dev/null 2>&1 || true
[ "$pull_ok" = 1 ] || { echo "::error::Couldn't pull $API_IMAGE"; set_env API_IMAGE "$previous"; exit 1; }

# Caddy reads its file only at start; restart it when the file changed.
caddy_sum=$(sha256sum Caddyfile | cut -d' ' -f1)
old_caddy_sum=$(cat .caddyfile.sha256 2>/dev/null || true)

healthy() {
  # Through Caddy and TLS, as the internet sees it, but without leaving the VM.
  local insecure=()
  [ "$HEALTH_INSECURE_TLS" = 1 ] && insecure=(-k)
  curl -fsS "${insecure[@]}" --max-time 5 --resolve "${API_DOMAIN}:443:127.0.0.1" \
    "https://${API_DOMAIN}/health/ready" >/dev/null 2>&1
}

wait_healthy() {
  local deadline=$((SECONDS + WAIT_SECONDS))
  while [ $SECONDS -lt $deadline ]; do
    if healthy; then return 0; fi
    sleep 3
  done
  return 1
}

echo "Starting $API_IMAGE"
compose up -d --remove-orphans
if [ "$caddy_sum" != "$old_caddy_sum" ]; then
  compose restart caddy
  echo "$caddy_sum" > .caddyfile.sha256
fi

if wait_healthy; then
  echo "Live: https://${API_DOMAIN} is answering with $API_IMAGE"
  docker image prune -af --filter "until=168h" >/dev/null 2>&1 || true
  compose ps
  exit 0
fi

echo "::error::The new release didn't become healthy within ${WAIT_SECONDS}s"
compose logs --tail 80 api worker caddy || true
if [ -n "$previous" ] && [ "$previous" != "$API_IMAGE" ]; then
  echo "Rolling back to $previous"
  set_env API_IMAGE "$previous"
  compose up -d --remove-orphans
  if wait_healthy; then
    echo "Rolled back: the previous release is serving again"
  else
    echo "::error::The previous release isn't healthy either; look at 'docker compose logs' on the VM"
  fi
fi
exit 1
