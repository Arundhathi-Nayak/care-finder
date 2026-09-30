import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ratelimit import RateLimiter, limiter
from app.repository import set_repo
from tests.fakes import ChatFakeRepo

client = TestClient(app)  # not used as a context manager, so no startup events run
LOC = {"lat": 13.48, "lng": 75.01}


class BrokenRepo:
    def __getattr__(self, name):
        def boom(*a, **k):
            raise RuntimeError("firestore down")
        return boom


@pytest.fixture(autouse=True)
def setup():
    set_repo(ChatFakeRepo())
    limiter.reset()
    yield
    set_repo(None)


def post(msg, **kw):
    return client.post("/api/v1/chat", json={"message": msg, **kw})


def test_nearest_sorted_cards():
    d = post("nearest PHC", location=LOC).json()
    assert d["source"] == "mock" and d["emergency"] is False
    assert [c["phc_id"] for c in d["cards"]] == ["PHC001", "PHC002"]
    assert d["cards"][0]["maps_url"].startswith("https://www.google.com/maps")


def test_medicine_levels_only():
    d = post("is paracetamol available?", location=LOC).json()
    first = d["cards"][0]
    assert first["phc_id"] == "PHC001"
    assert first["medicines"] == [{"name": "Paracetamol 500mg", "availability": "LOW"}]
    assert "current_stock" not in str(d)


def test_beds_and_doctors():
    assert "2 of 6" in post("Beds near me", location=LOC).json()["reply"]
    assert "no doctor present" in post("Doctors available now", location=LOC).json()["reply"]


def test_no_location_asks():
    d = post("nearest PHC").json()
    assert d["cards"] == [] and "location" in d["reply"].lower()
    assert "Udupi" in d["suggestions"]


def test_district_hint_and_district_in_text():
    ids = {c["phc_id"] for c in post("nearest PHC", district_hint="Udupi").json()["cards"]}
    assert ids == {"PHC001", "PHC002"}
    assert [c["phc_id"] for c in post("PHCs in Pune").json()["cards"]] == ["PHC003"]


def test_phc_followup():
    d = post("Tell me about Hebri PHC", location=LOC).json()
    assert d["cards"][0]["phc_id"] == "PHC001"
    assert len(d["cards"][0]["medicines"]) == 2


def test_which_medicine_and_help():
    assert "Paracetamol" in post("Which medicine is in stock?", location=LOC).json()["reply"]
    d = post("hello").json()
    assert d["cards"] == [] and d["suggestions"]


@pytest.mark.parametrize("msg", ["my father has chest pain", "मुझे सीने में दर्द है", "ನನಗೆ ಎದೆ ನೋವು ಇದೆ"])
def test_emergency(msg):
    d = post(msg, location=LOC).json()
    assert d["emergency"] is True and "108" in d["reply"] and "112" in d["reply"]
    assert d["cards"]


def test_emergency_survives_repo_failure():
    set_repo(BrokenRepo())
    r = post("chest pain", location=LOC)
    assert r.status_code == 200 and r.json()["emergency"] is True and r.json()["cards"] == []


def test_validation():
    assert post("").status_code == 422
    assert post("hi", location={"lat": 999, "lng": 0}).status_code == 422


def test_rate_limit_http_and_emergency_exempt():
    for _ in range(20):
        assert post("hello").status_code == 200
    r = post("hello")
    assert r.status_code == 429 and r.json()["detail"]
    assert post("chest pain").status_code == 200   # emergencies are never blocked


def test_limiter_window():
    rl = RateLimiter(limit=2, window=60)
    assert rl.allow("a", now=0) and rl.allow("a", now=1)
    assert not rl.allow("a", now=2)
    assert rl.allow("b", now=2)             # separate key
    assert rl.allow("a", now=61)            # window passed