"""Point d'entree CLI du pipeline d'extraction PDF vers UTF-8."""

import argparse
from pathlib import Path

from app.ocr.pdf_detector import detect_pdf_type, is_text_corrupted
from app.ocr.pdf_reader import extract_text_from_pdf
from app.ocr.tesseract_service import ocr_pdf
from app.preprocess.text_cleaner import clean_text


def extract_pdf_to_txt(
    pdf_path: str,
    output_dir: str = "output",
    keep_page_markers: bool = False,
    force_ocr: bool = False,
) -> str:
    """Extrait un PDF et retourne le chemin du fichier texte produit."""
    source = Path(pdf_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"PDF introuvable : {source}")
    if source.suffix.lower() != ".pdf":
        raise ValueError(f"Le fichier doit etre un PDF : {source}")

    destination_dir = Path(output_dir).expanduser().resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    output_path = destination_dir / f"{source.stem}.txt"

    print(f"[1/4] Analyse du PDF : {source}")
    pdf_type = "scanned" if force_ocr else detect_pdf_type(str(source))
    print(f"[2/4] Type detecte : {pdf_type}")

    extraction_method = "tesseract"
    if pdf_type == "text" and not force_ocr:
        raw_text = extract_text_from_pdf(str(source))
        if is_text_corrupted(raw_text):
            print("      Texte natif corrompu : bascule vers Tesseract")
            raw_text = ocr_pdf(str(source))
        else:
            extraction_method = "native"
    else:
        raw_text = ocr_pdf(str(source))

    if not raw_text.strip():
        raise RuntimeError("L'extraction n'a produit aucun texte.")

    print(f"[3/4] Nettoyage du texte ({extraction_method})")
    cleaned_text = clean_text(raw_text, keep_page_markers=keep_page_markers)
    output_path.write_text(cleaned_text, encoding="utf-8")

    print(
        f"[4/4] Texte sauvegarde : {output_path} "
        f"({len(cleaned_text)} caracteres)"
    )
    return str(output_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extrait le texte natif ou OCR d'un jugement PDF.",
    )
    parser.add_argument(
        "pdf",
        nargs="?",
        default="uploads/Xerox Scan_04062026143239.pdf",
        metavar="PDF",
        help="Chemin du PDF a traiter (defaut : uploads/Xerox Scan_04062026143239.pdf)",
    )
    parser.add_argument("-o", "--output-dir", default="output")
    parser.add_argument("--force-ocr", action="store_true")
    parser.add_argument("--keep-page-markers", action="store_true")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    extract_pdf_to_txt(
        args.pdf,
        output_dir=args.output_dir,
        keep_page_markers=args.keep_page_markers,
        force_ocr=args.force_ocr,
    )
