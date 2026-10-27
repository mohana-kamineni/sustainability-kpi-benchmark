# Sustainability KPI Extraction Benchmark

**Project Title:** *Benchmarking LLM-Based Sustainability KPI Extraction from Industrial Reports*
**Research Question:** *How accurately and cost-effectively can different extraction methods retrieve sustainability KPIs from industrial corporate sustainability reports, with evidence traceable to the original source?*

---

## 1. Overview & Research Scope

This repository provides an end-to-end, reproducible research benchmark comparing three distinct extraction paradigms for non-financial disclosures across leading Nordic industrial peers:

- **Method A: Rule-Based Baseline** (Regex, heuristic table scanning, pattern matching, explicit missing handling)
- **Method B: Direct LLM Extraction** (`openai/gpt-oss-20b` and `openai/gpt-oss-120b` via Groq)
- **Method C: Retrieval-Augmented Extraction (RAG)** (Lexical BM25 page chunk retrieval + LLM extraction)

### Corpus (FY2025 Reports)
The benchmark evaluates 32 gold-standard observations across four major industrial companies reporting under CSRD / ESRS (European Sustainability Reporting Standards):
1. **Sandvik AB** (180 pages, FY2025 Annual Report with integrated Sustainability Statement)
2. **Epiroc AB** (241 pages, FY2025 Annual and Sustainability Report)
3. **Alleima AB** (144 pages, FY2025 Annual Report)
4. **Boliden AB** (196 pages, FY2025 Annual and Sustainability Report)

### 8 Evaluated KPI Categories
1. **Scope 1 GHG Emissions** (Gross direct emissions in tonnes CO2e)
2. **Scope 2 GHG Emissions** (Market-based indirect emissions in tonnes CO2e; location-based recorded as secondary boundary)
3. **Scope 3 GHG Emissions** (Total gross indirect value-chain emissions in tonnes CO2e)
4. **Total Energy Consumption** (MWh across fossil, nuclear, and renewable sources)
5. **Renewable Electricity / Energy Share** (% share of renewable sources in energy mix)
6. **Net-Zero Target Year** (Target commitment year, e.g. 2050)
7. **SBTi Target Status** (Validation or commitment status under Science Based Targets initiative)
8. **Occupational Safety Metric** (TRIFR or LTIF frequency rate per million hours worked)

> [!NOTE]
> **Target Label Coarseness:** All four companies are labelled with net-zero target year `2050` and SBTi status `validated` as categorical benchmark targets, but these disclosures are not strictly like-for-like: Boliden's 2050 net-zero target covers only Scope 1–2 under ICMM guidelines, and only its near-term 2030 targets are SBTi-validated (its long-term target is not yet validated under SBTi's Corporate Net-Zero Standard). In contrast, Sandvik's net-zero is an overarching corporate commitment with SBTi validation dating from 2023, while Epiroc and Alleima maintain verified full value-chain targets.

---

## 2. Methodology & Deterministic Verification

### Deterministic Unsupported-Value Check
Unlike pipelines that rely on an LLM as an ungrounded evaluator, this benchmark implements an automated, deterministic verification check (`src/evidence_check.py`):
- Locates the cited PDF page by index.
- Normalizes numeric representations (handling spaces, comma groupings, European decimals).
- Checks whether the reported candidate value and associated unit appear in the text across a $\pm 1$ page window (adjusted post-hoc to account for report folio-to-index offsets).
- Classifies candidate evidence as `supported`, `ambiguous`, or `not_found`.
- *Note:* Lexical checking verifies string presence on the cited page; it does not constitute semantic validation of metric or temporal attribution.

### Statistical Methodology
- **Proportion Uncertainty:** 95% Wilson Score confidence intervals for accuracy, coverage, and failure rates.
- **Paired Comparisons:** Non-parametric paired bootstrap resampling (1,000 iterations, seed 42) to estimate empirical delta accuracy ($Acc_B - Acc_A$) across identical company-KPI observations.

