"""
Extraction Methods Module
Implements:
  - Method A: Rule-Based Baseline
  - Method B: Direct LLM Extraction
  - Method C: Retrieval-Augmented Extraction (RAG)
"""

import json
import re
from typing import Any, Dict, List, Optional
from src.normalisation import clean_numeric_string, parse_target_year, normalise_kpi_value
from src.retrieval import LexicalPageRetriever


EXTRACTION_SCHEMA_INSTRUCTION = """
You are an expert sustainability analyst. Extract the requested KPI for reporting year 2025 from the provided corporate report text.

You MUST respond with valid JSON strictly adhering to this schema:
{
  "kpi_name": "<exact_kpi_name>",
  "raw_value": <number or string or null>,
  "raw_unit": "<unit string or null>",
  "disclosure_status": "disclosed" | "not_disclosed" | "not_comparable_or_ambiguous",
  "reporting_boundary": "<e.g. group_operations, market_based, location_based, own_operations or null>",
  "pdf_page_index": <0-based integer page index where evidence was found, or null>,
  "evidence_text": "<exact sentence or table cell excerpt supporting the value>",
  "confidence": <float between 0.0 and 1.0>
}

Rules:
1. Do not hallucinate or guess. If the metric is not disclosed in the text, set disclosure_status to "not_disclosed" and raw_value to null.
2. Never substitute 0 for a missing KPI.
3. Keep the original raw reported number and original unit.
4. For emissions, differentiate Scope 1, Scope 2 (market-based preferred), and Scope 3.
5. For net-zero target, return the target year (e.g. 2050).
6. For SBTi status, specify whether targets are validated or committed.
"""


# ── Method A: Rule-Based Baseline ──────────────────────────────────────────

