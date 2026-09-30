from fastapi import APIRouter, Depends, Query

from .. import services
from ..repository import Repository, get_repo
from ..schemas import NetworkStatus, TransferOut

router = APIRouter(prefix="/api/v1", tags=["network"])


@router.get("/network-status", response_model=NetworkStatus)
def network_status(repo: Repository = Depends(get_repo)):
    return services.build_network_status(repo)


@router.get("/transfers", response_model=list[TransferOut])
def transfers(limit: int = Query(20, ge=1, le=100), repo: Repository = Depends(get_repo)):
    names = {p["phc_id"]: p["phc_name"] for p in repo.get_all_phcs()}
    rows = repo.list_transfers(limit)
    for r in rows:
        r["source_phc_name"] = names.get(r["source_phc_id"])
        r["target_phc_name"] = names.get(r["target_phc_id"])
    return rows
