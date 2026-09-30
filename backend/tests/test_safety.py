import pytest
from app.safety import detect_emergency, emergency_message


@pytest.mark.parametrize("text,lang", [
    ("My father has chest pain", "en"),
    ("he is unconscious", "en"),
    ("snake bite in the field", "en"),
    ("मुझे सीने में दर्द हो रहा है", "hi"),
    ("वो बेहोश हो गया", "hi"),
    ("बाबांना छातीत दुखत आहे", "mr"),
    ("त्याला साप चावला", "mr"),
    ("ನನಗೆ ಎದೆ ನೋವು ಇದೆ", "kn"),
    ("ಹಾವು ಕಚ್ಚಿದೆ", "kn"),
])
def test_emergency_detected(text, lang):
    assert detect_emergency(text) == lang


@pytest.mark.parametrize("text", [
    "nearest PHC please",
    "is paracetamol available?",
    "मेरे पास पैरासिटामोल कहाँ मिलेगी",
    "ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆ ಯಾವುದು",
    "",
])
def test_no_false_positive(text):
    assert detect_emergency(text) is None


def test_message_mentions_108_and_112():
    for lang in ("en", "hi", "mr", "kn"):
        m = emergency_message("x", lang)
        assert "108" in m and "112" in m