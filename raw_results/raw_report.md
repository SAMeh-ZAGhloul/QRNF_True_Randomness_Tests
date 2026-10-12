# Raw Entropy Source Assessment: `data.bin`

**Generated:** 12 October 2026 03:47  
**Data:** 1,000,000 samples of 1 bit(s) (0.12 MB)  
**Tool:** `qrng_raw_entropy_tests.py`

---

## 1. Executive summary

| Suite | Outcome | Detail |
|---|---|---|
| Diagnostics | Flags: none | Shannon 1.000 / 1 bits; MCV min-entropy 0.992 / 1 bits |
| SP 800-90B | **0.8717 bits/sample** (0.8717 per bit) | 1 x 1,000,000 samples, non-IID track, restart test NOT run |
| NIST SP 800-22 | 12 PASS, 3 FAIL, 26 N/A (of 41 test rows); flagged: 01 Frequency (Monobit), 13 Cumulative Sums #1, 13 Cumulative Sums #2 | 1 sequence x 1,000,000 bits (weak sample) |
| Dieharder | not run | skipped (insufficient data: 0.1 MB, needs about 100 MB) |
| PractRand | 0 failure/suspicious, 0 unusual | evaluated up to 2^16 bytes |
| TestU01 | not run | skipped (insufficient data: 0.1 MB, needs about 944 MB) |

**Key findings**

- The symbol distribution is not uniform (chi-square p = 0.00176): a small bias that costs min-entropy (most-common-value bound 0.9918 of 1 bits).
- Assessed min-entropy: **0.8717 bits per 1-bit sample (87.2% of nominal)**, non-IID track.
- SP 800-22 flags (pass-proportion rule): 01 Frequency (Monobit), 13 Cumulative Sums #1, 13 Cumulative Sums #2. See section 5 for how likely that is by chance.

This is a raw noise-source assessment. The headline number is the SP 800-90B min-entropy; verdicts of the general statistical suites on unconditioned data are diagnostics only (raw noise is normally biased or correlated).

---

## 2. Dataset and configuration

| Item | Value |
|---|---|
| File | `data.bin` |
| Samples | 1,000,000 |
| Sample width | 1 bit(s), packed back-to-back |
| Raw data size | 0.12 MB |
| SP 800-90B chunks | 1 x 1,000,000 samples |
| Claimed entropy | none given |
| Restart file | none |
| NIST sequence length / alpha | 1,000,000 bits / 0.01 |

---

## 3. Diagnostics

| Metric | Value |
|---|---|
| Shannon entropy / sample | 1.0000 of 1 bits (1.0000 per bit) |
| MCV min-entropy / sample (99% bound) | 0.9918 of 1 bits (0.9918 per bit) |
| Most common value frequency | 0.501564 (uniform = 0.500000) |
| Chi-square uniformity | chi2 = 9.8, p = 0.00176 |
| Longest identical-symbol run | 21 (uniform-source expectation about 19.9) |
| Stationarity (10 slices, chi-square homogeneity) | 0.809 |
| Compression ratio zlib-9 / bz2 / lzma | 1.0004 / 1.0074 / 1.0005 (1.0 = incompressible) |

**Serial correlation (lags 1 to 16)**

| Lag | r | p-value |
|---|---|---|
| 1 | -0.00100 | 0.3169 |
| 2 | +0.00009 | 0.9297 |
| 3 | +0.00136 | 0.1753 |
| 4 | +0.00106 | 0.29 |
| 5 | -0.00177 | 0.07593 |
| 6 | +0.00005 | 0.9615 |
| 7 | +0.00072 | 0.4708 |
| 8 | -0.00084 | 0.401 |
| 9 | -0.00065 | 0.5165 |
| 10 | +0.00015 | 0.8838 |
| 11 | -0.00025 | 0.8035 |
| 12 | -0.00028 | 0.7781 |
| 13 | +0.00008 | 0.9401 |
| 14 | -0.00010 | 0.9189 |
| 15 | -0.00089 | 0.3709 |
| 16 | -0.00048 | 0.6342 |

With 16 lags the smallest p-value is expected to be about 0.06 by chance. A lag is flagged only below 6.3e-05 (0.1% family-wise level, Bonferroni). The smallest observed is 0.07593.

---

## 4. NIST SP 800-90B entropy assessment

**Per chunk**

| Chunk | H_original (non-IID) | H_bitstring | non-IID result | IID result | IID checks |
|---|---|---|---|---|---|
| 1 | 0.8717 | n/a | 0.8717 | 0.9918 | passed |

**Non-IID estimators (bits per sample)**

