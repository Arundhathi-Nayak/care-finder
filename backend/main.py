"""
HealthGrid AI - Federated PHC Resource & Supply Chain Platform (prototype)
Run (from healthgrid-ai/backend):  uvicorn main:app --reload
"""
import json
import math
import os
import re
import threading
from pathlib import Path

import numpy as np
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sklearn.linear_model import Ridge

# --------------------------------------------------------------------------
# 1. CONFIG + GEMINI CLIENT (graceful fallback when key / SDK is missing)
# --------------------------------------------------------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")  # override e.g. gemini-2.5-flash
API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client, genai_types = None, None
if API_KEY:
    try:
        from google import genai
        from google.genai import types as genai_types

        gemini_client = genai.Client(api_key=API_KEY)
    except Exception as exc:  # SDK missing / bad init
        print(f"[HealthGrid] Gemini disabled ({exc}); using mock fallbacks.")
else:
    print("[HealthGrid] GEMINI_API_KEY not set -> running with MOCK AI fallbacks.")


def gemini_json(system: str, prompt: str) -> dict:
    """Call Gemini with JSON mime type. Raises on any failure (callers fall back)."""
    if gemini_client is None:
        raise RuntimeError("Gemini client not configured")
    resp = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    text = (resp.text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text).strip()
    data = json.loads(text)
    if isinstance(data, list) and data:
        data = data[0]
    return data


# --------------------------------------------------------------------------
# 2. DATASET CREATION (schema modelled on NHM HMIS / e-Aushadhi / data.gov.in)
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent          # healthgrid-ai/
DATA_DIR = BASE_DIR / "data"
FRONTEND = BASE_DIR / "frontend" / "index.html"
DATA_DIR.mkdir(exist_ok=True)
PHC_CSV, INV_CSV = DATA_DIR / "phc_directory.csv", DATA_DIR / "inventory_telemetry.csv"

if not PHC_CSV.exists():
    pd.DataFrame(
        [
            ("PHC001", "Hebri PHC", "Udupi", "Karnataka", 13.4770, 75.0000, 4, 10, 1, 2),
            ("PHC002", "Karkala CHC", "Udupi", "Karnataka", 13.2130, 74.9930, 18, 30, 4, 5),
            ("PHC003", "Paud PHC", "Pune", "Maharashtra", 18.5230, 73.6180, 2, 8, 1, 2),
            ("PHC004", "Bhor PHC", "Pune", "Maharashtra", 18.1500, 73.8400, 9, 12, 2, 2),
        ],
        columns="phc_id,phc_name,district,state,lat,lng,beds_available,beds_total,doctors_present,doctors_total".split(","),
    ).to_csv(PHC_CSV, index=False)

if not INV_CSV.exists():
    P, O, A, M, X, R = ("Paracetamol 500mg", "ORS Sachets", "Amoxicillin 500mg",
                        "Metformin 500mg", "Oxytocin Inj", "Anti-Rabies Vaccine")
    h1, h2, h3, h4 = "45,52,60,58,70,85,92", "38,41,40,44,43,46,45", "55,60,66,70,74,80,88", "28,30,29,33,31,34,32"
    rows = [
        ("PHC001", P, 120, h1), ("PHC001", O, 700, h1), ("PHC001", A, 260, h1), ("PHC001", M, 420, h1), ("PHC001", X, 80, h1), ("PHC001", R, 30, h1),
        ("PHC002", P, 1800, h2), ("PHC002", O, 900, h2), ("PHC002", A, 700, h2), ("PHC002", M, 500, h2), ("PHC002", X, 90, h2), ("PHC002", R, 60, h2),
        ("PHC003", P, 380, h3), ("PHC003", O, 60, h3), ("PHC003", A, 900, h3), ("PHC003", M, 400, h3), ("PHC003", X, 40, h3), ("PHC003", R, 35, h3),
        ("PHC004", P, 1400, h4), ("PHC004", O, 500, h4), ("PHC004", A, 600, h4), ("PHC004", M, 450, h4), ("PHC004", X, 60, h4), ("PHC004", R, 40, h4),
    ]
    pd.DataFrame(rows, columns=["phc_id", "medicine_name", "current_stock", "daily_patient_footfall_history"]).to_csv(INV_CSV, index=False)

# Units consumed per patient visit (illustrative planning norms)
USAGE = {"Paracetamol 500mg": 1.0, "ORS Sachets": 0.6, "Amoxicillin 500mg": 0.5,
         "Metformin 500mg": 0.35, "Oxytocin Inj": 0.08, "Anti-Rabies Vaccine": 0.05}
