"""Turkish and English prompt injection detection."""

import re
import unicodedata

SUSPICIOUS_PATTERNS = [
    # Previous instructions
    r"\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|rules|prompts)\b",
    r"\b(disregard|forget)\s+(all\s+)?(previous|prior|above)\s+(instructions|rules)\b",
    r"\b(onceki|onceki tum|yukaridaki)\s+(talimatlari|kurallari|komutlari)\s+(unut|yok say|gormezden gel)\b",

    # Additional instruction override patterns
    r"\b(talimatlari|kurallari|komutlari)\s+(unut|yok say|gormezden gel)\b",
    r"\bignore\s+((all|the)\s+)?(instructions|rules|prompts)\b",
    r"\bforget\s+everything\s+above\b",
    r"\bdisregard\s+everything\s+you\s+were\s+told\b",

    # System prompt disclosure
    r"\b(reveal|show|print|display)\s+(your\s+)?(system|developer|hidden)\s+(prompt|instructions|message)\b",
    r"\b(sistem|gizli|gelistirici)\s+(promptunu|talimatlarini|mesajini)\s+(goster|acikla|paylas)\b",

    # Role and authority manipulation
    r"\b(you are now|act as|pretend to be)\s+(a\s+)?(system|developer|administrator|admin)\b",
    r"\b(artik|simdi)\s+(sistem|yonetici|admin)\s+(rolundesin|olarak davran)\b",
    r"\b(system|developer)\s+override\b",
    r"\b(jailbreak|developer mode|dan mode)\b",
    r"\byou\s+are\s+now\s+(dan|in\s+developer\s+mode)\b",
    r"\b(yonetici|admin)\s+gibi\s+davran\b",

    # Security bypass
    r"\b(bypass|disable|remove)\s+(all\s+)?(security|safety|restrictions|filters)\b",
    r"\b(guvenlik|filtreleme|koruma)\s+(kurallarini|kontrollerini|filtresini)\s+(kapat|devre disi birak|as)\b",

    # Forged role delimiters
    r"\[/?(?:inst|sys)\]",
    r"<\|(?:im_start|im_end|system)\|>",
]


def _normalize(text: str) -> str:
    """Normalize Unicode and Turkish characters for pattern matching."""
    text = unicodedata.normalize("NFKC", text)
    text = text.casefold()
    text = text.replace("\u0307", "")

    replacements = str.maketrans({
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
    })

    return text.translate(replacements)


def is_suspicious(text: str) -> bool:
    """Return True when the text contains a known injection pattern."""
    if not isinstance(text, str) or not text.strip():
        return False

    normalized_text = _normalize(text)

    return any(
        re.search(pattern, normalized_text, flags=re.IGNORECASE)
        for pattern in SUSPICIOUS_PATTERNS
    )
