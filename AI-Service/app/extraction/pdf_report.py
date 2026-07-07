"""Generation d'un rapport PDF a partir de l'extraction LLM."""

import json
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _font_path() -> Path:
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\tahoma.ttf"),
    ]
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        raise RuntimeError("Police arabe Arial ou Tahoma introuvable")
    return path


def _rtl(value) -> str:
    text = "null" if value is None else str(value)
    return get_display(arabic_reshaper.reshape(text))


def create_extraction_pdf(data: dict, output_path: str) -> str:
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont("Arabic", str(_font_path())))

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleArabic", parent=styles["Title"], fontName="Arabic", fontSize=18,
        leading=24, alignment=TA_RIGHT, textColor=colors.HexColor("#17365D"),
    )
    value_style = ParagraphStyle(
        "ValueArabic", parent=styles["BodyText"], fontName="Arabic", fontSize=11,
        leading=17, alignment=TA_RIGHT,
    )
    label_style = ParagraphStyle(
        "Label", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=10,
        leading=15, textColor=colors.HexColor("#17365D"),
    )

    document = SimpleDocTemplate(
        str(destination), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
    )
    story = [Paragraph(_rtl("تقرير استخراج الحكم"), title), Spacer(1, 8 * mm)]

    parties = data.get("parties") if isinstance(data.get("parties"), dict) else {}
    references = data.get("references_juridiques")
    if isinstance(references, list):
        references = "\n".join(f"- {item}" for item in references)

    rows = [
        ("Tribunal", data.get("tribunal")),
        ("Numero du dossier", data.get("numero_dossier")),
        ("Date de decision", data.get("date_decision")),
        ("Demandeur", parties.get("demandeur")),
        ("Defendeur", parties.get("defendeur")),
        ("Banque", data.get("banque")),
        ("Entreprise", data.get("entreprise")),
        ("Montant", data.get("montant")),
        ("References juridiques", references),
        ("Decision", data.get("decision")),
        ("Justification", data.get("decision_justification")),
        ("Resume", data.get("resume")),
    ]
    table_data = [
        [Paragraph(label, label_style), Paragraph(_rtl(value).replace("\n", "<br/>"), value_style)]
        for label, value in rows
    ]
    table = Table(table_data, colWidths=[48 * mm, 120 * mm], repeatRows=0)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C4CE")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF0F6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    document.build(story)
    return str(destination)
