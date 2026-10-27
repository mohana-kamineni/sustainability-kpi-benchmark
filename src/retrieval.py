"""
Lightweight Lexical Retrieval Module for RAG Extraction
Scores and retrieves top-k relevant page chunks for a given sustainability KPI query.
"""

import math
import re
from typing import Dict, List, Tuple


# KPI query mapping with targeted domain vocabulary
KPI_SEARCH_QUERIES = {
    "scope_1_ghg_emissions": [
        "Gross Scope 1 GHG emissions", "Scope 1 greenhouse gas", "direct emissions", "ton CO2eq", "ktCO2e", "E1-6"
    ],
    "scope_2_ghg_emissions": [
        "Gross Scope 2 GHG emissions", "market-based Scope 2", "location-based", "purchased electricity", "E1-6"
    ],
    "scope_3_ghg_emissions": [
        "Gross Scope 3 GHG emissions", "indirect value chain emissions", "Category 1", "Use of sold products", "E1-6"
    ],
    "total_energy_consumption": [
        "Total energy consumption", "fossil energy", "nuclear sources", "renewable energy consumption", "MWh", "GWh", "E1-5"
    ],
    "renewable_electricity_share": [
        "Share of renewable sources in total energy consumption", "renewable electricity share", "fossil-free electricity", "%", "E1-5"
    ],
    "net_zero_target_year": [
        "net-zero GHG emissions", "net zero by", "target year", "climate neutrality", "E1-4"
    ],
    "sbti_target_status": [
        "Science Based Targets initiative", "SBTi validation", "validated by SBTi", "SBTi commitment", "E1-4"
    ],
    "occupational_safety_metric": [
        "Total Recordable Injury Frequency Rate", "TRIFR", "Lost Time Injury Frequency", "LTIF", "LTIFR", "S1-5", "S1-14"
    ]
}


class LexicalPageRetriever:
    def __init__(self, pages: List[Dict]):
        """
        Initializes retriever with list of parsed page dicts:
        Each page dict must contain 'pdf_page_index', 'printed_page_number', 'text'.
        """
        self.pages = pages
        self.corpus_size = len(pages)
        self.doc_term_freqs = []
        self.doc_lengths = []
        self.doc_freqs = {}

        # Tokenize and build inverted index
        for p in pages:
            tokens = self._tokenize(p.get("text", ""))
            freqs = {}
            for t in tokens:
                freqs[t] = freqs.get(t, 0) + 1
            self.doc_term_freqs.append(freqs)
            self.doc_lengths.append(len(tokens))
            for t in freqs:
                self.doc_freqs[t] = self.doc_freqs.get(t, 0) + 1

        self.avg_doc_len = (sum(self.doc_lengths) / self.corpus_size) if self.corpus_size > 0 else 1.0

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [w.lower() for w in re.findall(r'\b[a-zA-Z0-9_\-\.]{2,}\b', text)]

    def score_bm25(self, query: str, k1: float = 1.5, b: float = 0.75) -> List[float]:
        q_tokens = self._tokenize(query)
        scores = [0.0] * self.corpus_size

        for token in q_tokens:
            if token not in self.doc_freqs:
                continue
            df = self.doc_freqs[token]
            idf = math.log((self.corpus_size - df + 0.5) / (df + 0.5) + 1.0)

            for doc_idx, term_freqs in enumerate(self.doc_term_freqs):
                tf = term_freqs.get(token, 0)
                if tf > 0:
                    d_len = self.doc_lengths[doc_idx]
                    numerator = tf * (k1 + 1.0)
                    denominator = tf + k1 * (1.0 - b + b * (d_len / self.avg_doc_len))
                    scores[doc_idx] += idf * (numerator / denominator)

        return scores

    def retrieve_top_k(self, kpi_name: str, top_k: int = 3) -> List[Dict]:
        """
        Retrieves top_k most relevant pages for the specified KPI name.
        Combines predefined search terms and computes aggregated BM25 scores.
        """
        terms = KPI_SEARCH_QUERIES.get(kpi_name, [kpi_name])
        combined_query = " ".join(terms)
        scores = self.score_bm25(combined_query)

        ranked_indices = sorted(range(self.corpus_size), key=lambda i: scores[i], reverse=True)

        results = []
        for rank, idx in enumerate(ranked_indices[:top_k]):
            p = self.pages[idx]
            results.append({
                "rank": rank + 1,
                "score": round(scores[idx], 4),
                "pdf_page_index": p["pdf_page_index"],
                "printed_page_number": p["printed_page_number"],
                "text": p["text"]
            })
        return results
