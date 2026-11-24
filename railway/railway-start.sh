#!/usr/bin/env bash
# Railway start script for AI Git Bot (runs under tini as appuser).
#  1. Turns Railway's postgres:// DATABASE_URL into the JDBC settings the app reads.
#  2. Sizes the JVM from the container's memory and CPU limits (Railway shows the
#     host's CPUs, so thread pools and heap would otherwise be sized for the host).
#  3. On an empty database, creates the admin account from ADMIN_PASSWORD on a
#     loopback-only instance (so /setup is never reachable from the internet) and
#     seeds the AI integration, Git integration and bot from the variables.
#  4. Starts the app on $PORT. Any failure exits non-zero, so Railway restarts it.
set -euo pipefail

log() { echo "[railway-start] $*"; }
fail() { echo "[railway-start] ERROR: $*" >&2; exit 1; }

export PORT="${PORT:-8080}"
export SERVER_PORT="$PORT"

# --- database --------------------------------------------------------------
[ -n "${DATABASE_URL:-}" ] || fail "DATABASE_URL is empty: point it at the Postgres service (\${{Postgres.DATABASE_URL}})"
eval "$(python3 /usr/local/lib/railway/railway_helper.py jdbc)"
export DATABASE_URL="$JDBC_URL" DATABASE_USERNAME="$JDBC_USER" DATABASE_PASSWORD="$JDBC_PASSWORD"
unset JDBC_URL JDBC_USER JDBC_PASSWORD
export DATABASE_DRIVER=org.postgresql.Driver

# --- public URL (used for CI callbacks and links) ---------------------------
case "${APP_PUBLIC_URL:-}" in
  http://?*|https://?*) ;;
  *) if [ -n "${RAILWAY_PUBLIC_DOMAIN:-}" ]; then APP_PUBLIC_URL="https://${RAILWAY_PUBLIC_DOMAIN}"; else APP_PUBLIC_URL="http://localhost:${PORT}"; fi ;;
esac
export APP_PUBLIC_URL="${APP_PUBLIC_URL%/}"

[ -n "${APP_ENCRYPTION_KEY:-}" ] || fail "APP_ENCRYPTION_KEY is empty: keep the generated value, the stored API keys and tokens are encrypted with it"

# --- memory and CPU ---------------------------------------------------------
mem_bytes=$(cat /sys/fs/cgroup/memory.max 2>/dev/null || echo max)
if [ "$mem_bytes" = "max" ] || [ -z "$mem_bytes" ]; then
  mem_bytes=$(awk '/MemTotal/ {print $2 * 1024}' /proc/meminfo)
fi
mem_mb=$(( mem_bytes / 1048576 ))
cpus=1
if read -r quota period < /sys/fs/cgroup/cpu.max 2>/dev/null && [ "$quota" != "max" ]; then
  cpus=$(( (quota + period - 1) / period ))
else
  cpus=$(nproc 2>/dev/null || echo 2)
fi
[ "$cpus" -ge 1 ] || cpus=1
[ "$cpus" -le 8 ] || cpus=8

# Heap ~40% of the limit (at least 160 MB, at most 4 GB); the rest is left for
# metaspace, code cache, threads and the git/build processes the agents start.
heap_mb=$(( mem_mb * 40 / 100 ))
[ "$heap_mb" -ge 160 ] || heap_mb=160
[ "$heap_mb" -le 4096 ] || heap_mb=4096
gc="-XX:+UseSerialGC"
[ "$mem_mb" -lt 1536 ] || gc="-XX:+UseG1GC"
export JAVA_TOOL_OPTIONS="-Xms64m -Xmx${heap_mb}m -XX:MaxMetaspaceSize=200m -XX:ReservedCodeCacheSize=64m -XX:MaxDirectMemorySize=64m -Xss512k ${gc} -XX:ActiveProcessorCount=${cpus} -XX:+ExitOnOutOfMemoryError -Djava.security.egd=file:/dev/urandom ${JAVA_EXTRA_OPTS:-}"
export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"
export SERVER_TOMCAT_THREADS_MAX="${SERVER_TOMCAT_THREADS_MAX:-40}"
export SPRING_DATASOURCE_HIKARI_MAXIMUM_POOL_SIZE="${SPRING_DATASOURCE_HIKARI_MAXIMUM_POOL_SIZE:-8}"
export SPRING_MAIN_BANNER_MODE=off
# Railway's proxy terminates TLS: honour X-Forwarded-Proto/-For from it, so redirects
# and links use https://YOUR-DOMAIN/ and session cookies are Secure. Trusted: Railway's
# proxy ranges (100.64.0.0/10, 152.233.0.0/16) plus loopback and private networks.
export SERVER_FORWARD_HEADERS_STRATEGY="${SERVER_FORWARD_HEADERS_STRATEGY:-native}"
trusted='10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}|127\.\d{1,3}\.\d{1,3}\.\d{1,3}|100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.\d{1,3}\.\d{1,3}|152\.233\.\d{1,3}\.\d{1,3}|0:0:0:0:0:0:0:1|::1|f[cd][0-9a-f]{2}:.*|fe80:.*'
export SERVER_TOMCAT_REMOTEIP_INTERNAL_PROXIES="${SERVER_TOMCAT_REMOTEIP_INTERNAL_PROXIES:-$trusted}"
unset trusted
# Upstream logs every AI request and agent step at DEBUG; INFO keeps prompts and
# code out of Railway's logs (set LOGGING_LEVEL_ORG_REMUS_GITEABOT=DEBUG to debug).
export LOGGING_LEVEL_ORG_REMUS_GITEABOT="${LOGGING_LEVEL_ORG_REMUS_GITEABOT:-INFO}"
export LOGGING_LEVEL_ORG_REMUS_GITEABOT_AI="${LOGGING_LEVEL_ORG_REMUS_GITEABOT_AI:-INFO}"
export LOGGING_LEVEL_ORG_REMUS_GITEABOT_AGENT="${LOGGING_LEVEL_ORG_REMUS_GITEABOT_AGENT:-INFO}"
# Go, Node and .NET tools the agents may run: keep their worker counts to our CPUs.
export GOMAXPROCS="${GOMAXPROCS:-$cpus}" UV_THREADPOOL_SIZE="${UV_THREADPOOL_SIZE:-$cpus}" DOTNET_PROCESSOR_COUNT="${DOTNET_PROCESSOR_COUNT:-$cpus}" DOTNET_GCHeapHardLimitPercent="${DOTNET_GCHeapHardLimitPercent:-30}"
log "limits: ${mem_mb} MB, ${cpus} CPU; JVM heap ${heap_mb} MB"
if [ "$mem_mb" -lt 1000 ]; then
  log "note: below 1 GB the PR review and triage workflows run fine; the coding agent and E2E (Chromium) workflows need 2 GB or more"
fi

# --- first boot -------------------------------------------------------------
unset APP_CONFIG_JSON APP_CONFIG_FILE
python3 /usr/local/lib/railway/railway_helper.py bootstrap || fail "first-boot setup failed; not opening the public port"

log "starting AI Git Bot on port ${PORT}"
cd /app
exec java -jar /app/app.jar
