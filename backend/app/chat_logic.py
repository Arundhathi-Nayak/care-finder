"""Rule-based chat (mock mode) and the emergency reply. Both use the same tools as Gemini will."""
import re
import unicodedata

from app import config, tools
from .availability import data_as_of
from .cards import build_cards
from .repository import get_repo
from .safety import emergency_message
from .schemas import ChatRequest, ChatResponse

DEFAULT_SUGGESTIONS = ["Nearest PHC", "Is paracetamol available?", "Beds near me", "Doctors available now"]
LEVEL_TEXT = {"IN_STOCK": "in stock", "LOW": "low stock", "OUT": "out of stock"}

BED_WORDS = ("bed", "बेड", "बिस्तर", "खाट", "ಹಾಸಿಗೆ")
DOCTOR_WORDS = ("doctor", "डॉक्टर", "डाक्टर", "वैद्य", "ವೈದ್ಯ", "ಡಾಕ್ಟರ್")
MED_WORDS = ("medicine", "tablet", "drug", "stock", "syrup", "दवा", "औषध", "ಔಷಧ", "ಮಾತ್ರೆ")
NEAR_WORDS = ("near", "phc", "chc", "hospital", "clinic", "health cent", "अस्पताल", "नज़दीक", "नजदीक",
              "रुग्णालय", "जवळ", "ಆಸ್ಪತ್ರೆ", "ಹತ್ತಿರ")


def _has(text: str, words) -> bool:
    return any(w in text for w in words)


def _districts() -> list[str]:
    return sorted({p["district"] for p in get_repo().get_all_phcs()})


def _district_from_text(norm: str) -> str | None:
    for d in sorted(_districts(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(tools._norm(d))}\b", norm):
            return d
    return None


def _phc_from_text(norm: str) -> dict | None:
    for p in get_repo().get_all_phcs():
        if tools._norm(p["phc_name"]) in norm:
            return p
    return None


def _resp(reply: str, results: list[dict], suggestions: list[str] | None = None) -> ChatResponse:
    return ChatResponse(reply=reply, source="mock", data_as_of=data_as_of(),
                        cards=build_cards(results), suggestions=suggestions or DEFAULT_SUGGESTIONS)


def _need_location() -> ChatResponse:
    return _resp("Please share your location with the 'Use my location' button, or choose a district "
                 "(for example " + " or ".join(_districts()) + "), and I will look up nearby facilities.",
                 [], _districts())


def _error_reply(res: dict) -> ChatResponse:
    if res.get("error") == "location_needed":
        return _need_location()
    if res.get("error") == "unknown_district":
        return _resp("I don't have data for that district. Available: "
                     + ", ".join(res.get("known_districts", [])) + ".", [], res.get("known_districts"))
    return _resp("Sorry, I could not find that. Please try another question.", [])


def _line(f: dict, kind: str) -> str:
    name = f["name"] + (f" ({f['distance_km']} km)" if f.get("distance_km") is not None else "")
    if kind == "beds":
        return f"{name}: {f['beds_available']} of {f['beds_total']} beds free"
    if kind == "doctors":
        if f["doctors_present"] == 0:
            return f"{name}: no doctor present"
        return f"{name}: {f['doctors_present']} of {f['doctors_total']} doctors present"
    if kind == "medicine":
        return f"{name}: {LEVEL_TEXT[f['medicines'][0]['availability']]}"
    return name


def _list_reply(res: dict, kind: str, medicine: str | None = None) -> ChatResponse:
    if "error" in res:
        return _error_reply(res)
    facs = res.get("facilities", [])
    if not facs:
        return _resp("I could not find any facility within 50 km. If it is urgent, call 108 or 112.", [])
    head = {"nearest": "Nearest facilities, closest first: ", "beds": "Beds available: ",
            "doctors": "Doctors present now: ",
            "medicine": f"{medicine} availability, closest first: "}[kind]
    return _resp(head + "; ".join(_line(f, kind) for f in facs) + ".", [res])


def mock_reply(req: ChatRequest) -> ChatResponse:
    low = unicodedata.normalize("NFC", req.message).lower()
    norm = tools._norm(req.message)  # ASCII-only: use for names, not for Hindi/Kannada keywords

    district_text = _district_from_text(norm)
    use_loc = req.location is not None and district_text is None
    lat = req.location.lat if use_loc else None
    lng = req.location.lng if use_loc else None
    district = district_text or req.district_hint
    located = use_loc or bool(district)

    phc = _phc_from_text(norm)
    if phc:  # e.g. the "Ask about this PHC" button
        res = tools.get_phc_details(phc["phc_id"])
        if "error" in res:
            return _error_reply(res)
        f = res["facilities"][0]
        meds = ", ".join(f"{m['name']} {LEVEL_TEXT[m['availability']]}" for m in f["medicines"])
        doc = "no doctor present" if f["doctors_present"] == 0 else \
            f"{f['doctors_present']} of {f['doctors_total']} doctors present"
        return _resp(f"{f['name']} ({f['district']}): {f['beds_available']} of {f['beds_total']} beds free, "
                     f"{doc}. Medicines: {meds}.", [res])

    med = tools.resolve_medicine(req.message)
    if med or _has(low, MED_WORDS):
        if not med:
            return _resp("Which medicine? I can check: " + ", ".join(config.USAGE) + ".", [],
                         ["Is paracetamol available?", "Is ORS available?"])
        if not located:
            return _need_location()
        res = tools.get_medicine_availability(med, lat, lng, district, limit=3)
        return _list_reply(res, "medicine", med)

    if _has(low, BED_WORDS):
        kind = "beds"
    elif _has(low, DOCTOR_WORDS):
        kind = "doctors"
    elif _has(low, NEAR_WORDS) or district_text:
        kind = "nearest"
    else:
        return _resp("I can help you find nearby health centres, check medicine availability, beds and "
                     "whether a doctor is present. What would you like to know?", [])

    if not located:
        return _need_location()
    res = (tools.find_nearest_phcs(lat, lng, limit=3) if lat is not None
           else tools.list_phcs_by_district(district))
    return _list_reply(res, kind)


def emergency_reply(req: ChatRequest, lang: str) -> ChatResponse:
    """Fixed message first; facility cards are best-effort and must never block the message."""
    cards = []
    try:
        res = None
        if req.location:
            res = tools.find_nearest_phcs(req.location.lat, req.location.lng, limit=3)
        elif req.district_hint:
            res = tools.list_phcs_by_district(req.district_hint)
        cards = build_cards([res]) if res else []
    except Exception:
        cards = []
    return ChatResponse(reply=emergency_message(req.message, lang), emergency=True, source="mock",
                        data_as_of=data_as_of(), cards=cards, suggestions=[])