class RuleBasedExtractor:
    """Modest regex and rule-based baseline extractor."""

    def __init__(self, pages: List[Dict]):
        self.pages = pages

    def extract_kpi(self, kpi_name: str) -> Dict[str, Any]:
        kpi = kpi_name.lower()
        if "scope_1" in kpi:
            return self._extract_scope_1()
        elif "scope_2" in kpi:
            return self._extract_scope_2()
        elif "scope_3" in kpi:
            return self._extract_scope_3()
        elif "energy" in kpi:
            return self._extract_energy()
        elif "renewable" in kpi:
            return self._extract_renewable_share()
        elif "net_zero" in kpi:
            return self._extract_net_zero()
        elif "sbti" in kpi:
            return self._extract_sbti()
        elif "safety" in kpi or "trifr" in kpi or "ltif" in kpi:
            return self._extract_safety()
        return self._missing_result(kpi_name)

    def _missing_result(self, kpi_name: str) -> Dict[str, Any]:
        return {
            "kpi_name": kpi_name,
            "raw_value": None,
            "raw_unit": None,
            "disclosure_status": "not_disclosed",
            "reporting_boundary": None,
            "pdf_page_index": None,
            "evidence_text": None,
            "confidence": 0.0
        }

    def _extract_scope_1(self) -> Dict[str, Any]:
        # Search for Gross Scope 1 GHG emissions followed by numbers
        pattern = re.compile(r'(?:gross\s+)?scope\s*1\s*(?:ghg\s*)?emissions?[^\n\d]*?(\d{1,3}(?:[,\s]\d{3})*|\d+)', re.I)
        for p in self.pages:
            t = p["text"]
            if "scope 1" in t.lower() and ("ton" in t.lower() or "tco2" in t.lower() or "ktco2" in t.lower() or "e1-6" in t.lower()):
                m = pattern.search(t)
                if m:
                    raw_val = m.group(1).replace(" ", "").replace(",", "")
                    unit = "ktCO2e" if "kt" in t[m.start():m.end()+30].lower() else "ton CO2eq"
                    return {
                        "kpi_name": "scope_1_ghg_emissions",
                        "raw_value": float(raw_val),
                        "raw_unit": unit,
                        "disclosure_status": "disclosed",
                        "reporting_boundary": "group_operations_gross",
                        "pdf_page_index": p["pdf_page_index"],
                        "evidence_text": t[max(0, m.start()-20):min(len(t), m.end()+40)].strip(),
                        "confidence": 0.8
                    }
        return self._missing_result("scope_1_ghg_emissions")

    def _extract_scope_2(self) -> Dict[str, Any]:
        pattern = re.compile(r'(?:gross\s+)?(?:market-based\s+)?scope\s*2\s*(?:ghg\s*)?emissions?[^\n\d]*?(\d{1,3}(?:[,\s]\d{3})*|\d+)', re.I)
        for p in self.pages:
            t = p["text"]
            if "scope 2" in t.lower() and ("market-based" in t.lower() or "location-based" in t.lower() or "e1-6" in t.lower()):
                m = pattern.search(t)
                if m:
                    raw_val = m.group(1).replace(" ", "").replace(",", "")
                    unit = "ktCO2e" if "kt" in t[m.start():m.end()+30].lower() else "ton CO2eq"
                    return {
                        "kpi_name": "scope_2_ghg_emissions",
                        "raw_value": float(raw_val),
                        "raw_unit": unit,
                        "disclosure_status": "disclosed",
                        "reporting_boundary": "market_based",
                        "pdf_page_index": p["pdf_page_index"],
                        "evidence_text": t[max(0, m.start()-20):min(len(t), m.end()+40)].strip(),
                        "confidence": 0.75
                    }
        return self._missing_result("scope_2_ghg_emissions")

    def _extract_scope_3(self) -> Dict[str, Any]:
        pattern = re.compile(r'(?:total\s+)?(?:gross\s+)?(?:indirect\s+)?\(?scope\s*3\)?[^\n\d]*?(\d{1,3}(?:[,\s]\d{3})*|\d+)', re.I)
        for p in self.pages:
            t = p["text"]
            if "scope 3" in t.lower() and ("ton" in t.lower() or "tco2" in t.lower() or "kt" in t.lower() or "e1-6" in t.lower()):
                m = pattern.search(t)
                if m:
                    raw_val = m.group(1).replace(" ", "").replace(",", "")
                    unit = "ktCO2e" if "kt" in t[m.start():m.end()+30].lower() else "ton CO2eq"
                    return {
                        "kpi_name": "scope_3_ghg_emissions",
                        "raw_value": float(raw_val),
                        "raw_unit": unit,
                        "disclosure_status": "disclosed",
                        "reporting_boundary": "total_gross_indirect",
                        "pdf_page_index": p["pdf_page_index"],
                        "evidence_text": t[max(0, m.start()-20):min(len(t), m.end()+40)].strip(),
                        "confidence": 0.7
                    }
        return self._missing_result("scope_3_ghg_emissions")

    def _extract_energy(self) -> Dict[str, Any]:
        pattern = re.compile(r'total\s+energy\s+consumption[^\n\d]*?(\d{1,3}(?:[,\s]\d{3})*|\d+)', re.I)
        for p in self.pages:
            t = p["text"]
            if "total energy consumption" in t.lower():
                m = pattern.search(t)
                if m:
                    raw_val = m.group(1).replace(" ", "").replace(",", "")
                    unit = "GWh" if "gwh" in t[max(0, m.start()-100):m.end()+50].lower() else "MWh"
                    return {
                        "kpi_name": "total_energy_consumption",
                        "raw_value": float(raw_val),
                        "raw_unit": unit,
                        "disclosure_status": "disclosed",
                        "reporting_boundary": "own_operations_total",
                        "pdf_page_index": p["pdf_page_index"],
                        "evidence_text": t[max(0, m.start()-20):min(len(t), m.end()+40)].strip(),
                        "confidence": 0.8
                    }
        return self._missing_result("total_energy_consumption")

    def _extract_renewable_share(self) -> Dict[str, Any]:
        pattern = re.compile(r'share\s+of\s+renewable\s+(?:sources|energy)[^\n\d]*?(\d+(?:[,\.]\d+)?)\s*%', re.I)
        for p in self.pages:
            t = p["text"]
            if "renewable" in t.lower() and "%" in t:
                m = pattern.search(t)
                if m:
                    raw_val = m.group(1).replace(",", ".")
                    return {
                        "kpi_name": "renewable_electricity_share",
                        "raw_value": float(raw_val),
                        "raw_unit": "%",
                        "disclosure_status": "disclosed",
                        "reporting_boundary": "total_energy_mix",
                        "pdf_page_index": p["pdf_page_index"],
                        "evidence_text": t[max(0, m.start()-20):min(len(t), m.end()+30)].strip(),
                        "confidence": 0.75
                    }
        return self._missing_result("renewable_electricity_share")

    def _extract_net_zero(self) -> Dict[str, Any]:
        pattern = re.compile(r'net[- ]zero[^\n\.]*?(?:by|in)\s*(20[3-5]\d)', re.I)
        for p in self.pages:
            t = p["text"]
            if "net-zero" in t.lower() or "net zero" in t.lower():
                m = pattern.search(t)
                if m:
                    return {
                        "kpi_name": "net_zero_target_year",
                        "raw_value": int(m.group(1)),
                        "raw_unit": "year",
                        "disclosure_status": "disclosed",
                        "reporting_boundary": "full_value_chain",
                        "pdf_page_index": p["pdf_page_index"],
                        "evidence_text": t[max(0, m.start()-10):min(len(t), m.end()+40)].strip(),
                        "confidence": 0.85
                    }
        return self._missing_result("net_zero_target_year")

    def _extract_sbti(self) -> Dict[str, Any]:
        for p in self.pages:
            t = p["text"]
            if "sbti" in t.lower() or "science based targets" in t.lower():
                if "validated" in t.lower() or "approved" in t.lower() or "verified" in t.lower():
                    m = re.search(r'([^.\n]*?(?:sbti|science based targets)[^.\n]*?(?:validated|approved|verified)[^.\n]*)', t, re.I)
                    snippet = m.group(1) if m else "Validated by SBTi"
                    return {
                        "kpi_name": "sbti_target_status",
                        "raw_value": "validated",
                        "raw_unit": "status",
                        "disclosure_status": "disclosed",
                        "reporting_boundary": "group_targets",
                        "pdf_page_index": p["pdf_page_index"],
                        "evidence_text": snippet.strip(),
                        "confidence": 0.85
                    }
        return self._missing_result("sbti_target_status")

    def _extract_safety(self) -> Dict[str, Any]:
        pattern_trifr = re.compile(r'(?:trifr|total\s+recordable\s+injury\s+frequency\s+rate)[^\n\d]*?(\d+(?:[,\.]\d+)?)', re.I)
        pattern_ltif = re.compile(r'(?:ltif|lost\s+time\s+injury\s+frequency)[^\n\d]*?(\d+(?:[,\.]\d+)?)', re.I)

        for p in self.pages:
            t = p["text"]
            if "trifr" in t.lower():
                m = pattern_trifr.search(t)
                if m:
                    return {
                        "kpi_name": "occupational_safety_metric",
                        "raw_value": float(m.group(1).replace(",", ".")),
                        "raw_unit": "TRIFR",
                        "disclosure_status": "disclosed",
                        "reporting_boundary": "employees_and_contractors",
                        "pdf_page_index": p["pdf_page_index"],
                        "evidence_text": t[max(0, m.start()-20):min(len(t), m.end()+30)].strip(),
                        "confidence": 0.8
                    }
            elif "ltif" in t.lower():
                m = pattern_ltif.search(t)
                if m:
                    return {
                        "kpi_name": "occupational_safety_metric",
                        "raw_value": float(m.group(1).replace(",", ".")),
                        "raw_unit": "LTIF",
                        "disclosure_status": "disclosed",
                        "reporting_boundary": "employees_and_contractors",
                        "pdf_page_index": p["pdf_page_index"],
                        "evidence_text": t[max(0, m.start()-20):min(len(t), m.end()+30)].strip(),
                        "confidence": 0.75
                    }
        return self._missing_result("occupational_safety_metric")


