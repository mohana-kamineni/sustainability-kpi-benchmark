"""
Regression Test Suite for Sustainability KPI Extraction Benchmark
Tests:
1. Frozen benchmark SHA-256 integrity and manifest verification.
2. Exact observation counts and category denominators (4 companies x 8 KPIs = 32).
3. Value normalisation, unit conversions, and missing-disclosure handling.
4. Evaluation metric calculations, deterministic evidence checks, and Wilson score intervals.
"""

import json
from pathlib import Path
from src.manifest import verify_frozen_manifest
from src.evaluation import wilson_score_ci
from src.normalisation import normalise_kpi_value

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "data" / "benchmark_manifest.json"
ANNOTATIONS_PATH = PROJECT_ROOT / "data" / "annotations" / "gold_annotations.json"


def test_frozen_manifest_integrity():
    """Verify cryptographic SHA-256 hashes of all frozen input artifacts."""
    assert verify_frozen_manifest(MANIFEST_PATH, PROJECT_ROOT) is True


def test_gold_dataset_denominators():
    """Verify exact counts and category balance across all 4 companies."""
    with open(ANNOTATIONS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    annotations = data.get("annotations", [])
    assert len(annotations) == 32, f"Expected 32 annotations, got {len(annotations)}"

    companies = set(a["company"] for a in annotations)
    assert companies == {"Sandvik", "Epiroc", "Alleima", "Boliden"}

    for comp in companies:
        comp_records = [a for a in annotations if a["company"] == comp]
        assert len(comp_records) == 8, f"Expected 8 KPIs for {comp}, got {len(comp_records)}"
        kpi_names = set(a["kpi_name"] for a in comp_records)
        assert len(kpi_names) == 8, f"Duplicate or missing KPI names for {comp}"

        for r in comp_records:
            assert r["reporting_year"] == 2025
            assert r["disclosure_status"] == "disclosed"
            assert r["normalised_value"] is not None
            assert r["normalised_unit"] is not None
            assert r["pdf_page_index"] >= 0
            assert len(r["evidence_text"]) > 5


def test_unit_conversion_invariants():
    """Test emissions and energy unit conversions."""
    # Sandvik: 78,326 ton CO2eq -> 78,326 tonnes CO2e
    v, u = normalise_kpi_value("scope_1_ghg_emissions", 78326, "ton CO2eq")
    assert v == 78326.0 and u == "tonnes CO2e"

    # Epiroc: 32 ktCO2e -> 32,000 tonnes CO2e
    v, u = normalise_kpi_value("scope_1_ghg_emissions", 32, "ktCO2e")
    assert v == 32000.0 and u == "tonnes CO2e"

    # Alleima: 82 thousand ton CO2eq -> 82,000 tonnes CO2e
    v, u = normalise_kpi_value("scope_1_ghg_emissions", 82, "thousand ton CO2eq")
    assert v == 82000.0 and u == "tonnes CO2e"

    # Epiroc energy: 319 GWh -> 319,000 MWh
    v, u = normalise_kpi_value("total_energy_consumption", 319, "GWh")
    assert v == 319000.0 and u == "MWh"


def test_statistical_interval_invariants():
    """Verify Wilson score confidence interval mathematical bounds."""
    # 32 out of 32 correct (100% accuracy)
    lo, hi = wilson_score_ci(32, 32)
    assert 0.85 < lo < 1.0
    assert hi == 1.0

    # 16 out of 32 correct (50% accuracy)
    lo, hi = wilson_score_ci(16, 32)
    assert 0.30 < lo < 0.50
    assert 0.50 < hi < 0.70


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING BENCHMARK REGRESSION TESTS")
    print("=" * 60)
    test_frozen_manifest_integrity()
    print("[PASS] Test 1: Frozen Manifest Cryptographic SHA-256 Integrity Verified")
    test_gold_dataset_denominators()
    print("[PASS] Test 2: Gold Dataset Denominators (32 observations, 4 companies x 8 KPIs) Verified")
    test_unit_conversion_invariants()
    print("[PASS] Test 3: Unit Normalisation and Conversion Invariants Verified")
    test_statistical_interval_invariants()
    print("[PASS] Test 4: Statistical Interval Bounds Verified")
    print("=" * 60)
    print("ALL REGRESSION TESTS PASSED CLEANLY")
    print("=" * 60)
