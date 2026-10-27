"""
Download Official Sustainability Reports
Downloads the four official FY2025 annual reports evaluated in the benchmark
directly from their respective investor relations portals into data/raw_reports/.
"""

import json
from pathlib import Path
import urllib.request
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "data" / "source_manifest.json"
REPORTS_DIR = PROJECT_ROOT / "data" / "raw_reports"


def download_reports():
    if not MANIFEST_PATH.exists():
        print(f"Error: Source manifest not found at {MANIFEST_PATH}")
        sys.exit(1)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    print(f"Downloading {len(manifest['reports'])} official reports to {REPORTS_DIR}...\n")

    for rep in manifest["reports"]:
        company = rep["company"]
        url = rep["official_source_url"]
        local_name = rep["local_filename"]
        dest_path = REPORTS_DIR / local_name

        if dest_path.exists() and dest_path.stat().st_size > 100_000:
            size_mb = dest_path.stat().st_size / (1024 * 1024)
            print(f"[EXISTS] {company:8} -> {local_name} ({size_mb:.1f} MB)")
            continue

        print(f"[FETCHING] {company:8} from {url}...")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp, open(dest_path, "wb") as out:
                out.write(resp.read())
            size_mb = dest_path.stat().st_size / (1024 * 1024)
            print(f"[DONE]     {company:8} -> {local_name} ({size_mb:.1f} MB)")
        except Exception as e:
            print(f"[FAILED]   {company:8} -> Error: {e}")
            print(f"           Manual download URL: {url}\n")


if __name__ == "__main__":
    download_reports()
