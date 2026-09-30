"""POST /api/v1/recommend-redistribution. Quantity is ALWAYS computed in code."""
from fastapi import APIRouter, Depends, HTTPException

from .. import config, gemini_client, geo, services
from ..repository import Repository, get_repo
from ..schemas import Brief, RedistributionRequest, RedistributionResponse

router = APIRouter(prefix="/api/v1", tags=["dispatch"])

SYSTEM = (
    "You are a logistics assistant for a District Medical Officer in India. Using ONLY the facts provided, "
    "write a concise redistribution brief. Return ONLY a JSON object with keys: transport_mode (string), "
    "route_priority (one of HIGH, MEDIUM, LOW), emergency_justification (max 2 sentences, no invented numbers), "
    "estimated_travel_time (string). Do not include a quantity."
)


def travel_time_text(distance_km: float) -> str:
    minutes = int(round(distance_km * 1.4 / 35 * 60))  # road factor 1.4, 35 km/h average
    h, m = divmod(max(minutes, 5), 60)
    return f"~{h} h {m} min" if h else f"~{m} min"


def mock_brief(facts: dict) -> dict:
    cold = facts["cold_chain"]
    days = facts["target_days_to_stockout"]
    priority = "HIGH" if days < config.CRITICAL_DAYS else "MEDIUM" if days < config.WARNING_DAYS else "LOW"
    return {
        "transport_mode": "Refrigerated vehicle (cold chain)" if cold else
        ("Motorbike courier" if facts["distance_km"] <= 15 and facts["transfer_quantity"] <= 300 else "Light truck"),
        "route_priority": priority,
        "emergency_justification": (
            f"{facts['target_phc_name']} has about {days} days of {facts['item']} left, while "
            f"{facts['source_phc_name']} holds a surplus beyond its {config.SAFETY_DAYS}-day safety cover."
        ),
        "estimated_travel_time": travel_time_text(facts["distance_km"]),
    }


def _find(inv_rows: list[dict], name: str) -> dict | None:
    return next((i for i in inv_rows if i["medicine_name"].lower() == name.strip().lower()), None)


@router.post("/recommend-redistribution", response_model=RedistributionResponse)
def recommend(req: RedistributionRequest, repo: Repository = Depends(get_repo)):
    src = repo.get_phc(req.source_phc_id)
    tgt = repo.get_phc(req.target_phc_id)
    if not src or not tgt:
        raise HTTPException(400, "Invalid source or target PHC id")
    if src["phc_id"] == tgt["phc_id"]:
        raise HTTPException(400, "Source and target PHC must be different")

    s_inv = _find(repo.get_inventory_for_phc(src["phc_id"]), req.item_name)
    t_inv = _find(repo.get_inventory_for_phc(tgt["phc_id"]), req.item_name)
    if not s_inv or not t_inv:
        raise HTTPException(404, f"Item '{req.item_name}' not found at both facilities")

    s_fc, t_fc = services.item_forecast(s_inv), services.item_forecast(t_inv)
    qty = services.compute_transfer_qty(s_inv["current_stock"], s_fc["_avg_raw"],
                                        t_inv["current_stock"], t_fc["_avg_raw"])
    if qty <= 0:
        raise HTTPException(
            409, f"{src['phc_name']} has no safe surplus of {s_inv['medicine_name']} "
                 f"(it would drop below {config.SAFETY_DAYS} days of cover) or {tgt['phc_name']} does not need it.")

    dist = geo.haversine_km(src["lat"], src["lng"], tgt["lat"], tgt["lng"])
    facts = {
        "item": s_inv["medicine_name"],
        "source_phc_id": src["phc_id"], "source_phc_name": src["phc_name"], "source_district": src["district"],
        "target_phc_id": tgt["phc_id"], "target_phc_name": tgt["phc_name"], "target_district": tgt["district"],
        "cross_district": src["district"] != tgt["district"],
        "distance_km": round(dist, 1),
        "donor_stock": s_inv["current_stock"], "donor_avg_daily_demand": s_fc["avg_daily_demand"],
        "donor_surplus": int(s_inv["current_stock"] - config.SAFETY_DAYS * s_fc["_avg_raw"]),
        "target_stock": t_inv["current_stock"], "target_avg_daily_demand": t_fc["avg_daily_demand"],
        "target_days_to_stockout": t_fc["days_to_stockout"], "target_status": t_fc["status"],
        "cold_chain": s_inv["medicine_name"] in config.COLD_CHAIN,
        "transfer_quantity": qty,
    }

    source, reason, brief = "mock", None, None
    if gemini_client.is_enabled():
        try:
            raw = gemini_client.gemini_json(SYSTEM, f"Facts: {facts}")
            fallback = mock_brief(facts)
            prio = str(raw.get("route_priority", "")).upper()
            brief = {
                "transport_mode": str(raw.get("transport_mode") or fallback["transport_mode"]),
                "route_priority": prio if prio in ("HIGH", "MEDIUM", "LOW") else fallback["route_priority"],
                "emergency_justification": str(raw.get("emergency_justification") or fallback["emergency_justification"]),
                "estimated_travel_time": str(raw.get("estimated_travel_time") or fallback["estimated_travel_time"]),
            }
            source = "gemini"
        except Exception as exc:
            reason = f"Gemini failed: {type(exc).__name__}"
    else:
        reason = "GEMINI_API_KEY not set"
    if brief is None:
        brief = mock_brief(facts)
    brief["transfer_quantity"] = qty  # code ALWAYS overrides the LLM

    repo.add_transfer(facts["item"], src["phc_id"], tgt["phc_id"], qty, brief, source)
    return RedistributionResponse(source=source, fallback_reason=reason if source == "mock" else None,
                                  facts=facts, brief=Brief(**brief))
