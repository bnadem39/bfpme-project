"""OCR arabe base sur Tesseract."""

import os
import re
import shutil
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path
from PIL import Image, ImageOps
from pytesseract import Output


POPPLER_PATH = os.getenv(
    "POPPLER_PATH",
    r"C:\Users\htc12\Downloads\Release-26.02.0-0\poppler-26.02.0\Library\bin",
)
TESSERACT_LANG = os.getenv("TESSERACT_LANG", "ara")
TESSERACT_OEM = os.getenv("TESSERACT_OEM", "1")
PROJECT_TESSDATA_DIR = Path(__file__).resolve().parents[2] / "tessdata_best"
TESSDATA_DIR = Path(os.getenv("TESSDATA_DIR", str(PROJECT_TESSDATA_DIR)))
if (TESSDATA_DIR / f"{TESSERACT_LANG}.traineddata").is_file():
    os.environ["TESSDATA_PREFIX"] = str(TESSDATA_DIR)
TESSERACT_PSM_MODES = tuple(
    mode.strip()
    for mode in os.getenv("TESSERACT_PSM_MODES", "6,11").split(",")
    if mode.strip()
)
OCR_STRUCTURED_ANCHOR_PATTERN = re.compile(
    r"(?:القضي[ةه]|تاريخ|المحكم[ةه]|المدع[ىي]|تمويل|المؤسسات|"
    r"قضت|ل[هي]ذه|أسباب|المبالغ\s+المالية)"
)


def _configure_tesseract() -> None:
    """Configure l'executable, avec surcharge possible via TESSERACT_CMD."""
    configured = os.getenv("TESSERACT_CMD")
    candidates = [
        configured,
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    executable = next((path for path in candidates if path and Path(path).is_file()), None)
    if executable:
        pytesseract.pytesseract.tesseract_cmd = executable


_configure_tesseract()
_tesseract_validated = False


def _tesseract_config(psm: str) -> str:
    return f"--oem {TESSERACT_OEM} --psm {psm}"


def _validate_tesseract() -> None:
    global _tesseract_validated
    if _tesseract_validated:
        return
    try:
        languages = pytesseract.get_languages(config="")
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract OCR n'est pas installe. Installez Tesseract puis "
            "definissez TESSERACT_CMD avec le chemin de tesseract.exe."
        ) from exc
    if TESSERACT_LANG not in languages:
        raise RuntimeError(
            f"La langue Tesseract '{TESSERACT_LANG}' est absente. "
            "Installez le fichier ara.traineddata dans le dossier tessdata."
        )
    _tesseract_validated = True


def get_ocr_engine():
    """Compatibilite avec l'ancienne API : retourne le module pytesseract."""
    _validate_tesseract()
    return pytesseract


def pdf_to_images(
    pdf_path: str,
    output_dir: str = "output/temp_images",
    dpi: int = 300,
) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    poppler_path = POPPLER_PATH if os.path.isdir(POPPLER_PATH) else None

    image_paths = []
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    if poppler_path or shutil.which("pdfinfo"):
        images = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path)
        for index, image in enumerate(images, start=1):
            image_path = os.path.join(output_dir, f"{base_name}_page_{index}.png")
            image.save(image_path, "PNG")
            image_paths.append(image_path)
        return image_paths

    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(pdf_path) as document:
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = os.path.join(output_dir, f"{base_name}_page_{index}.png")
            pixmap.save(image_path)
            image_paths.append(image_path)
    return image_paths


def _extract_candidate(image, psm: str) -> dict:
    data = pytesseract.image_to_data(
        image,
        lang=TESSERACT_LANG,
        config=_tesseract_config(psm),
        output_type=Output.DICT,
    )
    lines = []
    words = []
    confidences = []
    current_line = None
    for index, raw_text in enumerate(data["text"]):
        text = raw_text.strip()
        if not text:
            continue
        line_key = (
            data["block_num"][index],
            data["par_num"][index],
            data["line_num"][index],
        )
        if current_line is not None and line_key != current_line and words:
            lines.append(" ".join(words))
            words = []
        current_line = line_key
        words.append(text)
        confidence = float(data["conf"][index])
        if confidence >= 0:
            confidences.append(confidence)
    if words:
        lines.append(" ".join(words))
    return {
        "text": "\n".join(lines).strip(),
        "words": len(confidences),
        "confidence": (
            sum(confidences) / len(confidences) if confidences else 0.0
        ),
    }


