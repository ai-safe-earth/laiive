"""Test environment setup.

The root .env carries a real INTERNAL_API_KEY, and the internal-auth middleware
installs at import time of agent.api — so it must be blanked *before* any test
module imports the app, or every request 403s. Process env beats env_file in
pydantic-settings. Enforcement itself is covered in shared's
test_internal_auth.py.
"""

import os

os.environ["INTERNAL_API_KEY"] = ""
# Same trap: a real SUPABASE_URL in the root .env would make every endpoint
# test fire a live eval_records insert. Empty URL no-ops the write.
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
# Same trap once more: a dev box with PHOENIX_ENABLED=true in the root .env
# would instrument the openai module for the whole suite and ship test spans to
# whatever collector is configured, mixed in with real turns.
os.environ["PHOENIX_ENABLED"] = "false"
