"""
Unit tests for PDF parsing and page extraction.
"""

from pathlib import Path
from src.pdf_parser import PDFReportParser

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_REPORTS_DIR = PROJECT_ROOT / "data" / "raw_reports"


def test_pdf_parser_loads_and_extracts():
    pdf_path = RAW_REPORTS_DIR / "sandvik_annual_report_2025.pdf"
    if not pdf_path.exists():
        return  # Skip if raw PDF is not present in local test environment

    with PDFReportParser(pdf_path) as parser:
        assert parser.total_pages == 180
        text = parser.extract_page_text(71)  # 0-based index 71 (page 72)
        assert len(text) > 0
        assert "E1-6" in text or "Scope 1" in text

        printed_page = parser.detect_printed_page_number(71, text)
        assert 65 <= printed_page <= 75
