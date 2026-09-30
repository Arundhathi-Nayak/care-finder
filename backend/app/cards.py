"""Build UI cards from tool results: dedupe by phc_id, keep order, merge medicine lists."""
from app.schemas import PhcCard

MAX_CARDS = 5


def build_cards(results: list[dict], max_cards: int = MAX_CARDS) -> list[PhcCard]:
    merged: dict[str, dict] = {}
    for res in results:
        if not isinstance(res, dict):
            continue
        for fac in res.get("facilities", []):
            pid = fac.get("phc_id")
            if not pid:
                continue
            if pid not in merged:
                merged[pid] = {**fac, "medicines": list(fac.get("medicines", []))}
                continue
            have = {m["name"] for m in merged[pid]["medicines"]}
            merged[pid]["medicines"] += [m for m in fac.get("medicines", []) if m["name"] not in have]
            if merged[pid].get("distance_km") is None:
                merged[pid]["distance_km"] = fac.get("distance_km")
    return [PhcCard(**f) for f in list(merged.values())[:max_cards]]  # extra keys (state) are ignored