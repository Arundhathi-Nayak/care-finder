"""Gemini function-calling chat. Tool data comes only from tools.py; cards are built from tool
results, never from the model's prose. Coordinates are injected server-side and never sent to Gemini."""
from google import genai
from google.genai import types

from app import config, tools
from .availability import data_as_of
from .cards import build_cards
from .chat_logic import DEFAULT_SUGGESTIONS, _districts
from .schemas import ChatRequest, ChatResponse

MAX_ITERATIONS = 4

SYSTEM_PROMPT = """You are Care Finder, a helper for rural patients in India who want to find nearby \
government health facilities (PHCs/CHCs).
Rules:
- Reply in the user's language (Hindi, Kannada, Marathi or English) in short, simple sentences.
- Use ONLY data returned by tools. Never invent facilities, distances, beds, doctors or medicine availability.
- Availability levels are IN_STOCK, LOW, OUT. Never state exact stock numbers.
- You are not a doctor. Give no diagnosis, no dosing, no treatment advice. For anything serious, advise \
going to a facility with a doctor present or the district hospital.
- If a tool returns location_needed, ask the user to press 'Use my location' or choose a district.
- If no facility is found within the radius, say so and suggest calling 108 or 112.
- The data is demo data and may be a few minutes old.
- Facility cards with details and directions are shown to the user automatically, so keep your text brief \
and do not repeat every detail."""

_STR, _INT, _OBJ = "STRING", "INTEGER", "OBJECT"


def _decl(name: str, description: str, props: dict, required: list[str] | None = None):
    return types.FunctionDeclaration(
        name=name, description=description,
        parameters={"type": _OBJ, "properties": props, "required": required or []},
    )


TOOL = types.Tool(function_declarations=[
    _decl("find_nearest_phcs",
          "Find the health facilities nearest to the user's location. Location is added automatically.",
          {"radius_km": {"type": _INT, "description": "Search radius in km, default 50"},
           "limit": {"type": _INT, "description": "Max facilities, 1-5, default 3"}}),
    _decl("get_medicine_availability",
          "Which facilities have a medicine (IN_STOCK, LOW or OUT). Accepts brand or generic names "
          "like dolo, paracetamol, ORS. Uses the user's location automatically.",
          {"medicine_name": {"type": _STR}, "limit": {"type": _INT},
           "district": {"type": _STR, "description": "Only if the user named a district"}},
          ["medicine_name"]),
    _decl("get_phc_details",
          "Beds, doctors and medicine availability for one facility.",
          {"phc_id": {"type": _STR, "description": "e.g. PHC001, from an earlier tool result"}},
          ["phc_id"]),
    _decl("list_phcs_by_district",
          "List facilities in a district. Use when the user has no location.",
          {"district": {"type": _STR}}, ["district"]),
])


def _client() -> genai.Client:
    key = config.gemini_api_key()
    if not key:
        raise RuntimeError("no GEMINI_API_KEY")
    return genai.Client(api_key=key, http_options=types.HttpOptions(timeout=15_000))  # ms


def _contents(req: ChatRequest) -> list[types.Content]:
    out = [types.Content(role="user" if t.role == "user" else "model", parts=[types.Part(text=t.text)])
           for t in req.history]
    out.append(types.Content(role="user", parts=[types.Part(text=req.message)]))
    return out


def _system(req: ChatRequest) -> str:
    ctx = "User location: " + ("available (added to tool calls automatically)."
                               if req.location else "NOT available.")
    if req.district_hint:
        ctx += f" User-selected district: {req.district_hint}."
    return f"{SYSTEM_PROMPT}\n\n{ctx}"


def _execute(name: str, args: dict, req: ChatRequest) -> dict:
    args = {k: v for k, v in args.items() if k not in ("lat", "lng")}   # model must never set these
    if req.location and name in ("find_nearest_phcs", "get_medicine_availability"):
        args.update(lat=req.location.lat, lng=req.location.lng)
    if name in ("get_medicine_availability", "list_phcs_by_district") and req.district_hint:
        args.setdefault("district", req.district_hint)
    return tools.run_tool(name, args)


def _for_model(result: dict) -> dict:
    """Trim what the model sees (URLs are only needed by the UI cards)."""
    facs = [{k: v for k, v in f.items() if k != "maps_url"} for f in result.get("facilities", [])]
    return {**result, "facilities": facs} if "facilities" in result else result


def _suggestions(req: ChatRequest) -> list[str]:
    if not req.location and not req.district_hint:
        return _districts() or DEFAULT_SUGGESTIONS
    return DEFAULT_SUGGESTIONS


def gemini_reply(req: ChatRequest) -> ChatResponse:
    """Raises on any failure; the router then falls back to mock mode."""
    client = _client()
    contents = _contents(req)
    cfg = types.GenerateContentConfig(
        system_instruction=_system(req), tools=[TOOL], temperature=0.2, max_output_tokens=700,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    results: list[dict] = []
    for _ in range(MAX_ITERATIONS):
        resp = client.models.generate_content(model=config.GEMINI_MODEL, contents=contents, config=cfg)
        calls = resp.function_calls
        if not calls:
            text = (resp.text or "").strip()
            if not text:
                raise RuntimeError("empty reply")
            return ChatResponse(reply=text, source="gemini", data_as_of=data_as_of(),
                                cards=build_cards(results), suggestions=_suggestions(req))
        contents.append(resp.candidates[0].content)
        parts = []
        for c in calls:
            out = _execute(c.name, dict(c.args or {}), req)
            results.append(out)
            parts.append(types.Part.from_function_response(name=c.name, response={"result": _for_model(out)}))
        contents.append(types.Content(role="user", parts=parts))
    raise RuntimeError("tool loop did not finish")