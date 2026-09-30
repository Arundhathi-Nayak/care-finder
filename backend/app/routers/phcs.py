from fastapi import APIRouter, Depends, Query

from .. import geo
from ..repository import Repository, get_repo
from ..schemas import NearbyPhc

router = APIRouter(prefix="/api/v1", tags=["phcs"])


@router.get("/phcs/nearby", response_model=list[NearbyPhc])
def nearby(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(50, gt=0, le=500),
    limit: int = Query(5, ge=1, le=20),
    repo: Repository = Depends(get_repo),
):
    # Coordinates are used for this request only; never stored or logged.
    rows = []
    for p in repo.get_all_phcs():
        d = geo.haversine_km(lat, lng, p["lat"], p["lng"])
        if d <= radius_km:
            rows.append({
                "phc_id": p["phc_id"], "name": p["phc_name"], "district": p["district"], "state": p["state"],
                "distance_km": round(d, 1),
                "beds_available": p["beds_available"], "beds_total": p["beds_total"],
                "doctors_present": p["doctors_present"], "doctors_total": p["doctors_total"],
                "maps_url": geo.maps_url(p["lat"], p["lng"]),
            })
    rows.sort(key=lambda r: r["distance_km"])
    return rows[:limit]
