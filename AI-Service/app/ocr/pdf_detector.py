# ocr/pdf_detector.py

import re
import unicodedata

import fitz  # PyMuPDF


def is_text_corrupted(text: str, threshold: float = 0.08) -> bool:
    """
    Detecte si le texte extrait est corrompu (lettres repetees en boucle,
    typique d'un mauvais mapping de police arabe).
    Retourne True si le ratio de caracteres repetes consecutifs depasse le seuil.
    """
    compact_text = "".join(
        char for char in unicodedata.normalize("NFKC", text or "")
        if not char.isspace()
    )
    if not compact_text:
        return False

    # Compter les caracteres contenus dans les longues repetitions, et non le
    # nombre de repetitions. L'ancien calcul donnait par exemple 1 / len(text)
    # pour "دددددددد", ce qui masquait precisement les polices arabes cassees.
    repeated_chars = sum(
        len(match.group(0))
        for match in re.finditer(r"(.)\1{3,}", compact_text)
    )
    repeated_ratio = repeated_chars / len(compact_text)

    # Un mapping de police casse produit aussi beaucoup de mots comme دددددص.
    tokens = re.findall(r"[^\W_]+", compact_text, flags=re.UNICODE)
    corrupted_tokens = sum(
        bool(re.search(r"(.)\1{2,}", token)) for token in tokens
    )
    corrupted_token_ratio = corrupted_tokens / len(tokens) if tokens else 0.0

    # Une ancienne couche OCR / un mauvais mapping de police produit souvent
    # des doubles lettres arabes partout (رر، تت، مم), sans atteindre quatre
    # repetitions. Dans un texte arabe normal, ce taux reste tres faible.
    adjacent_duplicates = len(re.findall(r"([\u0621-\u064a])\1", compact_text))
    adjacent_duplicate_ratio = adjacent_duplicates / len(compact_text)

    return (
        repeated_ratio >= threshold
        or corrupted_token_ratio >= 0.20
        or adjacent_duplicate_ratio >= 0.025
    )

def detect_pdf_type(pdf_path: str, min_chars_per_page: int = 20) -> str:
    """
    Détecte si un PDF est 'text' (texte natif) ou 'scanned' (image/scan).
    
    Retourne : 'text' ou 'scanned'
    """
    with fitz.open(pdf_path) as doc:
        if not doc:
            return "scanned"

        for page in doc:
            text = page.get_text().strip()
            if len(text) < min_chars_per_page or is_text_corrupted(text):
                # Le pipeline actuel traite le document entier avec une seule
                # methode : une page illisible suffit donc a imposer l'OCR.
                return "scanned"

    return "text"


def detect_pdf_type_detailed(pdf_path: str) -> dict:
    """
    Version détaillée : donne le type par page (utile si un PDF est mixte,
    ex: certaines pages scannées, d'autres non).
    """
    pages_info = []

    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            text = page.get_text().strip()
            char_count = len(text)
            corrupted = is_text_corrupted(text)
            page_type = "text" if char_count >= 20 and not corrupted else "scanned"
            pages_info.append({
                "page": i + 1,
                "char_count": char_count,
                "corrupted": corrupted,
                "type": page_type
            })

    return {
        "total_pages": len(pages_info),
        "pages": pages_info,
        "global_type": "scanned" if all(p["type"] == "scanned" for p in pages_info) else "mixed_or_text"
    }
