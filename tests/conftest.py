import socket

import pytest
from pydantic import SecretStr

from uranus_research_service.config import Settings
from uranus_research_service.version import ENCODER_EXPECTED

KEY = "synthetic-service-key-for-tests-0123456789"


@pytest.fixture
def settings():
    return Settings(
        api_key=SecretStr(KEY), planner_api_key=SecretStr(KEY), encoder_api_key=SecretStr(KEY)
    )


@pytest.fixture
def encoder_version():
    return {
        **ENCODER_EXPECTED,
        "service_version": "0.2.0",
        "backend": "torch",
        "runtime": "synthetic-test-runtime",
    }


@pytest.fixture
def encoder_ready(encoder_version):
    return {
        k: v
        for k, v in encoder_version.items()
        if k not in {"model_repository", "chunk_version", "service_version"}
    } | {"status": "ready"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch, request):
    if request.node.get_closest_marker("integration"):
        return

    def denied(*args, **kwargs):
        raise AssertionError("Unit tests must not access real networks")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
