Here is the complete report as a single Markdown document — save it as `randomness_test_report.md`:

````markdown
# Randomness Assessment Report
**Combined PractRand v0.95 & NIST STS Results**

---

## 1. Document Information

| Item | Detail |
|---|---|
| Source files | `practrand_report.txt`, `nist_summary.csv`, `nist_pvalues.csv` |
| Generator under test | Supplied via stdin (identity / seed **not recorded**) |
| Batteries | PractRand v0.95 (core set, standard folding); NIST STS (15 test families) |
| Significance level (NIST) | α = 0.01 per sequence |
| Sequences (NIST) | 26 (indexed #0–#25) |
| PractRand coverage | 1 KiB → 256 KiB (run terminated early by stdin error) |

---

## 2. Executive Summary

| Battery | Outcome | Key observations |
|---|---|---|
| **PractRand** (core) | **No failure** | 1 low-severity anomaly (`[Low4/32]DC6-9x1Bytes-1`, p = 9.1e-3, "unusual") at 16 KiB only; did **not** recur at larger sizes. Run truncated at 256 KiB. |
| **NIST STS** | **2 of 15 test families flagged** | Binary Matrix Rank & Linear Complexity failed the pass-proportion check (24/26 = 0.9231 < 0.9315). All uniformity checks passed. Sequence **#23** shows a cluster of 4 low p-values — the single most notable signal. |
| **Overall verdict** | **INCONCLUSIVE — no failure established; screening-level result only** | Data volume was far too small for a definitive assessment. Borderline flags + sequence #23 cluster warrant follow-up before any conclusion about the generator. |

---

## 3. PractRand Results

**Configuration:** `RNG_test` v0.95 · test set = core · folding = standard (unknown format) · input = `RNG_stdin` · seed = unknown

| Data length | Tests run | Time (s) | Anomalies | Result |
|---|---:|---:|---:|---|
| 1 KiB (2^10) | 6 | 0.2 | 0 | Clean |
| 2 KiB (2^11) | 8 | 0.3 | 0 | Clean |
| 4 KiB (2^12) | 12 | 0.5 | 0 | Clean |
| 8 KiB (2^13) | 25 | 0.6 | 0 | Clean |
| 16 KiB (2^14) | 30 | 1.0 | **1** | see below |
| 32 KiB (2^15) | 45 | 1.5 | 0 | Clean |
| 64 KiB (2^16) | 54 | 2.1 | 0 | Clean |
| 128 KiB (2^17) | 64 | 2.6 | 0 | Clean |
| 256 KiB (2^18) | 70 | 3.3 | 0 | Clean |
| **Total** | **314** | **12.1** | **1** | |

**Anomaly detail (16 KiB):**

```
[Low4/32]DC6-9x1Bytes-1    R= +6.5    p = 9.1e-3    Evaluation: unusual
```
- DC6-9x1Bytes: byte-oriented correlation test over 9 consecutive bytes (low 4 bits of 32-bit words).
- Severity tier "unusual" is the **lowest** anomaly class; p = 9.1e-3 is marginal.
- The signal did **not** persist or strengthen at 32–256 KiB → consistent with an expected false positive.

**Run termination:**

```
error reading standard input
```
The data stream ended prematurely. PractRand's automatic loop normally continues to ≥ 256 MB; testing stopped at 256 KiB — roughly **three orders of magnitude below** recommended coverage. Sensitivity of this run is therefore **limited**.

---

## 4. NIST STS Results

### 4.1 Decision rules applied
- Per-sequence test passes if p ≥ α = 0.01.
- Proportion check: acceptable range = 0.99 ± 3·√(0.99·0.01/N). For **N = 26**: **[0.9315 – 1.0000]** (a test fails if ≥ 3 of 26 sequences have p < 0.01).
- Uniformity check: chi-square P ≥ 0.0001.

### 4.2 Core tests (tests 01–13)

| # | Test | n_p | Proportion | Uniformity P | Verdict |
|---|---|---:|---:|---:|---|
| 01 | Frequency (Monobit) | 26 | 0.9615 | 0.9955 | PASS |
| 02 | Block Frequency | 26 | 1.0000 | 0.7088 | PASS |
| 03 | Runs | 26 | 1.0000 | 0.2312 | PASS |
| 04 | Longest Run of Ones | 26 | 1.0000 | 0.8539 | PASS |
| 05 | Binary Matrix Rank | 26 | **0.9231** | 0.6291 | **FAIL (proportion)** |
| 06 | DFT (Spectral) | 26 | 1.0000 | 0.7851 | PASS |
| 07 | Non-overlapping Template | 26 | 0.9615 | 0.4735 | PASS |
| 08 | Overlapping Template | 26 | 0.9615 | 0.4026 | PASS |
| 09 | Maurer's Universal | 0 | — | — | **N/A** (sequences too short) |
| 10 | Linear Complexity | 26 | **0.9231** | 0.4735 | **FAIL (proportion)** |
| 11 | Serial #1 | 26 | 0.9615 | 0.2810 | PASS |
| 11 | Serial #2 | 26 | 1.0000 | 0.8539 | PASS |
| 12 | Approximate Entropy | 26 | 0.9615 | 0.3382 | PASS |
| 13 | Cumulative Sums #1 | 26 | 0.9615 | 0.6291 | PASS |
| 13 | Cumulative Sums #2 | 26 | 0.9615 | 0.6291 | PASS |

### 4.3 Random Excursions family

| Family | Variants | n_p each | Proportion | Uniformity P (min–max) | Verdict |
|---|---:|---:|---:|---:|---|
| Random Excursions | 8 | 4 | 1.000 (4/4) | 0.0127 – 0.7399 | PASS (all) |
| Random Excursions Variant | 18 | 4 | 1.000 (4/4) | 0.0669 – 0.7399 | PASS (all) |

- Applicable to only **4 of 26 sequences** (#1, #8, #13, #25 — those with sufficient zero-crossings); statistical power is minimal.
- Lowest uniformity P = 0.0127 (RE #5) — above the 0.0001 threshold → PASS.

### 4.4 Failure accounting (p < 0.01 per sequence)

| Test | Failing sequences | Count |
|---|---|---:|
| Binary Matrix Rank | #0 (0.0018), #7 (0.0004) | 2 |
| Linear Complexity | #8 (0.0035), #13 (0.0082) | 2 |
| Frequency (Monobit) | #23 (0.0015) | 1 |
| Non-overlapping Template | #23 (0.0007) | 1 |
| Overlapping Template | #21 (0.0084) | 1 |
| Serial #1 | #4 (0.0085) | 1 |
| Approximate Entropy | #12 (0.0099) | 1 |
| Cumulative Sums #1 | #23 (0.0025) | 1 |
| Cumulative Sums #2 | #23 (0.0014) | 1 |
| **Total** | | **11** |

- Expected failures at α = 0.01 across 364 core comparisons: ≈ 3.6. Observed: **11** (~3× expected).
- **4 of the 11 occur in sequence #23 alone** — under independence this cluster is extremely unlikely (~1e-5 per sequence; same-sequence statistics are correlated, but the cluster remains a genuine outlier).
- Excluding #23, the residual excess (7 failures) is within normal statistical variation.
- Overall p < 0.05 rate: 22/364 ≈ 6.0% (expected ≈ 5%) — not significant by itself.

---

## 5. Interpretation

1. **No conclusive evidence of non-randomness.** No battery produced a decisive failure; both NIST proportion flags are borderline (each driven by exactly 2/26 sequences) and all uniformity checks passed comfortably.
2. **Sequence #23 is the primary open question.** Four low p-values (two p < 0.003) on one sequence suggest a localized data issue (segment provenance, boundary/serialization artifact) or an unlucky draw. It should be isolated and re-tested.
3. **PractRand result is negligible on its own** — a single lowest-tier "unusual" flag among 314 results that vanishes at larger block sizes is typical noise — but the run's early termination means the generator was effectively untested above 256 KiB.
4. **Testing depth is the dominant limitation.** NIST used 26 short sequences (Maurer's Universal could not run; RE/REV applicable to only 4 sequences). This is a screening, not a certification-grade, evaluation.

---

## 6. Recommendations

1. **Fix the stdin feed** (the `error reading standard input` condition) and re-run PractRand uninterrupted to ≥ 2^30–2^32 bytes; verify the DC6/Low4/32 anomaly does not reappear at scale.
2. **Re-run NIST STS** with ≥ 100 sequences of ≥ 10^6 bits each — this enables Maurer's Universal, applies RE/REV to all sequences, and makes proportion statistics meaningful.
3. **Investigate sequence #23**: check its position in the data stream, re-test it in isolation, and look for duplicated or structured content in that segment.
4. Monitor the two flagged families (**Binary Matrix Rank, Linear Complexity**) specifically in the re-run.
5. If anomalies persist at scale, escalate to additional batteries (Dieharder, TestU01 BigCrush) and review generator design.

---

## Appendix A — NIST proportion bound derivation
For N = 26, α = 0.01: 0.99 ± 3·√(0.99 × 0.01 / 26) = 0.99 ± 0.0585 → **[0.9315, 1.0000]**.
Hence 25/26 (0.9615) passes and 24/26 (0.9231) fails.

## Appendix B — Watchlist: all core p-values < 0.05

| Seq | Test | p | Status |
|---|---|---:|---|
| #0 | 05 Binary Matrix Rank | 0.0018 | below α |
| #4 | 11 Serial #1 | 0.0085 | below α |
| #4 | 08 Overlapping Template | 0.0141 | low |
| #4 | 11 Serial #2 | 0.0318 | low |
| #5 | 03 Runs | 0.0463 | low |
| #7 | 05 Binary Matrix Rank | 0.0004 | below α |
| #8 | 10 Linear Complexity | 0.0035 | below α |
| #9 | 10 Linear Complexity | 0.0468 | low |
| #11 | 06 DFT (Spectral) | 0.0485 | low |
| #12 | 12 Approximate Entropy | 0.0099 | below α |
| #13 | 10 Linear Complexity | 0.0082 | below α |
| #16 | 08 Overlapping Template | 0.0439 | low |
| #20 | 07 Non-overlapping Template | 0.0177 | low |
| #20 | 10 Linear Complexity | 0.0204 | low |
| #21 | 03 Runs | 0.0119 | low |
| #21 | 08 Overlapping Template | 0.0084 | below α |
| #21 | 12 Approximate Entropy | 0.0334 | low |
| #23 | 01 Frequency (Monobit) | 0.0015 | below α |
| #23 | 07 Non-overlapping Template | 0.0007 | below α |
| #23 | 13 Cumulative Sums #1 | 0.0025 | below α |
| #23 | 13 Cumulative Sums #2 | 0.0014 | below α |
| #25 | 10 Linear Complexity | 0.0253 | low |

No RE/REV p-value fell below 0.05 (family minimum: 0.061, seq #13).

## Appendix C — Data completeness notes
- `nist_pvalues.csv` is truncated mid-way through sequence #25 (Random Excursions Variant section); aggregate statistics in `nist_summary.csv` are complete and unaffected.
- PractRand recorded `seed = unknown` and `folding = standard (unknown format)` — input treated as a raw byte stream; generator identity not logged, limiting reproducibility.

---

*End of report.*
````

**Highlights of what the report concludes:** PractRand found nothing conclusive (one lowest-tier "unusual" anomaly at 16 KiB that disappeared, but the run died early at 256 KiB via a stdin error); NIST flagged Binary Matrix Rank and Linear Complexity on borderline pass-proportions (24/26), all uniformity checks passed, and sequence #23 — with 4 p-values below 0.01 — is the one item genuinely worth investigating. Overall verdict: inconclusive screening result, no established failure, re-test with much more data recommended.