def _choose_candidate(candidates: list[dict]) -> dict:
    """Privilegie la confiance sans accepter une transcription trop courte."""
    maximum_words = max((item["words"] for item in candidates), default=0)
    sufficiently_complete = [
        item for item in candidates
        if item["words"] >= maximum_words * 0.85
    ]
    pool = sufficiently_complete or candidates
    best_confidence = max(item["confidence"] for item in pool)
    # Une difference inferieure a deux points n'est pas significative. Dans
    # ce cas, conserver la variante couvrant le plus de mots.
    close_confidence = [
        item for item in pool
        if item["confidence"] >= best_confidence - 2.0
    ]
    return max(
        close_confidence,
        key=lambda item: (item["words"], item["confidence"]),
    )


def _normalize_ocr_line(value: str) -> str:
    return re.sub(r"[\W_]+", "", value or "", flags=re.UNICODE)


def _structured_candidate_lines(text: str) -> list[str]:
    """Keep short windows around legal header and dispositive anchors."""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    selected: list[str] = []
    seen: set[str] = set()

    for index, line in enumerate(lines):
        if not OCR_STRUCTURED_ANCHOR_PATTERN.search(line):
            continue
        for context_line in lines[max(0, index - 1):min(len(lines), index + 3)]:
            normalized = _normalize_ocr_line(context_line)
            if normalized and normalized not in seen:
                seen.add(normalized)
                selected.append(context_line)
    return selected


def _merge_ocr_candidates(candidates: list[dict]) -> dict:
    """Preserve structured data read by an alternate Tesseract PSM mode.

    PSM 6 generally gives the best continuous body text, whereas PSM 11 often
    recognizes headers, case numbers, and party labels more accurately on court
    scans. Dropping the latter solely on average confidence loses key fields.
    """
    primary = _choose_candidate(candidates)
    primary_lines = {
        _normalize_ocr_line(line)
        for line in primary["text"].splitlines()
        if _normalize_ocr_line(line)
    }
    supplementary: list[str] = []
    seen = set(primary_lines)
    supplementary_seen: set[str] = set()

    for candidate in candidates:
        if candidate is primary:
            continue
        for line in _structured_candidate_lines(candidate["text"]):
            normalized = _normalize_ocr_line(line)
            is_anchor = bool(OCR_STRUCTURED_ANCHOR_PATTERN.search(line))
            if (
                normalized
                and normalized not in supplementary_seen
                and (normalized not in seen or is_anchor)
            ):
                seen.add(normalized)
                supplementary_seen.add(normalized)
                supplementary.append(line)

    if not supplementary:
        return primary

    return {
        **primary,
        # Put the supplemental header first so downstream extractors and the
        # context compactor see it even when the first page is long.
        "text": "\n".join([*supplementary, primary["text"]]).strip(),
    }


def _ocr_with_psm_modes(image, return_meta: bool = False):
    candidate = _merge_ocr_candidates([
        _extract_candidate(image, psm) for psm in TESSERACT_PSM_MODES
    ])
    return candidate if return_meta else candidate["text"]