# ── Method B: Direct LLM Extraction ────────────────────────────────────────

class DirectLLMExtractor:
    """Directly prompts candidate LLM with relevant section text."""

    def __init__(self, runner_client, model_id: str):
        self.client = runner_client
        self.model_id = model_id

    def extract_kpi(self, kpi_name: str, context_text: str, page_index: Optional[int] = None) -> Dict[str, Any]:
        prompt = f"""
{EXTRACTION_SCHEMA_INSTRUCTION}

TARGET KPI: {kpi_name}
REPORTING YEAR: 2025
CONTEXT TEXT (from report page {page_index if page_index is not None else 'unknown'}):
---
{context_text[:12000]}
---
"""
        res = self.client.call_inference(self.model_id, prompt)
        return self._parse_response(res, kpi_name, page_index)

    def _parse_response(self, res: Dict[str, Any], kpi_name: str, fallback_page: Optional[int]) -> Dict[str, Any]:
        raw_text = res.get("raw_text", "").strip()
        parsed = {}
        try:
            # Strip markdown code fences if model enclosed JSON in ```json ... ```
            if raw_text.startswith("```"):
                raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
                raw_text = re.sub(r'\s*```$', '', raw_text)
            parsed = json.loads(raw_text)
        except Exception as e:
            return {
                "kpi_name": kpi_name,
                "raw_value": None,
                "raw_unit": None,
                "disclosure_status": "extraction_error",
                "reporting_boundary": None,
                "pdf_page_index": fallback_page,
                "evidence_text": None,
                "confidence": 0.0,
                "error": f"JSON parse failure: {e}",
                "latency_ms": res.get("latency_ms", 0),
                "cost_usd": res.get("cost_usd", 0.0)
            }

        # Normalize page index
        p_idx = parsed.get("pdf_page_index")
        if p_idx is None:
            p_idx = fallback_page

        return {
            "kpi_name": kpi_name,
            "raw_value": parsed.get("raw_value"),
            "raw_unit": parsed.get("raw_unit"),
            "disclosure_status": parsed.get("disclosure_status", "disclosed"),
            "reporting_boundary": parsed.get("reporting_boundary"),
            "pdf_page_index": p_idx,
            "evidence_text": parsed.get("evidence_text"),
            "confidence": float(parsed.get("confidence", 0.9)),
            "latency_ms": res.get("latency_ms", 0),
            "cost_usd": res.get("cost_usd", 0.0)
        }


