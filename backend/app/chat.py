import logging

from fastapi import APIRouter, Request

from app  import config
from app.chat_logic import emergency_reply, mock_reply
from .gemini_chat import gemini_reply
from .ratelimit import check_rate_limit
from .safety import detect_emergency
from .schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/v1", tags=["chat"])
log = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    lang = detect_emergency(req.message)          # safety first, never rate limited
    if lang:
        return emergency_reply(req, lang)

    check_rate_limit(request)

    if config.gemini_api_key():
        try:
            return gemini_reply(req)
        except Exception as e:                    # log the class only: messages could contain user text
            log.warning("gemini chat failed, using mock: %s", type(e).__name__)
            print(f"gemini chat failed, using mock: {type(e).__name__}: {e}")
    return mock_reply(req)