"""
PDF Parser module for Sustainability Reports
Extracts text, page numbers, and structural page chunks preserving provenance.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional
import fitz  # PyMuPDF


class PDFReportParser:
    def __init__(self, pdf_path: Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found at {self.pdf_path}")
        self.doc = fitz.open(self.pdf_path)
        self.total_pages = len(self.doc)

    def extract_page_text(self, page_index: int) -> str:
        """Extract plain text for 0-based page_index."""
        if page_index < 0 or page_index >= self.total_pages:
            raise IndexError(f"Page index {page_index} out of range (0..{self.total_pages - 1})")
        return self.doc[page_index].get_text()

    def detect_printed_page_number(self, page_index: int, text: Optional[str] = None) -> int:
        """
        Attempts to detect printed folio number on the page.
        Falls back to page_index + 1 if no printed number is reliably identified.
        """
        if text is None:
            text = self.extract_page_text(page_index)

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return page_index + 1

        # Check first 3 and last 3 lines for page number patterns
        candidates = lines[:3] + lines[-3:]
        for line in candidates:
            # Pattern like "P. 71", "Page 71", "71 | Sandvik", "108 | Alleima", or standalone number
            m = re.search(r'(?:p\.?\s*|page\s*)?(\d{1,3})(?:\s*\|\s*|\s*$)', line, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                if 1 <= val <= self.total_pages + 20:
                    return val

        # Fallback
        return page_index + 1

    def parse_all_pages(self) -> List[Dict]:
        """
        Parses all pages in the document and returns a list of page dicts:
        [
            {
                "pdf_page_index": int (0-based),
                "printed_page_number": int (1-based),
                "text": str,
                "char_count": int,
                "word_count": int
            }, ...
        ]
        """
        pages = []
        for idx in range(self.total_pages):
            text = self.extract_page_text(idx)
            printed_p = self.detect_printed_page_number(idx, text)
            pages.append({
                "pdf_page_index": idx,
                "printed_page_number": printed_p,
                "text": text,
                "char_count": len(text),
                "word_count": len(text.split())
            })
        return pages

    def close(self):
        if self.doc:
            self.doc.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
