# app/utils/language_detector.py

import re

ARABIC_RANGE = re.compile(r'[\u0600-\u06FF]')
LATIN_RANGE = re.compile(r'[A-Za-zÀ-ÿ]')

def detect_segment_language(segment: str) -> str:
    """
    Detecte la langue dominante d'un segment de texte.
    Retourne 'ar', 'fr', ou 'mixed'.
    """
    arabic_chars = len(ARABIC_RANGE.findall(segment))
    latin_chars = len(LATIN_RANGE.findall(segment))

    total = arabic_chars + latin_chars
    if total == 0:
        return "unknown"

    arabic_ratio = arabic_chars / total

    if arabic_ratio > 0.7:
        return "ar"
    elif arabic_ratio < 0.3:
        return "fr"
    else:
        return "mixed"


def split_by_language(text: str) -> list[dict]:
    """
    Decoupe le texte en segments (par ligne) avec langue detectee.
    Utile pour appliquer un traitement specifique par langue.
    """
    lines = text.split('\n')
    segments = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        lang = detect_segment_language(line)
        segments.append({"text": line, "lang": lang})

    return segments