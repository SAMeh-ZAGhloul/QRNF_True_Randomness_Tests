# Raw Entropy Source Assessment: `data.bin`

**Generated:** 11 October 2026 19:52  
**Data:** 125,000 samples of 8 bit(s) (0.12 MB)  
**Tool:** `qrng_raw_entropy_tests.py`

---

## 1. Executive summary

| Suite | Outcome | Detail |
|---|---|---|
| Diagnostics | Flags: none | Shannon 7.998 / 8 bits; MCV min-entropy 7.658 / 8 bits |
| SP 800-90B | not run | skipped (fewer than 1,000,000 samples, or tools not installed) |
| NIST SP 800-22 | 12 PASS, 3 FAIL, 26 N/A (of 41 test rows); flagged: 01 Frequency (Monobit), 13 Cumulative Sums #1, 13 Cumulative Sums #2 | 1 sequences x 1,000,000 bits (weak sample) |
| Dieharder | not run | skipped (insufficient data: 0.1 MB, needs about 100 MB) |
| PractRand | 0 failure/suspicious, 0 unusual | evaluated up to 2^16 bytes |
| TestU01 | not run | skipped (insufficient data: 0.1 MB, needs about 944 MB) |

**Key findings**

- SP 800-22 flags (pass-proportion rule): 01 Frequency (Monobit), 13 Cumulative Sums #1, 13 Cumulative Sums #2. See section 6 for how likely that is by chance.

This is a raw noise-source assessment. The headline number is the SP 800-90B min-entropy; verdicts of the general statistical suites on unconditioned data are diagnostics only (raw noise is normally biased or correlated).

---

## 2. Dataset and configuration

| Item | Value |
|---|---|
| File | `data.bin` |
| Samples | 125,000 |
| Sample width | 8 bit(s), one sample per byte |
| Raw data size | 0.12 MB |
| SP 800-90B chunks | 1 x 1,000,000 samples |
| Claimed entropy | none given |
| Restart file | none |
| NIST sequence length / alpha | 1,000,000 bits / 0.01 |

---

## 3. Diagnostics

| Metric | Value |
|---|---|
| Shannon entropy / sample | 7.9984 of 8 bits (0.9998 per bit) |
| MCV min-entropy / sample (99% bound) | 7.6584 of 8 bits (0.9573 per bit) |
| Most common value frequency | 0.004464 (uniform = 0.003906) |
| Chi-square uniformity | chi2 = 275.2, p = 0.1842 |
| Longest identical-symbol run | 3 (uniform-source expectation about 3.1) |
| Stationarity (10 slices, chi-square homogeneity) | 0.2712 |
| Compression ratio zlib-9 / bz2 / lzma | 1.0004 / 1.0074 / 1.0005 (1.0 = incompressible) |

**Serial correlation (lags 1 to 16)**

| Lag | r | p-value |
|---|---|---|
| 1 | +0.00222 | 0.4325 |
| 2 | -0.00380 | 0.1794 |
| 3 | -0.00304 | 0.2828 |
| 4 | -0.00096 | 0.7343 |
| 5 | -0.00132 | 0.6401 |
| 6 | -0.00163 | 0.5651 |
| 7 | +0.00388 | 0.17 |
| 8 | -0.00105 | 0.7111 |
| 9 | -0.00170 | 0.5483 |
| 10 | +0.00246 | 0.3843 |
| 11 | +0.00181 | 0.5223 |
| 12 | +0.00092 | 0.7458 |
| 13 | +0.00323 | 0.2539 |
| 14 | +0.00043 | 0.8778 |
| 15 | +0.00297 | 0.2935 |
| 16 | +0.00084 | 0.767 |

With 16 lags the smallest p-value is expected to be about 0.06 by chance. A lag is flagged only below 6.3e-05 (0.1% family-wise level, Bonferroni). The smallest observed is 0.17.

---

## 4. NIST SP 800-90B entropy assessment

Not run: skipped (fewer than 1,000,000 samples, or tools not installed).

---

## 5. NIST SP 800-22 statistical tests

Pure-Python implementation, 1 sequences x 1,000,000 bits, alpha = 0.01. Non-overlapping Template runs one template (`000000001`), not all 148. Not the official NIST STS; cross-check before any formal claim.

| Test | Passed | Proportion | Uniformity P | Lowest p | Verdict |
|---|---|---|---|---|---|
| 01 Frequency (Monobit) | 0/1 | 0.000 | 0.437 | 0.00176 | FAIL |
| 02 Block Frequency | 1/1 | 1.000 | 0.437 | 0.2977 | PASS |
| 03 Runs | 1/1 | 1.000 | 0.437 | 0.3164 | PASS |
| 04 Longest Run of Ones | 1/1 | 1.000 | 0.437 | 0.7607 | PASS |
| 05 Binary Matrix Rank | 1/1 | 1.000 | 0.437 | 0.5198 | PASS |
| 06 DFT (Spectral) | 1/1 | 1.000 | 0.437 | 0.8328 | PASS |
| 07 Non-overlapping Template | 1/1 | 1.000 | 0.437 | 0.3277 | PASS |
| 08 Overlapping Template | 1/1 | 1.000 | 0.437 | 0.3377 | PASS |
| 09 Maurer's Universal | 1/1 | 1.000 | 0.437 | 0.4362 | PASS |
| 10 Linear Complexity | 1/1 | 1.000 | 0.437 | 0.322 | PASS |
| 11 Serial #1 | 1/1 | 1.000 | 0.437 | 0.1583 | PASS |
| 11 Serial #2 | 1/1 | 1.000 | 0.437 | 0.1769 | PASS |
| 12 Approximate Entropy | 1/1 | 1.000 | 0.437 | 0.0387 | PASS |
| 13 Cumulative Sums #1 | 0/1 | 0.000 | 0.437 | 0.003059 | FAIL |
| 13 Cumulative Sums #2 | 0/1 | 0.000 | 0.437 | 0.002711 | FAIL |
| 14 Random Excursions (8 states) | n/a | n/a | n/a | n/a | N/A (fewer than 500 cycles in every sequence) |
| 15 Random Excursions Variant (18 states) | n/a | n/a | n/a | n/a | N/A (fewer than 500 cycles in every sequence) |

