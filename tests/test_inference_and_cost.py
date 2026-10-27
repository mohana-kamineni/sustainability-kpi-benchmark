"""
Unit tests for inference, cost accounting, and evaluation metrics.
"""

import math
from src.inference import compute_token_cost, MockInferenceRunner, RATES
from src.evaluation import wilson_score_ci, run_paired_bootstrap_comparison, evaluate_predictions


def test_compute_token_cost():
    # 20B rate: prompt $0.075 / 1M, completion $0.300 / 1M
    cost_20b = compute_token_cost(1_000_000, 1_000_000, "openai/gpt-oss-20b")
    assert math.isclose(cost_20b, 0.075 + 0.300, rel_tol=1e-5)

    # 120B rate: prompt $0.150 / 1M, completion $0.600 / 1M
    cost_120b = compute_token_cost(1_000_000, 1_000_000, "openai/gpt-oss-120b")
    assert math.isclose(cost_120b, 0.150 + 0.600, rel_tol=1e-5)


def test_mock_inference_runner():
    runner = MockInferenceRunner()
    res = runner.call_mock("openai/gpt-oss-20b", "scope_1_ghg_emissions", gold_record={"raw_value": 78326, "raw_unit": "ton CO2eq", "pdf_page_index": 71})
    assert res["status"] == "success"
    assert res["prompt_tokens"] > 0
    assert res["cost_usd"] > 0.0
    assert "78326" in res["raw_text"]


def test_wilson_score_ci():
    # 0 out of 10
    lo, hi = wilson_score_ci(0, 10)
    assert lo == 0.0
    assert hi > 0.0

    # 10 out of 10
    lo, hi = wilson_score_ci(10, 10)
    assert lo < 1.0
    assert hi == 1.0

    # 5 out of 10
    lo, hi = wilson_score_ci(5, 10)
    assert 0.20 < lo < 0.50
    assert 0.50 < hi < 0.80


def test_run_paired_bootstrap_comparison():
    # Method A: 8/10, Method B: 10/10
    a = [1, 1, 1, 1, 1, 1, 1, 1, 0, 0]
    b = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    res = run_paired_bootstrap_comparison(a, b, n_iterations=500, seed=42)
    assert math.isclose(res["delta_mean"], 0.2, abs_tol=0.05)
    assert res["ci_95"][0] >= 0.0  # CI should be >= 0 because B is always >= A
