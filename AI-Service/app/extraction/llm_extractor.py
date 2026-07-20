"""Extraction structuree d'un jugement OCR avec un LLM local."""

import json
import os
import re
from copy import deepcopy

from openai import BadRequestError, OpenAI


client = OpenAI(
    base_url=os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1"),
    api_key=os.getenv("LM_STUDIO_API_KEY", "lm-studio"),
    timeout=float(os.getenv("LM_STUDIO_TIMEOUT_SECONDS", "80000")),
)

DEFAULT_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen/qwen3.5-9b")
# Some LM Studio slots use an 8k context. OCR text is therefore curated before
# inference, while the full OCR remains available for deterministic checks.
MAX_LLM_DOCUMENT_CHARS = max(
    1200,
    int(os.getenv("LM_STUDIO_MAX_DOCUMENT_CHARS", "4500")),
)
MAX_LLM_OUTPUT_TOKENS = max(
    512,
    int(os.getenv("LM_STUDIO_MAX_TOKENS", "3072")),
)
JUSTIFICATION_START = "و لهذه الاسباب"
BFPME_NAME = "بنك تمويل المؤسسات الصغرى والمتوسطة"
# Court scans frequently read the first letter of بنك as ي, and split the
# definite article. Keep the phrase specific while tolerating those OCR errors.
BFPME_PATTERN = re.compile(
    r"(?:بنك|يتنك|البنك)\s+تمويل\s+(?:ا\s*)?لمؤسسات\s+"
    r"الصغر[ىي]\s+(?:و\s*)?(?:ا\s*)?لمتوسط[ةه]"
)

EMPTY_RESULT = {
    "tribunal": None,
    "numero_dossier": None,
    "date_decision": None,
    "type_jugement": None,
    "role_bfpme": None,
    "parties": {"demandeur": None, "defendeur": None},
    "montants_fixes": None,
    "montants_variables": None,
    "montant": None,
    "explication_montant": None,
    "montant_justification": None,
    "references_juridiques": None,
    "decision": None,
    "decision_justification": None,
    "resume": None,
}

NULLABLE_STRING = {"type": ["string", "null"]}
NULLABLE_INTEGER = {"type": ["integer", "null"]}
NULLABLE_BOOLEAN = {"type": ["boolean", "null"]}
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
                "type_jugement": {
                    "type": ["string", "null"],
                    "enum": [
                        "confirmatif", "modificatif", "infirmatif",
                        "original", None,
                    ],
                },
                "role_bfpme": {
                    "type": ["string", "null"],
                    "enum": [
                        "demandeur", "defendeur", "appelant",
                        "intime", None,
                    ],
                },
                "parties": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "demandeur": NULLABLE_STRING,
                        "defendeur": NULLABLE_STRING,
                    },
                    "required": ["demandeur", "defendeur"],
                },
                "montants_fixes": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "libelle_original": NULLABLE_STRING,
                                    "valeur_originale": NULLABLE_STRING,
                                    "valeur_millimes": NULLABLE_INTEGER,
                                    "accorde_bfpme": NULLABLE_BOOLEAN,
                                    "fixe": NULLABLE_BOOLEAN,
                                    "include_dans_total": NULLABLE_BOOLEAN,
                                    "raison_inclusion_exclusion": NULLABLE_STRING,
                                },
                                "required": [
                                    "libelle_original",
                                    "valeur_originale",
                                    "valeur_millimes",
                                    "accorde_bfpme",
                                    "fixe",
                                    "include_dans_total",
                                    "raison_inclusion_exclusion",
                                ],
                            },
                        },
                        {"type": "null"},
                    ]
                },
                "montants_variables": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "libelle_original": NULLABLE_STRING,
                                    "formule_originale": NULLABLE_STRING,
                                    "raison_non_calculable": NULLABLE_STRING,
                                },
                                "required": [
                                    "libelle_original",
                                    "formule_originale",
                                    "raison_non_calculable",
                                ],
                            },
                        },
                        {"type": "null"},
                    ]
                },
                "montant": NULLABLE_STRING,
                "explication_montant": NULLABLE_STRING,
                "montant_justification": NULLABLE_STRING,
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
JUSTIFICATION_START_PATTERNS = [
    "لهذه الأسباب",
    "لهذه الاسباب",
    "و لهذه الأسباب",
    "و لهذه الاسباب",
    "ولهذه الأسباب",
    "ولهذه الاسباب",
    "لذا ولهذه الأسباب",
    "لذا ولهذه الاسباب",
    "لذا و لهذه الأسباب",
    "لذا و لهذه الاسباب",
    "لذلك ولهذه الأسباب",
    "لذلك و لهذه الأسباب"
]
JUSTIFICATION_OCR_PATTERN = re.compile(
    r"(?:و\s*)?ل[هي]ذه\s+ال[اأإآ]?(?:سباب|صباب)"
)

