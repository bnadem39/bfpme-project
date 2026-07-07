# ocr/pdf_reader.py

import fitz  # PyMuPDF

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extrait le texte brut d'un PDF texte (non scanné).
    Retourne le texte complet, page par page, concaténé.
    """
    doc = fitz.open(pdf_path)
    full_text = []

    for i, page in enumerate(doc):
        text = page.get_text()
        full_text.append(f"--- Page {i+1} ---\n{text}")

    doc.close()
    return "\n\n".join(full_text)


def extract_text_by_page(pdf_path: str) -> list[dict]:
    """
    Extrait le texte page par page sous forme de liste structurée.
    Utile pour garder la traçabilité (ex: 'la date est trouvée page 2').
    """
    doc = fitz.open(pdf_path)
    pages = []

    for i, page in enumerate(doc):
        pages.append({
            "page_number": i + 1,
            "text": page.get_text()
        })

    doc.close()
    return pages


def extract_text_with_blocks(pdf_path: str) -> list[dict]:
    """
    Extraction plus fine : par blocs de texte avec position (x, y).
    Utile plus tard si tu veux repérer la structure du document
    (ex: en-tête tribunal en haut, signature en bas).
    """
    doc = fitz.open(pdf_path)
    all_blocks = []

    for i, page in enumerate(doc):
        blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, ...)
        for b in blocks:
            all_blocks.append({
                "page": i + 1,
                "bbox": b[:4],
                "text": b[4].strip()
            })

    doc.close()
    return all_blocks