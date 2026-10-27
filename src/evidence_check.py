"""
Lexical Evidence Presence Check Module
Performs rule-based verification of whether an extracted KPI value and unit
actually appear on the cited PDF page, without relying on an LLM judge.

IMPORTANT METHODOLOGICAL SCOPE:
This check verifies strictly LEXICAL presence. It does NOT establish semantic attribution,
correct reporting year, metric definition, or table column alignment. A value may be
lexically present on the cited page (e.g., historical baseline or adjacent safety metric)
while being semantically incorrect.
"""

import re
from typing import Any, Dict, List, Optional
from src.normalisation import clean_numeric_string


def generate_numeric_variants(val: Any) -> List[str]:
    """
    Generates string representations for a numeric value to handle
    formatting variants (e.g. 78326 -> '78,326', '78 326', '78326', '78.3').
    """
    variants = []
    if val is None:
        return variants

    val_str = str(val).strip()
    variants.append(val_str)

    num = clean_numeric_string(val)
    if num is not None:
        if num.is_integer():
            i_val = int(num)
            variants.append(str(i_val))
            variants.append(f"{i_val:,}")
            variants.append(f"{i_val:,}".replace(",", " "))
            variants.append(f"{i_val:,}".replace(",", "\xa0"))
        else:
            variants.append(f"{num:.1f}")
            variants.append(f"{num:.2f}")
            variants.append(f"{num:.1f}".replace(".", ","))
            variants.append(f"{num:.2f}".replace(".", ","))

    return list(dict.fromkeys(variants))  # Preserve unique in order


def check_evidence_on_page(
    page_text: str,
    raw_value: Any,
    raw_unit: Optional[str] = None,
    normalised_value: Optional[Any] = None,
    context_window_chars: int = 200
) -> Dict[str, Any]:
    """
    Checks if raw_value (or normalised_value) exists in page_text.
    Distingushes lexical string presence from semantic attribution.

    Returns:
    {
        "status": "supported" | "not_found" | "ambiguous",
        "match_found": bool,
        "lexical_value_present": bool,
        "matched_substring": str or None,
        "evidence_snippet": str or None,
        "unit_found": bool or None,
        "unit_status": "matched" | "missing" | "not_applicable",
        "semantic_validation": False,
        "reason": str
    }
    """
    if not page_text or (raw_value is None and normalised_value is None):
        return {
            "status": "not_found",
            "match_found": False,
            "lexical_value_present": False,
            "matched_substring": None,
            "evidence_snippet": None,
            "unit_found": None,
            "unit_status": "not_applicable",
            "semantic_validation": False,
            "reason": "Missing page text or values to verify"
        }

    # Normalize whitespace in page text
    collapsed_page = re.sub(r'\s+', ' ', page_text)

    # Candidate strings to search for
    candidates = generate_numeric_variants(raw_value)
    if normalised_value is not None:
        candidates.extend(generate_numeric_variants(normalised_value))

    matched_variant = None
    snippet = None
    match_pos = -1

    for cand in candidates:
        if not cand or len(cand) < 1:
            continue
        # Use boundary search for short strings/numbers to avoid false positives inside words
        pattern = r'(?<![\w\d])' + re.escape(cand) + r'(?![\w\d])'
        match = re.search(pattern, collapsed_page)
        if match:
            matched_variant = cand
            match_pos = match.start()
            start = max(0, match_pos - context_window_chars // 2)
            end = min(len(collapsed_page), match.end() + context_window_chars // 2)
            snippet = collapsed_page[start:end].strip()
            break

    if not matched_variant:
        unit_status = "missing" if (raw_unit and str(raw_unit).strip() not in ["", "status", "year"]) else "not_applicable"
        return {
            "status": "not_found",
            "match_found": False,
            "lexical_value_present": False,
            "matched_substring": None,
            "evidence_snippet": None,
            "unit_found": False if unit_status == "missing" else None,
            "unit_status": unit_status,
            "semantic_validation": False,
            "reason": f"Value variants {candidates[:4]} not found on cited page."
        }

    # Explicit unit verification
    if raw_unit and str(raw_unit).strip() not in ["", "status", "year"]:
        u_clean = raw_unit.lower().replace("co2eq", "").replace("co2e", "").strip()
        if u_clean and u_clean in snippet.lower():
            unit_found = True
            unit_status = "matched"
        else:
            unit_found = False
            unit_status = "missing"
    else:
        unit_found = None
        unit_status = "not_applicable"

    # Ambiguity check: e.g. very common small number like '0' or '1' with multiple occurrences
    if len(matched_variant) <= 2 and collapsed_page.count(matched_variant) > 3:
        status = "ambiguous"
        reason = f"Number '{matched_variant}' appears multiple times on the page; semantic context requires review."
    else:
        status = "supported"
        if unit_status == "matched":
            reason = f"Lexical match '{matched_variant}' verified on page with associated unit '{raw_unit}'."
        elif unit_status == "missing":
            reason = f"Lexical match '{matched_variant}' found on page, but expected unit '{raw_unit}' was not located within snippet window."
        else:
            reason = f"Lexical match '{matched_variant}' verified on page."

    return {
        "status": status,
        "match_found": True,
        "lexical_value_present": True,
        "matched_substring": matched_variant,
        "evidence_snippet": snippet,
        "unit_found": unit_found,
        "unit_status": unit_status,
        "semantic_validation": False,
        "reason": reason
    }