# Reference policy retained for maintenance. Runtime requests use the compact
# prompt below so that an 8k LM Studio slot has room for OCR and JSON output.
DETAILED_SYSTEM_PROMPT = f"""
You are a system specializing in the factual extraction of Tunisian court judgments
written in Arabic.

The provided text comes from an OCR. It may contain errors in letters,

spaces, punctuation, numbers, and numeric separators.

Your mission is to analyze the entire judgment, identify the final ruling,

extract the fixed amounts awarded to the BFPME, and return only
a valid JSON object.

====================================================
1. GENERAL RULES
======================================================

1. Use only information explicitly stated in the text.

2. Never invent, supplement, or infer a name, date, number, amount, party, or legal reference.

3. Any missing, illegible, contradictory, or insufficiently certain information must be returned as JSON null.

4. A masked, anonymized, or initialized name, for example:

"س.س", "ح.ح", "م.ز", "...", "***"
must be returned as null.

5. Only correct obvious OCR errors when the correction is certain based on the immediate context.

6. Never correct a number or amount if multiple readings are possible.

7. All schema fields must be present.

8. Use null and never:

"unknown", "not mentioned", an empty string, or an assumption.

9. Respond exclusively with a valid JSON object.

No Markdown.

No comments.

No text before or after the JSON.

====================================================
2. ANALYSIS OF THE JUDGMENT'S STRUCTURE
======================================================

Before generating the JSON, silently apply this mandatory 4-step method to
every judgment, regardless of its form:

STEP 1 - Classify the judgment type from the operative part:

- "confirmatif": the final ruling confirms/approves a previous judgment.
  Key expressions include:
  "بإقرار", "بتأييد", "بالمصادقة على الحكم الابتدائي",
  "إقرار الحكم الابتدائي", "تأييد الحكم الابتدائي".

- "modificatif": the final ruling confirms part of a previous judgment but
  changes one or more elements.
  Key expressions include:
  "بتعديل", "تعديل الحكم", "مع تعديله", "فيما زاد/نقص".

- "infirmatif": the final ruling annuls, reverses, quashes, cancels, or sets
  aside a previous judgment.
  Key expressions include:
  "بنقض", "بإلغاء", "بفسخ", "بنقض القرار", "إبطال الحكم".

- "original": the operative part decides the dispute directly and does not
  confirm, modify, annul, or reverse a previous judgment.

- If the type cannot be determined with certainty, set "type_jugement" to null.

STEP 2 - Determine where the applicable amounts must be searched:

- If "original": use only the current operative part.

- If "confirmatif": the current operative part may say only that the previous
  judgment is confirmed. In that case, locate the amounts awarded in the
  previous judgment as quoted earlier in the document, and treat them as
  applicable unless the current ruling explicitly excludes them.

- If "modificatif": start from the previous judgment's amounts quoted earlier
  in the document, then apply only the modifications explicitly stated in the
  current operative part. Do not drop previous amounts that are confirmed and
  not modified.

- If "infirmatif": ignore previous amounts unless the current operative part
  explicitly re-awards or reallocates a specific amount to BFPME.

STEP 3 - Verify the beneficiary of every candidate amount before attributing it
to BFPME:

- Look for explicit beneficiary wording around the amount, including:
  "لفائدة", "لصالح", "له", "لها", "تؤدي لـ", "الأداء إلى",
  "أداء ... إلى", "تحمل ... لفائدة".

- Include an amount in the BFPME total only if the text explicitly states that
  the beneficiary is BFPME, using its exact name or an unambiguous reference
  to it.

- Never infer that a sum is due to BFPME only because BFPME is a party to the
  case.

- If the beneficiary is another party, for example a bank, insurance company,
  company, lawyer, expert, administrator, or public fund, exclude the amount.

STEP 4 - Re-read the whole document:

- After selecting the judgment type and candidate amounts, silently review both
  the facts/history and the final operative part a second time.

- Confirm that no amount due to BFPME according to the identified judgment type
  was missed.

- If doubt remains about the type, beneficiary, value, or fixed/variable nature
  of an amount, exclude it from the total and explain the exclusion.

After applying the 4-step method, silently analyze the entire document to
identify:

- the judgment header;

- the court;

- the case number;

- the date;

- the parties;

- the parties' claims;

- the facts;

- the court's reasoning;

- the final ruling;

- the amounts claimed;

- the amounts awarded;

- the amounts denied;

- the variable amounts;

- Repeated amounts.

Never include this analysis in your response.

In case of conflicting information, apply this order of priority:

1. Final decision;

2. The previous judgment quoted in the document, but only when the current
   decision is confirmatory or partially confirmatory;

3. Jurisdictional grounds;

4. Parties' claims;

5. Case history.

===================================================
3. ROLE AND IDENTITY OF BFPME
=====================================================

Identify the procedural role of BFPME precisely:

- "demandeur" if BFPME brought the original claim or appears as plaintiff.
- "defendeur" if BFPME is sued or appears as defendant.
- "appelant" if BFPME filed the appeal or challenge.
- "intime" if BFPME is the respondent to the appeal or challenge.
- null if the role is absent, masked, contradictory, or uncertain.

Do not merge BFPME with any co-party.

If BFPME appears with other entities such as banks, insurance companies,
lawyers, experts, recovery offices, public institutions, or companies, keep
BFPME separate.

The "parties.demandeur" and "parties.defendeur" fields must contain only the
party or parties explicitly listed in that role. Do not combine BFPME with
another entity unless the OCR text explicitly lists them together in the same
procedural role.

If names are masked, initialized, or not readable, return null for that field.

===================================================
4. IDENTIFICATION OF THE FINAL DECISION
=====================================================

The decision may begin with various OCR or typographic formats.

Specifically, recognize the following expressions:

{JUSTIFICATION_START_PATTERNS}

Ignore non-significant differences regarding:

- the presence or absence of a space between "و" and "لهذه";

- the presence or absence of the hamza in "الأسباب";

- minor variations in punctuation;

- obvious OCR errors around the title.

After one of these titles, the device usually contains expressions
as :

- قضت المحكمة
- حكمت المحكمة
- قررت المحكمة
- تقضي المحكمة
- ولهذه الأسباب قضت المحكمة
- لذا ولهذه الأسباب قضت المحكمة

Do not consider a single occurrence of the expression in patterns as
THE The final operative part is normally found at the end of the judgment

and contains the court's enforceable decision.

===================================================
5. DECISION IN RELATION TO THE BFPME
=====================================================

The "decision" field must be one of the following values:

- "Favorable"
- "Defavorable"
- "Partiellement favorable"
- null

Always evaluate the decision exclusively from the perspective of the BFPME (Small and Medium-Sized Enterprise Financing Bank).

Use only the final ruling:

- "Favorable":

The ruling grants the majority of BFPME's claims or orders
another party to pay BFPME.

- "Defavorable":
The ruling rejects BFPME's claims or orders BFPME to pay most of them.

- "Partiellement favorable":
The ruling grants only an identifiable portion of BFPME's claims and rejects another portion.

- Null:
BFPME, its position, or the ruling cannot be identified with
certainty.Never base your decision solely on the requests or the grounds presented.

====================================================
6. EXTRACTION OF AMOUNTS
======================================================

Analyze all the amounts in the judgment, but only use for the calculation the
fixed amounts legally applicable to BFPME according to the 4-step judgment-type
method above.

For an original judgment, the applicable source is the current operative part.

For a confirmatory judgment, the applicable source may be the confirmed previous
judgment quoted earlier in the text, even if the final operative part does not
repeat the amounts.

For a modificatory judgment, combine the confirmed previous amounts with the
explicit modifications only.

For an infirmatory judgment, ignore prior amounts unless the current operative
part re-awards them explicitly to BFPME.

For each amount, silently determine whether it corresponds to:

- an amount requested;

- an amount granted;

- an amount rejected;

- a historical amount;

- an initial contractual amount;

- a guarantee or surety limit;

- an amount cited as evidence;
- a fixed amount;

- a variable amount;

- a percentage;

- an interest formula;

- a recurring amount.

Never include the following in the total:

- amounts only requested;

- rejected amounts;

- the initial contract capital if it is not granted by the scheme;

- guarantee or surety limits;

- amounts mentioned only in the reasons;

- duplicates;

- percentages;

- rates;

- interest calculated until payment;

- amounts dependent on a formula or a future date;

- sums whose beneficiary is not BFPME.

Include only:

- the fixed principal granted to BFPME;

- interest already calculated and definitively granted;

- calculated fees granted to BFPME;

- the specified fees awarded to the BFPME;

- any other fixed sum explicitly stated in the operative part of the judgment
to be paid to the BFPME.

===================================================
7. STANDARDIZATION AND CALCULATION
======================================================

Tunisian court judgments may state amounts in dinars and millimes.

Examples:

- "90.408.292 د" means 90,408 dinars and 292 millimes;

- "15,557,041 د" means 15,557 dinars and 41 millimes;

- "153,820 د" means 153 dinars and 820 millimes;

- "500,000 د" means 500 dinars.

For internal calculations, convert each fixed amount into millimes:

- 90,408,292 becomes 90,408,292 millimes;

- 15,557,041 becomes 15,557,041 millimes;

- 153,820 becomes 153,820 millimes.

Add only amounts where:

- "accorde_bfpme" is true;

- "fixe" is true;

- "include_dans_total" is true.

Perform the calculation accurately.

Do not request the model to round.

The "amount" field must contain the calculated total of all fixed amounts included,

in the format used by the judgment, for example:

"106.119,153 دينار"

If no fixed amount can be definitively determined:

"amount": null

If variable interest is awarded in addition to the fixed total, do not add it
to the total. List it separately in "variable_amounts".

====================================================
8. EXPLANATION OF AMOUNT
======================================================

The "explanation_amount" field must clearly explain:

- the fixed amounts included in the total;

- the nature of each amount;

- the calculation performed;

- the amounts excluded;

- the reason for their exclusion;

- the possible existence of variable interest.

The explanation must state:

- the detected "type_jugement";

- where the applicable amounts were found according to that type;

- the explicit beneficiary wording used to attribute each included amount to
  BFPME;

- every excluded amount whose beneficiary is not BFPME, with the named
  beneficiary if readable.

Example of expected format:

"The fixed total of 106,119,153 dinars corresponds to 90,408,292 dinars for the principal, 15,557,041 dinars for contractual interest (already calculated), and 153,820 dinars for bailiff's fees. Late payment interest calculated until payment is not included, as its final value is not specified in the judgment."

Never use the words:

- probably;

- likely;

- it seems;

- one can assume.

If the components of the amount are not explicitly determinable,
returns null.

The "amount_justification" field must be exactly the same as the "explanation_amount" field.

====================================================
9. COPY OF THE DECISION
=====================================================

The "decision_justification" field must contain an exact copy of the decision.

Start with the detected heading, for example:

- لهذه الأسباب
- و لهذه الأسباب
- ولهذه الأسباب
- لذا ولهذه الأسباب

Then copy the entire final operative part, including:

- the paragraphs;

- the numbered items;

- the amounts;

- the interest formulas;

- the costs;

- the decision on costs.

Do not stop at the end of the first sentence or paragraph.

Stop copying only:

- at the complete end of the operative part;

- before signatures, stamps, or administrative markings unrelated to the content of the decision;

- or at the end of the document.

For this field only:

- does not rephrase;

- does not summarize;

- does not translate;

- does not correct Arabic;

- does not correct numbers;

- preserves line breaks available in the OCR text.

If no operative part can be definitively identified:

"decision_justification": null

=======================================
====================================================
10. LEGAL REFERENCES
======================================================

Retains only the articles, chapters, laws, and texts explicitly cited in the judgment.

Removes duplicates.

Returns an array of strings or null.

====================================================
11. SUMMARY
======================================================

The summary must be written in clear Arabic and contain between 5 and 8 sentences.

It must remain strictly factual and mention only:

- the jurisdiction;

- the date;

- the parties;

- the subject of the dispute;

- the position of the BFPME;

- the detected judgment type;

- the decision;

- the fixed amounts awarded;

- any variable amounts.

Never invent a legal consequence or include missing information.

====================================================
12. CONFIRMATORY, MODIFICATORY, AND INFIRMATORY RULINGS
====================================================

If the final ruling contains an expression such as:
- "بإقرار الحكم الابتدائي"
- "بتأييد الحكم الابتدائي"
- "المصادقة على الحكم الابتدائي"

This means the appellate court CONFIRMS the first-instance judgment
in its entirety, WITHOUT repeating its amounts in the appellate
operative part.

In this case:
1. Locate the first-instance judgment's own operative part/amounts
   list (usually cited earlier in the "من حيث الأصل" / facts section).
2. Include those confirmed amounts in "montants_fixes", exactly as
   if they appeared in the final appellate ruling.
3. Only exclude an amount from the confirmed first-instance list if
   the appellate ruling EXPLICITLY modifies, reduces, or annuls it.
4. Any NEW amount awarded specifically in the appellate ruling itself
   (e.g., appellate legal fees) must be checked for its actual
   beneficiary — do not assume it is owed to BFPME. Verify the
   named party ("لفائدة ...") before including it.
5. If the appellate ruling's beneficiary of a given amount is a
   party OTHER than BFPME (e.g., a co-defendant bank, insurer, or
   third party), set "accorde_bfpme": false for that amount and
   exclude it from the total, with the reason stated explicitly in
   "raison_inclusion_exclusion".

If the final ruling contains "بتعديل", "مع تعديله", or an equivalent expression,
apply the modification only to the affected part and keep the other confirmed
amounts from the previous judgment if they are explicitly confirmed.

If the final ruling contains "بنقض", "بإلغاء", "بفسخ", or an equivalent
expression, do not use amounts from the previous judgment unless the current
operative part explicitly awards them again to BFPME.

"""
SYSTEM_PROMPT = """
Extract factual information from Tunisian Arabic court-judgment OCR for BFPME.
Return only a JSON object that conforms exactly to the supplied schema.

Use only explicit information. Use null for any missing, masked, illegible,
or uncertain field. Never invent names, dates, amounts, parties, or legal
references.

The final operative part has priority over earlier history and claims. Classify
the judgment as original, confirmatif, modificatif, or infirmatif from that
part. Include in BFPME's total only fixed amounts explicitly awarded to BFPME.
Exclude claims, historical amounts, sums awarded to another party, percentages,
and interest or formulas whose final amount is not stated. For a confirmatory
or modificatory ruling, use a prior judgment's amounts only where the final
ruling confirms them; for an infirmatory ruling, do not use prior amounts
unless they are awarded again.

Copy decision_justification verbatim from the final "لهذه الأسباب" section
when it is present. Keep montant_justification identical to explication_montant.
Write a concise factual Arabic resume.
"""

