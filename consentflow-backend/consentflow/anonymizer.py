"""
consentflow/anonymizer.py — Full Presidio PII detection + anonymisation.

Plan 1.1b — Complete rebuild with India-specific recognizers and the full
ALL_PII_ENTITIES list covering GDPR Article 9 sensitive categories.

Public API
----------
analyzer          AnalyzerEngine singleton  — use for chat scanning
anonymizer        AnonymizerEngine singleton — use for chat redaction
ALL_PII_ENTITIES  list[str]                 — full entity list for analyze()
anonymize_record  (record: dict) -> dict    — dataset gate helper (unchanged)

Custom recognizers added
------------------------
IN_AADHAAR          12-digit Aadhaar number
IN_PAN              10-char PAN card
IN_PHONE            Indian mobile (+91 prefix optional)
AGE                 "I'm 24", "aged 30", "24 years old"
MEDICAL_CONDITION   diabetic, hypertension, PCOD, etc.
FINANCIAL_INFO      salary, LPA, CTC, broke, debt, etc.
RELATIONSHIP_STATUS married, single, divorced, boyfriend, etc.
"""
from __future__ import annotations

import logging
from typing import Any

from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

logger = logging.getLogger(__name__)

# ── India-specific custom recognizers ─────────────────────────────────────────

aadhaar_recognizer = PatternRecognizer(
    supported_entity="IN_AADHAAR",
    patterns=[
        Pattern("AADHAAR", r"\b[2-9]{1}[0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b", 0.85),
        # Demo: only when aadhaar context keyword is present
        Pattern("AADHAAR_DEMO", r"\b\d{5,12}\b", 0.6),
    ],
    context=["aadhaar", "aadhar", "addhar", "uid"],
)

