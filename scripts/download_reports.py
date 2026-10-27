"""
Download Official Sustainability Reports
Downloads the four official FY2025 annual reports evaluated in the benchmark
directly from their respective investor relations portals into data/raw_reports/.

Hardened validation:
- Downloads to a temporary file before touching destination.
- Verifies PDF magic bytes (%PDF) and minimum file size (>500 KB).
- Validates structural PDF integrity via PyMuPDF (fitz) page count.
- Atomically replaces destination path only after successful verification.
"""

import json
import os
from pathlib import Path
import tempfile
import urllib.request
import sys
import fitz  # PyMuPDF

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "data" / "source_manifest.json"
REPORTS_DIR = PROJECT_ROOT / "data" / "raw_reports"
MIN_FILE_SIZE_BYTES = 500_000  # All 4 corporate reports are multi-megabyte PDFs


def verify_pdf_integrity(file_path: Path) -> bool:
    """Verifies %PDF magic bytes and basic structural validity via fitz."""
    if not file_path.exists() or file_path.stat().st_size < MIN_FILE_SIZE_BYTES:
        return False

    with open(file_path, "rb") as f:
        header = f.read(4)
        if header != b"%PDF":
            return False

    try:
        doc = fitz.open(file_path)
        page_count = doc.page_count
        doc.close()
        return page_count > 0
    except Exception:
        return False


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

        if verify_pdf_integrity(dest_path):
            size_mb = dest_path.stat().st_size / (1024 * 1024)
            print(f"[VERIFIED] {company:8} -> {local_name} ({size_mb:.1f} MB, valid PDF)")
            continue

        print(f"[FETCHING] {company:8} from {url}...")
        tmp_fd, tmp_path_str = tempfile.mkstemp(prefix=f"{dest_path.stem}_", suffix=".tmp", dir=REPORTS_DIR)
        os.close(tmp_fd)
        tmp_path = Path(tmp_path_str)

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp_path, "wb") as out:
                while chunk := resp.read(65536):
                    out.write(chunk)

            if not verify_pdf_integrity(tmp_path):
                raise ValueError(f"Downloaded file failed PDF signature or structural integrity check (size: {tmp_path.stat().st_size} bytes)")

            # Atomic replacement
            os.replace(tmp_path, dest_path)
            size_mb = dest_path.stat().st_size / (1024 * 1024)
            print(f"[DONE]     {company:8} -> {local_name} ({size_mb:.1f} MB, valid PDF)")
        except Exception as e:
            print(f"[FAILED]   {company:8} -> Error: {e}")
            print(f"           Manual download URL: {url}\n")
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass


if __name__ == "__main__":
    download_reports()