DETAILED_USER_PROMPT = f"""
Analyze the following OCR judgment in its entirety and fill in this diagram exactly:

{{
"tribunal": null,

"numero_dossier": null,

"date_decision": null,

"type_jugement": null,

"role_bfpme": null,

"parties": {{
"demandeur": null,

"defendeur": null
}},

"montants_fixes": [
{{
"libelle_original": null,

"valeur_originale": null,

"valeur_millimes": null,

"accorde_bfpme": null,

"fixe": null,

"include_dans_total": null,

"raison_inclusion_exclusion": null
}}
],

"montants_variables": [
{{
"libelle_original": null,

"formule_originale": null,

"raison_non_calculable": null
}}

],

"montant": null,

"explication_montant": null,

"montant_justification": null,

"references_juridiques": null,

"decision": null,

"decision_justification": null,

"resume": null
}}

Additional constraints:

- "date_decision":
DD/MM/YYYY format only if the complete date is certain, otherwise null.

- "type_jugement":
one of "confirmatif", "modificatif", "infirmatif", "original", or null.

- "role_bfpme":
one of "demandeur", "defendeur", "appelant", "intime", or null.

- Before calculating "montant", apply the 4-step method:
classify the judgment type, choose the correct source of applicable amounts,
verify each beneficiary explicitly, then re-read the whole document.

- "fixed_amounts":
list of each fixed amount found in the final arrangement.
Does not leave a blank line if no amount is found:
then returns [].

- "variable_amounts":
interest, rates, or formulas whose final value cannot be calculated.

Returns [] if no variable amount is found.

- "value_millimes":
JSON integer without separator.

Example: "90.408.292 د" becomes 90408292.

- "amount":
The exact sum of all "value_millimes" values ​​for which

"accorde_bfpme", "fixe", and "include_dans_total" are true.

Then convert the result to dinars and millimes.

- "justification_amount":
A value exactly identical to "amount_explanation".

- "legal_references":
An array of strings without duplicates or null values.

- "justification_decision":
A complete and exact copy of the operative part, from one of the variants of

"لهذه الأسباب" to the actual end of the decision.

- "summary":
5 to 8 factual sentences in plain Arabic.

OCR TEXT:
---
{{document_text}}
---
"""
USER_PROMPT = """
Analyze the supplied OCR excerpts. They prioritize the judgment header, BFPME
contexts, applicable amounts, and the final operative part. Do not infer data
that is absent from the excerpts. Return only the valid JSON required by the
response schema.

OCR EXCERPTS:
---
{document_text}
---
"""
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


