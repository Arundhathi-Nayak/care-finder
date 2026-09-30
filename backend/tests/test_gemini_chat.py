from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from google.genai import types

from app import gemini_chat
from app.main import app
from app.ratelimit import limiter
from app.repository import set_repo
from tests.fakes import ChatFakeRepo

client = TestClient(app)
LOC = {"lat": 13.48, "lng": 75.01}


class FakeCall:
    def __init__(self, name, args):
        self.name, self.args = name, args


class FakeResp:
    def __init__(self, calls=None, text=None):
        self.function_calls, self.text = calls, text
        self.candidates = [SimpleNamespace(content=types.Content(role="model", parts=[types.Part(text=text or "call")]))]


class FakeClient:
    def __init__(self, responses):
        self.models, self._r, self.seen = self, list(responses), []

    def generate_content(self, model, contents, config):
        self.seen.append((list(contents), config))
        return self._r.pop(0)


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    set_repo(ChatFakeRepo())
    limiter.reset()
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    yield
    set_repo(None)


def post(msg, **kw):
    return client.post("/api/v1/chat", json={"message": msg, **kw}).json()


def test_tool_loop_builds_cards_and_hides_coordinates(monkeypatch):
    fake = FakeClient([FakeResp(calls=[FakeCall("find_nearest_phcs", {"lat": 1, "lng": 2, "limit": 2})]),
                       FakeResp(text="Hebri PHC is closest.")])
    monkeypatch.setattr(gemini_chat, "_client", lambda: fake)
    d = post("nearest PHC", location=LOC)
    assert d["source"] == "gemini" and d["reply"] == "Hebri PHC is closest."
    assert [c["phc_id"] for c in d["cards"]] == ["PHC001", "PHC002"]      # server location won, not lat=1
    everything = " ".join(str(c) + str(cfg) for c, cfg in fake.seen)
    assert "13.48" not in everything and "75.01" not in everything


def test_district_hint_injected(monkeypatch):
    fake = FakeClient([FakeResp(calls=[FakeCall("list_phcs_by_district", {"district": "Pune"})]),
                       FakeResp(text="ok")])
    monkeypatch.setattr(gemini_chat, "_client", lambda: fake)
    d = post("show facilities", district_hint="Pune")
    assert [c["phc_id"] for c in d["cards"]] == ["PHC003"]


def test_unknown_tool_does_not_crash(monkeypatch):
    fake = FakeClient([FakeResp(calls=[FakeCall("drop_database", {})]), FakeResp(text="Sorry.")])
    monkeypatch.setattr(gemini_chat, "_client", lambda: fake)
    assert post("hi")["source"] == "gemini"


def test_failure_falls_back_to_mock(monkeypatch):
    def boom():
        raise RuntimeError("api down")
    monkeypatch.setattr(gemini_chat, "_client", boom)
    d = post("nearest PHC", location=LOC)
    assert d["source"] == "mock" and d["cards"]


def test_endless_tool_calls_fall_back(monkeypatch):
    fake = FakeClient([FakeResp(calls=[FakeCall("find_nearest_phcs", {})]) for _ in range(10)])
    monkeypatch.setattr(gemini_chat, "_client", lambda: fake)
    assert post("nearest PHC", location=LOC)["source"] == "mock"


def test_emergency_never_calls_gemini(monkeypatch):
    def boom():
        raise AssertionError("LLM must not be called")
    monkeypatch.setattr(gemini_chat, "_client", boom)
    d = post("chest pain", location=LOC)
    assert d["emergency"] is True and "108" in d["reply"]