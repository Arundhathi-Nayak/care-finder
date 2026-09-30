"""Chat tools. Each returns compact JSON-safe dicts built from the repository + forecasting.
Public output uses availability LEVELS only, never exact stock counts."""
import difflib
import re

from . import config
from .availability import availability_level
from .forecasting import forecast
from .geo import haversine_km, maps_url
from .repository import get_repo

# alias (normalised) -> token that must appear in the canonical medicine name
ALIASES = {
    "paracetamol": "paracetamol", "dolo": "paracetamol", "crocin": "paracetamol",
    "calpol": "paracetamol", "pcm": "paracetamol", "acetaminophen": "paracetamol",
    "ors": "ors", "oral rehydration": "ors", "electral": "ors",
    "amoxicillin": "amoxicillin", "amoxil": "amoxicillin",
    "metformin": "metformin", "glycomet": "metformin",
    "oxytocin": "oxytocin", "pitocin": "oxytocin",
    "rabies": "rabies", "anti rabies": "rabies", "arv": "rabies", "dog bite vaccine": "rabies",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def resolve_medicine(query: str) -> str | None:
    """Map free text ('dolo', 'ORS', 'paracetmol') to a canonical name from config.USAGE."""
    q = _norm(query)
    if not q:
        return None
    token = None
    for alias in sorted(ALIASES, key=len, reverse=True):          # longest alias first
        if re.search(rf"\b{re.escape(alias)}\b", q):
            token = ALIASES[alias]
            break
    if token is None:                                             # typo tolerance
        for word in q.split():
            m = difflib.get_close_matches(word, list(ALIASES), n=1, cutoff=0.8)
            if m:
                token = ALIASES[m[0]]
                break
    if token is None:
        return None
    for name in config.USAGE:
        if token in _norm(name):
            return name
    return None


def _level(item: dict) -> str:
    rate = config.USAGE.get(item["medicine_name"], 0.5)
    f = forecast(item["footfall_history"], item["current_stock"], rate)
    return availability_level(item["current_stock"], f["status"])


def _facility(phc: dict, distance: float | None) -> dict:
    return {
        "phc_id": phc["phc_id"], "name": phc["phc_name"], "district": phc["district"],
        "state": phc["state"],
        "distance_km": round(distance, 1) if distance is not None else None,
        "beds_available": phc["beds_available"], "beds_total": phc["beds_total"],
        "doctors_present": phc["doctors_present"], "doctors_total": phc["doctors_total"],
        "maps_url": maps_url(phc["lat"], phc["lng"]),
    }


def _with_distance(phcs, lat, lng):
    if lat is None or lng is None:
        return [(p, None) for p in phcs]
    return [(p, haversine_km(lat, lng, p["lat"], p["lng"])) for p in phcs]


def _match_district(phcs, district):
    d = _norm(district)
    return [p for p in phcs if _norm(p["district"]) == d]


def _clamp(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


# ---------------- the four tools ----------------
def find_nearest_phcs(lat=None, lng=None, radius_km=50, limit=3) -> dict:
    if lat is None or lng is None:
        return {"error": "location_needed"}
    radius = _clamp(radius_km, 1, 200, 50)
    limit = _clamp(limit, 1, 5, 3)
    rows = [(p, d) for p, d in _with_distance(get_repo().get_all_phcs(), lat, lng) if d <= radius]
    rows.sort(key=lambda r: r[1])
    return {"radius_km": radius, "facilities": [_facility(p, d) for p, d in rows[:limit]]}


def get_medicine_availability(medicine_name, lat=None, lng=None, district=None, limit=5) -> dict:
    if lat is None and district is None:
        return {"error": "location_needed"}
    canonical = resolve_medicine(medicine_name or "")
    if canonical is None:
        return {"error": "unknown_medicine", "known_medicines": list(config.USAGE)}
    limit = _clamp(limit, 1, 5, 5)
    repo = get_repo()
    phcs = {p["phc_id"]: p for p in repo.get_all_phcs()}
    if lat is None and district:
        allowed = {p["phc_id"] for p in _match_district(phcs.values(), district)}
    else:
        allowed = set(phcs)
    rows = []
    for item in repo.get_all_inventory():
        if item["medicine_name"] != canonical or item["phc_id"] not in allowed:
            continue
        p = phcs.get(item["phc_id"])
        if p is None:
            continue
        dist = haversine_km(lat, lng, p["lat"], p["lng"]) if lat is not None and lng is not None else None
        fac = _facility(p, dist)
        fac["medicines"] = [{"name": canonical, "availability": _level(item)}]
        rows.append(fac)
    order = {"IN_STOCK": 0, "LOW": 1, "OUT": 2}
    rows.sort(key=lambda f: (f["distance_km"] is None, f["distance_km"] or 0,
                             order[f["medicines"][0]["availability"]], f["name"]))
    return {"medicine": canonical, "facilities": rows[:limit]}


def get_phc_details(phc_id: str) -> dict:
    repo = get_repo()
    phc = repo.get_phc(phc_id)
    if phc is None:
        return {"error": "not_found"}
    fac = _facility(phc, None)
    fac["medicines"] = [{"name": i["medicine_name"], "availability": _level(i)}
                        for i in repo.get_inventory_for_phc(phc_id)]
    return {"facilities": [fac]}


def list_phcs_by_district(district: str) -> dict:
    phcs = get_repo().get_all_phcs()
    rows = _match_district(phcs, district or "")
    if not rows:
        return {"error": "unknown_district",
                "known_districts": sorted({p["district"] for p in phcs})}
    return {"district": rows[0]["district"], "facilities": [_facility(p, None) for p in rows[:5]]}


# ---------------- dispatcher used by the Gemini loop and mock mode ----------------
TOOLS = {
    "find_nearest_phcs": find_nearest_phcs,
    "get_medicine_availability": get_medicine_availability,
    "get_phc_details": get_phc_details,
    "list_phcs_by_district": list_phcs_by_district,
}


def run_tool(name: str, args: dict | None) -> dict:
    fn = TOOLS.get(name)
    if fn is None:
        return {"error": "unknown_tool"}
    try:
        return fn(**(args or {}))
    except TypeError:          # model sent unexpected/missing arguments
        return {"error": "bad_arguments"}