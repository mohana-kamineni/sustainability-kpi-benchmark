"""
Audit Invariant Regression Tests
Locks in findings and accounting invariants discovered during the self-audit:
1. Exact observation denominators and alignment across all 5 methods.
2. Exact numerators, denominators, and unrounded cost per correct KPI.
3. Unsupported-value denominator semantics (extracted count vs total count).
4. Wilson score intervals for zero-count numerators (e.g. 0/24 upper bound).
5. Grounding check behavior: distinguishes lexical match from semantic verification.
"""

import json
from pathlib import Path
import pytest
from src.evaluation import wilson_score_ci, evaluate_predictions
from src.evidence_check import check_evidence_on_page
from src.normalisation import normalise_kpi_value

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
TABLE1_FIXTURE_PATH = FIXTURES_DIR / "table1_recomputed_run.json"
TABLE2_FIXTURE_PATH = FIXTURES_DIR / "table2_recovered_run.json"
ANNOTATIONS_PATH = PROJECT_ROOT / "data" / "annotations" / "gold_annotations.json"


@pytest.fixture(scope="module")
def audit_data():
    """Provides Table 1 (original run with fixed checker) as immutable test fixture."""
    with open(TABLE1_FIXTURE_PATH, "r", encoding="utf-8") as f:
        res = json.load(f)
    with open(ANNOTATIONS_PATH, "r", encoding="utf-8") as f:
        gold = json.load(f)["annotations"]
    return res, gold


@pytest.fixture(scope="module")
def recovered_data():
    """Provides Table 2 (recovered run with fixed checker) as immutable test fixture."""
    with open(TABLE2_FIXTURE_PATH, "r", encoding="utf-8") as f:
        res = json.load(f)
    with open(ANNOTATIONS_PATH, "r", encoding="utf-8") as f:
        gold = json.load(f)["annotations"]
    return res, gold


def test_observation_alignment_and_count(audit_data):
    """Verify that all 5 methods evaluated the exact same 32 observation IDs in identical order."""
    res, gold = audit_data
    gold_ids = [g["observation_id"] for g in gold]
    assert len(gold_ids) == 32

    for method, records in res["detailed_records"].items():
        assert len(records) == 32, f"Method {method} evaluated {len(records)} records, expected 32"
        pred_ids = [r["observation_id"] for r in records]
        assert pred_ids == gold_ids, f"Observation ID sequence mismatch in {method}"


def test_exact_metric_numerators_and_denominators(audit_data):
    """Verify exact numerators and denominators for each method under fixed evidence checker."""
    res, _ = audit_data
    records = res["detailed_records"]

    expected_counts = {
        "Method_A_RuleBased": {
            "val_corr": 9, "page_corr": 5, "extracted": 19, "unsupported": 1, "tech_fail": 0
        },
        "Method_B_Direct_openai_gpt-oss-20b": {
            "val_corr": 24, "page_corr": 32, "extracted": 32, "unsupported": 1, "tech_fail": 0
        },
        "Method_B_Direct_openai_gpt-oss-120b": {
            "val_corr": 26, "page_corr": 31, "extracted": 31, "unsupported": 2, "tech_fail": 0
        },
        "Method_C_RAG_openai_gpt-oss-20b": {
            "val_corr": 16, "page_corr": 17, "extracted": 20, "unsupported": 1, "tech_fail": 10
        },
        "Method_C_RAG_openai_gpt-oss-120b": {
            "val_corr": 22, "page_corr": 23, "extracted": 24, "unsupported": 0, "tech_fail": 5
        },
    }

    for method, exp in expected_counts.items():
        recs = records[method]
        val_corr = sum(1 for r in recs if r.get("value_correct") is True)
        page_corr = sum(1 for r in recs if r.get("page_correct") is True)
        extracted = sum(1 for r in recs if r.get("pred_raw_value") is not None)
        unsupported = sum(1 for r in recs if r.get("pred_raw_value") is not None and r.get("evidence_status") == "not_found")
        tech_fail = sum(1 for r in recs if "failure_reason" in r)

        assert val_corr == exp["val_corr"], f"{method} value correct count mismatch: {val_corr} vs {exp['val_corr']}"
        assert page_corr == exp["page_corr"], f"{method} page correct count mismatch: {page_corr} vs {exp['page_corr']}"
        assert extracted == exp["extracted"], f"{method} extracted count mismatch: {extracted} vs {exp['extracted']}"
        assert unsupported == exp["unsupported"], f"{method} unsupported count mismatch: {unsupported} vs {exp['unsupported']}"
        assert tech_fail == exp["tech_fail"], f"{method} tech fail count mismatch: {tech_fail} vs {exp['tech_fail']}"


