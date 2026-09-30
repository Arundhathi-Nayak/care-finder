"""POST /api/v1/log-daily-voice-report: Gemini extraction (multilingual) with regex fallback."""
import re

from fastapi import APIRouter, Depends, HTTPException

from .. import config, gemini_client
from ..repository import Repository, get_repo
from ..schemas import Extracted, VoiceReportRequest, VoiceReportResponse

router = APIRouter(prefix="/api/v1", tags=["voice"])

# ---------------- mock (rule-based) extraction ----------------
# Devanagari (Hindi/Marathi) and Kannada digits -> ASCII
_DIGITS = str.maketrans({
    **{chr(0x0966 + i): str(i) for i in range(10)},
    **{chr(0x0CE6 + i): str(i) for i in range(10)},
})
PATIENT_KW = ["patients", "patient", "footfall", "opd", "मरीजों", "मरीज", "रोगियों", "रोगी", "रुग्ण",
              "पेशेंट", "ರೋಗಿಗಳು", "ರೋಗಿಗಳ", "ರೋಗಿ"]
PARACETAMOL_KW = ["paracetamol", "dolo", "पैरासिटामोल", "पेरासिटामोल", "पॅरासिटामोल",
                  "ಪ್ಯಾರಸಿಟಮಾಲ್", "ಪ್ಯಾರಾಸಿಟಮಾಲ್", "ಪ್ಯಾರಸಿಟಮೋಲ್"]
DOCTOR_KW = ["doctors", "doctor", "डॉक्टर", "चिकित्सक", "ಡಾಕ್ಟರ್", "ವೈದ್ಯರು", "ವೈದ್ಯ"]
NEG = re.compile(r"\b(?:not|no|absent|unavailable|leave)\b|नहीं|नही|अनुपस्थित|नाही|नाहीत|छुट्टी|ಇಲ್ಲ|ಬಂದಿಲ್ಲ|ಗೈರು", re.I)
POS = re.compile(r"\b(?:present|here|available|came|arrived|attending)\b|मौजूद|उपस्थित|उपलब्ध|आए|आया|आई|हैं|आहेत|ಇದ್ದಾರೆ|ಹಾಜರ್|ಬಂದಿದ್ದಾರೆ", re.I)
EMERGENCY_HINTS = {
    "snake": "Snake bite case reported", "सांप": "Snake bite case reported", "ಹಾವು": "Snake bite case reported",
    "accident": "Accident case reported", "दुर्घटना": "Accident case reported", "ಅಪಘಾತ": "Accident case reported",
    "bleeding": "Bleeding case reported", "रक्तस्राव": "Bleeding case reported",
    "delivery": "Delivery / obstetric case reported", "प्रसव": "Delivery / obstetric case reported",
    "ಹೆರಿಗೆ": "Delivery / obstetric case reported",
}
MAX_GAP = 25


def _kw_regex(words: list[str]) -> re.Pattern:
    return re.compile("|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)), re.I)


def _nearest_number(text: str, keywords: list[str], exclude: set | None = None):
    """Return (value, span) of the number closest to any keyword (within MAX_GAP chars)."""
    exclude = exclude or set()
    nums = [(m.start(), m.end(), int(m.group())) for m in re.finditer(r"\d+", text)]
    best = None
    for kw in _kw_regex(keywords).finditer(text):
        for s, e, v in nums:
            if (s, e) in exclude:
                continue
            gap = s - kw.end() if s >= kw.end() else (kw.start() - e if e <= kw.start() else 0)
            if gap <= MAX_GAP and (best is None or gap < best[0]):
                best = (gap, (s, e), v)
    return (best[2], best[1]) if best else (None, None)


def _doctor_present(text: str) -> bool | None:
    for m in _kw_regex(DOCTOR_KW).finditer(text):
        if re.search(r"\b(?:no|without)\s+$", text[:m.start()], re.I):
            return False
        after = re.split(r"[,.।;\n]", text[m.end(): m.end() + 35])[0]
        if NEG.search(after):
            return False
        if POS.search(after):
            return True
    return None


def mock_extract(transcript: str) -> dict:
    text = transcript.translate(_DIGITS)
    text = re.sub(r"\d+\s*(?:mg|mcg|ml)\b", "", text, flags=re.I)  # drop "500mg" so it isn't read as stock
    stock, span = _nearest_number(text, PARACETAMOL_KW)
    patients, _ = _nearest_number(text, PATIENT_KW, exclude={span} if span else None)
    notes = sorted({label for kw, label in EMERGENCY_HINTS.items() if kw in text.lower()})
    return {
        "patient_count": patients,
        "paracetamol_stock": stock,
        "doctor_present": _doctor_present(text),
        "emergency_notes": "; ".join(notes) if notes else "None reported (basic extraction)",
    }


# ---------------- Gemini extraction ----------------
SYSTEM = (
    "You extract structured data from a daily report given by a health-centre worker in India. "
    "The transcript may be in Hindi, Kannada, Marathi or English. Return ONLY a JSON object with keys: "
    "patient_count (integer or null), paracetamol_stock (integer tablets remaining or null), "
    "doctor_present (true/false or null), emergency_notes (short English summary, empty string if none). "
    "Use null for anything not clearly stated. Never guess."
)


def _to_int(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        n = int(float(str(v).translate(_DIGITS).replace(",", "")))
    except (ValueError, TypeError):
        return None
    return n if n >= 0 else None


def _to_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str) and v.strip().lower() in ("true", "false"):
        return v.strip().lower() == "true"
    return None


def gemini_extract(transcript: str, language: str) -> dict:
    raw = gemini_client.gemini_json(SYSTEM, f"Language hint: {language}\nTranscript: {transcript}")
    return {
        "patient_count": _to_int(raw.get("patient_count")),
        "paracetamol_stock": _to_int(raw.get("paracetamol_stock")),
        "doctor_present": _to_bool(raw.get("doctor_present")),
        "emergency_notes": str(raw.get("emergency_notes") or ""),
    }


@router.post("/log-daily-voice-report", response_model=VoiceReportResponse)
def log_daily_voice_report(req: VoiceReportRequest, repo: Repository = Depends(get_repo)):
    if repo.get_phc(req.phc_id) is None:
        raise HTTPException(404, f"Unknown PHC id '{req.phc_id}'")

    source, reason = "mock", None
    extracted = None
    if gemini_client.is_enabled():
        try:
            extracted = gemini_extract(req.audio_transcript, req.language)
            source = "gemini"
        except Exception as exc:  # any Gemini failure -> rule-based fallback
            reason = f"Gemini failed: {type(exc).__name__}"
    else:
        reason = "GEMINI_API_KEY not set"
    if extracted is None:
        extracted = mock_extract(req.audio_transcript)

    # Persist to the network
    if extracted["patient_count"] is not None:
        repo.push_footfall(req.phc_id, extracted["patient_count"])
    if extracted["paracetamol_stock"] is not None:
        repo.update_stock(req.phc_id, config.PARACETAMOL, extracted["paracetamol_stock"])
    if extracted["doctor_present"] is not None:
        repo.update_doctors_present(req.phc_id, extracted["doctor_present"])
    repo.add_report(req.phc_id, req.audio_transcript, req.language, extracted, source)

    return VoiceReportResponse(
        source=source, fallback_reason=reason if source == "mock" else None,
        phc_id=req.phc_id, extracted=Extracted(**extracted), applied_to_network=True,
    )