COLD_CHAIN = {"Oxytocin Inj", "Anti-Rabies Vaccine"}
SAFETY_DAYS = 10  # donor keeps this many days of cover

# In-memory "database" hydrated from CSVs
DB = {"phc": pd.read_csv(PHC_CSV), "inv": pd.read_csv(INV_CSV)}
TRANSFERS: list[dict] = []
LOCK = threading.Lock()

# --------------------------------------------------------------------------
# 3. FORECASTING (Ridge Regression on 7-day footfall -> demand -> stock-out)
# --------------------------------------------------------------------------
def forecast_footfall(history: list[int]) -> np.ndarray:
    x = np.arange(len(history)).reshape(-1, 1)
    model = Ridge(alpha=1.0).fit(x, np.array(history, dtype=float))
    future = np.arange(len(history), len(history) + 7).reshape(-1, 1)
    return np.clip(model.predict(future), 1, None)


def analyse(stock: float, history_str: str, medicine: str) -> dict:
    history = [int(v) for v in str(history_str).split(",")]
    daily_demand = forecast_footfall(history) * USAGE.get(medicine, 0.5)
    remaining, days = float(stock), None
    for d, dem in enumerate(daily_demand, 1):
        if remaining <= dem:
            days = d - 1 + remaining / dem
            break
        remaining -= dem
    if days is None:
        days = 7 + remaining / daily_demand[-1]
    status = "CRITICAL" if days < 3 else "WARNING" if days < 7 else "GREEN"
    return {
        "history": history,
        "projected_demand_7d": int(round(daily_demand.sum())),
        "avg_daily_demand": round(float(daily_demand.mean()), 1),
        "days_to_stockout": round(days, 1),
        "status": status,
    }


def haversine(lat1, lng1, lat2, lng2) -> float:
    r = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def surplus_of(phc_id: str, medicine: str) -> float:
    row = DB["inv"][(DB["inv"].phc_id == phc_id) & (DB["inv"].medicine_name == medicine)]
    if row.empty:
        return 0
    a = analyse(row.iloc[0].current_stock, row.iloc[0].daily_patient_footfall_history, medicine)
    return float(row.iloc[0].current_stock) - SAFETY_DAYS * a["avg_daily_demand"]


def best_source(target_id: str, medicine: str):
    cands = [(surplus_of(p, medicine), p) for p in DB["phc"].phc_id if p != target_id]
    cands = [c for c in cands if c[0] > 0]
    return max(cands)[1] if cands else None


def safe_transfer_qty(source_id: str, target_id: str, medicine: str) -> int:
    row = DB["inv"][(DB["inv"].phc_id == target_id) & (DB["inv"].medicine_name == medicine)].iloc[0]
    a = analyse(row.current_stock, row.daily_patient_footfall_history, medicine)
    need = SAFETY_DAYS * a["avg_daily_demand"] - float(row.current_stock)
    return int(max(0, min(surplus_of(source_id, medicine), need)))


# --------------------------------------------------------------------------
# 4. API
# --------------------------------------------------------------------------
app = FastAPI(title="HealthGrid AI", version="1.0")


class VoiceReport(BaseModel):
    audio_transcript: str
    phc_id: str
    language: str = "Hindi"


class RedistributionRequest(BaseModel):
    source_phc_id: str
    target_phc_id: str
    item_name: str


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND)


@app.get("/api/v1/network-status")
def network_status():
    with LOCK:
        phcs, active_alerts = [], 0
        for _, p in DB["phc"].iterrows():
            items = []
            for _, r in DB["inv"][DB["inv"].phc_id == p.phc_id].iterrows():
                a = analyse(r.current_stock, r.daily_patient_footfall_history, r.medicine_name)
                src = best_source(p.phc_id, r.medicine_name) if a["status"] == "CRITICAL" else None
                active_alerts += a["status"] == "CRITICAL"
                items.append({"medicine_name": r.medicine_name, "current_stock": int(r.current_stock),
                              "suggested_source_id": src,
                              "suggested_source_name": (DB["phc"].set_index("phc_id").phc_name[src] if src else None),
                              **a})
            d = {k: (v.item() if hasattr(v, "item") else v) for k, v in p.items()}
            phcs.append({**d, "inventory": items})
        ba, bt = int(DB["phc"].beds_available.sum()), int(DB["phc"].beds_total.sum())
        return {
            "summary": {"total_phcs": len(phcs), "active_stockout_alerts": int(active_alerts),
                        "beds_available": ba, "beds_total": bt, "bed_availability_ratio": round(ba / bt, 3),
                        "active_ai_transfers": len(TRANSFERS),
                        "ai_mode": "gemini" if gemini_client else "mock"},
            "phcs": phcs,
        }


