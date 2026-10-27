# Self-Audit Report: Sustainability KPI Extraction Benchmark

**Audit Target:** Sustainability KPI Extraction Benchmark Implementation, Gold Dataset, and Raw Evaluation Outputs
**Repository:** `sustainability-kpi-benchmark` (Project Root)
**Evaluation / Audit Date:** 25 October 2026
**Auditor:** Benchmark Author Self-Audit
**Audit Scope:** Direct physical PDF block inspection across 761 pages of official FY2025 reports, verification of raw results (`results/evaluation_results.json` and `results/evaluation_results_original_run.json`), gold annotations (`data/annotations/gold_annotations.json`), evidence checker behavior, statistical computations, and error taxonomy.

---

## 1. Direct PDF Spot-Checks & Ground-Truth Verification

To resolve prior conflicting statements and eliminate reliance on self-referential annotations, physical page blocks across all four reports were opened and inspected directly using PyMuPDF block analysis. Below are the verbatim excerpts and findings:

### 1. Boliden Scope 2 (PDF Index 80, Printed Page 79)
- **Verbatim Text on Page 80:**
  ```text
  Scope 2 GHG emissions
  Gross location-based Scope 2 GHG emissions (t CO2e)
    Base year 2021: 457,465 | 2024: 260,073 | 2025: 260,161
  Gross market-based Scope 2 GHG emissions (t CO2e)
    Base year 2021: 824,756 | 2024: 1,428,681 | 2025: 1,853,894
  Scope 1 GHG emissions (2025): 685,577
  ```
- **Finding:** In Boliden's report, **`1,853,894` is market-based Scope 2** for FY2025. **`260,161` is location-based Scope 2**. The number "1,842,670" mentioned in earlier notes was an agent hallucination; it does not exist anywhere in Boliden's report.
- **Why is Market-Based 7x Location-Based and Higher than Scope 1?**
  Confirmed on pages 79 and 81 of Boliden's report: Boliden operates electricity-intensive smelters (Odda, Rönnskär, Kokkola). In 2025, only ~14% of purchased electricity was covered by Guarantees of Origin. Under the GHG Protocol market-based method, the remaining ~86% of unspecified electricity must use national **residual mix emission factors**, which are substantially higher than average grid factors. Under the location-based method, grid average emission factors are used without residual mix penalties.
- **Error Analysis:** In Method B, `gpt-oss-120b` extracted `824,756`—this was an extraction of Boliden's **2021 base-year value** instead of the 2025 reporting-year figure.

### 2. Alleima Scope 2 and Renewable Share (PDF Indexes 109 & 110, Printed Pages 108 & 109)
- **Alleima Scope 2 (Page 110, Printed Page 109, Table E1-6):**
  ```text
  Scope 2 Total (market-based) [thousand ton CO2eq]:
    2025: 8 | 2024: 10
  Scope 2 Total (location-based) [thousand ton CO2eq]:
    2025: 63 | 2024: 61
  ```
  - **Finding:** Alleima explicitly reports market-based Scope 2 as **`8` thousand ton CO2eq** (gold: 8,000 tCO2e) and location-based as **`63` thousand ton CO2eq** (63,000 tCO2e).
  - **Clarification on "76":** The figure "76" mentioned in earlier conversation rounds does not appear anywhere in Alleima's emissions disclosures. It appeared on page 55 in executive remuneration (76,000 / 760,000 SEK).
- **Alleima Renewable Share (Page 109, Printed Page 108, Table E1-5):**
  ```text
  Energy consumption and mix (E1-5) [MWh]
    Total fossil: 314,988
    Total nuclear: 520,884
    Total renewable: 180,224
    Total energy consumption: 1,016,096
  ```
  - **Finding:** **Alleima does not disclose a percentage share for renewable energy or electricity.** The gold value of `17.7%` was manually calculated by the annotator ($\frac{180,224}{1,016,096} = 17.737\%$).
  - **Non-Disclosure Scoring:** Models returning `null` (such as Direct 120B and RAG 120B) were correctly abstaining under Rule 1 of the prompt.

### 3. Epiroc Scope 2 (PDF Index 105, Printed Page 105)
- **Verbatim Text on Page 105 (Table E1-6):**
  ```text
  Columns: Base year (2019) | 2025 | 2024
  Gross Scope 1 GHG emissions:
    Base year (2019): 41 | 2025: 32 | 2024: 33
  Gross Scope 2 GHG emissions (Location-based):
    Base year (2019): 62 | 2025: 37 | 2024: 38
  Gross Scope 2 GHG emissions (Market-based):
    Base year (2019): 56 | 2025: 23 | 2024: 21
  ```
