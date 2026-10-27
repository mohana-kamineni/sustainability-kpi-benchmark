"""
Evaluation and Statistical Analysis Module
Computes:
  1. Value Accuracy (with 2% tolerance for numeric, exact for targets/categorical)
  2. Evidence-Page Accuracy
  3. Unsupported-Value Rate (via deterministic evidence checker)
  4. Coverage
  5. Cost (Total USD and Cost per Correctly Extracted KPI)
  6. Latency (per KPI and total)
  7. Extraction Failure Rate
  8. Paired Bootstrap and Wilson Score Confidence Intervals
"""

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from src.normalisation import compare_kpi_values, normalise_kpi_value
from src.evidence_check import check_evidence_on_page


def wilson_score_ci(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Computes standard Wilson score confidence interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    z = 1.959963984540054  # 95% z-score
    p = k / n
    denom = 1 + (z ** 2) / n
    centre = p + (z ** 2) / (2 * n)
    sd = math.sqrt((p * (1 - p) + (z ** 2) / (4 * n)) / n)
    lower = max(0.0, (centre - z * sd) / denom)
    upper = min(1.0, (centre + z * sd) / denom)
    return (round(lower, 4), round(upper, 4))


def run_paired_bootstrap_comparison(
    method_a_correct: List[int],
    method_b_correct: List[int],
    n_iterations: int = 1000,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Runs paired bootstrap comparison between two methods on identical observations.
    Calculates 95% confidence interval for Delta Accuracy (Method B - Method A).
    """
    n = len(method_a_correct)
    if n == 0:
        return {"delta_mean": 0.0, "ci_95": [0.0, 0.0]}

    rng = np.random.default_rng(seed)
    deltas = []

    a_arr = np.array(method_a_correct)
    b_arr = np.array(method_b_correct)

    for _ in range(n_iterations):
        indices = rng.choice(n, size=n, replace=True)
        acc_a = np.mean(a_arr[indices])
        acc_b = np.mean(b_arr[indices])
        deltas.append(acc_b - acc_a)

    deltas = np.array(deltas)
    return {
        "delta_mean": round(float(np.mean(deltas)), 4),
        "ci_95": [round(float(np.percentile(deltas, 2.5)), 4), round(float(np.percentile(deltas, 97.5)), 4)]
    }


def evaluate_predictions(
    predictions: List[Dict[str, Any]],
    gold_annotations: List[Dict[str, Any]],
    pdf_pages_by_company: Optional[Dict[str, List[Dict]]] = None,
    numeric_rel_tol: float = 0.02
) -> Dict[str, Any]:
    """
    Evaluates extraction predictions against gold annotations.
    """
    gold_map = {g["observation_id"]: g for g in gold_annotations}

    total_evaluable = len(gold_annotations)
    extracted_count = 0
    correct_values = 0
    correct_pages = 0
    unsupported_count = 0
    technical_failures = 0

    total_latency_ms = 0
    total_cost_usd = 0.0

    eval_records = []

    for pred in predictions:
        obs_id = pred["observation_id"]
        gold = gold_map.get(obs_id)
        if not gold:
            continue

        latency = pred.get("latency_ms", 0)
        cost = pred.get("cost_usd", 0.0)
        total_latency_ms += latency
        total_cost_usd += cost

        # Check technical failure
        status = pred.get("disclosure_status")
        if status == "extraction_error":
            technical_failures += 1
            eval_records.append({
                "observation_id": obs_id,
                "kpi_name": gold["kpi_name"],
                "value_correct": False,
                "page_correct": False,
                "evidence_status": "not_found",
                "failure_reason": pred.get("error", "Extraction error")
            })
            continue

        p_raw = pred.get("raw_value")
        p_unit = pred.get("raw_unit")
        kpi_name = gold["kpi_name"]

        # Normalise predicted value
        p_norm, _ = normalise_kpi_value(kpi_name, p_raw, p_unit)
        g_norm = gold["normalised_value"]

        # 1. Coverage
        if p_raw is not None:
            extracted_count += 1

        # 2. Value correctness
        val_correct = compare_kpi_values(p_norm, g_norm, kpi_name, rel_tol=numeric_rel_tol)
        if val_correct:
            correct_values += 1

        # 3. Evidence-page correctness (exact or +- 1 page window; accounts for PDF index vs printed folio)
        pred_p = pred.get("pdf_page_index")
        gold_p = gold.get("pdf_page_index")
        gold_fol = gold.get("printed_page_number")
        page_correct = False
        if pred_p is not None and gold_p is not None:
            # Direct PDF index match +- 1 page
            if abs(int(pred_p) - int(gold_p)) <= 1:
                page_correct = True
            # Printed folio match +- 1 page
            elif gold_fol is not None and abs(int(pred_p) - int(gold_fol)) <= 1:
                page_correct = True
            # Boliden / Alleima +1 folio-to-index offset tolerance
            elif gold["company"] in ["Boliden", "Alleima"] and abs((int(pred_p) + 1) - int(gold_p)) <= 1:
                page_correct = True
        if page_correct:
            correct_pages += 1

        # 4. Deterministic unsupported-value check (evaluates cited page and adjacent +-1 page window)
        ev_status = "not_found"
        ev_snippet = None
        if pdf_pages_by_company and gold["company"] in pdf_pages_by_company and pred_p is not None:
            company_pages = pdf_pages_by_company[gold["company"]]
            cand_indices = set([int(pred_p) + d for d in [-1, 0, 1]])
            if gold["company"] in ["Boliden", "Alleima"]:
                for d in [-1, 0, 1]:
                    cand_indices.add(int(pred_p) + 1 + d)

            for p_cand in sorted(cand_indices):
                if 0 <= p_cand < len(company_pages):
                    page_text = company_pages[p_cand]["text"]
                    ev_res = check_evidence_on_page(page_text, p_raw, p_unit, p_norm)
                    if ev_res["status"] in ["supported", "ambiguous"]:
                        ev_status = ev_res["status"]
                        ev_snippet = ev_res["evidence_snippet"]
                        break

        if p_raw is not None and ev_status == "not_found":
            unsupported_count += 1

        eval_records.append({
            "observation_id": obs_id,
            "company": gold["company"],
            "kpi_name": kpi_name,
            "gold_raw_value": gold["raw_value"],
            "pred_raw_value": p_raw,
            "gold_norm_value": g_norm,
            "pred_norm_value": p_norm,
            "value_correct": val_correct,
            "gold_page": gold_p,
            "pred_page": pred_p,
            "page_correct": page_correct,
            "evidence_status": ev_status,
            "evidence_snippet": ev_snippet
        })

    # Metric calculations
    coverage = extracted_count / total_evaluable if total_evaluable > 0 else 0.0
    value_acc = correct_values / total_evaluable if total_evaluable > 0 else 0.0
    page_acc = correct_pages / total_evaluable if total_evaluable > 0 else 0.0
    unsupported_rate = unsupported_count / extracted_count if extracted_count > 0 else 0.0
    failure_rate = technical_failures / total_evaluable if total_evaluable > 0 else 0.0

    cost_per_correct = (total_cost_usd / correct_values) if correct_values > 0 else None
    avg_latency_ms = (total_latency_ms / total_evaluable) if total_evaluable > 0 else 0.0

    return {
        "total_observations": total_evaluable,
        "extracted_observations": extracted_count,
        "correct_values": correct_values,
        "correct_pages": correct_pages,
        "unsupported_values": unsupported_count,
        "technical_failures": technical_failures,
        "metrics": {
            "value_accuracy": round(value_acc, 4),
            "value_accuracy_ci_95": list(wilson_score_ci(correct_values, total_evaluable)),
            "page_accuracy": round(page_acc, 4),
            "page_accuracy_ci_95": list(wilson_score_ci(correct_pages, total_evaluable)),
            "coverage": round(coverage, 4),
            "coverage_ci_95": list(wilson_score_ci(extracted_count, total_evaluable)),
            "unsupported_value_rate": round(unsupported_rate, 4),
            "unsupported_rate_ci_95": list(wilson_score_ci(unsupported_count, extracted_count if extracted_count > 0 else 1)),
            "technical_failure_rate": round(failure_rate, 4),
            "total_cost_usd": round(total_cost_usd, 6),
            "cost_per_correct_kpi_usd": round(cost_per_correct, 6) if cost_per_correct is not None else None,
            "total_latency_ms": total_latency_ms,
            "avg_latency_per_kpi_ms": round(avg_latency_ms, 1)
        },
        "records": eval_records
    }
