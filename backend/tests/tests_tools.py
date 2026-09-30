import pytest

from app import tools
from app.repository import set_repo
from tests.fakes import FakeRepo

HEBRI = (13.48, 75.01)


@pytest.fixture(autouse=True)
def fake_repo():
    set_repo(FakeRepo())
    yield
    set_repo(None)


@pytest.mark.parametrize("q,expected", [
    ("paracetamol", "Paracetamol 500mg"),
    ("Dolo 650", "Paracetamol 500mg"),
    ("do you have PCM?", "Paracetamol 500mg"),
    ("paracetmol", "Paracetamol 500mg"),      # typo
    ("ORS", "ORS Sachets"),
    ("anti-rabies vaccine", "Anti-Rabies Vaccine"),
    ("dog bite vaccine", "Anti-Rabies Vaccine"),
])
def test_resolve_medicine(q, expected):
    assert tools.resolve_medicine(q) == expected


@pytest.mark.parametrize("q", ["", "unicorn dust", "cors"])
def test_resolve_none(q):
    assert tools.resolve_medicine(q) is None


def test_nearest_sorted_and_radius():
    r = tools.find_nearest_phcs(*HEBRI, radius_km=50, limit=3)
    names = [f["name"] for f in r["facilities"]]
    assert names == ["Hebri PHC", "Karkala CHC"]          # Paud is far outside 50 km
    assert r["facilities"][0]["distance_km"] < r["facilities"][1]["distance_km"]
    assert r["facilities"][0]["maps_url"].startswith("https://www.google.com/maps")


def test_nearest_needs_location():
    assert tools.find_nearest_phcs() == {"error": "location_needed"}


def test_medicine_levels_no_counts():
    r = tools.get_medicine_availability("dolo", *HEBRI)
    by_id = {f["phc_id"]: f["medicines"][0]["availability"] for f in r["facilities"]}
    assert by_id["PHC001"] == "LOW"           # hero row: CRITICAL -> LOW
    assert by_id["PHC002"] == "IN_STOCK"
    assert "current_stock" not in str(r)


def test_out_of_stock():
    r = tools.get_medicine_availability("ors", *HEBRI)
    assert r["facilities"][0]["medicines"][0]["availability"] == "OUT"


def test_medicine_by_district_only():
    r = tools.get_medicine_availability("paracetamol", district="udupi")
    assert {f["phc_id"] for f in r["facilities"]} == {"PHC001", "PHC002"}
    assert all(f["distance_km"] is None for f in r["facilities"])


def test_medicine_location_needed_and_unknown():
    assert tools.get_medicine_availability("paracetamol")["error"] == "location_needed"
    assert tools.get_medicine_availability("unicorn dust", district="Udupi")["error"] == "unknown_medicine"


def test_phc_details_and_not_found():
    r = tools.get_phc_details("PHC001")["facilities"][0]
    assert {m["name"] for m in r["medicines"]} == {"Paracetamol 500mg", "ORS Sachets"}
    assert tools.get_phc_details("NOPE") == {"error": "not_found"}


def test_district_listing():
    assert len(tools.list_phcs_by_district("Udupi")["facilities"]) == 2
    bad = tools.list_phcs_by_district("Mars")
    assert bad["error"] == "unknown_district" and "Udupi" in bad["known_districts"]


def test_run_tool_is_safe():
    assert tools.run_tool("nope", {}) == {"error": "unknown_tool"}
    assert tools.run_tool("find_nearest_phcs", {"bogus": 1}) == {"error": "bad_arguments"}
    assert tools.run_tool("find_nearest_phcs", {"lat": 13.48, "lng": 75.01})["facilities"]