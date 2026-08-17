#!/usr/bin/env bash
# Turn the root .env into the overlay's secrets.env.
#
# This is what keeps the "one root .env" developer experience intact: keep
# editing .env for local work, run this to push a change to the cluster. Only the
# keys listed below travel; everything non-secret belongs in
# k8s/base/configmap.yaml where it is readable in a diff.
#
#   ./k8s/scripts/env-to-secret.sh prod   # writes + encrypts overlays/prod/secrets.enc.yaml
#   ./k8s/scripts/env-to-secret.sh local  # writes overlays/local/secrets.env, unencrypted
#
# INTERNAL_API_KEY is generated if the root .env does not have one yet — the
# gateway and the three services must all see the same value, which is exactly
# why it lives in the same place as every other shared setting.
set -euo pipefail

OVERLAY="${1:-prod}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
OUT_DIR="$REPO_ROOT/k8s/overlays/$OVERLAY"

SECRET_KEYS=(
  OPENAI_API_KEY
  NEO4J_URI
  NEO4J_PASSWORD
  SUPABASE_SERVICE_ROLE_KEY
  SUPABASE_URL
  SUPABASE_PUBLISHABLE_KEY
  TAVILY_API_KEY
  LANGFUSE_SECRET_KEY
  LANGFUSE_PUBLIC_KEY
  LANGFUSE_HOST
  INTERNAL_API_KEY
)

[[ -f "$ENV_FILE" ]] || { echo "no $ENV_FILE — copy .example.env and fill it in" >&2; exit 1; }
[[ -d "$OUT_DIR" ]] || { echo "no overlay $OVERLAY at $OUT_DIR" >&2; exit 1; }

value_of() {
  # Last assignment wins, matching how dotenv and pydantic-settings read the file.
  grep -E "^${1}=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true
}

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

missing=()
for key in "${SECRET_KEYS[@]}"; do
  val="$(value_of "$key")"
  if [[ -z "$val" && "$key" == "INTERNAL_API_KEY" ]]; then
    val="$(openssl rand -hex 32)"
    # .env may not end in a newline — appending blind would splice the new key
    # onto the end of the last setting and silently corrupt it.
    [[ -n "$(tail -c1 "$ENV_FILE")" ]] && printf '\n' >> "$ENV_FILE"
    printf 'INTERNAL_API_KEY=%s\n' "$val" >> "$ENV_FILE"
    echo "generated INTERNAL_API_KEY and appended it to .env" >&2
  fi
  [[ -z "$val" ]] && { missing+=("$key"); continue; }
  printf '%s=%s\n' "$key" "$val" >> "$tmp"
done

if (( ${#missing[@]} )); then
  echo "missing in .env: ${missing[*]}" >&2
  exit 1
fi

if [[ "$OVERLAY" == "prod" ]]; then
  # Committed encrypted; decrypted only inside the deploy job, never left on disk.
  mv "$tmp" "$OUT_DIR/secrets.env"
  trap - EXIT
  sops -e "$OUT_DIR/secrets.env" > "$OUT_DIR/secrets.enc.yaml"
  rm -f "$OUT_DIR/secrets.env"
  echo "wrote $OUT_DIR/secrets.enc.yaml (encrypted, safe to commit)"
  echo "the deploy job runs: sops -d secrets.enc.yaml > secrets.env"
else
  mv "$tmp" "$OUT_DIR/secrets.env"
  trap - EXIT
  echo "wrote $OUT_DIR/secrets.env (PLAINTEXT — gitignored, do not commit)"
fi
