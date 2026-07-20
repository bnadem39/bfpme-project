import os
import tempfile
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import APIConnectionError, APIError, APITimeoutError
from pydantic import BaseModel

from app.extraction.llm_extractor import EMPTY_RESULT, extract_with_llm
from app.ocr.pdf_detector import detect_pdf_type, is_text_corrupted
from app.ocr.pdf_reader import extract_text_from_pdf
from app.ocr.tesseract_service import ocr_pdf
from app.preprocess.text_cleaner import clean_text


DEFAULT_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen/qwen3.5-9b")


def _parse_origins() -> list[str]:
    raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


app = FastAPI(
    title="BFPME AI Extraction Service",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExtractionResponse(BaseModel):
    status: str
    file_name: str
    pdf_type: str
    extraction_method: str
    result: dict


def extract_judgment_text(pdf_path: str, force_ocr: bool = False) -> tuple[str, str]:
    source = Path(pdf_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"PDF introuvable : {source}")

    pdf_type = "scanned" if force_ocr else detect_pdf_type(str(source))
    extraction_method = "ocr"

    if pdf_type == "text" and not force_ocr:
        raw_text = extract_text_from_pdf(str(source))
        if is_text_corrupted(raw_text):
            raw_text = ocr_pdf(str(source))
        else:
            extraction_method = "native"
    else:
        raw_text = ocr_pdf(str(source))

    if not raw_text or not raw_text.strip():
        raise RuntimeError("Le PDF n'a produit aucun texte exploitable.")

    # Page markers let the LLM context selector keep the header and the final
    # dispositive pages of long scanned judgments.
    cleaned_text = clean_text(raw_text, keep_page_markers=True)
    if not cleaned_text.strip():
        raise RuntimeError("Le texte extrait est vide apres nettoyage.")

    return pdf_type, extraction_method, cleaned_text


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}


def _parse_multipart_form(
    content_type: str,
    body: bytes,
) -> tuple[str, bytes, bool, str]:
    if "multipart/form-data" not in content_type:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_CONTENT_TYPE",
                "message": "Le contenu doit etre en multipart/form-data.",
            },
        )

    parser_input = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
        + body
    )
    message = BytesParser(policy=default).parsebytes(parser_input)

    file_name = None
    file_bytes = None
    force_ocr = False
    model = DEFAULT_MODEL

    for part in message.iter_parts():
        field_name = part.get_param("name", header="content-disposition")
        if not field_name:
            continue

        if field_name == "file":
            file_name = part.get_filename()
            file_bytes = part.get_payload(decode=True) or b""
        elif field_name == "force_ocr":
            value = (part.get_payload(decode=True) or b"").decode(
                "utf-8",
                errors="ignore",
            )
            force_ocr = value.strip().lower() in {"1", "true", "yes", "on"}
        elif field_name == "model":
            value = (part.get_payload(decode=True) or b"").decode(
                "utf-8",
                errors="ignore",
            ).strip()
            if value:
                model = value

    if file_name is None or file_bytes is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "MISSING_FILE",
                "message": "Le champ fichier est requis.",
            },
        )

    return file_name, file_bytes, force_ocr, model


@app.post("/extract", response_model=ExtractionResponse)
async def extract_pdf(request: Request):
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    file_name, payload, force_ocr, model = _parse_multipart_form(content_type, body)

    if not file_name:
        raise HTTPException(
            status_code=400,
            detail={"code": "MISSING_FILENAME", "message": "Nom de fichier manquant."},
        )

    if not file_name.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_FILE_TYPE", "message": "Le fichier doit etre un PDF."},
        )

    temp_path = None
    try:
        if not payload:
            raise HTTPException(
                status_code=400,
                detail={"code": "EMPTY_FILE", "message": "Le fichier PDF est vide."},
            )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(payload)
            temp_path = temp_file.name

        pdf_type, extraction_method, cleaned_text = extract_judgment_text(
            temp_path,
            force_ocr=force_ocr,
        )
        result = extract_with_llm(cleaned_text, model=model)

        if "error" in result:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "LLM_INVALID_JSON",
                    "message": result["error"],
                    "raw": result.get("raw"),
                },
            )

        return ExtractionResponse(
            status="success",
            file_name=file_name,
            pdf_type=pdf_type,
            extraction_method=extraction_method,
            result=result,
        )
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "FILE_NOT_FOUND", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_INPUT", "message": str(exc)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "EXTRACTION_FAILED", "message": str(exc)},
        ) from exc
    except APITimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail={"code": "LLM_TIMEOUT", "message": "Le modele local a mis trop de temps a repondre."},
        ) from exc
    except APIConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "LLM_UNAVAILABLE", "message": "Connexion au modele local impossible."},
        ) from exc
    except APIError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "LLM_ERROR", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "INTERNAL_ERROR", "message": str(exc)},
        ) from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