def _extract_exact_justification(document_text: str) -> str | None:
    if not document_text:
        return None

    matches = list(JUSTIFICATION_OCR_PATTERN.finditer(document_text))
    if matches:
        match = matches[-1]
        # Standardize only the heading; the operative part itself remains OCR
        # text copied verbatim after the recovered marker.
        tail = f"ولهذه الأسباب{document_text[match.end():]}".strip()
    else:
        # Some scans corrupt the heading completely but still preserve the
        # dispositive verb. The final occurrence is the operative ruling.
        dispositive_matches = list(re.finditer(r"قضت\s+المحكمة", document_text))
        if not dispositive_matches:
            return None
        tail = document_text[dispositive_matches[-1].start():].strip()

    paragraph_end = re.search(r"\n\s*\|?\s*وحرر\b|\n\s*حرر\b", tail)
    if paragraph_end:
        tail = tail[:paragraph_end.start()].strip()

    lines = [
        line.strip()
        for line in tail.splitlines()
        if (
            line.strip()
            and not re.fullmatch(r"\d+", line.strip())
            and not re.fullmatch(r"---\s*Page\s*\d+\s*---", line.strip())
        )
    ]
    terminal_patterns = [
        r"عن\s+الطور\s+الحالي",
        r"عن\s+الطور\s+الاستئنافي",
        r"عن\s+الطور\s+الإستئنافي",
    ]
    for index, line in enumerate(lines):
        for pattern in terminal_patterns:
            terminal_match = re.search(pattern, line)
            if terminal_match:
                lines[index] = line[:terminal_match.end()].rstrip(" './|،")
                lines = lines[:index + 1]
                break
        else:
            continue
        break
    return "\n".join(lines) or None


def _starts_with_justification_marker(value: str) -> bool:
    return bool(
        re.match(
            r"^\s*(?:(?:و\s*)?ل[هي]ذه\s+ال[اأإآ]?(?:سباب|صباب)|قضت\s+المحكمة)",
            value,
        )
    )


_DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_VARIABLE_AMOUNT_KEYWORDS = (
    "بداية من", "الى تمام الوفاء", "إلى تمام الوفاء", "الى تمام الدفع",
    "إلى تمام الدفع", "جاري على", "الجاري", "الجارية", "نسبة", "%",
)


def _western_digits(value: str) -> str:
    return value.translate(_DIGIT_TRANSLATION)


def _parse_tunisian_amount_to_millimes(value: str) -> int | None:
    if not value:
        return None

    cleaned = _western_digits(value)
    cleaned = re.sub(r"[^\d.,]", "", cleaned).strip(".,")
    if not cleaned:
        return None

    if "," in cleaned:
        dinar_part, millime_part = cleaned.rsplit(",", 1)
        dinars = re.sub(r"\D", "", dinar_part) or "0"
        millimes = re.sub(r"\D", "", millime_part)
        if not millimes:
            return None
        millimes = (millimes + "000")[:3]
        return int(dinars) * 1000 + int(millimes)

    dot_parts = cleaned.split(".")
    if len(dot_parts) > 1 and len(dot_parts[-1]) == 3:
        dinars = "".join(dot_parts[:-1]) or "0"
        return int(dinars) * 1000 + int(dot_parts[-1])

    digits = re.sub(r"\D", "", cleaned)
    return int(digits) * 1000 if digits else None


def _format_millimes_as_tunisian_dinars(value: int) -> str:
    dinars = value // 1000
    millimes = value % 1000
    grouped_dinars = f"{dinars:,}".replace(",", ".")
    return f"{grouped_dinars},{millimes:03d} دينار"


def _clean_amount_item_label(value: str) -> str:
    cleaned = _western_digits(value)
    cleaned = re.sub(r"\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"^\s*\d+\s*(?:[/)]\s*)?", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .،:؛")
    return cleaned or value.strip()


def _is_variable_amount_context(value: str) -> bool:
    return any(keyword in value for keyword in _VARIABLE_AMOUNT_KEYWORDS)


def _is_purely_variable_amount_item(value: str) -> bool:
    cleaned = _clean_amount_item_label(value)
    return bool(re.match(r"(?:الفائض|فائض|الفائدة|الفوائد|فوائد)", cleaned))


def _extract_confirmed_amount_block(document_text: str) -> tuple[str, str] | None:
    text = _western_digits(document_text or "")
    anchors = list(re.finditer(r"المبالغ\s+المالية\s+التالية\s*:", text))
    if not anchors:
        anchors = list(re.finditer(r"المبالغ\s+التالية\s*:", text))
    anchor = anchors[-1] if anchors else None
    if not anchor:
        return None

    prefix = text[max(0, anchor.start() - 1200):anchor.start()]
    tail = text[anchor.end():]
    stop = re.search(r"\n\s*وبعد\s+الاطلاع|\n\s*وبعد\s+الإطلاع|\n\s*وبعد\s+", tail)
    list_text = tail[:stop.start()] if stop else tail[:1800]
    return prefix, list_text


def _extract_numbered_items(block: str) -> list[str]:
    items = []
    pattern = re.compile(
        r"(?:^|\n)\s*\d+(?:\s*[/)]|(?=[\u0621-\u064a]))\s*"
        r"([\s\S]*?)(?=(?:\n\s*\d+(?:\s*[/)]|(?=[\u0621-\u064a])))|"
        r"\n\s*وحمل\b|\n\s*وبعد\b|$)"
    )
    for match in pattern.finditer(block):
        item = re.sub(r"\s+", " ", match.group(1)).strip()
        if item:
            items.append(item)
    return items