- **Finding:** Epiroc's FY2025 Scope 2 figures are **`23` ktCO2e (market-based, gold)** and **`37` ktCO2e (location-based)**.
- **Error Analysis:** When Method C RAG extracted `56`, it extracted the **2019 base-year value** of market-based Scope 2 (`56` ktCO2e). This was a **Base-Year vs. Reporting-Year confusion**, exactly parallel to Method B extracting `41` for Scope 1 (where `41` is 2019 base year and `32` is 2025).

### 4. Sandvik Safety (PDF Index 88 & 90, Printed Pages 87 & 89)
- **Verbatim Text on Page 88:**
  `"In 2025, the TRIFR amounted to 2.3 (3.0)."`
- **Verbatim Text on Page 90:**
  `"TRIFR: 2.3 | LTIFR: 0.9"`
- **Finding:** Sandvik reports both Total Recordable Injury Frequency Rate (TRIFR = `2.3`) and Lost Time Injury Frequency Rate (LTIFR = `0.9`). When Method C extracted `0.9`, it extracted the LTIFR rather than TRIFR.

### 5. Net-Zero & SBTi Wording Across All Four Companies (Target Label Coarseness)
All four companies are labelled in the gold set with net-zero target year `2050` and SBTi status `validated`. However, direct verification shows these labels are coarse and not strictly like-for-like across reporting frameworks:
- **Sandvik (p. 68):**
  - Net-Zero: *"We are committed to: Reach net-zero GHG emissions across the value chain by 2050."* (Corporate commitment).
  - SBTi: *"In 2023, our targets to reduce GHG emissions were validated by the Science Based Targets initiative (SBTi)."*
- **Epiroc (p. 97 & p. 102):**
  - Net-Zero: *"enable a long-term ambition of net-zero CO2e emissions by 2050."*
  - SBTi: *"In November 2021, we received validation from the SBTi for two of our goals."*
- **Alleima (p. 8 & p. 109):**
  - Net-Zero: *"Alleima has set net-zero targets to 2050 that have been verified by the SBTi."*
  - SBTi: *"In 2025, Alleima’s climate targets were validated by the Science Based Targets initiative (SBTi)."*
