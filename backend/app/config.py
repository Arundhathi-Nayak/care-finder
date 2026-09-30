"""Environment + constants. Loaded once at import time."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()
]

# Patients-per-day -> units-per-day usage rates
USAGE = {
    "Paracetamol 500mg": 1.0,
    "ORS Sachets": 0.6,
    "Amoxicillin 500mg": 0.5,
    "Metformin 500mg": 0.35,
    "Oxytocin Inj": 0.08,
    "Anti-Rabies Vaccine": 0.05,
}
DEFAULT_USAGE = 0.5
COLD_CHAIN = {"Oxytocin Inj", "Anti-Rabies Vaccine"}
PARACETAMOL = "Paracetamol 500mg"

SAFETY_DAYS = 10        # donor must keep 10 days of cover; target is topped up to 10 days
CRITICAL_DAYS = 3
WARNING_DAYS = 7
CACHE_TTL_SECONDS = 5


def gemini_api_key() -> str | None:
    """Read at call time so tests / runtime changes are respected."""
    return os.getenv("GEMINI_API_KEY") or None
