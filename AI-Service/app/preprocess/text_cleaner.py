"""Nettoyage conservateur du texte arabe extrait."""

import re

from app.preprocess.legal_corrector import correct_legal_references


def remove_tatweel(text: str) -> str:
    return text.replace("\u0640", "")


def normalize_arabic_diacritics(text: str) -> str:
    return re.sub(r"[\u064b-\u0652\u0670\u0640]", "", text)


def normalize_ocr_arabic(text: str) -> str:
    """Corrige des artefacts certains sans deviner les mots juridiques."""
    text = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", text)
    arabic_letter = r"\u0621-\u064a"
    text = re.sub(
        rf"[\u0627\u0623\u0625\u0622]\s+\u0644(?=[{arabic_letter}])",
        "\u0627\u0644",
        text,
    )
    text = re.sub(
        rf"(?<![{arabic_letter}])\u0648\s+(?=[{arabic_letter}]{{2}})",
        "\u0648",
        text,
    )
    return text


def clean_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" +\n", "\n", text)
    return text.strip()


def remove_page_markers(text: str) -> str:
    return re.sub(r"---\s*Page\s*\d+\s*---", "", text)


def clean_text(text: str, keep_page_markers: bool = False) -> str:
    if not keep_page_markers:
        text = remove_page_markers(text)
    text = remove_tatweel(text)
    text = normalize_arabic_diacritics(text)
    text = normalize_ocr_arabic(text)
    text = correct_legal_references(text)
    return clean_whitespace(text)