| Estimator | Chunk 1 | Min |
|---|---|---|
| Most Common Value Estimate | 0.9918 | 0.9918 |
| Collision Test Estimate | 0.9306 | 0.9306 |
| Markov Test Estimate | 0.9969 | 0.9969 |
| Compression Test Estimate | 0.8717 | 0.8717 |
| T-Tuple Test Estimate | 0.9330 | 0.9330 |
| LRS Test Estimate | 0.9672 | 0.9672 |
| Multi Most Common in Window (MultiMCW) Prediction Test Estimate | 0.9971 | 0.9971 |
| Lag Prediction Test Estimate | 0.9973 | 0.9973 |
| Multi Markov Model with Counting (MultiMMC) Prediction Test Estimate | 0.9956 | 0.9956 |
| LZ78Y Prediction Test Estimate | 0.9929 | 0.9929 |

**Limiting estimator (chunk 1):** Compression Test Estimate = 0.8717; all other estimators are between 0.9306 and 0.9973.

**Calibration against ideal random data**

The same estimator was run on 20 freshly generated ideal random datasets of the same size (1,000,000 samples of 1 bit(s)). Non-IID estimates of ideal data are well below the symbol size because the estimators are conservative at this sample size.

| Baseline (ideal random) | Value |
|---|---|
| Minimum | 0.8157 |
| Median | 0.8498 |
| Maximum | 0.9015 |
| Limiting estimator (trials) | Compression Test Estimate (18), Collision Test Estimate (2) |
| Your non-IID value | **0.8717** |
| Baseline runs below your value | 17 of 20 |

Your value lies within the range ideal random data produces, so the gap to the symbol size is explained by estimator conservatism, not by detected structure. Note this baseline reflects ideal data; a biased source is expected to sit slightly lower.

**IID checks (chunk 1)**

| Check | Result |
|---|---|
| chi square tests | Passed |
| length of longest repeated substring test | Passed |
| IID permutation tests | Passed |

**Result**

| Item | Value |
|---|---|
| H (non-IID), minimum over chunks | 0.8717 bits/sample |
| H (IID) | 0.9918 bits/sample (IID verified: True) |
| Track used | non-IID (default: no IID claim needed) |
| H_I after claim | 0.8717 bits/sample |
| Final assessed min-entropy | **0.8717 bits/sample** (0.8717 per bit) |

**Reading these numbers**

- The headline value uses the non-IID track, which makes no independence assumption. Using the IID track requires claiming (and justifying from the source design) that samples are independent and identically distributed; passing the permutation tests alone does not establish that.
- The non-IID track is deliberately conservative. Even ideal uniform 8-bit data typically assesses well below 8 bits per sample at 1M samples (about 6.6 to 6.9 in tests), while the IID track gives about 7.9. A non-IID value below the symbol size is not a defect by itself.
- The assessed value is the minimum over all estimators and chunks, so a single conservative estimator (e.g. the Compression or MultiMMC estimator on biased data) can dominate.
- When raw samples feed a conditioning function and DRBG, the usable entropy rate must be justified under SP 800-90C using this min-entropy figure.

---

## 5. NIST SP 800-22 statistical tests

Pure-Python implementation, 1 sequence x 1,000,000 bits, alpha = 0.01. Non-overlapping Template runs one template (`000000001`), not all 148. Not the official NIST STS; cross-check before any formal claim.

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

With 1 sequence at alpha = 0.01, the acceptable pass proportion is **0.6915 to 1.0**, so at least **1 of 1** sequences must pass each test.

With only 1 sequence, the pass-proportion rule reduces to "did the p-value reach alpha"; read the individual p-values instead.
Smallest p-value: **0.00176** (01 Frequency (Monobit)). Counting Monobit and Cumulative Sums as one row (they measure the same imbalance), there are 13 effectively independent rows; the probability that the smallest of 13 p-values is this small or smaller by chance (Sidak) is about **2.3%**.

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

- No restart test was run, so the entropy assessment is incomplete (SP 800-90B 3.1.4)
- NIST SP 800-22: only 1 sequence (NIST recommends about 100 at alpha = 0.01); the pass-proportion results are noisy
- PractRand only reached 2^16 bytes (its power grows with length; weak sources typically fail at MB to GB scales)

## 11. Recommended next steps

1. Collect restart data (1000 restarts x 1000 samples, one restart per row) and rerun with `--restart-file`.
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
python3 qrng_raw_entropy_tests.py data.bin --out raw_results --sample-bits 1 --packed
```

Per-tool outputs in this folder: `ea_non_iid_chunk*.txt`, `ea_iid_chunk*.txt`, `ea_restart.txt`, `nist_summary.csv`, `nist_pvalues.csv`, `dieharder_report.txt`, `practrand_report.txt`, `testu01_*_report.txt`, `raw_summary.json`.
