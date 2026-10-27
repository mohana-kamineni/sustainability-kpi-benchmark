"""
Deterministic Unsupported-Value Check
Performs rule-based verification of whether an extracted KPI value and unit
actually appear on the cited PDF page, without relying on an LLM judge.
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
    Returns:
    {
        "status": "supported" | "not_found" | "ambiguous",
        "match_found": bool,
        "matched_substring": str or None,
        "evidence_snippet": str or None,
        "reason": str
    }
    """
    if not page_text or (raw_value is None and normalised_value is None):
        return {
            "status": "not_found",
            "match_found": False,
            "matched_substring": None,
            "evidence_snippet": None,
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
        return {
            "status": "not_found",
            "match_found": False,
            "matched_substring": None,
            "evidence_snippet": None,
            "reason": f"Value variants {candidates[:4]} not found on cited page."
        }

    # Check unit if provided
    unit_found = False
    if raw_unit:
        u_clean = raw_unit.lower().replace("co2eq", "").replace("co2e", "").strip()
        if u_clean and u_clean in snippet.lower():
            unit_found = True

    # Ambiguity check: e.g. very common small number like '0' or '1' with multiple occurrences
    if len(matched_variant) <= 2 and collapsed_page.count(matched_variant) > 3:
        status = "ambiguous"
        reason = f"Number '{matched_variant}' appears multiple times on the page; semantic context requires review."
    else:
        status = "supported"
        reason = f"Value '{matched_variant}' verified on page" + (f" with associated unit '{raw_unit}'." if unit_found else ".")

    return {
        "status": status,
        "match_found": True,
        "matched_substring": matched_variant,
        "evidence_snippet": snippet,
        "unit_found": unit_found,
        "reason": reason
    }