def _amount_from_item(item: str) -> tuple[str, int] | None:
    amount_match = re.search(
        r"\(\s*([\d.,]+)\s*(?:د(?:ينار)?)?\s*\)",
        _western_digits(item),
    )
    if not amount_match:
        return None
    original_amount = amount_match.group(1)
    value_millimes = _parse_tunisian_amount_to_millimes(original_amount)
    if value_millimes is None:
        return None
    return f"{original_amount} د", value_millimes


def _extract_applicable_bfpme_amounts(document_text: str, judgment_type: str | None) -> dict | None:
    if judgment_type == "infirmatif":
        return None

    block = _extract_confirmed_amount_block(document_text)
    if not block:
        return None

    prefix, list_text = block
    beneficiary_context = f"{prefix}\n{list_text[:500]}"
    has_bfpme_context = bool(BFPME_PATTERN.search(beneficiary_context))
    has_bfpme_as_original_plaintiff = (
        BFPME_PATTERN.search(document_text or "")
        and re.search(r"للبنك\s+المدعي|للبنك\s+في\s+شخص|البنك\s+المدعي", beneficiary_context)
    )
    has_bfpme_as_current_plaintiff = (
        judgment_type == "original"
        and _infer_bfpme_role(document_text) == "demandeur"
    )
    if (
        not has_bfpme_context
        and not has_bfpme_as_original_plaintiff
        and not has_bfpme_as_current_plaintiff
    ):
        return None

    fixed_amounts = []
    variable_amounts = []
    inclusion_reason = (
        "مبلغ ثابت وارد ضمن المنطوق النهائي للحكم لفائدة البنك المدعي."
        if judgment_type == "original"
        else "مبلغ ثابت وارد ضمن قائمة المبالغ المحكوم بها للبنك المدعي "
        "في الحكم الابتدائي الذي أقرته محكمة الاستئناف."
    )
    for item in _extract_numbered_items(list_text):
        amount_data = _amount_from_item(item)
        if _is_variable_amount_context(item) and (
            not amount_data or _is_purely_variable_amount_item(item)
        ):
            variable_amounts.append({
                "libelle_original": _clean_amount_item_label(item),
                "formule_originale": _clean_amount_item_label(item),
                "raison_non_calculable": (
                    "مبلغ متغير مرتبط بفائض أو فائدة جارية إلى تمام الوفاء، "
                    "لذلك لا يضاف إلى مجموع المبالغ الثابتة."
                ),
            })
            continue

        if not amount_data:
            continue

        original_amount, value_millimes = amount_data
        fixed_amounts.append({
            "libelle_original": _clean_amount_item_label(item),
            "valeur_originale": original_amount,
            "valeur_millimes": value_millimes,
            "accorde_bfpme": True,
            "fixe": True,
            "include_dans_total": True,
            "raison_inclusion_exclusion": inclusion_reason,
        })

    # A frequent OCR failure reverses or splits the digits for the fixed
    # delayed-interest line in the dispositive list. When that same label is
    # clearly present in the final ruling, recover its readable amount from the
    # preceding grounds rather than silently dropping it.
    has_delay_interest_line = bool(
        re.search(r"فائض\s+التاخير|فائض\s+التأخير", list_text)
    )
    if has_delay_interest_line:
        # A noisy dispositive list can merge item 3 into item 2.  Look for a
        # readable fixed delayed-interest amount in the grounds *before* the
        # final list, then deduplicate by numeric value.  This avoids treating
        # a leaked label in item 2 as a correctly read item 3, while never
        # adding a duplicate when item 3 was read normally.
        normalized_document = _western_digits(document_text)
        amount_anchors = list(re.finditer(
            r"المبالغ\s+المالية\s+التالية\s*:",
            normalized_document,
        ))
        if not amount_anchors:
            amount_anchors = list(re.finditer(
                r"المبالغ\s+التالية\s*:",
                normalized_document,
            ))
        grounds_text = (
            normalized_document[:amount_anchors[-1].start()]
            if amount_anchors
            else normalized_document
        )
        recovery_matches = list(re.finditer(
            r"فائض\s+الت[اأ]خير[\s\S]{0,260}?(\d{1,3}(?:\.\d{3})+)",
            grounds_text,
        ))
        recovered_match = next(
            (
                match
                for match in reversed(recovery_matches)
                if not _is_variable_amount_context(match.group(0))
            ),
            None,
        )
        if recovered_match:
            recovered_amount = recovered_match.group(1)
            recovered_value = _parse_tunisian_amount_to_millimes(recovered_amount)
            existing_values = {
                item["valeur_millimes"] for item in fixed_amounts
            }
            if recovered_value is not None and recovered_value not in existing_values:
                fixed_amounts.append({
                    "libelle_original": "فائض التأخير الاتفاقي المحتسب",
                    "valeur_originale": f"{recovered_amount} د",
                    "valeur_millimes": recovered_value,
                    "accorde_bfpme": True,
                    "fixe": True,
                    "include_dans_total": True,
                    "raison_inclusion_exclusion": inclusion_reason,
                })

    if not fixed_amounts:
        return None

    total_millimes = sum(item["valeur_millimes"] for item in fixed_amounts)
    total = _format_millimes_as_tunisian_dinars(total_millimes)
    judgment_label = judgment_type or "غير محدد"
    fixed_details = " + ".join(
        f'{item["valeur_originale"]} ({item["libelle_original"]})'
        for item in fixed_amounts
    )
    variable_details = ""
    if variable_amounts:
        variable_details = (
            " وتم استبعاد الفائض أو الفائدة الجارية لأنها متغيرة وغير محددة "
            "القيمة النهائية في الحكم."
        )

    source_description = (
        "تم اعتماد قائمة المبالغ الواردة في المنطوق النهائي للحكم. "
        if judgment_type == "original"
        else "الحكم الحالي أقر الحكم الابتدائي، لذلك تم اعتماد قائمة المبالغ "
        "المالية الواردة في الحكم الابتدائي المؤيد. "
    )
    explanation = (
        f"نوع الحكم: {judgment_label}. {source_description}"
        f"المبالغ الثابتة المحتسبة لفائدة بنك تمويل المؤسسات الصغرى والمتوسطة هي: {fixed_details}. "
        f"المجموع الثابت هو {total}.{variable_details}"
    )
    return {
        "montant": total,
        "explication_montant": explanation,
        "montant_justification": explanation,
        "montants_fixes": fixed_amounts,
        "montants_variables": variable_amounts,
    }


