"""
Unit tests for deterministic unsupported-value check and evidence verification.
"""

from src.evidence_check import check_evidence_on_page, generate_numeric_variants


def test_generate_numeric_variants():
    v = generate_numeric_variants(78326)
    assert "78326" in v
    assert "78,326" in v
    assert "78 326" in v

    v_dec = generate_numeric_variants(14.9)
    assert "14.9" in v_dec
    assert "14,9" in v_dec


def test_check_evidence_exact_and_spaced():
    page_text = "Sandvik gross Scope 1 GHG emissions amounted to 78,326 ton CO2eq in 2025."
    res = check_evidence_on_page(page_text, raw_value=78326, raw_unit="ton CO2eq")
    assert res["status"] == "supported"
    assert res["match_found"] is True
    assert res["matched_substring"] == "78,326"
    assert res["unit_found"] is True

    # Test with space separator
    page_text_spaced = "Gross Scope 1 emissions were 78 326 tonnes CO2e."
    res_spaced = check_evidence_on_page(page_text_spaced, raw_value=78326, raw_unit="tonnes CO2e")
    assert res_spaced["status"] == "supported"
    assert res_spaced["match_found"] is True


def test_check_evidence_not_found():
    page_text = "The quick brown fox jumps over the lazy dog."
    res = check_evidence_on_page(page_text, raw_value=99999)
    assert res["status"] == "not_found"
    assert res["match_found"] is False


def test_check_evidence_ambiguous():
    # If a short number appears more than 3 times on a page
    page_text = "Section 0 item 0 category 0 note 0 details 0."
    res = check_evidence_on_page(page_text, raw_value=0)
    assert res["status"] == "ambiguous"


def test_check_evidence_missing_unit_state():
    # Number appears without expected unit
    page_text = "The target value was recorded as 450 in the summary table."
    res = check_evidence_on_page(page_text, raw_value=450, raw_unit="MWh")
    assert res["status"] == "supported"
    assert res["match_found"] is True
    assert res["lexical_value_present"] is True
    assert res["unit_found"] is False
    assert res["unit_status"] == "missing"
    assert res["semantic_validation"] is False