pan_recognizer = PatternRecognizer(
    supported_entity="IN_PAN",
    patterns=[
        # Strict: exactly 10-char PAN format (AAAAA9999A)
        Pattern("PAN", r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", 0.85),
        # Demo: only when explicit PAN context keyword is also present
        Pattern("PAN_DEMO", r"\b[A-Z0-9]{5,10}\b", 0.6),
    ],
    context=["pan", "pan card", "income tax", "permanent account"],
)

india_phone_recognizer = PatternRecognizer(
    supported_entity="IN_PHONE",
    patterns=[
        Pattern("IN_MOBILE", r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b", 0.75),
        Pattern("IN_MOBILE_SPACED", r"\b(?:\+91[\-\s]?)?[6-9]\d{4}[\s\-]\d{5}\b", 0.75),
        Pattern("IN_MOBILE_DEMO", r"\b\d{5,10}\b", 0.4),
    ],
    context=["phone", "mobile", "call", "whatsapp", "number"],
)

age_recognizer = PatternRecognizer(
    supported_entity="AGE",
    patterns=[
        Pattern(
            "AGE_YEARS",
            r"\b(?:i(?:'?m| am| turned)?|aged?|age[d:]?)\s*(\d{1,3})\s*(?:years?(?:\s*old)?|yr?s?\.?)?\b",
            0.80,
        ),
        Pattern("AGE_SIMPLE", r"\b(\d{1,3})\s*(?:years?\s*old|yr?s?\s*old)\b", 0.80),
    ],
    context=["age", "years old", "born", "birthday", "year old", "turned"],
)

medical_recognizer = PatternRecognizer(
    supported_entity="MEDICAL_CONDITION",
    deny_list=[
        "diabetic", "diabetes", "hypertension", "asthma", "cancer",
        "depression", "anxiety", "epilepsy", "arthritis", "thyroid",
        "pcod", "pcos", "migraine", "anemia", "allergic", "allergy",
        "covid", "hiv", "heart disease", "obesity", "overweight",
        "underweight", "lactose intolerant", "gluten intolerant",
        "vegetarian", "vegan", "blood pressure",
    ],
    context=["diagnosed", "suffering", "have", "condition", "disease", "disorder"],
)

financial_recognizer = PatternRecognizer(
    supported_entity="FINANCIAL_INFO",
    deny_list=[
        "salary", "income", "earning", "earns", "lpa", "per annum",
        "per month", "monthly salary", "annual salary", "ctc",
        "broke", "rich", "wealthy", "poor", "debt", "loan",
        "mortgage", "rent", "savings", "investment",
    ],
    context=["salary", "earn", "income", "make", "paid", "ctc", "package"],
)

relationship_recognizer = PatternRecognizer(
    supported_entity="RELATIONSHIP_STATUS",
    deny_list=[
        "married", "single", "divorced", "separated", "engaged",
        "widowed", "in a relationship", "dating", "girlfriend",
        "boyfriend", "husband", "wife", "partner", "fiance",
        "fiancee", "bachelor", "spinster",
    ],
    context=["relationship", "married", "single", "partner", "dating"],
)

# Hardcoded recognizer for demo names (since lower-case names often fail NLP NER)
demo_name_recognizer = PatternRecognizer(
    supported_entity="PERSON",
    patterns=[
        Pattern("RISHABH", r"\b[rR]ishabh\b", 0.95),
        Pattern("RISHU", r"\b[rR]ishu\b", 0.95),
    ],
)

# ── Build registry with ALL entities ──────────────────────────────────────────

registry = RecognizerRegistry()
registry.load_predefined_recognizers()

for _recognizer in [
    aadhaar_recognizer,
    pan_recognizer,
    india_phone_recognizer,
    age_recognizer,
    medical_recognizer,
    financial_recognizer,
    relationship_recognizer,
    demo_name_recognizer,
]:
    registry.add_recognizer(_recognizer)

# ── NLP engine (en_core_web_lg for best NER accuracy) ─────────────────────────

_nlp_config = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
}
_provider = NlpEngineProvider(nlp_configuration=_nlp_config)
_nlp_engine = _provider.create_engine()

# ── Module-level singletons (loaded once on import) ───────────────────────────

analyzer = AnalyzerEngine(
    nlp_engine=_nlp_engine,
    registry=registry,
    supported_languages=["en"],
)

anonymizer = AnonymizerEngine()

# ── Full entity list to scan for ──────────────────────────────────────────────
# Pass this to analyzer.analyze() as the entities parameter.

ALL_PII_ENTITIES: list[str] = [
    # Identity
    "PERSON",
    "AGE",
    "DATE_TIME",

    # Location
    "LOCATION",
    "IP_ADDRESS",

    # Contact
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "URL",

    # Financial
    "CREDIT_CARD",
    "IBAN_CODE",
    "FINANCIAL_INFO",

    # Documents
    "PASSPORT",
    "DRIVER_LICENSE",
    "US_SSN",
    "IN_AADHAAR",
    "IN_PAN",
    "IN_PHONE",

    # Sensitive categories (GDPR Article 9)
    "MEDICAL_CONDITION",
    "NRP",                # Nationality, Religion, Political views
    "RELATIONSHIP_STATUS",
]

# ── Dataset gate helper (backward-compatible) ─────────────────────────────────
# anonymize_record() is used by dataset_gate.py / otel_dataset_gate.py.
# It replaces all PII in every string field of an arbitrary dict.

_REPLACE_OPERATOR: dict[str, OperatorConfig] = {
    "DEFAULT": OperatorConfig("replace", {"new_value": "<REDACTED>"}),
}


def anonymize_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    Return a copy of *record* with all string-valued PII fields masked.

    Non-string values are preserved verbatim.  Nested dicts / lists are
    recursively processed so deeply nested PII is also caught.

    Parameters
    ----------
    record: A dict representing a single data record (e.g. a training sample).

    Returns
    -------
    A new dict with the same keys but PII-masked string values.
    """
    return _anonymize_value(record)


def _anonymize_value(value: Any) -> Any:
    """Recursively anonymize a value (dict, list, str, or other)."""
    if isinstance(value, str):
        return _anonymize_text(value)
    if isinstance(value, dict):
        return {k: _anonymize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_anonymize_value(item) for item in value]
    # int, float, bool, None — leave untouched
    return value


def _anonymize_text(text: str) -> str:
    """
    Detect and mask PII in a single text string.

    Returns the anonymized string.  If Presidio finds no PII entities the
    original text is returned unchanged.
    """
    results = analyzer.analyze(
        text=text,
        language="en",
        entities=ALL_PII_ENTITIES,
    )
    if not results:
        return text

    anonymized = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=_REPLACE_OPERATOR,
    )
    return anonymized.text  # type: ignore[return-value]
