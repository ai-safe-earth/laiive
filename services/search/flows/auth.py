"""Admin JWT for gateway calls — Supabase password grant, minted per run.

Configuration resolution: environment first (a local run picks up the root
`.env` values already in the shell), then Prefect Cloud — Variables for the
non-secret settings, Secret blocks for the service-account credentials.
Nothing lives in the repo.
"""

import os
from typing import cast

import httpx

AUTH_TIMEOUT = 30.0

# env key -> Prefect Variable name (non-secret settings)
_VARIABLES = {
    "GATEWAY_URL": "laiive_gateway_url",
    "SUPABASE_URL": "laiive_supabase_url",
    "SUPABASE_PUBLISHABLE_KEY": "laiive_supabase_publishable_key",
}

# env key -> Prefect Secret block name (credentials)
_SECRETS = {
    "SUPABASE_ADMIN_EMAIL": "supabase-admin-email",
    "SUPABASE_ADMIN_PASSWORD": "supabase-admin-password",  # pragma: allowlist secret
}


def _setting(env_key: str) -> str:
    value = os.environ.get(env_key)
    if value:
        return value
    name = _VARIABLES[env_key]
    from prefect.variables import Variable

    value = cast(str | None, Variable.get(name, default=None))
    if not value:
        raise RuntimeError(
            f"Missing setting: set env {env_key} or Prefect Variable {name}"
        )
    return value


def _secret(env_key: str) -> str:
    value = os.environ.get(env_key)
    if value:
        return value
    name = _SECRETS[env_key]
    from prefect.blocks.system import Secret

    try:
        block = cast(Secret, Secret.load(name))
    except ValueError as e:
        raise RuntimeError(
            f"Missing credential: set env {env_key} or Prefect Secret block {name}"
        ) from e
    return cast(str, block.get())


def gateway_url() -> str:
    return _setting("GATEWAY_URL").rstrip("/")


def get_admin_jwt() -> str:
    """Password grant for the admin service account -> short-lived JWT.

    The custom access token hook stamps `user_role: admin` on it, which is
    what the gateway's requireRole("admin") reads.
    """
    supabase_url = _setting("SUPABASE_URL").rstrip("/")
    response = httpx.post(
        f"{supabase_url}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": _setting("SUPABASE_PUBLISHABLE_KEY")},
        json={
            "email": _secret("SUPABASE_ADMIN_EMAIL"),
            "password": _secret("SUPABASE_ADMIN_PASSWORD"),
        },
        timeout=AUTH_TIMEOUT,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Password grant succeeded but returned no access_token")
    return cast(str, token)
