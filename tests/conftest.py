import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# The plugin runs from its root directory, so the tests do the same.
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, status_code: int, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeHTTP:
    """Replaces requests.request. It records each call and returns queued responses."""

    def __init__(self):
        self.calls: list[dict] = []
        self.responses: list = []

    def reply(self, status_code: int, body) -> None:
        self.responses.append(FakeResponse(status_code, body))

    def raise_error(self, error: Exception) -> None:
        self.responses.append(error)

    def __call__(self, method, url, headers=None, json=None, timeout=None):
        self.calls.append({"method": method, "url": url, "headers": headers, "json": json, "timeout": timeout})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def http(monkeypatch):
    import cloro_api

    fake = FakeHTTP()
    monkeypatch.setattr(cloro_api.requests, "request", fake)
    return fake
