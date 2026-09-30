"""Thin wrapper over google-genai. JSON mode, low temperature, raises on any failure."""
import json
import re

from app import config

_client = None


def is_enabled() -> bool:
    return bool(config.gemini_api_key())


def _get_client():
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=config.gemini_api_key())
    return _client


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def gemini_json(system: str, prompt: str) -> dict:
    if not is_enabled():
        raise RuntimeError("GEMINI_API_KEY not set")
    from google.genai import types

    resp = _get_client().models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    if not resp.text:
        raise ValueError("Gemini returned an empty response")
    data = json.loads(_strip_fences(resp.text))
    if not isinstance(data, dict):
        raise ValueError("Gemini did not return a JSON object")
    return data