# ── Method C: Retrieval-Augmented Extraction (RAG) ──────────────────────────

class RAGExtractor:
    """Retrieves top-k page chunks lexical search, then prompts candidate LLM."""

    def __init__(self, runner_client, model_id: str, retriever: LexicalPageRetriever):
        self.client = runner_client
        self.model_id = model_id
        self.retriever = retriever

    def extract_kpi(self, kpi_name: str, top_k: int = 3) -> Dict[str, Any]:
        top_chunks = self.retriever.retrieve_top_k(kpi_name, top_k=top_k)

        context_blocks = []
        for c in top_chunks:
            context_blocks.append(
                f"[PDF PAGE INDEX {c['pdf_page_index']} (Printed page {c['printed_page_number']})]\n{c['text']}"
            )
        combined_context = "\n\n=== NEXT EVIDENCE PAGE ===\n\n".join(context_blocks)

        prompt = f"""
{EXTRACTION_SCHEMA_INSTRUCTION}

TARGET KPI: {kpi_name}
REPORTING YEAR: 2025

RETRIEVED CANDIDATE PAGES:
---
{combined_context[:14000]}
---
"""
        res = self.client.call_inference(self.model_id, prompt)
        top_page = top_chunks[0]["pdf_page_index"] if top_chunks else None
        return DirectLLMExtractor(self.client, self.model_id)._parse_response(res, kpi_name, top_page)