def test_recovered_run_invariants():
    """Verify invariants for the recovered run artifact with merged successful calls."""
    recovered_path = PROJECT_ROOT / "results" / "evaluation_results_recovered.json"
    assert recovered_path.exists()
    with open(recovered_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # In recovered run, RAG 120B has 26/32 correct and only 1 technical failure
    summary = data["methods_summary"]
    assert summary["Method_C_RAG_openai_gpt-oss-120b"]["value_accuracy"] == 0.8125
    assert summary["Method_C_RAG_openai_gpt-oss-120b"]["technical_failure_rate"] == 0.0312
    assert summary["Method_C_RAG_openai_gpt-oss-120b"]["unsupported_value_rate"] == 0.0


def test_recovered_exact_numerators_and_denominators(recovered_data):
    """Verify exact numerators and denominators for recovered run under fixed evidence checker."""
    res, _ = recovered_data
    records = res["detailed_records"]

    expected_recovered = {
        "Method_A_RuleBased": {"val_corr": 9, "page_corr": 5, "extracted": 19, "unsupported": 1, "tech_fail": 0},
        "Method_B_Direct_openai_gpt-oss-20b": {"val_corr": 24, "page_corr": 32, "extracted": 32, "unsupported": 1, "tech_fail": 0},
        "Method_B_Direct_openai_gpt-oss-120b": {"val_corr": 26, "page_corr": 31, "extracted": 31, "unsupported": 2, "tech_fail": 0},
        "Method_C_RAG_openai_gpt-oss-20b": {"val_corr": 21, "page_corr": 21, "extracted": 25, "unsupported": 1, "tech_fail": 5},
        "Method_C_RAG_openai_gpt-oss-120b": {"val_corr": 26, "page_corr": 27, "extracted": 28, "unsupported": 0, "tech_fail": 1},
    }

    for method, exp in expected_recovered.items():
        recs = records[method]
        val_corr = sum(1 for r in recs if r.get("value_correct") is True)
        page_corr = sum(1 for r in recs if r.get("page_correct") is True)
        extracted = sum(1 for r in recs if r.get("pred_raw_value") is not None)
        unsupported = sum(1 for r in recs if r.get("pred_raw_value") is not None and r.get("evidence_status") == "not_found")
        tech_fail = sum(1 for r in recs if "failure_reason" in r)

        assert val_corr == exp["val_corr"], f"{method} recovered value correct count mismatch: {val_corr} vs {exp['val_corr']}"
        assert page_corr == exp["page_corr"], f"{method} recovered page correct count mismatch: {page_corr} vs {exp['page_corr']}"
        assert extracted == exp["extracted"], f"{method} recovered extracted count mismatch: {extracted} vs {exp['extracted']}"
        assert unsupported == exp["unsupported"], f"{method} recovered unsupported count mismatch: {unsupported} vs {exp['unsupported']}"
        assert tech_fail == exp["tech_fail"], f"{method} recovered tech fail count mismatch: {tech_fail} vs {exp['tech_fail']}"


def test_unrounded_cost_accounting(audit_data):
    """Verify that cost per correct KPI uses unrounded values and matches expected formulas."""
    res, _ = audit_data
    summary = res["methods_summary"]

    # Method B 120B: $0.025465 / 26 correct
    cost_b_120 = summary["Method_B_Direct_openai_gpt-oss-120b"]["total_cost_usd"]
    expected_b_120 = cost_b_120 / 26
    assert abs(expected_b_120 - 0.000979423) < 1e-6
    assert round(expected_b_120, 6) == 0.000979

    # Method C 120B: $0.021177 / 22 correct
    cost_c_120 = summary["Method_C_RAG_openai_gpt-oss-120b"]["total_cost_usd"]
    expected_c_120 = cost_c_120 / 22
    assert abs(expected_c_120 - 0.000962591) < 1e-6
    assert round(expected_c_120, 6) == 0.000963


def test_wilson_ci_zero_numerator_bound():
    """Verify Wilson score CI for 0/24 (RAG 120B unsupported rate): upper bound is ~13.8%, not 0.0%."""
    lo, hi = wilson_score_ci(0, 24)
    assert lo == 0.0
    assert 0.13 < hi < 0.14  # Exact Wilson upper bound is 0.1380


def test_evidence_checker_lexical_limitation():
    """
    Verify audit finding that evidence_check detects string presence, NOT semantic support.
    E.g. A wrong KPI number (0.9 instead of 2.3) will be marked 'supported' if 0.9 appears on the page.
    """
    page_text = "In 2025 our lost time injury frequency was 0.9, while total recordable TRIFR was 2.3."
    # Extracting 0.9 for TRIFR is semantically wrong, but evidence_check marks it supported:
    res = check_evidence_on_page(page_text, raw_value=0.9, raw_unit="TRIFR")
    assert res["status"] == "supported"
    assert res["match_found"] is True
    # This demonstrates that evidence checker confirms string presence, not semantic correctness.


def test_derived_annotation_alleima_renewable_share(audit_data):
    """Verify that Alleima renewable share gold annotation is derived and flagged in notes."""
    _, gold = audit_data
    alleima_share = next(g for g in gold if g["observation_id"] == "alleima_2025_renewable_electricity_share")
    assert alleima_share["raw_value"] == 17.7
    # Note must explain the calculation from 180,224 / 1,016,096
    assert "180,224" in alleima_share["evidence_text"]
    assert "1,016,096" in alleima_share["evidence_text"]
