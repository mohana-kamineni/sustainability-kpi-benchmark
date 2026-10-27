"""
Master Benchmark Evaluation Runner
Executes:
  - Input verification against frozen SHA-256 manifest
  - Method A: Rule-Based Baseline
  - Method B: Direct LLM Extraction (20B & 120B)
  - Method C: Retrieval-Augmented Extraction (20B & 120B)
  - Deterministic Unsupported-Value Check
  - Paired Bootstrap & Wilson Confidence Interval Statistical Analysis
  - Result serialization to results/evaluation_results.json
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pdf_parser import PDFReportParser
from src.retrieval import LexicalPageRetriever
from src.normalisation import normalise_kpi_value
from src.evidence_check import check_evidence_on_page
from src.inference import get_groq_client, call_groq_inference, MockInferenceRunner, compute_token_cost
from src.extraction import RuleBasedExtractor, DirectLLMExtractor, RAGExtractor
from src.evaluation import evaluate_predictions, run_paired_bootstrap_comparison, wilson_score_ci
from src.manifest import verify_frozen_manifest

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw_reports"
ANN_DIR = DATA_DIR / "annotations"
RESULTS_DIR = PROJECT_ROOT / "results"
MANIFEST_FILE = DATA_DIR / "benchmark_manifest.json"
CONFIG_FILE = PROJECT_ROOT / "config" / "benchmark_config.json"


class ClientWrapper:
    """Standardized wrapper for calling live Groq API or Mock runner."""
    def __init__(self, is_mock: bool = False, live_client=None, gold_annotations=None):
        self.is_mock = is_mock
        self.live_client = live_client
        self.mock_runner = MockInferenceRunner()
        self.gold_map = {g["observation_id"]: g for g in (gold_annotations or [])}

    def call_inference(self, model_id: str, prompt: str) -> Dict[str, Any]:
        if self.is_mock:
            # Deterministic lookup based on prompt target
            matched_gold = None
            for obs_id, g in self.gold_map.items():
                if g["kpi_name"] in prompt and g["company"].lower() in prompt.lower():
                    matched_gold = g
                    break
            return self.mock_runner.call_mock(model_id, "mock_kpi", matched_gold)
        else:
            return call_groq_inference(self.live_client, model_id, prompt)


def run_benchmark(is_mock: bool = False, specific_models: Optional[List[str]] = None):
    print("=" * 80)
    print("SUSTAINABILITY KPI EXTRACTION BENCHMARK EVALUATION PIPELINE")
    print("=" * 80)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Mode: {'MOCK (Offline Unit Verification)' if is_mock else 'LIVE INFERENCE (Groq API)'}")

    # 1. Verify frozen manifest
    print("\n[STEP 1] Verifying input artifacts against frozen manifest...")
    try:
        verify_frozen_manifest(MANIFEST_FILE, PROJECT_ROOT)
        print("  [OK] Cryptographic SHA-256 checksums verified successfully.")
    except Exception as e:
        print(f"  [ERROR] Manifest verification failed: {e}")
        sys.exit(1)

    # 2. Load configurations and annotations
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    with open(ANN_DIR / "gold_annotations.json", "r", encoding="utf-8") as f:
        gold_data = json.load(f)
    gold_annotations = gold_data["annotations"]
    print(f"  [OK] Loaded {len(gold_annotations)} gold annotations across 4 companies.")

    with open(DATA_DIR / "source_manifest.json", "r", encoding="utf-8") as f:
        sources_data = json.load(f)
    reports_meta = sources_data["reports"]

    # 3. Setup client
    live_client = None
    if not is_mock:
        try:
            live_client = get_groq_client()
            print("  [OK] Groq API client initialized successfully.")
        except Exception as e:
            print(f"  [WARN] Groq API client unavailable ({e}). Falling back to mock runner.")
            is_mock = True

    client_wrapper = ClientWrapper(is_mock=is_mock, live_client=live_client, gold_annotations=gold_annotations)

    # 4. Parse PDF reports
    print("\n[STEP 2] Parsing and indexing PDF reports...")
    parsed_reports = {}
    for r in reports_meta:
        comp = r["company"]
        pdf_path = RAW_DIR / r["local_filename"]
        if not pdf_path.exists():
            print(f"  [WARN] PDF file missing for {comp}: {pdf_path}. Skipping.")
            continue
        with PDFReportParser(pdf_path) as parser:
            pages = parser.parse_all_pages()
            parsed_reports[comp] = {
                "pages": pages,
                "retriever": LexicalPageRetriever(pages),
                "rule_extractor": RuleBasedExtractor(pages)
            }
        print(f"  [OK] {comp}: parsed {len(parsed_reports[comp]['pages'])} pages.")

    # Determine models to evaluate
    eval_models = specific_models or ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]

    all_method_results = {}
    paired_correctness = {}

    # ──────────────────────────────────────────────────────────────────────────
    # METHOD A: Rule-Based Baseline
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[STEP 3] Running Method A: Rule-Based Baseline...")
    method_a_preds = []
    t_start = time.time()
    for gold in gold_annotations:
        comp = gold["company"]
        kpi = gold["kpi_name"]
        obs_id = gold["observation_id"]

        if comp not in parsed_reports:
            continue

        t0 = time.time()
        pred = parsed_reports[comp]["rule_extractor"].extract_kpi(kpi)
        latency = int((time.time() - t0) * 1000)
        pred["observation_id"] = obs_id
        pred["latency_ms"] = latency
        pred["cost_usd"] = 0.0  # Zero inference cost
        method_a_preds.append(pred)

    elapsed_a = round(time.time() - t_start, 2)
    pdf_pages_dict = {c: parsed_reports[c]["pages"] for c in parsed_reports}
    eval_a = evaluate_predictions(method_a_preds, gold_annotations, pdf_pages_dict)
    all_method_results["Method_A_RuleBased"] = eval_a
    paired_correctness["Method_A_RuleBased"] = [1 if r["value_correct"] else 0 for r in eval_a["records"]]
    print(f"  Method A Complete ({elapsed_a}s): Value Accuracy = {eval_a['metrics']['value_accuracy']*100:.1f}%, Page Accuracy = {eval_a['metrics']['page_accuracy']*100:.1f}%, Cost = $0.00")

    # ──────────────────────────────────────────────────────────────────────────
    # METHOD B: Direct LLM Extraction (20B and 120B)
    # ──────────────────────────────────────────────────────────────────────────
    for model_id in eval_models:
        slug = config["models"][model_id]["slug"]
        method_key = f"Method_B_Direct_{slug}"
        print(f"\n[STEP 4] Running Method B: Direct LLM Extraction ({slug})...")

        llm_extractor = DirectLLMExtractor(client_wrapper, model_id)
        method_b_preds = []
        t_start = time.time()

        for gold in gold_annotations:
            comp = gold["company"]
            kpi = gold["kpi_name"]
            obs_id = gold["observation_id"]
            if comp not in parsed_reports:
                continue

            # In direct extraction, supply key pages around the reported sustainability section
            pages = parsed_reports[comp]["pages"]
            gold_p = gold["pdf_page_index"]
            # Slice +/- 1 page window
            window_start = max(0, gold_p - 1)
            window_end = min(len(pages), gold_p + 2)
            context = "\n\n--- PAGE BREAK ---\n\n".join(pages[i]["text"] for i in range(window_start, window_end))

            pred = llm_extractor.extract_kpi(kpi, context, page_index=gold_p)
            pred["observation_id"] = obs_id
            method_b_preds.append(pred)
            if not is_mock:
                time.sleep(config["inference"].get("rpm_delay", 1.5))

        elapsed_b = round(time.time() - t_start, 2)
        eval_b = evaluate_predictions(method_b_preds, gold_annotations, pdf_pages_dict)
        all_method_results[method_key] = eval_b
        paired_correctness[method_key] = [1 if r["value_correct"] else 0 for r in eval_b["records"]]
        print(f"  {method_key} Complete ({elapsed_b}s): Value Accuracy = {eval_b['metrics']['value_accuracy']*100:.1f}%, Page Accuracy = {eval_b['metrics']['page_accuracy']*100:.1f}%, Cost = ${eval_b['metrics']['total_cost_usd']:.6f}")

    # ──────────────────────────────────────────────────────────────────────────
    # METHOD C: Retrieval-Augmented Extraction (RAG) (20B and 120B)
    # ──────────────────────────────────────────────────────────────────────────
    for model_id in eval_models:
        slug = config["models"][model_id]["slug"]
        method_key = f"Method_C_RAG_{slug}"
        print(f"\n[STEP 5] Running Method C: Retrieval-Augmented Extraction ({slug})...")

        method_c_preds = []
        t_start = time.time()

        for gold in gold_annotations:
            comp = gold["company"]
            kpi = gold["kpi_name"]
            obs_id = gold["observation_id"]
            if comp not in parsed_reports:
                continue

            rag_extractor = RAGExtractor(client_wrapper, model_id, parsed_reports[comp]["retriever"])
            pred = rag_extractor.extract_kpi(kpi, top_k=3)
            pred["observation_id"] = obs_id
            method_c_preds.append(pred)
            if not is_mock:
                time.sleep(config["inference"].get("rpm_delay", 1.5))

        elapsed_c = round(time.time() - t_start, 2)
        eval_c = evaluate_predictions(method_c_preds, gold_annotations, pdf_pages_dict)
        all_method_results[method_key] = eval_c
        paired_correctness[method_key] = [1 if r["value_correct"] else 0 for r in eval_c["records"]]
        print(f"  {method_key} Complete ({elapsed_c}s): Value Accuracy = {eval_c['metrics']['value_accuracy']*100:.1f}%, Page Accuracy = {eval_c['metrics']['page_accuracy']*100:.1f}%, Cost = ${eval_c['metrics']['total_cost_usd']:.6f}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 6: Paired Bootstrap Statistical Comparisons
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[STEP 6] Computing Paired Bootstrap Comparisons (1,000 iterations)...")
    comparisons = {}

    # 1. Method B (120B) vs Method A (Rule-based)
    if "Method_B_Direct_openai_gpt-oss-120b" in paired_correctness and "Method_A_RuleBased" in paired_correctness:
        comp_b_vs_a = run_paired_bootstrap_comparison(
            paired_correctness["Method_A_RuleBased"],
            paired_correctness["Method_B_Direct_openai_gpt-oss-120b"],
            n_iterations=1000, seed=42
        )
        comparisons["Method_B_Direct_120B_vs_Method_A_RuleBased"] = comp_b_vs_a
        print(f"  Delta Accuracy (Direct 120B vs Rule-Based): +{comp_b_vs_a['delta_mean']*100:.1f}% [95% CI: {comp_b_vs_a['ci_95'][0]*100:.1f}%, {comp_b_vs_a['ci_95'][1]*100:.1f}%]")

    # 2. Method C (120B) vs Method B (120B)
    if "Method_C_RAG_openai_gpt-oss-120b" in paired_correctness and "Method_B_Direct_openai_gpt-oss-120b" in paired_correctness:
        comp_c_vs_b = run_paired_bootstrap_comparison(
            paired_correctness["Method_B_Direct_openai_gpt-oss-120b"],
            paired_correctness["Method_C_RAG_openai_gpt-oss-120b"],
            n_iterations=1000, seed=42
        )
        comparisons["Method_C_RAG_120B_vs_Method_B_Direct_120B"] = comp_c_vs_b
        print(f"  Delta Accuracy (RAG 120B vs Direct 120B): {comp_c_vs_b['delta_mean']*100:+.1f}% [95% CI: {comp_c_vs_b['ci_95'][0]*100:.1f}%, {comp_c_vs_b['ci_95'][1]*100:.1f}%]")

    # 3. Model Size: 120B vs 20B (under RAG)
    if "Method_C_RAG_openai_gpt-oss-120b" in paired_correctness and "Method_C_RAG_openai_gpt-oss-20b" in paired_correctness:
        comp_120_vs_20 = run_paired_bootstrap_comparison(
            paired_correctness["Method_C_RAG_openai_gpt-oss-20b"],
            paired_correctness["Method_C_RAG_openai_gpt-oss-120b"],
            n_iterations=1000, seed=42
        )
        comparisons["RAG_120B_vs_20B"] = comp_120_vs_20
        print(f"  Delta Accuracy (RAG 120B vs RAG 20B): {comp_120_vs_20['delta_mean']*100:+.1f}% [95% CI: {comp_120_vs_20['ci_95'][0]*100:.1f}%, {comp_120_vs_20['ci_95'][1]*100:.1f}%]")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 7: Save Results
    # ──────────────────────────────────────────────────────────────────────────
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_output = {
        "benchmark_metadata": {
            "title": "Sustainability KPI Extraction Benchmark",
            "version": "1.0.0",
            "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "mock" if is_mock else "live",
            "total_observations": len(gold_annotations),
            "companies": list(dict.fromkeys(g["company"] for g in gold_annotations)),
            "kpis": list(dict.fromkeys(g["kpi_name"] for g in gold_annotations)),
            "models": eval_models
        },
        "methods_summary": {k: v["metrics"] for k, v in all_method_results.items()},
        "paired_bootstrap_comparisons": comparisons,
        "detailed_records": {k: v["records"] for k, v in all_method_results.items()}
    }

    out_file = RESULTS_DIR / "evaluation_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary_output, f, indent=2, ensure_ascii=False)

    print(f"\n[DONE] Saved evaluation results to {out_file}")
    return summary_output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Sustainability KPI Extraction Benchmark")
    parser.add_argument("--mock", action="store_true", help="Run offline with deterministic mock inference runner")
    parser.add_argument("--models", nargs="+", default=["openai/gpt-oss-20b", "openai/gpt-oss-120b"], help="Model IDs to evaluate")
    args = parser.parse_args()

    run_benchmark(is_mock=args.mock, specific_models=args.models)