def _find_horizontal_boundaries(image: Image.Image, band_height: int = 850) -> list[int]:
    """Place les coupures pres des lignes blanches pour ne pas couper le texte."""
    gray = image.convert("L")
    preview_width = min(256, gray.width)
    preview_height = max(1, round(gray.height * preview_width / gray.width))
    preview = gray.resize((preview_width, preview_height))
    rows = list(preview.getdata())
    darkness = [
        sum(255 - pixel for pixel in rows[y * preview_width:(y + 1) * preview_width])
        for y in range(preview_height)
    ]
    scale = preview_height / image.height
    boundaries = [0]
    target = band_height
    while target < image.height:
        center = round(target * scale)
        radius = max(2, round(120 * scale))
        start = max(boundaries[-1] * preview_height // image.height + 1, center - radius)
        end = min(preview_height - 1, center + radius)
        best_row = min(range(start, end + 1), key=lambda row: darkness[row])
        boundary = round(best_row / scale)
        if boundary - boundaries[-1] >= 300:
            boundaries.append(boundary)
        target = boundaries[-1] + band_height
    boundaries.append(image.height)
    return boundaries


def _ocr_by_horizontal_bands(image: Image.Image, return_meta: bool = False):
    boundaries = _find_horizontal_boundaries(image)
    chunks = []
    total_words = 0
    weighted_confidence = 0.0
    for top, bottom in zip(boundaries, boundaries[1:]):
        band = image.crop((0, top, image.width, bottom))
        # Une marge blanche aide Tesseract a reconnaitre les lignes proches
        # des bords de chaque bande.
        band = ImageOps.expand(band, border=30, fill="white")
        candidate = _ocr_with_psm_modes(band, return_meta=True)
        if candidate["text"]:
            chunks.append(candidate["text"])
            total_words += candidate["words"]
            weighted_confidence += candidate["confidence"] * candidate["words"]
    result = {
        "text": "\n".join(chunks),
        "words": total_words,
        "confidence": weighted_confidence / total_words if total_words else 0.0,
    }
    return result if return_meta else result["text"]


def _find_text_line_boxes(image: Image.Image) -> list[tuple[int, int]]:
    """Repere les lignes d'encre afin de les soumettre separement a Tesseract."""
    gray = image.convert("L")
    preview_width = min(500, gray.width)
    preview_height = max(1, round(gray.height * preview_width / gray.width))
    preview = gray.resize((preview_width, preview_height))
    pixels = list(preview.getdata())
    minimum_ink = max(3, round(preview_width * 0.006))
    active_rows = [
        y for y in range(preview_height)
        if sum(
            pixel < 190
            for pixel in pixels[y * preview_width:(y + 1) * preview_width]
        ) >= minimum_ink
    ]
    if not active_rows:
        return []

    groups = [[active_rows[0]]]
    for row in active_rows[1:]:
        # Les points et signes diacritiques arabes peuvent etre separes du
        # corps des lettres par quelques lignes blanches.
        if row - groups[-1][-1] <= 1:
            groups[-1].append(row)
        else:
            groups.append([row])

    scale = image.height / preview_height
    boxes = []
    for group in groups:
        top = max(0, round(group[0] * scale) - 25)
        bottom = min(image.height, round((group[-1] + 1) * scale) + 25)
        if bottom - top >= 20:
            boxes.append((top, bottom))
    return boxes


def _ocr_line_by_line(image: Image.Image) -> str:
    lines = []
    left = round(image.width * 0.04)
    right = round(image.width * 0.96)
    for top, bottom in _find_text_line_boxes(image):
        candidates = []
        # Une marge verticale trop grande peut attirer une ligne voisine,
        # tandis qu'une marge trop faible coupe les hampes arabes.
        for inset in (0, 7):
            line_image = image.crop((left, top + inset, right, bottom - inset))
            line_image = ImageOps.expand(line_image, border=25, fill="white")
            candidates.append(pytesseract.image_to_string(
                line_image,
                lang=TESSERACT_LANG,
                config=_tesseract_config("7"),
            ).strip())
        text = max(candidates, key=lambda value: len("".join(value.split())))
        if text:
            lines.append(text)
    return "\n".join(lines)


def ocr_image(image_path: str) -> str:
    _validate_tesseract()
    with Image.open(image_path) as image:
        global_candidate = _ocr_with_psm_modes(image, return_meta=True)
    return global_candidate["text"]


def ocr_pdf(pdf_path: str, output_dir: str = "output/temp_images") -> str:
    pages = []
    for page_number, image_path in enumerate(
        pdf_to_images(pdf_path, output_dir), start=1
    ):
        pages.append(f"--- Page {page_number} ---\n{ocr_image(image_path)}")
    return "\n\n".join(pages)


def ocr_pdf_detailed(
    pdf_path: str,
    output_dir: str = "output/temp_images",
) -> list[dict]:
    _validate_tesseract()
    pages = []
    for page_number, image_path in enumerate(
        pdf_to_images(pdf_path, output_dir), start=1
    ):
        data = pytesseract.image_to_data(
            image_path,
            lang=TESSERACT_LANG,
            config=_tesseract_config(TESSERACT_PSM_MODES[0]),
            output_type=Output.DICT,
        )
        lines = []
        for index, text in enumerate(data["text"]):
            text = text.strip()
            confidence = float(data["conf"][index])
            if not text or confidence < 0:
                continue
            lines.append({
                "text": text,
                "confidence": round(confidence / 100, 3),
                "bbox": [
                    data["left"][index],
                    data["top"][index],
                    data["width"][index],
                    data["height"][index],
                ],
            })
        pages.append({"page": page_number, "lines": lines})
    return pages