# ---- voice report -------------------------------------------------------
_DIGITS = str.maketrans("०१२३४५६७८९೦೧೨೩೪೫೬೭೮೯", "01234567890123456789")
_PATIENT_KW = re.compile(r"मरीज|patient|ರೋಗಿ|ರೋಗಿಗಳು", re.I)
_STOCK_KW = re.compile(r"स्ट्रिप|strip|stock|स्टॉक|ಸ್ಟ್ರಿಪ್|ಸ್ಟಾಕ್", re.I)
_PARA_KW = re.compile(r"पैरासिटामोल|पेरासिटामोल|paracetamol|ಪ್ಯಾರಾಸಿಟಮಾಲ್|ಪ್ಯಾರಸಿಟಮಾಲ್", re.I)
_DOC_ABSENT = re.compile(r"डॉक्टर (नहीं|अनुपस्थित|गैरहाजिर)|no doctor|doctor (is )?absent|ವೈದ್ಯರು ಇಲ್ಲ|ವೈದ್ಯರಿಲ್ಲ", re.I)
_DOC_PRESENT = re.compile(r"डॉक्टर (उपस्थित|मौजूद|हैं|है)|doctor (is )?present|ವೈದ್ಯರು ಇದ್ದಾರೆ|ವೈದ್ಯರು ಹಾಜರ್", re.I)
_EMERG = re.compile(r"आपात|इमरजेंसी|emergency|सांप|ತುರ್ತು|ಹಾವು", re.I)


def mock_extract(text: str) -> dict:
    t = text.translate(_DIGITS)
    patients = stock = None
    for m in re.finditer(r"\d+", t):
        after, before = t[m.end(): m.end() + 14], t[max(0, m.start() - 25): m.start()]
        if patients is None and _PATIENT_KW.search(after):
            patients = int(m.group())
        elif stock is None and (_STOCK_KW.search(after) or _PARA_KW.search(before)):
            stock = int(m.group())
    doctor = False if _DOC_ABSENT.search(t) else True if _DOC_PRESENT.search(t) else None
    return {"patient_count": patients, "paracetamol_stock": stock, "doctor_present": doctor,
            "emergency_notes": text.strip() if _EMERG.search(t) else "None reported"}


VOICE_SYSTEM = (
    "You extract structured data from daily reports spoken by ASHA/PHC workers in Indian languages "
    "(Hindi, Kannada, Marathi, English or mixed). Return ONLY JSON with keys: "
    "patient_count (integer or null), paracetamol_stock (integer strips remaining or null), "
    "doctor_present (boolean or null), emergency_notes (short English summary, or 'None reported'). "
    "Never invent values that were not stated; use null instead."
)


@app.post("/api/v1/log-daily-voice-report")
def log_daily_voice_report(req: VoiceReport):
    if req.phc_id not in set(DB["phc"].phc_id):
        raise HTTPException(404, f"Unknown phc_id {req.phc_id}")
    source, reason = "gemini", None
    try:
        data = gemini_json(VOICE_SYSTEM, f"Language: {req.language}\nTranscript: {req.audio_transcript}")
    except Exception as exc:
        data, source, reason = mock_extract(req.audio_transcript), "mock", str(exc)[:160]

    # Normalise types
    def _int(v):
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    data = {"patient_count": _int(data.get("patient_count")),
            "paracetamol_stock": _int(data.get("paracetamol_stock")),
            "doctor_present": data.get("doctor_present") if isinstance(data.get("doctor_present"), bool) else None,
            "emergency_notes": str(data.get("emergency_notes") or "None reported")}
    # Apply to the in-memory network state so the dashboard updates live
    with LOCK:
        inv, phc = DB["inv"], DB["phc"]
        mask = inv.phc_id == req.phc_id
        if data["patient_count"] is not None:
            for i in inv[mask].index:
                hist = str(inv.at[i, "daily_patient_footfall_history"]).split(",")[1:] + [str(data["patient_count"])]
                inv.at[i, "daily_patient_footfall_history"] = ",".join(hist)
        if data["paracetamol_stock"] is not None:
            inv.loc[mask & (inv.medicine_name == "Paracetamol 500mg"), "current_stock"] = data["paracetamol_stock"]
        if data["doctor_present"] is not None:
            pm = phc.phc_id == req.phc_id
            phc.loc[pm, "doctors_present"] = 0 if not data["doctor_present"] else max(1, int(phc.loc[pm, "doctors_present"].iloc[0]))
    return {"source": source, "fallback_reason": reason, "phc_id": req.phc_id, "extracted": data, "applied_to_network": True}


