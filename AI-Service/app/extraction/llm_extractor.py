"""Extraction structuree d'un jugement OCR avec un LLM local."""

import json
import os
import re
from copy import deepcopy

from openai import OpenAI


client = OpenAI(
    base_url=os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1"),
    api_key=os.getenv("LM_STUDIO_API_KEY", "lm-studio"),
    timeout=float(os.getenv("LM_STUDIO_TIMEOUT_SECONDS", "180")),
)

DEFAULT_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen2.5-7b-instruct-1m")

EMPTY_RESULT = {
    "tribunal": None,
    "numero_dossier": None,
    "date_decision": None,
    "parties": {"demandeur": None, "defendeur": None},
    "banque": None,
    "entreprise": None,
    "montant": None,
    "references_juridiques": None,
    "decision": None,
    "decision_justification": None,
    "resume": None,
}

NULLABLE_STRING = {"type": ["string", "null"]}
EXTRACTION_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "judgment_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "tribunal": NULLABLE_STRING,
                "numero_dossier": NULLABLE_STRING,
                "date_decision": NULLABLE_STRING,
                "parties": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "demandeur": NULLABLE_STRING,
                        "defendeur": NULLABLE_STRING,
                    },
                    "required": ["demandeur", "defendeur"],
                },
                "banque": NULLABLE_STRING,
                "entreprise": NULLABLE_STRING,
                "montant": NULLABLE_STRING,
                "references_juridiques": {
                    "anyOf": [
                        {"type": "array", "items": {"type": "string"}},
                        {"type": "null"},
                    ]
                },
                "decision": {
                    "type": ["string", "null"],
                    "enum": [
                        "Favorable", "Defavorable",
                        "Partiellement favorable", None,
                    ],
                },
                "decision_justification": NULLABLE_STRING,
                "resume": NULLABLE_STRING,
            },
            "required": list(EMPTY_RESULT.keys()),
        },
    },
}

SYSTEM_PROMPT = """Tu extrais des informations factuelles de jugements tunisiens en arabe.
Le texte vient d'un OCR et peut contenir des lettres, espaces ou chiffres errones.

REGLES OBLIGATOIRES :
1. Utilise exclusivement les informations explicitement lisibles dans le texte fourni.
2. N'invente, ne complete et ne deduis jamais un nom, une date, un montant ou un numero.
3. Une information absente, illisible, contradictoire ou incertaine vaut JSON null.
4. Un nom masque, anonymise, remplace par des initiales ou une forme comme "س.س",
   "ح.ح", "م.ز", "..." ou "***" vaut null. Ne retourne pas les initiales.
5. Corrige seulement les erreurs OCR evidentes dans les valeurs retournees, par exemple
   "الفيول 10 ي11" vers "الفصول 10 و11". Ne reecris pas une valeur incertaine.
6. Pour les references juridiques, conserve uniquement les articles et lois cites
   explicitement. Si aucune reference fiable n'apparait, retourne null.
7. "decision" doit etre exactement "Favorable", "Defavorable",
   "Partiellement favorable" ou null. Classe-la par rapport au demandeur seulement
   si celui-ci et le dispositif sont identifiables avec certitude.
8. Tous les champs doivent etre presents. Utilise null, jamais "inconnu",
   "non mentionne", une chaine vide ou une supposition.
9. Reponds uniquement avec un objet JSON valide, sans Markdown ni commentaire."""

USER_PROMPT = """Analyse le jugement OCR suivant et remplis exactement ce schema :

{{
  "tribunal": null,
  "numero_dossier": null,
  "date_decision": null,
  "parties": {{"demandeur": null, "defendeur": null}},
  "banque": null,
  "entreprise": null,
  "montant": null,
  "references_juridiques": null,
  "decision": null,
  "decision_justification": null,
  "resume": null
}}

Contraintes de format :
- date_decision : JJ/MM/AAAA si la date complete est certaine, sinon null ;
- references_juridiques : tableau de chaines ou null ;
- resume : 2 a 4 phrases factuelles en arabe clair, ou null.

TEXTE OCR :
---
{document_text}
---"""


def _nullable(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in {
            "null", "inconnu", "inconnue", "non mentionne", "non mentionnee",
            "absent", "absente", "n/a", "indetermine", "indeterminee",
        }:
            return None
    return value


def _is_masked_party(value) -> bool:
    if not isinstance(value, str):
        return False
    compact = re.sub(r"[\s\"'،,.]", "", value)
    if "*" in compact or "…" in compact:
        return True
    # Initiales arabes ou latines separees par des points : س.س / M.Z.
    return bool(re.fullmatch(r"(?:[A-Za-z\u0621-\u064a][.]?){1,4}", compact))


def normalize_result(payload: dict) -> dict:
    """Force le schema attendu et remplace les valeurs absentes par null."""
    result = deepcopy(EMPTY_RESULT)
    if not isinstance(payload, dict):
        return result

    for key in result:
        if key == "parties":
            continue
        if key in payload:
            result[key] = _nullable(payload[key])

    parties = payload.get("parties")
    if isinstance(parties, dict):
        for role in ("demandeur", "defendeur"):
            value = _nullable(parties.get(role))
            result["parties"][role] = None if _is_masked_party(value) else value

    references = result["references_juridiques"]
    if isinstance(references, list):
        references = [str(item).strip() for item in references if _nullable(item)]
        result["references_juridiques"] = references or None
    elif references is not None:
        result["references_juridiques"] = None

    allowed_decisions = {"Favorable", "Defavorable", "Partiellement favorable"}
    if result["decision"] not in allowed_decisions:
        result["decision"] = None

    case_number = result["numero_dossier"]
    if isinstance(case_number, str):
        match = re.search(r"\b(\d{3,8})[./](\d{4})\b", case_number)
        result["numero_dossier"] = (
            f"{match.group(1)}/{match.group(2)}" if match else case_number
        )

    decision_date = result["date_decision"]
    if isinstance(decision_date, str):
        match = re.fullmatch(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", decision_date)
        if match:
            year, month, day = match.groups()
            result["date_decision"] = f"{int(day):02d}/{int(month):02d}/{year}"
    return result


def _parse_json(raw_output: str) -> dict:
    cleaned = re.sub(r"```(?:json)?|```", "", raw_output, flags=re.I).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Le modele n'a retourne aucun objet JSON")
    return json.loads(cleaned[start:end + 1])


def extract_with_llm(document_text: str, model: str = DEFAULT_MODEL) -> dict:
    if not document_text or not document_text.strip():
        raise ValueError("Le texte du jugement est vide")

    response = client.chat.completions.create(
        model=model or DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT.format(document_text=document_text)},
        ],
        temperature=0,
        max_tokens=1800,
        response_format=EXTRACTION_RESPONSE_FORMAT,
    )
    raw_output = response.choices[0].message.content or ""
    try:
        return normalize_result(_parse_json(raw_output))
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            **deepcopy(EMPTY_RESULT),
            "error": f"JSON invalide retourne par le modele: {exc}",
            "raw": raw_output,
        }
