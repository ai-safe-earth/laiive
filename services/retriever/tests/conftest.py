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


# ── the frozen graph (evals: retrieval + cypher) ─────────────────────────────
#
# Session-scoped: seeding writes eighteen events through the real writer, which
# is a second or two, and every case reads the same graph without changing it.
# Skipped rather than failed when the container is not running — `make
# test-graph-up` starts it, and CI runs it as a service container.
import pytest  # noqa: E402

from tests import graph_fixture  # noqa: E402


@pytest.fixture(scope="session")
def frozen_graph():
    if not graph_fixture.reachable():
        pytest.skip(f"no test graph at {graph_fixture.TEST_URI} — `make test-graph-up`")

    # The read client asks for `settings.neo4j_database`, which is the Aura
    # database's name ("2099d44c") — the container serves plain "neo4j", so
    # every read here would be a DatabaseNotFound without this.
    from config import settings

    real_database = settings.neo4j_database
    settings.neo4j_database = graph_fixture.TEST_DATABASE

    driver = graph_fixture.driver()
    try:
        with driver.session() as session:
            graph_fixture.apply_schema(session)
            uids = graph_fixture.seed(session)
        yield graph_fixture.read_client(driver), uids
    finally:
        driver.close()
        settings.neo4j_database = real_database