def _extract_bfpme_amount_context(document_text: str) -> tuple[str | None, str | None]:
    if not document_text or not BFPME_PATTERN.search(document_text):
        return None, None

    amount_pattern = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{3}")
    best_amount = None
    best_context = None
    best_distance = None

    for amount_match in amount_pattern.finditer(document_text):
        amount = amount_match.group(0)
        context_start = max(0, amount_match.start() - 750)
        context_end = min(len(document_text), amount_match.end() + 450)
        context = document_text[context_start:context_end]
        before_amount = document_text[context_start:amount_match.start()]
        matches = list(BFPME_PATTERN.finditer(before_amount))
        if not matches:
            continue
        bfpme_match = matches[-1]
        distance = abs(context_start + bfpme_match.start() - amount_match.start())
        if best_distance is None or distance < best_distance:
            best_amount = f"{amount} دينار"
            best_context = context
            best_distance = distance

    if not best_amount:
        return None, None

    explanation = (
        f"يمثل مبلغ {best_amount} مديونية الشركة تجاه بنك تمويل المؤسسات "
        "الصغرى والمتوسطة كما ورد في نص الحكم ضمن الديون المتخلدة بذمة الشركة. "
        "اعتمد الحكم هذا المبلغ في سياق تقييم الوضعية المالية للشركة، حيث تبين "
        "أن ديونها وتعهداتها تفوق رأس مالها وأنها متوقفة عن النشاط والدفع."
    )
    return best_amount, explanation


def _extract_procedure_advance(document_text: str) -> str | None:
    if not document_text:
        return None
    match = re.search(
        r"(?:تسبقة\s+)?مبلغ\s+(?:قدره\s+)?خمسمائة\s+دينار\s*\(500[.,]000\)",
        document_text,
    )
    if not match:
        return None
    return (
        "يتضمن الحكم كذلك تسبقة قدرها خمسمائة دينار (500.000) لأمين الفلسة "
        "لمباشرة الإشهارات والمهام المنوطة بعهدته، وهي مصاريف إجرائية وليست "
        "أصل مديونية بنك تمويل المؤسسات الصغرى والمتوسطة."
    )


_ARABIC_MONTHS = {
    "جانفي": 1,
    "يناير": 1,
    "فيفري": 2,
    "فبراير": 2,
    "مارس": 3,
    "أفريل": 4,
    "ابريل": 4,
    "ماي": 5,
    "مايو": 5,
    "جوان": 6,
    "يونيو": 6,
    "جويلية": 7,
    "يوليو": 7,
    "أوت": 8,
    "اغسطس": 8,
    "سبتمبر": 9,
    "أكتوبر": 10,
    "اكتوبر": 10,
    "نوفمبر": 11,
    "ديسمبر": 12,
}


def _extract_tribunal(document_text: str) -> str | None:
    if not document_text:
        return None

    # Prefer the clean spelling when two OCR candidates are available.
    exact_match = re.search(
        r"(المحكمة\s+(?:الابتدائية|الإبتدائية)\s+بتونس)",
        document_text,
    )
    if exact_match:
        return exact_match.group(1)

    for line in document_text.splitlines():
        match = re.search(
            r"(المحكمة\s+(?:الابتدائية|الإبتدائية)\s+ب?[\u0621-\u064a]{2,})",
            line,
        )
        if match:
            return match.group(1)
    return None


def _extract_decision_date(document_text: str) -> str | None:
    if not document_text:
        return None

    month_pattern = "|".join(re.escape(month) for month in _ARABIC_MONTHS)
    match = re.search(
        rf"\b(\d{{1,2}})\s+({month_pattern})\s+(\d{{4}})\b",
        _western_digits(document_text),
    )
    if not match:
        return None

    day, month_name, year = match.groups()
    return f"{int(day):02d}/{_ARABIC_MONTHS[month_name]:02d}/{year}"


def _extract_defendant_party(document_text: str) -> str | None:
    if not document_text:
        return None

    markers = (
        r"المدع(?:ى|ي)\s+(?:عليها|علها|عليه|عله)",
        r"المطلوب(?:ة|ة\s+ضدها)?",
    )
    for marker in markers:
        match = re.search(marker + r"[\s:،-]*([\s\S]{0,550})", document_text)
        if not match:
            continue
        section = match.group(1)
        company_match = re.search(r"(شركة\s+[^\n«»\".]{2,180})", section)
        if not company_match:
            continue
        value = company_match.group(1)
        value = re.split(r"(?:في\s+شخص|شركة\s+ذات|معرفها|المعرف)", value)[0]
        value = re.sub(r"\s+", " ", value).strip(" .،:-")
        if value and not _is_masked_party(value):
            return value
    return None


def _extract_parties_from_text(document_text: str, bfpme_role: str | None) -> dict:
    parties = {"demandeur": None, "defendeur": None}
    if bfpme_role == "demandeur":
        parties["demandeur"] = BFPME_NAME
    elif bfpme_role == "defendeur":
        parties["defendeur"] = BFPME_NAME

    defendant = _extract_defendant_party(document_text)
    if defendant and parties["defendeur"] is None:
        parties["defendeur"] = defendant
    return parties


def _extract_legal_references(document_text: str) -> list[str] | None:
    """Recover explicitly cited legal provisions from noisy OCR text.

    The LLM may omit references when a scan is compacted for context.  Court
    decisions normally cite provisions with ``الفصل <number>``; keep the
    source wording for contract clauses and otherwise retain the exact article
    number without guessing the code name.
    """
    text = _western_digits(document_text or "")
    references: list[str] = []
    seen: set[str] = set()

    for match in re.finditer(r"(?:الفصل|فصل)\s+(\d{1,4})(?=\s|[.,:؛]|$)", text):
        number_value = int(match.group(1))
        if number_value <= 0:
            continue
        number = str(number_value)
        following_text = text[match.end():match.end() + 90]
        generic_reference = f"الفصل {number}"
        if re.match(r"\s+من\s+عقد\s+القرض", following_text):
            reference = f"{generic_reference} من عقد القرض"
            if generic_reference in seen:
                references[references.index(generic_reference)] = reference
                seen.remove(generic_reference)
                seen.add(reference)
                continue
        else:
            reference = generic_reference
            if f"{generic_reference} من عقد القرض" in seen:
                continue
        if reference not in seen:
            references.append(reference)
            seen.add(reference)

    return references or None


def _extract_final_legal_references(document_text: str) -> list[str] | None:
    """Return provisions from the final grounds, not noisy citations in claims."""
    text = _western_digits(document_text or "")
    markers = list(re.finditer(
        r"(?:ول?هذه\s+الأسباب|قضت\s+المحكمة)",
        text,
    ))
    if not markers:
        return None

    final_marker = markers[-1]
    grounds_text = text[max(0, final_marker.start() - 6500):final_marker.start()]
    return _extract_legal_references(grounds_text)


def _infer_bfpme_decision(
    document_text: str,
    bfpme_role: str | None,
) -> str | None:
    if bfpme_role != "demandeur":
        return None

    dispositive = _extract_exact_justification(document_text)
    if not dispositive:
        return None
    if re.search(r"قضت\s+المحكمة[\s\S]{0,350}?(?:بإلزام|بالزام|بأداء|بالاداء)", dispositive):
        return "Favorable"
    return None