# ---- redistribution brief ----------------------------------------------
DISPATCH_SYSTEM = (
    "You are a logistics advisor for a District Medical Officer (DMO) in India's National Health Mission. "
    "Given facts about a stock-out risk, write an actionable dispatch brief. Return ONLY JSON with keys: "
    "transfer_quantity (integer, use exactly the provided safe quantity), transport_mode (string, e.g. "
    "'108 Ambulance return trip', 'Cold-Chain Van', 'PHC vehicle'), route_priority (one of 'P1 - Immediate', "
    "'P2 - Same Day', 'P3 - Within 48h'), emergency_justification (2-3 sentences citing the numbers), "
    "estimated_travel_time (string). Use cold-chain transport for items flagged cold_chain=true."
)


def mock_brief(f: dict) -> dict:
    urgent = f["target_days_to_stockout"] < 2
    return {
        "transfer_quantity": f["safe_transfer_quantity"],
        "transport_mode": "Cold-Chain Van" if f["cold_chain"] else
        ("108 Ambulance return trip" if f["distance_km"] < 120 else "District PHC vehicle with relay"),
        "route_priority": "P1 - Immediate" if urgent else "P2 - Same Day",
        "emergency_justification": (
            f"{f['target_phc']} has {f['target_stock']} units of {f['item']} left, enough for only "
            f"{f['target_days_to_stockout']} days against a projected 7-day demand of {f['target_projected_demand_7d']}. "
            f"{f['source_phc']} holds surplus beyond its {SAFETY_DAYS}-day safety cover and is {f['distance_km']} km away."),
        "estimated_travel_time": f"~{max(1, round(f['distance_km'] / 40 * 60))} min",
    }


@app.post("/api/v1/recommend-redistribution")
def recommend_redistribution(req: RedistributionRequest):
    ids = set(DB["phc"].phc_id)
    if req.source_phc_id not in ids or req.target_phc_id not in ids or req.source_phc_id == req.target_phc_id:
        raise HTTPException(400, "Invalid source/target PHC ids")
    with LOCK:
        ph = DB["phc"].set_index("phc_id")
        tr = DB["inv"][(DB["inv"].phc_id == req.target_phc_id) & (DB["inv"].medicine_name == req.item_name)]
        if tr.empty:
            raise HTTPException(404, "Item not tracked at target PHC")
        a = analyse(tr.iloc[0].current_stock, tr.iloc[0].daily_patient_footfall_history, req.item_name)
        qty = safe_transfer_qty(req.source_phc_id, req.target_phc_id, req.item_name)
        s, t = ph.loc[req.source_phc_id], ph.loc[req.target_phc_id]
        facts = {
            "item": req.item_name, "cold_chain": req.item_name in COLD_CHAIN,
            "source_phc": s.phc_name, "source_district": f"{s.district}, {s.state}",
            "target_phc": t.phc_name, "target_district": f"{t.district}, {t.state}",
            "cross_district": s.district != t.district,
            "distance_km": round(haversine(s.lat, s.lng, t.lat, t.lng), 1),
            "target_stock": int(tr.iloc[0].current_stock), "target_days_to_stockout": a["days_to_stockout"],
            "target_projected_demand_7d": a["projected_demand_7d"],
            "safe_transfer_quantity": qty, "target_doctors_present": int(t.doctors_present),
        }
    if qty <= 0:
        raise HTTPException(409, "Source PHC has no safe surplus for this item (would breach its safety stock).")
    source, reason = "gemini", None
    try:
        brief = gemini_json(DISPATCH_SYSTEM, "Facts:\n" + json.dumps(facts, indent=2))
    except Exception as exc:
        brief, source, reason = mock_brief(facts), "mock", str(exc)[:160]
    brief["transfer_quantity"] = qty  # guardrail: never exceed the computed safe quantity
    result = {"source": source, "fallback_reason": reason, "facts": facts, "brief": brief}
    with LOCK:
        TRANSFERS.append({"item": req.item_name, "from": s.phc_name, "to": t.phc_name, "qty": qty})
    return result


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)