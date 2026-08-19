"""The listener has to answer on both families — that is its whole reason to exist."""

import socket

import pytest
from laiive_shared.serve import dual_stack_socket


@pytest.fixture
def listener():
    sock = dual_stack_socket(0)
    yield sock
    sock.close()


def test_binds_both_families(listener):
    if listener.family != socket.AF_INET6:
        pytest.skip("no IPv6 on this runtime; the v4 fallback is all there is")
    assert listener.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY) == 0


def test_accepts_an_ipv4_client(listener):
    """The case that broke Fly's health checks and every compose call."""
    port = listener.getsockname()[1]
    with socket.create_connection(("127.0.0.1", port), timeout=5):
        conn, _ = listener.accept()
        conn.close()


def test_accepts_an_ipv6_client(listener):
    """The case 6PN needs: one service reaching another over <app>.internal."""
    if listener.family != socket.AF_INET6:
        pytest.skip("no IPv6 on this runtime")
    port = listener.getsockname()[1]
    with socket.create_connection(("::1", port), timeout=5):
        conn, _ = listener.accept()
        conn.close()


def test_socket_survives_exec(listener):
    """uvicorn adopts it by number after execv, so it must not be CLOEXEC."""
    assert listener.get_inheritable()
