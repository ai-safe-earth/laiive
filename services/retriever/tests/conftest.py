"""Test environment setup.

The root .env carries a real INTERNAL_API_KEY, and the internal-auth middleware
installs at import time of agent.api — so it must be blanked *before* any test
module imports the app, or every request 403s. Process env beats env_file in
pydantic-settings. Enforcement itself is covered in shared's
test_internal_auth.py.
"""

import os

os.environ["INTERNAL_API_KEY"] = ""
