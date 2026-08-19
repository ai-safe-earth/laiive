"""Bind one dual-stack listener, then exec uvicorn onto it.

Every deploy target wants a different address family and Python gives exactly
one at a time. `asyncio.create_server` sets `IPV6_V6ONLY` on any AF_INET6
listener, so `uvicorn --host ::` refuses IPv4 outright and `--host 0.0.0.0`
refuses IPv6. Both were verified, and both break something:

- Fly's 6PN private network is IPv6-only, and `<app>.internal` resolves to an
  AAAA record — so the gateway can only reach a service that listens on `::`.
- Fly's machine health checks arrive over IPv4: a `::`-only listener answers
  them with ECONNREFUSED and the machine never becomes healthy.
- Compose's network is IPv4, so under compose a `::`-only listener means both
  the healthchecks and every gateway→service call fail.

A socket opened here with `IPV6_V6ONLY` off accepts both families (IPv4 peers
arrive as v4-mapped addresses), and uvicorn adopts it with `--fd`. `execv`
keeps uvicorn as PID 1, which is what makes its graceful-shutdown window work.

    python -m laiive_shared.serve agent.api:app 8002 [uvicorn args...]
"""

import os
import socket
import sys

UVICORN = os.environ.get("UVICORN_BIN", "/app/.venv/bin/uvicorn")

# Deep enough that a burst of connections queues rather than being refused
# while the app is busy; the kernel caps it at net.core.somaxconn anyway.
BACKLOG = 2048


def dual_stack_socket(port: int) -> socket.socket:
    """A listening socket on every local address, both families where possible.

    Falls back to IPv4 only where the runtime has no IPv6 at all (some CI
    containers), because refusing to start would be worse than one family.
    """
    try:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        sock.bind(("::", port))
    except OSError:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", port))
    sock.listen(BACKLOG)
    sock.set_inheritable(True)
    return sock


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        sys.exit("usage: python -m laiive_shared.serve <app> <port> [uvicorn args]")
    app, port, extra = args[0], int(args[1]), args[2:]

    sock = dual_stack_socket(port)
    os.execv(UVICORN, [UVICORN, app, "--fd", str(sock.fileno()), *extra])


if __name__ == "__main__":
    main()
