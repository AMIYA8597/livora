#!/usr/bin/env bash
# Runs on the free-tier VM, called over SSH by .github/workflows/free-tier-deploy.yml after it has
# copied docker-compose.yml, Caddyfile, web.caddy, web-www.caddy, api.env and this file to
# /opt/flatmate.
#
#   API_IMAGE=ghcr.io/owner/flatmate-api:<sha> API_DOMAIN=api.example.com ACME_EMAIL=you@example.com \
#   [WEB_IMAGE=ghcr.io/owner/flatmate-web:<tag> WEB_DOMAIN=example.com [WEB_WWW=0]] \
#     bash /opt/flatmate/deploy.sh  < registry-token-on-stdin (optional)
#
# Starts the new images, waits until the API (and the website, when WEB_IMAGE and WEB_DOMAIN are
# given) answer through Caddy over HTTPS, and otherwise puts the previous images back and fails.
# Without WEB_IMAGE and WEB_DOMAIN the website is not run here. www.<WEB_DOMAIN> redirects to the
# bare name unless WEB_WWW=0. A registry token on stdin is used
# for the pull and then forgotten (docker logout), so no long-lived credential stays on the VM.
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/flatmate}
: "${API_IMAGE:?API_IMAGE is required}"
: "${API_DOMAIN:?API_DOMAIN is required}"
: "${ACME_EMAIL:?ACME_EMAIL is required}"
WEB_IMAGE=${WEB_IMAGE:-} WEB_DOMAIN=${WEB_DOMAIN:-} NEW_WEB_WWW=${WEB_WWW:-1}
if { [ -n "$WEB_IMAGE" ] && [ -z "$WEB_DOMAIN" ]; } || { [ -z "$WEB_IMAGE" ] && [ -n "$WEB_DOMAIN" ]; }; then
  echo "::error::Give both WEB_IMAGE and WEB_DOMAIN, or neither"; exit 1
fi
# .env must be Compose's only source for these: Compose prefers the shell environment over .env,
# so leaving them exported would make a rollback silently start the new images again.
NEW_IMAGE=$API_IMAGE NEW_DOMAIN=$API_DOMAIN NEW_ACME_EMAIL=$ACME_EMAIL
NEW_WEB_IMAGE=$WEB_IMAGE NEW_WEB_DOMAIN=$WEB_DOMAIN
unset API_IMAGE API_DOMAIN ACME_EMAIL REDIS_PASSWORD WEB_IMAGE WEB_DOMAIN WEB_WWW COMPOSE_PROFILES
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
get_env() { sed -n "s/^$1=//p" .env | tail -1; }

previous=$(get_env API_IMAGE || true)
previous_web=$(get_env WEB_IMAGE || true)
set_env API_DOMAIN "$NEW_DOMAIN"
set_env ACME_EMAIL "$NEW_ACME_EMAIL"
set_env API_IMAGE "$NEW_IMAGE"

# The website: on with both settings, off without them. Caddy serves it only while
# sites/web.caddy exists.
install -d -m 0755 sites
if [ -n "$NEW_WEB_IMAGE" ]; then
  [ -f web.caddy ] || { echo "::error::$APP_DIR/web.caddy is missing"; exit 1; }
  set_env WEB_DOMAIN "$NEW_WEB_DOMAIN"
  set_env WEB_IMAGE "$NEW_WEB_IMAGE"
  set_env COMPOSE_PROFILES web
  install -m 0644 web.caddy sites/web.caddy
  if [ "$NEW_WEB_WWW" = 0 ]; then
    rm -f sites/web-www.caddy
  else
    [ -f web-www.caddy ] || { echo "::error::$APP_DIR/web-www.caddy is missing"; exit 1; }
    install -m 0644 web-www.caddy sites/web-www.caddy
  fi
  services=(api worker web)
else
  set_env WEB_DOMAIN ""
  set_env COMPOSE_PROFILES ""
  rm -f sites/web.caddy sites/web-www.caddy
  services=(api worker)
fi

compose() { docker compose --project-directory "$APP_DIR" "$@"; }