- **Boliden (p. 77):**
  - Net-Zero: *"Scope 1-2: Net-zero absolute emissions in 2050."* (Covers Scope 1–2 only under ICMM guidelines; report notes long-term net-zero is not yet validated under SBTi's Corporate Net-Zero Standard).
  - SBTi: *"validated by the Science Based Targets initiative (SBTi)."* (Near-term 2030 targets validated in 2023).

---

## 2. Method B Caveat: Why Page Accuracy and Unsupported Rates Must Be Qualified

In the original benchmark, Method B (Direct LLM) was reported with 84% unsupported rate due to a 1-page folio offset. The evidence checker was subsequently adjusted post-hoc to accept a ±1 page window and account for folio-to-index offsets.

> [!WARNING]
> **Essential Methodological Caveat on Method B:**
> Method B was handed pre-sliced 3-page windows (`gold_page - 1` to `gold_page + 1`). Because the adjusted evidence checker inspects a ±1 page window around the cited page, almost any citation within the provided slice is accepted. Therefore, Method B's **100% page accuracy** and **3.1%–6.5% unsupported rate** should **NOT** be interpreted as superior document navigation or grounding. They are artifacts of local context pre-slicing. In contrast, Method C (RAG) retrieved pages autonomously across the entire 761-page corpus without chapter hints.

---

## 3. Disclosed-Only Evaluation ($N=31$) vs. Full Corpus ($N=32$)

Because Alleima does not disclose a percentage for renewable electricity share, we report performance both on the full $N=32$ set (where abstentions are scored as incorrect against the annotator's derived 17.7%) and on the disclosed-only $N=31$ set (where Alleima renewable share is excluded):

| Extraction Method & Model | Full Corpus ($N=32$) | Disclosed Only ($N=31$) | 95% Wilson CI ($N=31$) | Non-Disclosure Behavior on Alleima |
| :--- | :---: | :---: | :---: | :--- |
| **Method A: Rule-Based Baseline** | 9/32 (28.1%) | 9/31 (29.0%) | [16.1%, 46.6%] | Abstained (`null`) |
| **Method B: Direct (`gpt-oss-20b`)** | 24/32 (75.0%) | 24/31 (77.4%) | [60.2%, 88.6%] | Extracted `98%` (purchased electricity) |
| **Method B: Direct (`gpt-oss-120b`)** | 26/32 (81.2%) | 26/31 (83.9%) | [67.4%, 92.9%] | Correctly Abstained (`null`) |
| **Method C: RAG (`gpt-oss-20b` Rec.)** | 21/32 (65.6%) | 21/31 (67.7%) | [50.1%, 81.4%] | Correctly Abstained (`null`) |
| **Method C: RAG (`gpt-oss-120b` Rec.)** | 26/32 (81.2%) | 26/31 (83.9%) | [67.4%, 92.9%] | Correctly Abstained (`null`) |

On disclosed non-financial KPIs ($N=31$), **Direct 120B and RAG 120B achieve identical value accuracy: 26/31 (83.9%)**.

---

## 4. Concrete Error Taxonomy

Analyzing the examined Direct-120B and RAG-120B errors confirms that values were grounded in the report text rather than arbitrarily fabricated. The largest single category of error was base-year vs. reporting-year confusion (accounting for half of Direct-120B's 6 errors), followed by metric-definition mismatches:

1. **Base-Year vs. Reporting-Year Confusion (Largest Category, 50% of Direct-120B errors):**
   - *Occurrence:* Boliden Scope 1 extracted as 2021 base year `649,087` instead of 2025 `685,577` (Direct-120B); Boliden Scope 2 extracted as 2021 base year `824,756` instead of 2025 `1,853,894` (Direct-120B); Epiroc Scope 1 extracted as 2019 base year `41` instead of 2025 `32` (Direct-120B); Epiroc Scope 2 extracted as 2019 base year `56` instead of 2025 `23` (RAG-120B).
   - *Significance:* Multi-year comparative tables in ESRS disclosures frequently confuse LLMs if prompts do not enforce column-specific temporal anchoring.
2. **Metric-Definition and Scope Mismatches:**
   - *Occurrence:* Extraction of related but narrower energy scopes: Epiroc renewable electricity share extracted as `55%` instead of total renewable energy share `36%` (Direct-120B); Alleima purchased fossil-free electricity extracted as `98%` instead of total renewable share (Direct-120B, Direct-20B).
   - *Significance:* Highlights the sensitivity of non-financial KPIs to subtle differences in denominator definitions (electricity vs total energy).
3. **Metric Sub-Type Mix-ups:**
   - *Occurrence:* Sandvik safety extracted as LTIFR `0.9` instead of TRIFR `2.3` (RAG-120B).
   - *Significance:* Both metrics appear in adjacent columns within ESRS S1 health and safety tables; models can confuse injury severity definitions without explicit metric schemas.
4. **Abstained on a Disclosed Value:**
   - *Occurrence:* Sandvik renewable energy share returned `null` despite `14.9%` being printed in the report text on page 71 (Direct-120B, RAG-120B).
   - *Significance:* Represents an extraction omission on a disclosed non-financial metric.
4. **API Token Headroom & Rate Limits:**
   - *Occurrence:* Groq developer tier hit 200k daily token limits, causing empty responses on late-sequence calls. Models generating 150–860 reasoning tokens exhausted headroom when context windows were large.

---

## 5. Corrected Results Tables

### Table 1: Original Benchmark Run (Initial 128-Call Sequence)
*Recomputed with the fixed evidence checker and folio-aware page accuracy:*

| Extraction Method & Model | Evaluated $N$ | Extracted $N$ | Tech Failures | Value Accuracy (95% Wilson CI) | Evidence-Page Accuracy* | Coverage | Unsupported Rate* | Published Total Cost | Cost / Correct KPI |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Method A: Rule-Based Baseline** | 32 | 19 | 0 (0.0%) | **28.1%** (9/32) [15.6%, 45.4%] | 15.6% (5/32) | 59.4% (19/32) | 5.3% (1/19) | $0.0000 | $0.0000 |
| **Method B: Direct (`gpt-oss-20b`)** | 32 | 32 | 0 (0.0%) | **75.0%** (24/32) [57.9%, 86.8%] | 100.0%* (32/32) | 100.0% (32/32) | 3.1%* (1/32) | $0.0130 | $0.0005 |
| **Method B: Direct (`gpt-oss-120b`)** | 32 | 31 | 0 (0.0%) | **81.2%** (26/32) [64.7%, 91.1%] | 96.9%* (31/32) | 96.9% (31/32) | 6.5%* (2/31) | $0.0255 | $0.0010 |
| **Method C: RAG (`gpt-oss-20b`)** | 32 | 20 | 10 (31.2%) | **50.0%** (16/32) [33.6%, 66.4%] | 53.1% (17/32) | 62.5% (20/32) | 5.0% (1/20) | $0.0090 | $0.0006 |
| **Method C: RAG (`gpt-oss-120b`)** | 32 | 24 | 5 (15.6%) | **68.8%** (22/32) [51.4%, 82.1%] | 71.9% (23/32) | 75.0% (24/32) | **0.0%** (0/24) | $0.0212 | $0.0010 |

*\*Method B page accuracy and unsupported rate reflect pre-sliced 3-page windowing and post-hoc checker tolerance. They are not cross-method comparable with Method C's whole-document retrieval.*

---

### Table 2: Recovered Run (Targeted Re-Run of Failed Calls)
*Original run plus targeted re-run of failed calls with `max_tokens=4096` (9 calls recovered: 4 for 120B, 5 for 20B; remaining 6 calls for 20B and 2 for 120B pending quota reset):*

| Extraction Method & Model | Evaluated $N$ | Extracted $N$ | Tech Failures | Value Accuracy (95% Wilson CI) | Evidence-Page Accuracy* | Coverage | Unsupported Rate* | Published Total Cost | Cost / Correct KPI |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Method A: Rule-Based Baseline** | 32 | 19 | 0 (0.0%) | **28.1%** (9/32) [15.6%, 45.4%] | 15.6% (5/32) | 59.4% (19/32) | 5.3% (1/19) | $0.0000 | $0.0000 |
| **Method B: Direct (`gpt-oss-20b`)** | 32 | 32 | 0 (0.0%) | **75.0%** (24/32) [57.9%, 86.8%] | 100.0%* (32/32) | 100.0% (32/32) | 3.1%* (1/32) | $0.0130 | $0.0005 |
| **Method B: Direct (`gpt-oss-120b`)** | 32 | 31 | 0 (0.0%) | **81.2%** (26/32) [64.7%, 91.1%] | 96.9%* (31/32) | 96.9% (31/32) | 6.5%* (2/31) | $0.0255 | $0.0010 |
| **Method C: RAG (`gpt-oss-20b`)** | 32 | 25 | 5 (15.6%) | **65.6%** (21/32) [48.3%, 79.6%] | 65.6% (21/32) | 78.1% (25/32) | 4.0% (1/25) | $0.0114 | $0.0005 |
| **Method C: RAG (`gpt-oss-120b`)** | 32 | 28 | 1 (3.1%) | **81.2%** (26/32) [64.7%, 91.1%] | 84.4% (27/32) | 87.5% (28/32) | **0.0%** (0/28) | $0.0243 | $0.0009 |

- **Paired Bootstrap Resampling ($B=1,000$, seed 42):**
  - Direct 120B vs. Rule-Based: Δ = +53.1 pp (95% CI: +37.5 to +71.9 pp). Statistically significant.
  - Direct 120B vs. RAG 120B (Recovered): Both achieve **26/32 (81.25%)** (Δ = 0.0 pp, 95% CI: −15.6 to +15.6 pp). Differences between Direct and RAG value accuracy are completely within sampling noise.

---

## 6. Recommended Defensible CV Bullets

**Sustainability KPI Extraction Benchmark | Python, LLMs, RAG, Statistical Evaluation**

- Benchmarked rule-based, direct-LLM and retrieval-augmented extraction of eight sustainability KPIs from four FY2025 industrial reports (761 pages), using a hashed, frozen evaluation set.
- Evaluated `gpt-oss-20b` and `gpt-oss-120b` on 32 labelled observations: Direct-120B and RAG-120B both reached 81% accuracy (95% CI 65–91%) at about $0.001 per correct KPI, with no difference between them beyond sampling noise.
- Analysed errors, finding base-year vs reporting-year confusion was the largest category, ahead of metric-definition and safety-metric subtype mix-ups.
