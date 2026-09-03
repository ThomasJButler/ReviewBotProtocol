"""The 'fully local' proof, part one: a socket-level guard.

Patching an HTTP client proves nothing here because the process contains
several HTTP stacks. The guard sits below all of them. The first two tests
prove the guard itself works; the end-to-end review test is skipped until the
Ollama pipeline exists (Phase 4 step 8) and REVIEWBOT_E2E=1 is set."""

import os
import socket

import pytest


class EgressBlocked(RuntimeError):
    pass


@pytest.fixture
def no_egress(monkeypatch):
    """Allow only loopback and an explicit allow-list of hosts."""
    allowed_hosts = {"127.0.0.1", "localhost", "::1"}
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def guarded_getaddrinfo(host, *args, **kwargs):
        if str(host) not in allowed_hosts:
            raise EgressBlocked(f"DNS lookup for {host!r} blocked by the egress guard")
        return real_getaddrinfo(host, *args, **kwargs)

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in allowed_hosts:
            raise EgressBlocked(f"connect to {host!r} blocked by the egress guard")
        return real_connect(self, address)

    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    return allowed_hosts


def test_guard_blocks_a_public_host(no_egress):
    with pytest.raises(EgressBlocked):
        socket.create_connection(("1.1.1.1", 53), timeout=1)


def test_guard_allows_loopback(no_egress):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass
    finally:
        srv.close()


def test_no_cloud_sdk_is_importable_after_migration():
    """Documents the target state. Today these modules ARE importable, which is the point."""
    pytest.xfail("Phase 4 step 1: openai, langchain_openai and sentry_sdk are removed from the runtime environment")


@pytest.mark.e2e
@pytest.mark.skipif(os.environ.get("REVIEWBOT_E2E") != "1", reason="set REVIEWBOT_E2E=1 with Ollama running")
def test_full_review_completes_with_egress_blocked(no_egress):
    pytest.xfail("Phase 4 step 8: full review through the local pipeline against a fake GitHub server")
