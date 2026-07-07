"""Corrections OCR conservatrices propres aux citations juridiques arabes."""

import re


_BROKEN_FUSUL = re.compile(
    r"(?:الفيول|الفيتول|الفيصول|الفصرول|الفصسول)(?=\s*\d)",
)


def correct_legal_references(text: str) -> str:
    """Corrige uniquement des formes certaines autour des numeros de loi."""
    text = _BROKEN_FUSUL.sub("الفصول", text)

    # Entre deux nombres, le ي reconnu par erreur est presque toujours le
    # connecteur و. La contrainte numerique evite de toucher le texte courant.
    text = re.sub(r"(?<=\d)\s*[ييى]\s*(?=\d)", " و", text)
    text = re.sub(r"(?<=\d)\s*و\s*(?=\d)", " و", text)

    # Une reference peut etre eclatee sur plusieurs lignes par l'OCR.
    citation = re.compile(
        r"(الفصول\s+\d+(?:\s+[وييى]\s*\d+)+)",
        flags=re.MULTILINE,
    )

    def normalize_citation(match: re.Match) -> str:
        value = re.sub(r"\s+", " ", match.group(1))
        value = re.sub(r"(?<=\d)\s+[ييى]\s*(?=\d)", " و", value)
        return value

    return citation.sub(normalize_citation, text)
