from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageInfo:
    code: str
    name: str
    native_name: str
    tts_code: str


SUPPORTED_LANGUAGES: dict[str, LanguageInfo] = {
    "en": LanguageInfo("en", "English", "English", "en-IN"),
    "hi": LanguageInfo("hi", "Hindi", "हिन्दी", "hi-IN"),
    "mr": LanguageInfo("mr", "Marathi", "मराठी", "mr-IN"),
    "gu": LanguageInfo("gu", "Gujarati", "ગુજરાતી", "gu-IN"),
    "bn": LanguageInfo("bn", "Bengali", "বাংলা", "bn-IN"),
    "ta": LanguageInfo("ta", "Tamil", "தமிழ்", "ta-IN"),
    "te": LanguageInfo("te", "Telugu", "తెలుగు", "te-IN"),
    "kn": LanguageInfo("kn", "Kannada", "ಕನ್ನಡ", "kn-IN"),
    "ml": LanguageInfo("ml", "Malayalam", "മലയാളം", "ml-IN"),
    "pa": LanguageInfo("pa", "Punjabi", "ਪੰਜਾਬੀ", "pa-IN"),
}


DEVANAGARI_RANGE = range(0x0900, 0x0980)


def detect_script_language(text: str) -> str:
    """Heuristic language detection for MVP without external deps."""
    if not text or not text.strip():
        return "en"

    sample = text[:2000]
    latin = sum(1 for c in sample if "A" <= c <= "Z" or "a" <= c <= "z")
    devanagari = sum(1 for c in sample if ord(c) in DEVANAGARI_RANGE)

    if latin > devanagari * 2 and latin > 20:
        return "en"

    if devanagari == 0:
        return "en"

    # Simple Marathi vs Hindi cues
    marathi_markers = ["आहे", "मध्ये", "म्हणून", "त्या", "होते", "करण्या", "सिंह", "उंदीर"]
    hindi_markers = ["है", "में", "के", "की", "और", "था", "थे", "चूहा", "शेर"]

    mr_score = sum(1 for m in marathi_markers if m in sample)
    hi_score = sum(1 for m in hindi_markers if m in sample)

    if mr_score > hi_score:
        return "mr"
    if hi_score > 0:
        return "hi"
    return "hi"


def get_language(code: str) -> LanguageInfo:
    return SUPPORTED_LANGUAGES.get(code, SUPPORTED_LANGUAGES["en"])