restore_previous() {
  set_env API_IMAGE "$previous"
  if [ -n "$NEW_WEB_IMAGE" ] && [ -z "$previous_web" ]; then
    # The website's first release failed: go back to running without it.
    set_env WEB_DOMAIN ""
    set_env COMPOSE_PROFILES ""
    rm -f sites/web.caddy sites/web-www.caddy
    NEW_WEB_DOMAIN=""
  elif [ -n "$previous_web" ]; then
    set_env WEB_IMAGE "$previous_web"
  fi
  return 0
}

token=""
if [ ! -t 0 ]; then token=$(cat || true); fi
if [ -n "$token" ] && [ -n "$REGISTRY_USER" ]; then
  printf '%s' "$token" | docker login "$REGISTRY" -u "$REGISTRY_USER" --password-stdin >/dev/null
fi
pull_ok=0
compose pull --quiet "${services[@]}" && pull_ok=1
[ -n "$token" ] && docker logout "$REGISTRY" >/dev/null 2>&1 || true
[ "$pull_ok" = 1 ] || { echo "::error::Couldn't pull ${services[*]}"; restore_previous; exit 1; }

curl_local() {  # curl_local DOMAIN PATH: through Caddy and TLS, as the internet sees it, without leaving the VM
  local insecure=()
  [ "$HEALTH_INSECURE_TLS" = 1 ] && insecure=(-k)
  curl -fsS "${insecure[@]}" --max-time 8 --resolve "$1:443:127.0.0.1" "https://$1$2" >/dev/null 2>&1
}

healthy() {
  curl_local "$NEW_DOMAIN" /health/ready || return 1
  if [ -n "$NEW_WEB_DOMAIN" ]; then curl_local "$NEW_WEB_DOMAIN" / || return 1; fi
  return 0
}

wait_healthy() {
  local deadline=$((SECONDS + WAIT_SECONDS))
  while [ $SECONDS -lt $deadline ]; do
    if healthy; then return 0; fi
    sleep 3
  done
  return 1
}

start_stack() {
  compose up -d --remove-orphans
  # A website switched off keeps its container until it is removed by name.
  if [ "$(get_env COMPOSE_PROFILES)" != web ]; then compose --profile web rm -sf web >/dev/null 2>&1 || true; fi
  # Caddy reads its files only at start; restart it when they changed.
  local sum
  sum=$( { cat Caddyfile; cat sites/*.caddy 2>/dev/null || true; } | sha256sum | cut -d' ' -f1)
  if [ "$sum" != "$(cat .caddyfile.sha256 2>/dev/null || true)" ]; then
    compose restart caddy
    echo "$sum" > .caddyfile.sha256
  fi
}

echo "Starting $NEW_IMAGE${NEW_WEB_IMAGE:+ and $NEW_WEB_IMAGE}"
start_stack

if wait_healthy; then
  echo "Live: https://${NEW_DOMAIN} is answering with $NEW_IMAGE"
  [ -n "$NEW_WEB_DOMAIN" ] && echo "Live: https://${NEW_WEB_DOMAIN} is answering with $NEW_WEB_IMAGE"
  # Search vectors for anything not yet embedded with the current model (all of them after an
  # embedding model change, otherwise none: unchanged text is skipped). Never fails the deploy;
  # search falls back to keywords for whatever is missing.
  timeout 600 docker compose --project-directory "$APP_DIR" exec -T worker \
    python -m app.ml.cli backfill-embeddings \
    || echo "::warning::Embedding backfill didn't finish; search uses keywords for what's missing"
  docker image prune -af --filter "until=168h" >/dev/null 2>&1 || true
  compose ps
  exit 0
fi

echo "::error::The new release didn't become healthy within ${WAIT_SECONDS}s"
compose logs --tail 80 "${services[@]}" caddy || true
if { [ -n "$previous" ] && [ "$previous" != "$NEW_IMAGE" ]; } ||
   { [ -n "$NEW_WEB_IMAGE" ] && [ "$previous_web" != "$NEW_WEB_IMAGE" ]; }; then
  echo "Rolling back to ${previous}${previous_web:+ and $previous_web}"
  restore_previous
  start_stack
  if wait_healthy; then
    echo "Rolled back: the previous release is serving again"
  else
    echo "::error::The previous release isn't healthy either; look at 'docker compose logs' on the VM"
  fi
fi
exit 1
