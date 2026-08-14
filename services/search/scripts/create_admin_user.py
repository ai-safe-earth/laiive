"""Provision the Supabase admin service account the Prefect flows sign in as.

Owner-run (writes to Supabase):

    cd services/search
    uv run --env-file ../../.env python scripts/create_admin_user.py \
        --email search-bot@laiive.internal

Creates the user via the auth admin API (email pre-confirmed, generated
password printed once) and upserts user_roles.role='admin' through PostgREST
with the service-role key — the existing custom_access_token_hook then stamps
`user_role: admin` on its JWTs with no new machinery. Idempotent: an existing
user gets its password reset and its role re-asserted.
"""

import argparse
import os
import secrets
import sys

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--password",
        default=None,
        help="omit to generate one (printed once at the end)",
    )
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not service_key:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set (use --env-file)")

    password = args.password or secrets.token_urlsafe(24)
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}

    created = httpx.post(
        f"{url}/auth/v1/admin/users",
        headers=headers,
        json={"email": args.email, "password": password, "email_confirm": True},
        timeout=30,
    )
    if created.status_code in (200, 201):
        user_id = created.json()["id"]
        print(f"created user {args.email} -> {user_id}")
    elif created.status_code == 422:
        listing = httpx.get(
            f"{url}/auth/v1/admin/users",
            headers=headers,
            params={"page": 1, "per_page": 100},
            timeout=30,
        )
        listing.raise_for_status()
        match = [u for u in listing.json()["users"] if u["email"] == args.email]
        if not match:
            sys.exit(f"user exists per 422 but not found in listing: {created.text}")
        user_id = match[0]["id"]
        httpx.put(
            f"{url}/auth/v1/admin/users/{user_id}",
            headers=headers,
            json={"password": password},
            timeout=30,
        ).raise_for_status()
        print(f"user {args.email} already existed -> {user_id}; password reset")
    else:
        sys.exit(f"create failed {created.status_code}: {created.text}")

    role = httpx.post(
        f"{url}/rest/v1/user_roles",
        headers={
            **headers,
            "Prefer": "resolution=merge-duplicates",
            "Content-Type": "application/json",
        },
        params={"on_conflict": "user_id"},
        json={"user_id": user_id, "role": "admin"},
        timeout=30,
    )
    if role.status_code not in (200, 201, 204):
        sys.exit(f"user_roles upsert failed {role.status_code}: {role.text}")
    print("user_roles.role = admin")

    print("\nPrefect Secret blocks to create (or local env for a dev run):")
    print(f"  supabase-admin-email    / SUPABASE_ADMIN_EMAIL    = {args.email}")
    print(f"  supabase-admin-password / SUPABASE_ADMIN_PASSWORD = {password}")
    print("\nNote: the role lands on the JWT via the access token hook; a token")
    print("minted before this run would not carry it — flows mint per run, fine.")


if __name__ == "__main__":
    main()
