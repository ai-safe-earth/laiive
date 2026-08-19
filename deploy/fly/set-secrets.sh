#!/usr/bin/env sh
# Push the root .env into Fly secrets, one app at a time (DEPLOY.md section 2).
#
# Doing this by hand is ~35 key/value pairs across four apps, and one of them --
# INTERNAL_API_KEY -- has to be byte-identical on all four or the gateway starts
# getting 403s from its own services. So it is a script.
#
# No secret value is ever printed: the check reports key NAMES only, and the
# values go straight from the file into flyctl.
#
#   sh deploy/fly/set-secrets.sh              # check + set every app
#   sh deploy/fly/set-secrets.sh --check      # check only, set nothing
#   sh deploy/fly/set-secrets.sh gateway      # one app
#
# CORS_ALLOW_ORIGINS is deliberately not set here: the Pages domain does not
# exist until section 4, so section 5 sets it.
set -eu

cd "$(dirname "$0")/../.."
ENV_FILE=${ENV_FILE:-.env}

CHECK_ONLY=0
APPS="gateway retriever pusher search"
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    gateway|retriever|pusher|search) APPS="$arg" ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

[ -f "$ENV_FILE" ] || { echo "no $ENV_FILE at the repo root (see .example.env)" >&2; exit 1; }

# One key out of the file. Last assignment wins, `export ` is tolerated, a
# trailing " # comment" is dropped (the template puts pragma markers there), and
# surrounding quotes come off.
read_key() {
  sed -n "s/^[[:space:]]*\(export[[:space:]]\+\)\?$1=//p" "$ENV_FILE" \
    | tail -n 1 \
    | sed -e 's/[[:space:]]\+#.*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/" \
    | tr -d '\r'
}

GATEWAY_KEYS="SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY INTERNAL_API_KEY"
RETRIEVER_KEYS="NEO4J_URI NEO4J_USERNAME NEO4J_PASSWORD NEO4J_DATABASE OPENAI_API_KEY INTERNAL_API_KEY"
PUSHER_KEYS="NEO4J_URI NEO4J_USERNAME NEO4J_PASSWORD NEO4J_DATABASE OPENAI_API_KEY INTERNAL_API_KEY"
SEARCH_KEYS="NEO4J_URI NEO4J_USERNAME NEO4J_PASSWORD NEO4J_DATABASE OPENAI_API_KEY TAVILY_API_KEY SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY INTERNAL_API_KEY"
# Tracing is optional -- set only when LANGFUSE_ENABLED is true in the file.
RETRIEVER_OPTIONAL="LANGFUSE_ENABLED LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY LANGFUSE_HOST"

keys_for() {
  case "$1" in
    gateway) echo "$GATEWAY_KEYS" ;;
    retriever) echo "$RETRIEVER_KEYS" ;;
    pusher) echo "$PUSHER_KEYS" ;;
    search) echo "$SEARCH_KEYS" ;;
  esac
}

missing=""
for app in $APPS; do
  for key in $(keys_for "$app"); do
    [ -n "$(read_key "$key")" ] || case " $missing " in *" $key "*) ;; *) missing="$missing $key" ;; esac
  done
done

if [ -n "$missing" ]; then
  echo "missing from $ENV_FILE:$missing" >&2
  case "$missing" in
    *INTERNAL_API_KEY*)
      echo "" >&2
      echo "INTERNAL_API_KEY is the gateway/service trust boundary and has no default." >&2
      echo "Generate one once, put it in $ENV_FILE, and never rotate it casually:" >&2
      echo "  openssl rand -hex 32" >&2 ;;
  esac
  exit 1
fi
echo "all required keys present in $ENV_FILE"

[ "$CHECK_ONLY" -eq 1 ] && exit 0

for app in $APPS; do
  keys=$(keys_for "$app")
  [ "$app" = "retriever" ] && [ "$(read_key LANGFUSE_ENABLED)" = "true" ] && keys="$keys $RETRIEVER_OPTIONAL"

  set -- # rebuild the argument list as KEY=value pairs, values never echoed
  for key in $keys; do
    value=$(read_key "$key")
    [ -n "$value" ] && set -- "$@" "$key=$value"
  done

  echo "laiive-$app: setting $# secrets"
  flyctl secrets set -a "laiive-$app" --stage "$@"
done

echo ""
echo "Staged, not applied: the next deploy of each app picks them up."
echo "Still to do by hand (DEPLOY.md section 5): CORS_ALLOW_ORIGINS on the gateway,"
echo "once the Pages domain exists."