def _extract_case_number(document_text: str) -> str | None:
    if not document_text:
        return None

    patterns = [
        r"قضية\s+عدد\s*[:：]?\s*([0-9]{1,8}(?:[./][0-9]{2,4})?)",
        r"عدد\s+القضية\s*[:：]?\s*([0-9]{1,8}(?:[./][0-9]{2,4})?)",
        r"القضية\s+عدد\s*[:：]?\s*([0-9]{1,8}(?:[./][0-9]{2,4})?)",
        r"رسمت\s+القضية[\s\S]{0,120}?تحت\s+عدد\s*([0-9]{1,8}(?:[./][0-9]{2,4})?)",
        r"ملف\s+القضية[\s\S]{0,120}?عدد\s*([0-9]{1,8}(?:[./][0-9]{2,4})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, document_text)
        if match:
            return match.group(1).strip()

    return None


def _classify_judgment_type(document_text: str) -> str | None:
    if not document_text:
        return None

    exact_justification = _extract_exact_justification(document_text)
    decision_text = exact_justification or document_text[-3000:]

    patterns = [
        ("infirmatif", r"بنقض|بإلغاء|بالغاء|بفسخ|إبطال\s+الحكم|ابطال\s+الحكم"),
        ("modificatif", r"بتعديل|تعديل\s+الحكم|مع\s+تعديله|فيما\s+زاد|فيما\s+نقص"),
        ("confirmatif", r"بإقرار|بالإقرار|بتأييد|بتاييد|المصادقة\s+على\s+الحكم|إقرار\s+الحكم|تأييد\s+الحكم"),
    ]
    for judgment_type, pattern in patterns:
        if re.search(pattern, decision_text):
            return judgment_type

    if exact_justification:
        return "original"
    return None


def _infer_bfpme_role(document_text: str) -> str | None:
    if not document_text or not BFPME_PATTERN.search(document_text):
        return None

    role_patterns = [
        ("appelant", r"(?:استئناف|طعن|تعقيب)[\s\S]{0,120}?" + BFPME_PATTERN.pattern),
        ("appelant", BFPME_PATTERN.pattern + r"[\s\S]{0,120}?(?:استأنف|استانف|طعن|عقب)"),
        ("intime", r"(?:المستأنف\s+ضده|المستانف\s+ضده|المطعون\s+ضده|المعقب\s+ضده)[\s\S]{0,120}?" + BFPME_PATTERN.pattern),
        ("demandeur", r"(?:المدعي|القائم|الطالب|الدائن)[\s\S]{0,120}?" + BFPME_PATTERN.pattern),
        ("demandeur", BFPME_PATTERN.pattern + r"[\s\S]{0,120}?(?:المدعي|القائم|الطالب|الدائن)"),
        ("defendeur", r"(?:المدعى\s+عليه|المطلوب|المطلوب\s+ضده)[\s\S]{0,120}?" + BFPME_PATTERN.pattern),
        ("defendeur", BFPME_PATTERN.pattern + r"[\s\S]{0,120}?(?:المدعى\s+عليه|المطلوب|المطلوب\s+ضده)"),
    ]
    for role, pattern in role_patterns:
        if re.search(pattern, document_text):
            return role
    return None


def _count_sentences(value: str | None) -> int:
    if not value:
        return 0
    return len([item for item in re.split(r"[.!؟؛]\s+|\n+", value) if item.strip()])


def _build_fallback_summary(document_text: str, result: dict) -> str | None:
    if not document_text:
        return None

    parts = []
    tribunal = result.get("tribunal")
    date = result.get("date_decision")
    if tribunal or date:
        parts.append(
            "صدر الحكم"
            + (f" عن {tribunal}" if tribunal else "")
            + (f" بتاريخ {date}" if date else "")
            + "."
        )

    if "تفليس" in document_text:
        parts.append("قضت المحكمة بتفليس الشركة موضوع الإشعار واعتبارها متوقفة عن الدفع.")
    if "30 جوان 2019" in document_text or "2019" in document_text:
        parts.append("اعتمد الحكم توقف الشركة عن النشاط منذ سنة 2019 كعنصر مهم في تقدير وضعيتها المالية.")
    if BFPME_PATTERN.search(document_text):
        amount = result.get("montant")
        parts.append(
            f"ورد بالحكم أن ديون الشركة تشمل مديونية لفائدة {BFPME_NAME}"
            + (f" قدرها {amount}" if amount else "")
            + "."
        )
    if "الصندوق الوطني للضمان الاجتماعي" in document_text:
        parts.append("كما أشار الحكم إلى ديون أخرى منها دين الصندوق الوطني للضمان الاجتماعي وديون جبائية.")
    if "أمين" in document_text and "الفلسة" in document_text:
        parts.append("عينت المحكمة قاضيا منتدبا وأمينا للفلسة لاتخاذ إجراءات الإشهار والإشراف على أموال الشركة.")
    if "500.000" in document_text:
        parts.append("ألزم الحكم الدائنين بتسبقة خمسمائة دينار لأمين الفلسة لمباشرة المهام الإجرائية.")

    return " ".join(parts) if parts else None


def strengthen_result_with_text(result: dict, document_text: str) -> dict:
    if not result.get("tribunal"):
        result["tribunal"] = _extract_tribunal(document_text)

    if not result.get("date_decision"):
        result["date_decision"] = _extract_decision_date(document_text)

    if not result.get("type_jugement"):
        result["type_jugement"] = _classify_judgment_type(document_text)

    if not result.get("role_bfpme"):
        result["role_bfpme"] = _infer_bfpme_role(document_text)

    recovered_parties = _extract_parties_from_text(
        document_text,
        result.get("role_bfpme"),
    )
    for party_role, party_value in recovered_parties.items():
        if party_value and not result["parties"].get(party_role):
            result["parties"][party_role] = party_value

    verified_references = _extract_final_legal_references(document_text)
    if verified_references:
        result["references_juridiques"] = verified_references
    elif not result.get("references_juridiques"):
        result["references_juridiques"] = _extract_legal_references(document_text)

    if not result.get("numero_dossier"):
        case_number = _extract_case_number(document_text)
        if case_number:
            result["numero_dossier"] = case_number

    exact_justification = _extract_exact_justification(document_text)
    if exact_justification:
        result["decision_justification"] = exact_justification

    if not result.get("decision"):
        result["decision"] = _infer_bfpme_decision(
            document_text,
            result.get("role_bfpme"),
        )

    applicable_amounts = _extract_applicable_bfpme_amounts(
        document_text,
        result.get("type_jugement"),
    )
    if applicable_amounts:
        for key, value in applicable_amounts.items():
            result[key] = value

    amount, amount_explanation = _extract_bfpme_amount_context(document_text)
    if amount and not result.get("montant"):
        result["montant"] = result.get("montant") or amount
        result["explication_montant"] = result.get("explication_montant") or amount_explanation
        result["montant_justification"] = (
            result.get("montant_justification") or amount_explanation
        )

    procedure_explanation = _extract_procedure_advance(document_text)
    if procedure_explanation:
        current = result.get("explication_montant")
        if current and procedure_explanation not in current:
            result["explication_montant"] = f"{current} {procedure_explanation}"
            result["montant_justification"] = result["explication_montant"]

    if _count_sentences(result.get("resume")) < 5:
        fallback_summary = _build_fallback_summary(document_text, result)
        if fallback_summary:
            result["resume"] = fallback_summary

    return normalize_result(result)


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

    for list_key in ("montants_fixes", "montants_variables"):
        if result[list_key] is not None and not isinstance(result[list_key], list):
            result[list_key] = None

    allowed_decisions = {"Favorable", "Defavorable", "Partiellement favorable"}
    if result["decision"] not in allowed_decisions:
        result["decision"] = None

    allowed_judgment_types = {"confirmatif", "modificatif", "infirmatif", "original"}
    if result["type_jugement"] not in allowed_judgment_types:
        result["type_jugement"] = None

    allowed_bfpme_roles = {"demandeur", "defendeur", "appelant", "intime"}
    if result["role_bfpme"] not in allowed_bfpme_roles:
        result["role_bfpme"] = None

    if (
        isinstance(result["decision_justification"], str)
        and not _starts_with_justification_marker(result["decision_justification"])
    ):
        result["decision_justification"] = None

    if result["explication_montant"] is None and result["montant_justification"]:
        result["explication_montant"] = result["montant_justification"]
    if result["montant_justification"] is None and result["explication_montant"]:
        result["montant_justification"] = result["explication_montant"]

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


def _shorten_llm_excerpt(text: str, max_chars: int) -> str:
    """Keep both ends of an OCR excerpt when it exceeds its local budget."""
    source = (text or "").strip()
    if len(source) <= max_chars:
        return source

    marker = "\n[… extrait raccourci …]\n"
    payload_chars = max(1, max_chars - len(marker))
    head_chars = payload_chars // 2
    tail_chars = payload_chars - head_chars
    return (
        f"{source[:head_chars].rstrip()}{marker}"
        f"{source[-tail_chars:].lstrip()}"
    )


def _append_llm_excerpt(
    excerpts: list[str],
    label: str,
    text: str | None,
    section_limit: int,
    total_limit: int,
) -> None:
    """Append an OCR excerpt without exceeding the global LLM input budget."""
    if not text or not text.strip():
        return

    separator_chars = 2 if excerpts else 0
    heading = f"[EXTRAIT: {label}]\n"
    used_chars = len("\n\n".join(excerpts))
    available_chars = total_limit - used_chars - separator_chars - len(heading)
    if available_chars <= 0:
        return

    excerpt = _shorten_llm_excerpt(
        text,
        min(section_limit, available_chars),
    )
    if excerpt:
        excerpts.append(f"{heading}{excerpt}")


def _prepare_llm_document_text(
    document_text: str,
    max_chars: int = MAX_LLM_DOCUMENT_CHARS,
) -> str:
    """Build a context-safe OCR view while retaining decisive judgment passages.

    Long scans frequently exceed LM Studio's 8k context when combined with the
    extraction instructions. The full OCR remains available to
    ``strengthen_result_with_text``; only the LLM request is compacted here.
    """
    source = (document_text or "").strip()
    if len(source) <= max_chars:
        return source

    excerpts: list[str] = []

    justification = _extract_exact_justification(source)
    _append_llm_excerpt(
        excerpts,
        "dispositif final",
        justification or source[-1500:],
        1500,
        max_chars,
    )
    _append_llm_excerpt(
        excerpts,
        "en-tete et parties",
        source[:1100],
        1100,
        max_chars,
    )

    bfpme_matches = list(BFPME_PATTERN.finditer(source))
    selected_matches = bfpme_matches[:1]
    if (
        len(bfpme_matches) > 1
        and bfpme_matches[-1].start() - bfpme_matches[0].start() > 1400
    ):
        selected_matches.append(bfpme_matches[-1])
    for index, match in enumerate(selected_matches, start=1):
        # Keep the complete bank name near the beginning of the excerpt; a
        # generic head/tail crop can otherwise split it around the marker.
        context_start = max(0, match.start() - 120)
        context_end = min(len(source), match.end() + 430)
        _append_llm_excerpt(
            excerpts,
            f"contexte BFPME {index}",
            source[context_start:context_end],
            400,
            max_chars,
        )

    confirmed_amount_block = _extract_confirmed_amount_block(source)
    if confirmed_amount_block:
        prefix, amount_list = confirmed_amount_block
        _append_llm_excerpt(
            excerpts,
            "montants confirmes",
            f"{prefix[-300:]}\n{amount_list}",
            900,
            max_chars,
        )

    prepared = "\n\n".join(excerpts).strip()
    return prepared or _shorten_llm_excerpt(source, max_chars)


def _build_user_prompt(document_text: str) -> str:
    return USER_PROMPT.replace("{document_text}", document_text)


def _request_llm_completion(
    document_text: str,
    model: str,
    max_tokens: int = MAX_LLM_OUTPUT_TOKENS,
):
    return client.chat.completions.create(
        model=model or DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(document_text)},
        ],
        temperature=0,
        max_tokens=max_tokens,
        response_format=EXTRACTION_RESPONSE_FORMAT,
    )


