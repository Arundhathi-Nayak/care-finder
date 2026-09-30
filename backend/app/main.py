from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, services
from .repository import get_repo
from .routers import dispatch, network, phcs, voice


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_repo()  # fail fast with a clear message if Firestore can't initialise
    yield


app = FastAPI(title="HealthGrid AI API", version="2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(network.router)
app.include_router(voice.router)
app.include_router(dispatch.router)
app.include_router(phcs.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_mode": services.ai_mode()}