### Analysis

With 1 sequences at alpha = 0.01, the acceptable pass proportion is **0.6915 to 1.0**, so at least **1 of 1** sequences must pass each test.

**Tests flagged on the pass-proportion rule:**

| Test | Failing sequences | Sequence (p-value) | P(>= that many failures | 1 seq, alpha=0.01) |
|---|---|---|---|
| 01 Frequency (Monobit) | 1 | #0 (p=0.00176) | 0.01 |
| 13 Cumulative Sums #1 | 1 | #0 (p=0.003059) | 0.01 |
| 13 Cumulative Sums #2 | 1 | #0 (p=0.002711) | 0.01 |

Across the 15 full-length test rows, the chance that at least one row shows 1 or more failures purely by chance is about **14.0%**.
The chance that at least 3 rows do is about **0.0%**.

**Overall:** 3 of 15 valid p-values are below 0.01 (expected about 0.1; naive binomial tail probability 0.000416).

**Clusters (3 or more low p-values in one sequence):**

- Sequence #0: 01 Frequency (Monobit) (p=0.00176), 13 Cumulative Sums #1 (p=0.003059), 13 Cumulative Sums #2 (p=0.002711)

Monobit and Cumulative Sums all measure ones/zeros imbalance, so they are strongly correlated: treat those as one event, not several.

**All p-values below alpha**

| Sequence | Test | p-value |
|---|---|---|
| 0 | 01 Frequency (Monobit) | 0.001760 |
| 0 | 13 Cumulative Sums #1 | 0.003059 |
| 0 | 13 Cumulative Sums #2 | 0.002711 |

On unconditioned raw data, failures here point to bias or correlation the conditioner must remove.

---

## 6. Dieharder

Not run: skipped (insufficient data: 0.1 MB, needs about 100 MB).

---

## 7. PractRand

PractRand 0.95, `-tlmin 1KB`. The final line `error reading standard input` is just end of file.

| Length | Test results | Status |
|---|---|---|
| 1 kilobyte | 6 | no anomalies |
| 2 kilobytes | 8 | no anomalies |
| 4 kilobytes | 12 | no anomalies |
| 8 kilobytes | 25 | no anomalies |
| 16 kilobytes | 30 | no anomalies |
| 32 kilobytes | 45 | no anomalies |
| 64 kilobytes | 54 | no anomalies |

About 180 test results were evaluated across checkpoints (checkpoints re-test overlapping data, so they are not independent). An isolated 'unusual' (about p = 0.01) is expected by chance; a 'suspicious' or 'FAIL' that persists at larger lengths is the real signal.

---

## 8. TestU01 (small)

Not run: skipped (insufficient data: 0.1 MB, needs about 944 MB).

---

## 9. What these results do and do not show

1. **Raw data is not expected to look full-entropy.** Bias and correlation are normal in an unconditioned noise source; the question is how much min-entropy remains, which is what SP 800-90B measures.
2. **An entropy claim needs more than one number:** the restart test, health tests at runtime, and a documented conditioning and DRBG design (SP 800-90A/B/C).
3. **Statistical tests cannot prove physical origin.** They can detect defects; a quantum origin is argued from the device physics and the 90B assessment of the raw readout.

## 10. Limitations of this run

- SP 800-90B did not run (needs at least 1,000,000 raw samples)
- NIST SP 800-22: only 1 sequences (NIST recommends about 100 at alpha = 0.01); the pass-proportion results are noisy
- PractRand only reached 2^16 bytes (its power grows with length; weak sources typically fail at MB to GB scales)

## 11. Recommended next steps

1. Collect at least 1,000,000 raw samples to enable the SP 800-90B assessment.
2. Provide at least 100 sequences x 1 Mbit (12.5 MB) for SP 800-22.
3. Dieharder needs at least ~100 MB (several GB for the full `-a` battery).
4. Provide at least 1 GB of raw data so PractRand can reach 2^30 bytes.
5. TestU01 SmallCrush needs about 1 GB of data (Crush tens of GB, BigCrush about 1 TB, rough).
6. Run `--chunks 3` or more to check that the min-entropy estimate is stable across the dataset.
7. Cross-check any flagged SP 800-22 test with the official NIST STS.
8. Repeat the assessment across operating conditions (temperature, time of day, each device/register) to show the estimate holds.

---

## Appendix: reproduction

```bash
python3 qrng_raw_entropy_tests.py data.bin --out raw_results
```

Per-tool outputs in this folder: `ea_non_iid_chunk*.txt`, `ea_iid_chunk*.txt`, `ea_restart.txt`, `nist_summary.csv`, `nist_pvalues.csv`, `dieharder_report.txt`, `practrand_report.txt`, `testu01_*_report.txt`, `raw_summary.json`.
