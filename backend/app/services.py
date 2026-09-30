"""Business logic shared by routers: forecasts, donor selection, transfer quantity, network status."""
from math import floor

from . import config, forecasting, gemini_client, geo
from .repository import Repository


def item_forecast(inv: dict) -> dict:
    rate = config.USAGE.get(inv["medicine_name"], config.DEFAULT_USAGE)
    return forecasting.forecast(inv["footfall_history"], inv["current_stock"], rate)


def compute_transfer_qty(donor_stock: float, donor_avg: float, target_stock: float, target_avg: float) -> int:
    """min(donor surplus, top-up for target). Donor never drops below SAFETY_DAYS of cover."""
    surplus = donor_stock - config.SAFETY_DAYS * donor_avg
    need = config.SAFETY_DAYS * target_avg - target_stock
    return max(0, int(floor(min(surplus, need))))


def ai_mode() -> str:
    return "gemini" if gemini_client.is_enabled() else "mock"


def build_network_status(repo: Repository) -> dict:
    phcs = repo.get_all_phcs()
    inventory = repo.get_all_inventory()
    phc_by_id = {p["phc_id"]: p for p in phcs}

    # forecast every inventory row once
    fc: dict[tuple[str, str], dict] = {}
    by_phc: dict[str, list[dict]] = {}
    for inv in inventory:
        f = item_forecast(inv)
        fc[(inv["phc_id"], inv["medicine_name"])] = {**f, "stock": inv["current_stock"], "history": inv["footfall_history"]}
        by_phc.setdefault(inv["phc_id"], []).append(inv)

    def best_donor(target_id: str, med: str) -> str | None:
        t = fc[(target_id, med)]
        tp = phc_by_id[target_id]
        candidates = []
        for (pid, m), d in fc.items():
            if m != med or pid == target_id or pid not in phc_by_id:
                continue
            qty = compute_transfer_qty(d["stock"], d["_avg_raw"], t["stock"], t["_avg_raw"])
            if qty <= 0:
                continue
            dp = phc_by_id[pid]
            dist = geo.haversine_km(tp["lat"], tp["lng"], dp["lat"], dp["lng"])
            candidates.append((dp["district"] != tp["district"], dist, pid))
        return min(candidates)[2] if candidates else None

    out_phcs, alerts = [], 0
    for p in phcs:
        items = []
        for inv in sorted(by_phc.get(p["phc_id"], []), key=lambda i: i["medicine_name"]):
            f = fc[(p["phc_id"], inv["medicine_name"])]
            src_id = src_name = None
            if f["status"] != "GREEN":
                src_id = best_donor(p["phc_id"], inv["medicine_name"])
                src_name = phc_by_id[src_id]["phc_name"] if src_id else None
            if f["status"] == "CRITICAL":
                alerts += 1
            items.append({
                "medicine_name": inv["medicine_name"],
                "current_stock": inv["current_stock"],
                "history": inv["footfall_history"],
                "projected_demand_7d": f["projected_demand_7d"],
                "avg_daily_demand": f["avg_daily_demand"],
                "days_to_stockout": f["days_to_stockout"],
                "status": f["status"],
                "suggested_source_id": src_id,
                "suggested_source_name": src_name,
            })
        out_phcs.append({**p, "inventory": items})

    beds_av = sum(p["beds_available"] for p in phcs)
    beds_tot = sum(p["beds_total"] for p in phcs)
    return {
        "summary": {
            "total_phcs": len(phcs),
            "active_stockout_alerts": alerts,
            "beds_available": beds_av,
            "beds_total": beds_tot,
            "bed_availability_ratio": round(beds_av / beds_tot, 3) if beds_tot else 0.0,
            "active_ai_transfers": repo.count_transfers(),
            "ai_mode": ai_mode(),
        },
        "phcs": out_phcs,
    }
