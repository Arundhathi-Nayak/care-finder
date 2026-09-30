import pytest
from fastapi.testclient import TestClient

from app import repository
from tests.fakes import FakeRepo


@pytest.fixture(autouse=True)
def no_gemini(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture
def repo():
    r = FakeRepo()
    repository.set_repo(r)
    yield r
    repository.set_repo(None)


@pytest.fixture
def client(repo):
    from app.main import app
    return TestClient(app)  # not used as a context manager -> lifespan (Firestore init) is skipped