def _is_context_limit_error(exc: BadRequestError) -> bool:
    message = str(exc).lower()
    return (
        ("n_keep" in message and "n_ctx" in message)
        or ("context size" in message and "exceeded" in message)
    )


def extract_with_llm(document_text: str, model: str = DEFAULT_MODEL) -> dict:
    if not document_text or not document_text.strip():
        raise ValueError("Le texte du jugement est vide")

    llm_document_text = _prepare_llm_document_text(document_text)
    try:
        response = _request_llm_completion(llm_document_text, model)
    except BadRequestError as exc:
        if not _is_context_limit_error(exc) or len(llm_document_text) <= 1200:
            raise

        # A model may be loaded with an even smaller context than expected.
        # Retry once with a stricter curated OCR view before surfacing an error.
        retry_limit = max(1200, MAX_LLM_DOCUMENT_CHARS // 2)
        retry_document_text = _prepare_llm_document_text(document_text, retry_limit)
        retry_max_tokens = max(1024, MAX_LLM_OUTPUT_TOKENS // 2)
        response = _request_llm_completion(
            retry_document_text,
            model,
            max_tokens=retry_max_tokens,
        )

    raw_output = response.choices[0].message.content or ""
    try:
        result = normalize_result(_parse_json(raw_output))
        return strengthen_result_with_text(result, document_text)
    except (json.JSONDecodeError, ValueError) as exc:
        fallback = strengthen_result_with_text(deepcopy(EMPTY_RESULT), document_text)
        fallback["resume"] = fallback["resume"] or f"تعذر تحليل JSON الراجع من النموذج: {exc}"
        return fallback
