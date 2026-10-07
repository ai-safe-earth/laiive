"""setup_tracing must never be able to stop a service booting.

That is the whole contract: it is called at module scope in two api.py files,
so anything it raises is an import error, not a degraded feature. The three
ways it can go wrong are a missing wheel, an unreachable collector and a
malformed endpoint — all of them have to come back False rather than throw.
"""

from unittest.mock import patch

from laiive_shared.tracing import _with_otlp_path, setup_tracing


def test_disabled_is_a_noop_and_imports_nothing():
    """The default path. If this ever imports phoenix, a service without the
    tracing wheels stops booting the moment someone leaves the flag off."""
    with patch.dict("sys.modules", {"phoenix.otel": None}):
        assert setup_tracing("retriever", enabled=False, endpoint="http://x") is False


def test_unreachable_collector_does_not_raise():
    """A registered exporter is lazy — nothing dials the collector here — but
    pin it anyway, because this is the case that would take production down."""
    assert (
        setup_tracing(
            "retriever",
            enabled=True,
            endpoint="http://127.0.0.1:1/v1/traces",
        )
        is True
    )


def test_missing_dependency_is_reported_not_raised():
    def _boom(*_args, **_kwargs):
        raise ModuleNotFoundError("No module named 'phoenix'")

    with patch("laiive_shared.tracing.logger") as log:
        with patch.dict("sys.modules", {"phoenix": None, "phoenix.otel": None}):
            with patch("builtins.__import__", side_effect=_boom):
                assert (
                    setup_tracing("pusher", enabled=True, endpoint="http://x") is False
                )
        assert log.warning.called


def test_malformed_endpoint_is_survivable():
    assert isinstance(setup_tracing("pusher", enabled=True, endpoint="not-a-url"), bool)


def test_bare_base_url_gets_the_otlp_path():
    """The form everyone types. Without a path phoenix.otel cannot tell HTTP
    from gRPC and warns on every boot."""
    assert _with_otlp_path("http://localhost:6006") == "http://localhost:6006/v1/traces"
    assert _with_otlp_path("http://phoenix:6006/") == "http://phoenix:6006/v1/traces"


def test_an_explicit_path_is_left_alone():
    """Phoenix Cloud hands out a full endpoint; appending to it would 404."""
    for endpoint in (
        "https://app.phoenix.arize.com/s/laiive/v1/traces",
        "http://collector:4317/some/path",
    ):
        assert _with_otlp_path(endpoint) == endpoint


def test_a_non_url_is_handed_over_as_typed():
    assert _with_otlp_path("not-a-url") == "not-a-url"
