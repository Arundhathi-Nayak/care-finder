"""Emergency detection. Runs BEFORE any LLM call. Pure functions, no I/O, no logging of text."""
import unicodedata

EMERGENCY_NUMBERS = {"ambulance": "108", "emergency": "112"}

# Substring keywords, matched on lowercased NFC-normalised text.
# Avoid short stems that are common inside other words (e.g. Hindi/Kannada "poison" stems vs "subject").
KEYWORDS: dict[str, list[str]] = {
    "en": [
        "chest pain", "heart attack", "unconscious", "not responding", "fainted",
        "severe bleeding", "bleeding a lot", "heavy bleeding", "snake bite", "snakebite",
        "bitten by snake", "difficulty breathing", "can't breathe", "cannot breathe",
        "trouble breathing", "seizure", "convulsion", "fits", "pregnancy emergency",
        "labour pain", "labor pain", "delivery pain", "poison", "overdose", "accident",
        "suicide",
    ],
    "hi": [
        "सीने में दर्द", "छाती में दर्द", "दिल का दौरा", "बेहोश", "बहुत खून", "खून बह",
        "सांप ने काटा", "साँप ने काटा", "सांप काटा", "साँप काटा", "सांस लेने में तकलीफ",
        "सांस नहीं", "साँस लेने में", "दौरा पड़", "मिर्गी", "जहर", "ज़हर", "दुर्घटना",
        "एक्सीडेंट", "प्रसव पीड़ा", "डिलीवरी का दर्द",
    ],
    "mr": [
        "छातीत दुखत", "छातीत दुखणे", "बेशुद्ध", "खूप रक्त", "रक्तस्राव", "साप चावला",
        "साप चावल", "श्वास घेण्यास त्रास", "धाप लागत", "झटके येत", "फिट आली", "विषबाधा",
        "विष प्राशन", "अपघात", "प्रसूती वेदना", "बाळंतपणाच्या वेदना",
    ],
    "kn": [
        "ಎದೆ ನೋವು", "ಎದೆನೋವು", "ಪ್ರಜ್ಞೆ ತಪ್ಪ", "ಪ್ರಜ್ಞೆಹೀನ", "ರಕ್ತಸ್ರಾವ", "ತುಂಬಾ ರಕ್ತ",
        "ಹಾವು ಕಚ್ಚ", "ಉಸಿರಾಟದ ತೊಂದರೆ", "ಉಸಿರಾಡಲು ಕಷ್ಟ", "ಫಿಟ್ಸ್", "ಸೆಳೆತ",
        "ವಿಷ ಕುಡಿ", "ವಿಷ ಸೇವನೆ", "ವಿಷಪ್ರಾಶನ", "ಅಪಘಾತ", "ಹೆರಿಗೆ ನೋವು",
    ],
}

MESSAGES = {
    "en": "This may be an emergency. Call 108 (ambulance) or 112 now. "
          "Do not wait. If someone is with you, ask them to take you to the nearest hospital.",
    "hi": "यह आपातकाल हो सकता है। अभी 108 (एम्बुलेंस) या 112 पर कॉल करें। "
          "इंतज़ार न करें। किसी को साथ लेकर नज़दीकी अस्पताल जाएँ।",
    "mr": "ही आणीबाणी असू शकते. आत्ताच 108 (रुग्णवाहिका) किंवा 112 वर कॉल करा. "
          "वाट पाहू नका. कोणालातरी सोबत घेऊन जवळच्या रुग्णालयात जा.",
    "kn": "ಇದು ತುರ್ತು ಪರಿಸ್ಥಿತಿ ಆಗಿರಬಹುದು. ಈಗಲೇ 108 (ಆಂಬ್ಯುಲೆನ್ಸ್) ಅಥವಾ 112 ಗೆ ಕರೆ ಮಾಡಿ. "
          "ಕಾಯಬೇಡಿ. ಯಾರನ್ನಾದರೂ ಜೊತೆಗೆ ಕರೆದುಕೊಂಡು ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ.",
}


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower().strip()


def detect_language(text: str) -> str:
    """Script-based guess: 'kn' Kannada, 'hi' Devanagari (Hindi/Marathi share script), else 'en'."""
    kn = sum(1 for c in text if "\u0c80" <= c <= "\u0cff")
    dev = sum(1 for c in text if "\u0900" <= c <= "\u097f")
    if kn and kn >= dev:
        return "kn"
    if dev:
        return "hi"
    return "en"


def detect_emergency(text: str) -> str | None:
    """Return the matched language code ('en'|'hi'|'mr'|'kn') or None. Checks all languages."""
    t = _normalize(text)
    if not t:
        return None
    for lang, words in KEYWORDS.items():
        if any(w in t for w in words):
            return lang
    return None


def emergency_message(text: str, matched_lang: str | None = None) -> str:
    """Fixed reply. Marathi and Hindi share a script, so use the matched keyword language."""
    lang = matched_lang if matched_lang in MESSAGES else detect_language(text)
    return MESSAGES[lang]