"""
Normalisation module for Sustainability KPI Extraction Benchmark
Handles numeric parsing, unit conversion, and tolerance-based value comparison.
"""

import math
import re
from typing import Any, Dict, Optional, Tuple, Union


def clean_numeric_string(raw: Any) -> Optional[float]:
    """
    Cleans raw string or numeric input into a float.
    Handles spaces ('78 326'), commas ('78,326' or European decimal '14,9'),
    percent signs ('14.9%'), negative signs ('-4%'), and missing indicators ('-', 'N/A').
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        if math.isnan(raw):
            return None
        return float(raw)

    s = str(raw).strip()
    if s in ["", "-", "–", "—", "N/A", "n/a", "None", "null", "Not disclosed"]:
        return None

    # Strip currency or symbols
    s = s.replace("$", "").replace("SEK", "").replace("EUR", "").replace("%", "").strip()

    # Handle European decimal: e.g. "14,9" -> "14.9", but "78,326" -> "78326"
    # If there is a single comma followed by 1 or 2 digits at the end: treat as decimal
    if re.search(r'^\d+,\d{1,2}$', s):
        s = s.replace(",", ".")
    else:
        # Otherwise remove thousands separators (commas and non-breaking spaces)
        s = s.replace(",", "").replace("\xa0", "").replace(" ", "")

    try:
        return float(s)
    except ValueError:
        return None


def parse_target_year(raw: Any) -> Optional[int]:
    """Extracts 4-digit target year (e.g. 2030, 2040, 2050) from string or number."""
    if raw is None:
        return None
    if isinstance(raw, int) and 2020 <= raw <= 2100:
        return raw
    m = re.search(r'\b(20[2-9]\d)\b', str(raw))
    if m:
        return int(m.group(1))
    return None


def normalise_kpi_value(
    kpi_name: str,
    raw_value: Any,
    raw_unit: Optional[str] = None
) -> Tuple[Optional[Union[float, int, str]], Optional[str]]:
    """
    Normalises raw value and unit to reference benchmark units:
    - Emissions -> tonnes CO2e
    - Energy -> MWh
    - Renewable share -> % (0..100)
    - Net-zero year -> int year
    - SBTi status -> 'validated' | 'committed' | 'none'
    - Safety metric -> float (frequency rate)
    """
    if raw_value is None:
        return None, None

    kpi = kpi_name.lower()
    unit = (raw_unit or "").strip().lower()

    # 1. Target Year
    if "net_zero" in kpi or "target_year" in kpi:
        year = parse_target_year(raw_value)
        return year, "year" if year else None

    # 2. SBTi Status
    if "sbti" in kpi:
        s = str(raw_value).strip().lower()

        # Check explicit negation FIRST (e.g. "not validated", "not yet validated", "unvalidated")
        is_negated = any(re.search(r'\b' + re.escape(w) + r'\b', s) for w in ["not", "unvalidated", "non-validated", "no", "none", "false"])

        # Check target scope distinctions (near-term vs long-term net-zero)
        has_near_term = any(w in s for w in ["near-term", "near term", "2030"])
        has_long_term = any(w in s for w in ["long-term", "long term", "net-zero", "net zero", "2050"])

        # Case: "near-term validated, but long-term net-zero not validated"
        if has_near_term and has_long_term and is_negated:
            return "near_term_validated", "status"

        # Explicit negation of validation (e.g. "not validated", "not yet validated")
        if is_negated and any(w in s for w in ["validat", "approv", "verifi", "yet"]):
            return "not_validated", "status"

        if is_negated and any(w in s for w in ["participat", "join", "member"]):
            return "not_participating", "status"

        if is_negated:
            return "not_validated", "status"

        # Scope distinction: near-term only validation
        if has_near_term and not has_long_term and any(w in s for w in ["validat", "approv", "verifi"]):
            return "near_term_validated", "status"

        # Positive validation / verification
        if any(w in s for w in ["validat", "approv", "yes", "verified", "true"]):
            return "validated", "status"

        # Positive commitment
        if any(w in s for w in ["commit", "pledg"]):
            return "committed", "status"

        return s, "status"

    # 3. Numeric KPIs
    val = clean_numeric_string(raw_value)
    if val is None:
        return None, None

    # GHG Emissions: Target is tonnes CO2e
    if "emission" in kpi or "ghg" in kpi or "scope" in kpi:
        # Check if unit is in kilotonnes / thousand tons
        if any(u in unit for u in ["kt", "kton", "thousand", "kilo"]):
            val = val * 1000.0
        elif "mton" in unit or "million" in unit:
            val = val * 1000000.0
        return val, "tonnes CO2e"

    # Energy Consumption: Target is MWh
    if "energy" in kpi:
        if "gwh" in unit:
            val = val * 1000.0
        elif "tj" in unit:
            val = val * 277.778
        elif "kwh" in unit and "mwh" not in unit and "gwh" not in unit:
            val = val / 1000.0
        return val, "MWh"

    # Renewable Share: Target is %
    if "renewable" in kpi or "share" in kpi or "percent" in kpi:
        # If expressed as fraction 0.149 instead of 14.9:
        if 0.0 < val <= 1.0 and "%" not in unit:
            val = val * 100.0
        return val, "%"

    # Occupational safety (TRIFR / LTIFR): Target is frequency rate
    if "safety" in kpi or "trifr" in kpi or "ltif" in kpi or "injury" in kpi:
        return val, "injuries per million hours worked"

    return val, raw_unit


def compare_kpi_values(
    pred_val: Any,
    gold_val: Any,
    kpi_name: str,
    rel_tol: float = 0.02
) -> bool:
    """
    Compares predicted value with gold standard value.
    - Categorical/Target Year: exact equality or normalized status match.
    - Numeric values: relative tolerance check abs(pred - gold) / gold <= rel_tol.
    """
    if pred_val is None or gold_val is None:
        return pred_val == gold_val

    # Categorical / Status
    if "sbti" in kpi_name.lower():
        p_str = str(pred_val).strip().lower()
        g_str = str(gold_val).strip().lower()

        # If prediction contains explicit negation of validation, it must NEVER match a validated gold label
        if any(neg in p_str for neg in ["not_validated", "not validated", "not yet", "unvalidated", "non-validated", "not_participating"]):
            return "not" in g_str or "unvalidated" in g_str

        if "validat" in g_str:
            return any(pos in p_str for pos in ["validat", "approv", "verifi"])

        if "commit" in g_str:
            return "commit" in p_str

        return p_str == g_str

    # Year
    if "year" in kpi_name.lower():
        try:
            return int(pred_val) == int(gold_val)
        except (ValueError, TypeError):
            return str(pred_val).strip() == str(gold_val).strip()

    # Numeric comparison
    try:
        p_num = float(pred_val)
        g_num = float(gold_val)
        if g_num == 0:
            return abs(p_num) < 1e-6
        return abs(p_num - g_num) / abs(g_num) <= rel_tol
    except (ValueError, TypeError):
        return str(pred_val).strip().lower() == str(gold_val).strip().lower()
