"""
Manifest and Artifact Hashing Module
Computes SHA-256 digests and manages the frozen benchmark manifest.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional


def compute_sha256(filepath: Path) -> str:
    """Computes lowercase hex SHA-256 digest on raw byte stream."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def create_frozen_manifest(
    project_root: Path,
    output_filename: str = "benchmark_manifest.json"
) -> Path:
    """
    Creates frozen benchmark manifest containing cryptographic checksums
    of all benchmark input definitions, annotations, and configs.
    """
    data_dir = project_root / "data"
    ann_dir = data_dir / "annotations"
    cfg_dir = project_root / "config"

    files_to_hash = {
        "gold_annotations.json": ann_dir / "gold_annotations.json",
        "gold_annotations.jsonl": ann_dir / "gold_annotations.jsonl",
        "source_manifest.json": data_dir / "source_manifest.json",
        "benchmark_config.json": cfg_dir / "benchmark_config.json",
    }

    hashes = {}
    for key, path in files_to_hash.items():
        if path.exists():
            hashes[key] = compute_sha256(path)
        else:
            raise FileNotFoundError(f"Cannot freeze manifest; required file missing: {path}")

    # Load annotations to include corpus summary
    with open(files_to_hash["gold_annotations.json"], "r", encoding="utf-8") as f:
        ann_data = json.load(f)

    annotations = ann_data.get("annotations", [])
    companies = list(dict.fromkeys(a["company"] for a in annotations))
    kpis = list(dict.fromkeys(a["kpi_name"] for a in annotations))

    manifest = {
        "title": "Sustainability KPI Extraction Benchmark Frozen Manifest",
        "version": "1.0.0",
        "frozen_timestamp": "2026-10-25T18:00:00Z",
        "corpus_scope": {
            "companies": companies,
            "reporting_year": 2025,
            "total_observations": len(annotations),
            "kpis": kpis
        },
        "frozen_artifacts_sha256": hashes,
        "models_evaluated": [
            "openai/gpt-oss-20b",
            "openai/gpt-oss-120b"
        ],
        "methods_evaluated": [
            "Method A: Rule-based baseline",
            "Method B: Direct LLM extraction",
            "Method C: Retrieval-augmented extraction (RAG)"
        ]
    }

    out_path = data_dir / output_filename
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return out_path


def verify_frozen_manifest(manifest_path: Path, project_root: Path) -> bool:
    """
    Verifies that all files listed in the frozen manifest match their expected SHA-256.
    Raises ValueError on mismatch.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    expected_hashes = manifest.get("frozen_artifacts_sha256", {})
    data_dir = project_root / "data"
    ann_dir = data_dir / "annotations"
    cfg_dir = project_root / "config"

    path_lookup = {
        "gold_annotations.json": ann_dir / "gold_annotations.json",
        "gold_annotations.jsonl": ann_dir / "gold_annotations.jsonl",
        "source_manifest.json": data_dir / "source_manifest.json",
        "benchmark_config.json": cfg_dir / "benchmark_config.json",
    }

    for name, expected_hash in expected_hashes.items():
        file_path = path_lookup.get(name, data_dir / name)
        if not file_path.exists():
            raise FileNotFoundError(f"Frozen file missing: {file_path}")
        actual_hash = compute_sha256(file_path)
        if actual_hash != expected_hash:
            raise ValueError(
                f"Cryptographic hash mismatch for {name}! Expected {expected_hash}, got {actual_hash}"
            )

    return True