---

## 3. Setup & Installation

### Requirements
- Python >= 3.10
- Dependencies: `PyMuPDF`, `openai`, `numpy`, `scipy`, `pydantic`, `pytest`

```bash
git clone <repo_url>
cd sustainability-kpi-benchmark
pip install -r requirements.txt
```

### Downloading Source Reports
The four official annual and sustainability reports (761 pages total) can be downloaded directly from their respective investor relations portals into `data/raw_reports/` using the automated script:

```bash
python scripts/download_reports.py
```

Alternatively, download them manually from the official investor relations portals:
- **Sandvik AB (FY2025):** [`entire-en-svk-ar25.pdf`](https://www.annualreport.sandvik/en/2025/_assets/downloads/entire-en-svk-ar25.pdf) -> `data/raw_reports/sandvik_annual_report_2025.pdf`
- **Epiroc AB (FY2025):** [`annual-and-sustainability-report-2025.pdf`](https://reports.epirocgroup.com/media/ld4los1m/annual-and-sustainability-report-2025.pdf) -> `data/raw_reports/epiroc_annual_and_sustainability_report_2025.pdf`
- **Alleima AB (FY2025):** [`alleima-annual-report-2025.pdf`](https://www.alleima.com/siteassets/documents/ir/2025-ar/alleima-annual-report-2025.pdf) -> `data/raw_reports/alleima_annual_report_2025.pdf`
- **Boliden AB (FY2025):** [`Boliden_AR_2025_ENG_Print.pdf`](https://investors.boliden.com/sites/boliden-ir/files/pr/Boliden_AR_2025_ENG_Print.pdf) -> `data/raw_reports/boliden_annual_and_sustainability_report_2025.pdf`

Full publication metadata, page counts, and chapter ranges are catalogued in `data/source_manifest.json`.

### Environment Configuration
Set your Groq API key:
```powershell
$env:GROQ_API_KEY = "your-api-key-here"
```

---

## 4. Running Tests & Reproducing Experiments

### Run the Unit & Regression Test Suite
Runs offline without API calls using deterministic mocks (27 tests):
```bash
python -m pytest tests/
```

### Run Full Benchmark Evaluation Pipeline
```bash
# Offline verification mode (zero API calls)
python run_benchmark_evaluation.py --mock

# Live inference mode (Groq API candidate models)
python run_benchmark_evaluation.py
```

Outputs are automatically generated in `results/evaluation_results.json`.

---

## 5. Benchmark Self-Audit & Empirical Results

A forensic **Self-Audit** ([`audit_report.md`](audit_report.md)) verified all 32 gold-standard records against official source PDFs, resolved folio-to-index offsets in Method B, and analyzed API rate limits. Both the original evaluation run and the recovered run (re-running failed calls with `max_tokens=4096`) are reported below:

### Empirical Performance Summary (Recovered Run)

| Extraction Method & Model | Evaluated $N$ | Value Accuracy (95% Wilson CI) | Evidence-Page Accuracy* | Coverage | Unsupported Rate* | Cost / Correct KPI | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Method A: Rule-Based Baseline** | 32 | **28.1%** [15.6%, 45.4%] | 15.6% [6.9%, 31.8%] | 59.4% | 5.3% | $0.0000 | Baseline |
| **Method B: Direct (`gpt-oss-20b`)** | 32 | **75.0%** [57.9%, 86.8%] | **100.0%** [89.3%, 100.0%]* | 100.0% | 3.1%* | $0.0005 | Zero-Shot |
| **Method B: Direct (`gpt-oss-120b`)** | 32 | **81.2%** [64.7%, 91.1%] | **96.9%** [84.3%, 99.5%]* | 96.9% | 6.5%* | $0.0010 | Zero-Shot |
| **Method C: RAG (`gpt-oss-20b`)** | 32 | **65.6%** [48.3%, 79.6%] | 65.6% [48.3%, 79.6%] | 78.1% | 4.0% | $0.0005 | Recovered |
| **Method C: RAG (`gpt-oss-120b`)** | 32 | **81.2%** [64.7%, 91.1%] | 84.4% [68.2%, 93.1%] | 87.5% | **0.0%** | $0.0009 | Recovered |

*\*Methodological Caveat on Method B: Method B was provided pre-sliced 3-page windows (`gold-1` to `gold+1`). Because the adjusted evidence checker accepts citations in a $\pm 1$ page window, almost any citation within the provided slice is accepted. Method B's 100% page accuracy and low unsupported rate reflect this pre-slicing window rather than autonomous document navigation.*

### Key Findings
- **Accuracy Parity Between Architectures:** Direct prompting and retrieval-augmented extraction (RAG) using `gpt-oss-120b` both reached **81.2% value accuracy (26/32)** (95% Wilson CI: [64.7%, 91.1%]). Paired bootstrap resampling ($B=1,000$, seed 42) indicates $\Delta = 0.0\%$ (95% CI: $[-15.6\%, +15.6\%]$), meaning any accuracy difference is completely within sampling noise.
- **Coverage vs. Autonomous Navigation:** Direct prompting on pre-sliced chapter text achieved 96.9% coverage (31/32) without retrieval misses. RAG operated autonomously over the entire 761-page corpus without chapter hints, achieving 87.5% coverage (28/32).
- **Non-Comparability of Evidence & Page Metrics Across Methods:** Direct prompting (Method B) was provided pre-sliced 3-page windows (`gold-1` to `gold+1`), and the evidence checker accepts a $\pm 1$ page window. As a result, Method B citations within its slice are inherently accepted (100% page accuracy, 3.1–6.5% unsupported rate). These figures cannot be meaningfully compared to Method C (RAG), which had to identify and retrieve pages across the full 761-page corpus.
- **Disclosed-Only Performance ($N=31$):** Alleima discloses renewable energy in MWh (`180,224` MWh of `1,016,096` MWh) but does not print a percentage share. Both Direct 120B and RAG 120B correctly abstained (`null`). On disclosed non-financial KPIs ($N=31$), both models achieve identical value accuracy: **26/31 (83.9%)**.
- **Error Taxonomy:** Among the examined Direct-120B errors, values were grounded in the report text rather than arbitrarily fabricated. The largest single category of error was base-year vs. reporting-year confusion (accounting for half of Direct-120B's 6 errors), followed by metric-definition mismatches:
  1. *Base-Year vs. Reporting-Year Confusion (Largest Category, ~50% of Direct-120B errors):* Multi-year comparative tables caused models to select historical baseline figures (e.g. Boliden Scope 1 extracted as 2021 baseline `649,087` instead of 2025 `685,577`; Boliden Scope 2 extracted as 2021 baseline `824,756` instead of 2025 `1,853,894`; Epiroc Scope 1 extracted as 2019 baseline `41` instead of 2025 `32`; Epiroc Scope 2 extracted as 2019 baseline `56` instead of 2025 `23`).
  2. *Metric-Definition and Scope Mismatches:* Models extracted related but narrower sub-scopes (e.g. Epiroc renewable electricity share `55%` instead of total energy mix `36%`; Alleima purchased fossil-free electricity `98%`).
  3. *Metric Sub-Type Mix-ups:* Adjacent metric confusion in multi-column tables (e.g. Sandvik LTIFR `0.9` instead of TRIFR `2.3`).

---

## 6. Post-Hoc Changes & Methodological Dispositions

To maintain complete research transparency, the following changes were made after inspecting initial benchmark execution:

1. **Evidence Checker Adjustment:** The initial checker flagged an 84% unsupported rate for Method B due to printed-page to PDF-index offsets (+1 page in Boliden and Alleima) and multi-page tables. The checker was adjusted post-hoc to evaluate a $\pm 1$ page window and resolve printed folios. Because Method B received pre-sliced 3-page windows, this relaxed checker accepts nearly all citations within the slice; hence, page accuracy and unsupported rates are not cross-method comparable.
2. **Targeted Re-Run of Rate-Limited Calls:** The initial live run suffered 15 empty completions on Method C caused by Groq API developer-tier daily token limits (429 TPD) combined with reasoning tokens (150–860 tokens). A targeted re-run with `max_tokens=4096` and polite delays recovered 9 calls (5 for 20B, 4 for 120B) before hitting daily quota. Both the initial run and the recovered run are preserved and reported side-by-side.
3. **Status of Remaining Failed Calls:** 6 calls remain unrecovered (5 for RAG-20B, 1 for RAG-120B). With Direct 120B and RAG 120B tied at 26/32 (81.25%), resolving the single remaining 120B call would yield at most 27/32 (84.4%), which is well within the 95% bootstrap confidence interval.
4. **Gold Set Grounding & Target Coarseness Dispositions:** Direct PDF inspection established that Alleima's 17.7% renewable energy share was derived by the annotator from raw MWh figures (`180,224 / 1,016,096`) and is not printed in the report. Models that abstained (`null`) were correctly adhering to prompt instructions. Results are reported for both full ($N=32$) and disclosed-only ($N=31$) sets. Additionally, target labels (net-zero year 2050, SBTi validated) are coarse categorical classifications; across the four companies they represent differing operational scopes (e.g., Boliden covers Scope 1–2 under ICMM, near-term SBTi validated, while Sandvik, Epiroc, and Alleima have verified full value-chain targets).
5. **Manifest Regeneration & Line-Ending Normalization:** The cryptographic benchmark manifest (`data/benchmark_manifest.json`) was regenerated after final line-ending normalization and whitespace cleanup, accompanied by a `.gitattributes` configuration (`* text=auto eol=lf`, `data/** -text`, `*.json -text`) to guarantee byte-level SHA-256 integrity across Windows and Unix platforms.

---

## 7. Recommended CV Bullet Points

**Sustainability KPI Extraction Benchmark | Python, LLMs, RAG, Statistical Evaluation**

- Benchmarked rule-based, direct-LLM and retrieval-augmented extraction of eight sustainability KPIs from four FY2025 industrial reports (761 pages), using a hashed, frozen evaluation set.
- Evaluated `gpt-oss-20b` and `gpt-oss-120b` on 32 labelled observations: Direct-120B and RAG-120B both reached 81% accuracy (95% CI 65–91%) at about $0.001 per correct KPI, with no difference between them beyond sampling noise.
- Analysed errors, finding base-year vs reporting-year confusion was the largest category, ahead of metric-definition and safety-metric subtype mix-ups.

---

## 8. Repository Structure

```text
sustainability-kpi-benchmark/
├── .gitattributes
├── .gitignore
├── README.md
├── audit_report.md
├── report.md
├── pyproject.toml
├── requirements.txt
├── config/
│   └── benchmark_config.json
├── data/
│   ├── source_manifest.json
│   ├── benchmark_manifest.json
│   └── annotations/
│       ├── gold_annotations.json
│       └── gold_annotations.jsonl
├── scripts/
│   └── download_reports.py
├── src/
│   ├── __init__.py
│   ├── pdf_parser.py
│   ├── retrieval.py
│   ├── normalisation.py
│   ├── evidence_check.py
│   ├── inference.py
│   ├── extraction.py
│   ├── evaluation.py
│   └── manifest.py
├── tests/
│   ├── test_audit_invariants.py
│   ├── test_normalisation.py
│   ├── test_evidence_check.py
│   ├── test_pdf_parser.py
│   ├── test_inference_and_cost.py
│   └── test_regression.py
├── results/
│   ├── evaluation_results.json
│   ├── evaluation_results_original_run.json
│   └── evaluation_results_recovered.json
└── run_benchmark_evaluation.py
```
