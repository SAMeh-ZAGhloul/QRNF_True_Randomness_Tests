# Raw Entropy Source Assessment: `sonicium-q135-channel134-bin.bin`

**Generated:** 16 October 2026 12:29  
**Data:** 1,701,800 samples of 1 bit(s) (0.21 MB)  
**Tool:** `qrng_raw_entropy_tests.py`

---

## 1. Executive summary

| Suite | Outcome | Detail |
|---|---|---|
| Diagnostics | Flags: non-uniform symbol distribution, non-stationary across slices | Shannon 1.000 / 1 bits; MCV min-entropy 0.988 / 1 bits |
| SP 800-90B | **0.8568 bits/sample** (0.8568 per bit) | 1 x 1,000,000 samples, non-IID track, restart test NOT run |
| NIST SP 800-22 | 10 PASS, 4 FAIL, 27 N/A (of 41 test rows); flagged: 01 Frequency (Monobit), 03 Runs, 13 Cumulative Sums #1, 13 Cumulative Sums #2 | 17 sequences x 100,000 bits (weak sample) |
| Dieharder | not run | skipped (insufficient data: 0.2 MB, needs about 100 MB) |
| PractRand | 6 failure/suspicious, 10 unusual | evaluated up to 2^16 bytes |
| TestU01 | not run | skipped (insufficient data: 0.2 MB, needs about 944 MB) |

**Key findings**

- Basic diagnostics flag: non-uniform symbol distribution, non-stationary across slices.
- **The bias is not constant over the capture** (see the slice and window tables in section 3). SP 800-90B estimates from one chunk are then a snapshot: assess several chunks across time, and expect time-varying bias to trigger PractRand's frequency-type tests (constant bias of the same size does not, in simulation).
- The symbol distribution is not uniform (chi-square p = 5.9e-18) (50.3309% ones): a small bias that costs min-entropy (most-common-value bound 0.9877 of 1 bits).
- Assessed min-entropy: **0.8568 bits per 1-bit sample (85.7% of nominal)**, non-IID track.
- **The IID checks FAILED**: the IID assumption is rejected, so only the non-IID estimate is valid; do not use the IID value.
- SP 800-22 flags (pass-proportion rule): 01 Frequency (Monobit), 03 Runs, 13 Cumulative Sums #1, 13 Cumulative Sums #2 (03 Runs p = 0 is the Monobit prerequisite failing, not separate evidence). See section 5 for how likely that is by chance.
- PractRand reported 6 suspicious/failing result(s); see section 7.

This is a raw noise-source assessment. The headline number is the SP 800-90B min-entropy; verdicts of the general statistical suites on unconditioned data are diagnostics only (raw noise is normally biased or correlated).

---

## 2. Dataset and configuration

| Item | Value |
|---|---|
| File | `sonicium-q135-channel134-bin.bin` |
| Samples | 1,701,800 |
| Sample width | 1 bit(s), packed back-to-back |
| Raw data size | 0.21 MB |
| SP 800-90B chunks | 1 x 1,000,000 samples |
| Claimed entropy | none given |
| Restart file | none |
| NIST sequence length / alpha | 100,000 bits / 0.01 |

---

## 3. Diagnostics

| Metric | Value |
|---|---|
| Shannon entropy / sample | 1.0000 of 1 bits (1.0000 per bit) |
| MCV min-entropy / sample (99% bound) | 0.9877 of 1 bits (0.9877 per bit) |
| Most common value frequency | 0.503309 (uniform = 0.500000) |
| Ones / zeros | 856,532 / 845,268 (50.3309% ones), z = +8.63 |
| Chi-square uniformity | chi2 = 74.6, p = 5.897e-18 |
| Longest identical-symbol run | 19 (uniform-source expectation about 20.7) |
| Stationarity (10 slices, chi-square homogeneity) | 0.0001863 |
| Compression ratio zlib-9 / bz2 / lzma | 1.0003 / 1.0063 / 1.0003 (1.0 = incompressible) |

**Serial correlation (lags 1 to 16)**

| Lag | r | p-value |
|---|---|---|
| 1 | +0.00035 | 0.6475 |
| 2 | -0.00057 | 0.4606 |
| 3 | -0.00039 | 0.6153 |
| 4 | +0.00028 | 0.7155 |
| 5 | -0.00068 | 0.3774 |
| 6 | -0.00107 | 0.1619 |
| 7 | -0.00063 | 0.4123 |
| 8 | -0.00018 | 0.8118 |
| 9 | -0.00008 | 0.9172 |
| 10 | +0.00014 | 0.8544 |
| 11 | +0.00123 | 0.1094 |
| 12 | +0.00091 | 0.2337 |
| 13 | +0.00099 | 0.1971 |
| 14 | +0.00097 | 0.205 |
| 15 | +0.00135 | 0.07886 |
| 16 | -0.00123 | 0.1073 |

With 16 lags the smallest p-value is expected to be about 0.06 by chance. A lag is flagged only below 6.3e-05 (0.1% family-wise level, Bonferroni). The smallest observed is 0.07886.

**Bias over time (10 consecutive slices)**

| Slice | Bits | Ones | Ones fraction | z vs overall mean |
|---|---|---|---|---|
| 1 | 170,180 | 86,350 | 50.7404% | +3.38 |
| 2 | 170,180 | 85,620 | 50.3114% | -0.16 |
| 3 | 170,180 | 85,763 | 50.3955% | +0.53 |
| 4 | 170,180 | 85,745 | 50.3849% | +0.45 |
| 5 | 170,180 | 85,438 | 50.2045% | -1.04 |
| 6 | 170,180 | 84,892 | 49.8837% | -3.69 |
| 7 | 170,180 | 85,299 | 50.1228% | -1.72 |
| 8 | 170,180 | 85,771 | 50.4002% | +0.57 |
| 9 | 170,180 | 85,693 | 50.3543% | +0.19 |
| 10 | 170,180 | 85,961 | 50.5118% | +1.49 |

**Is the mean constant over time? (overdispersion of window means)**

| Window | Windows | chi2 / dof | p-value | Largest |z| (window #) |
|---|---|---|---|---|
| 1,000 | 1701 | 1680.7 / 1700 | 0.6256 | 3.46 (#94) |
| 10,000 | 170 | 206.4 / 169 | 0.02641 | 2.98 (#99) |
| 100,000 | 17 | 50.8 / 16 | 1.689e-05 | 3.93 (#0) |

A small p-value means the mean varies over time by more than sampling noise at that window scale (drift, a warm-up transient, or interference). Several scales help locate its timescale.

---

## 4. NIST SP 800-90B entropy assessment

**Per chunk**

| Chunk | H_original (non-IID) | H_bitstring | non-IID result | IID result | IID checks |
|---|---|---|---|---|---|
| 1 | 0.8568 | n/a | 0.8568 | 0.9868 | FAILED |

**Non-IID estimators (bits per sample)**

| Estimator | Chunk 1 | Min |
|---|---|---|
| Most Common Value Estimate | 0.9868 | 0.9868 |
| Collision Test Estimate | 0.9175 | 0.9175 |
| Markov Test Estimate | 0.9907 | 0.9907 |
| Compression Test Estimate | 0.8568 | 0.8568 |
| T-Tuple Test Estimate | 0.9166 | 0.9166 |
| LRS Test Estimate | 0.9200 | 0.9200 |
| Multi Most Common in Window (MultiMCW) Prediction Test Estimate | 0.9937 | 0.9937 |
| Lag Prediction Test Estimate | 0.9953 | 0.9953 |
| Multi Markov Model with Counting (MultiMMC) Prediction Test Estimate | 0.9875 | 0.9875 |
| LZ78Y Prediction Test Estimate | 0.9868 | 0.9868 |

**Limiting estimator (chunk 1):** Compression Test Estimate = 0.8568; all other estimators are between 0.9166 and 0.9953.

**Calibration against ideal random data**

The same estimator was run on 20 freshly generated ideal random datasets of the same size (1,000,000 samples of 1 bit(s)). Non-IID estimates of ideal data are well below the symbol size because the estimators are conservative at this sample size.

| Baseline (ideal random) | Value |
|---|---|
| Minimum | 0.8138 |
| Median | 0.8512 |
| Maximum | 0.9097 |
| Limiting estimator (trials) | Compression Test Estimate (18), Collision Test Estimate (1), Multi Most Common in Window (MultiMCW) Prediction Test Estimate (1) |
| Your non-IID value | **0.8568** |
| Baseline runs below your value | 11 of 20 |

Your value lies within the range ideal random data produces, so the gap to the symbol size is explained by estimator conservatism, not by detected structure. Note this baseline reflects ideal data; a biased source is expected to sit slightly lower.

**IID checks (chunk 1)**

| Check | Result |
|---|---|
| chi square tests | Failed |
| length of longest repeated substring test | Passed |
| IID permutation tests | Failed |

**Result**

| Item | Value |
|---|---|
| H (non-IID), minimum over chunks | 0.8568 bits/sample |
| H (IID) | 0.9868 bits/sample (IID verified: False) |
| Track used | non-IID (default: no IID claim needed) |
| H_I after claim | 0.8568 bits/sample |
| Final assessed min-entropy | **0.8568 bits/sample** (0.8568 per bit) |

**Reading these numbers**

- The headline value uses the non-IID track, which makes no independence assumption. Using the IID track requires claiming (and justifying from the source design) that samples are independent and identically distributed; passing the permutation tests alone does not establish that.
- The non-IID track is deliberately conservative. Even ideal uniform 8-bit data typically assesses well below 8 bits per sample at 1M samples (about 6.6 to 6.9 in tests), while the IID track gives about 7.9. A non-IID value below the symbol size is not a defect by itself.
- The assessed value is the minimum over all estimators and chunks, so a single conservative estimator (e.g. the Compression or MultiMMC estimator on biased data) can dominate.
- When raw samples feed a conditioning function and DRBG, the usable entropy rate must be justified under SP 800-90C using this min-entropy figure.

---

## 5. NIST SP 800-22 statistical tests

Pure-Python implementation, 17 sequences x 100,000 bits, alpha = 0.01. Non-overlapping Template runs one template (`000000001`), not all 148. Not the official NIST STS; cross-check before any formal claim.

| Test | Passed | Proportion | Uniformity P | Lowest p | Verdict |
|---|---|---|---|---|---|
| 01 Frequency (Monobit) | 12/17 | 0.706 | 0.000 | 1.667e-09 | FAIL |
| 02 Block Frequency | 17/17 | 1.000 | 0.163 | 0.1856 | PASS |
| 03 Runs | 14/17 | 0.824 | 0.057 | 0 (Monobit prerequisite failed) | FAIL |
| 04 Longest Run of Ones | 17/17 | 1.000 | 0.625 | 0.02645 | PASS |
| 05 Binary Matrix Rank | 17/17 | 1.000 | 0.746 | 0.04555 | PASS |
| 06 DFT (Spectral) | 16/17 | 0.941 | 0.746 | 0.009803 | PASS |
| 07 Non-overlapping Template | 17/17 | 1.000 | 0.223 | 0.03281 | PASS |
| 08 Overlapping Template | 16/17 | 0.941 | 0.301 | 0.007079 | PASS |
| 09 Maurer's Universal | n/a | n/a | n/a | n/a | N/A (not applicable at this sequence length) |
| 10 Linear Complexity | 17/17 | 1.000 | 0.854 | 0.05723 | PASS |
| 11 Serial #1 | 17/17 | 1.000 | 0.012 | 0.04096 | PASS |
| 11 Serial #2 | 17/17 | 1.000 | 0.936 | 0.1022 | PASS |
| 12 Approximate Entropy | 17/17 | 1.000 | 0.000 | 0.08948 | PASS |
| 13 Cumulative Sums #1 | 12/17 | 0.706 | 0.000 | 2.851e-09 | FAIL |
| 13 Cumulative Sums #2 | 12/17 | 0.706 | 0.000 | 2.251e-09 | FAIL |
| 14 Random Excursions (8 states) | n/a | n/a | n/a | n/a | N/A (fewer than 500 cycles in every sequence) |
| 15 Random Excursions Variant (18 states) | n/a | n/a | n/a | n/a | N/A (fewer than 500 cycles in every sequence) |

### Analysis

With 17 sequences at alpha = 0.01, the acceptable pass proportion is **0.9176 to 1.0**, so at least **16 of 17** sequences must pass each test.

**Tests flagged on the pass-proportion rule:**

| Test | Failing sequences | Sequence (p-value) | P(>= that many failures | 17 seq, alpha=0.01) |
|---|---|---|---|
| 01 Frequency (Monobit) | 5 | #0 (p=1.667e-09), #1 (p=0.001942), #4 (p=0.002893), #5 (p=5.608e-05), #15 (p=3.25e-05) | 5.6e-07 |
| 03 Runs | 3 | #0 (p=0), #5 (p=0), #15 (p=0) | 0.000612 |
| 13 Cumulative Sums #1 | 5 | #0 (p=2.851e-09), #1 (p=0.001818), #4 (p=0.0009394), #5 (p=9.667e-05), #15 (p=4.919e-05) | 5.6e-07 |
| 13 Cumulative Sums #2 | 5 | #0 (p=2.251e-09), #1 (p=0.00155), #4 (p=0.004411), #5 (p=7.773e-05), #15 (p=3.657e-05) | 5.6e-07 |

Across the 14 full-length test rows, the chance that at least one row shows 5 or more failures purely by chance is about **0.0%**.
The chance that at least 4 rows do is about **0.0%**.

**Overall:** 20 of 238 valid p-values are below 0.01 (expected about 2.4; naive binomial tail probability 7.68e-13).
Pooled p-values of the full-length tests (238) vs uniform: Kolmogorov-Smirnov p = 2.95e-06, mean p = 0.399.

**Clusters (3 or more low p-values in one sequence):**

- Sequence #0: 01 Frequency (Monobit) (p=1.667e-09), 03 Runs (p=0), 13 Cumulative Sums #1 (p=2.851e-09), 13 Cumulative Sums #2 (p=2.251e-09)
- Sequence #1: 01 Frequency (Monobit) (p=0.001942), 13 Cumulative Sums #1 (p=0.001818), 13 Cumulative Sums #2 (p=0.00155)
- Sequence #4: 01 Frequency (Monobit) (p=0.002893), 06 DFT (Spectral) (p=0.009803), 13 Cumulative Sums #1 (p=0.0009394), 13 Cumulative Sums #2 (p=0.004411)
- Sequence #5: 01 Frequency (Monobit) (p=5.608e-05), 03 Runs (p=0), 13 Cumulative Sums #1 (p=9.667e-05), 13 Cumulative Sums #2 (p=7.773e-05)
- Sequence #15: 01 Frequency (Monobit) (p=3.25e-05), 03 Runs (p=0), 13 Cumulative Sums #1 (p=4.919e-05), 13 Cumulative Sums #2 (p=3.657e-05)

Monobit and Cumulative Sums all measure ones/zeros imbalance, so they are strongly correlated: treat those as one event, not several.

**All p-values below alpha**

| Sequence | Test | p-value |
|---|---|---|
| 0 | 01 Frequency (Monobit) | 0.000000 |
| 0 | 03 Runs | 0.000000 |
| 0 | 13 Cumulative Sums #1 | 0.000000 |
| 0 | 13 Cumulative Sums #2 | 0.000000 |
| 1 | 01 Frequency (Monobit) | 0.001942 |
| 1 | 13 Cumulative Sums #1 | 0.001818 |
| 1 | 13 Cumulative Sums #2 | 0.001550 |
| 2 | 08 Overlapping Template | 0.007079 |
| 4 | 01 Frequency (Monobit) | 0.002893 |
| 4 | 06 DFT (Spectral) | 0.009803 |
| 4 | 13 Cumulative Sums #1 | 0.000939 |
| 4 | 13 Cumulative Sums #2 | 0.004411 |
| 5 | 01 Frequency (Monobit) | 0.000056 |
| 5 | 03 Runs | 0.000000 |
| 5 | 13 Cumulative Sums #1 | 0.000097 |
| 5 | 13 Cumulative Sums #2 | 0.000078 |
| 15 | 01 Frequency (Monobit) | 0.000032 |
| 15 | 03 Runs | 0.000000 |
| 15 | 13 Cumulative Sums #1 | 0.000049 |
| 15 | 13 Cumulative Sums #2 | 0.000037 |

On unconditioned raw data, failures here point to bias or correlation the conditioner must remove.

---

## 6. Dieharder

Not run: skipped (insufficient data: 0.2 MB, needs about 100 MB).

---

## 7. PractRand

PractRand 0.95, `-tlmin 1KB`. The final line `error reading standard input` is just end of file.

| Length | Test results | Status |
|---|---|---|
| 1 kilobyte | 6 | unusual |
| 2 kilobytes | 8 | unusual |
| 4 kilobytes | 12 | mildly suspicious; unusual |
| 8 kilobytes | 25 | unusual |
| 16 kilobytes | 30 | VERY SUSPICIOUS; suspicious; unusual |
| 32 kilobytes | 45 | VERY SUSPICIOUS |
| 64 kilobytes | 54 | VERY SUSPICIOUS; FAIL; unusual |

**Anomalies**

| At length | Test | R | p | Evaluation |
|---|---|---|---|---|
| 1 kilobyte | DC6-9x1Bytes-1 | +7.0 | 7.9e-3 | unusual |
| 2 kilobytes | DC6-9x1Bytes-1 | +5.5 | 0.019 | unusual |
| 4 kilobytes | BCFN(2+0,13-9,T) | +15.5 | 1.2e-4 | mildly suspicious |
| 4 kilobytes | DC6-9x1Bytes-1 | +7.1 | 3.1e-3 | unusual |
| 8 kilobytes | BCFN(2+0,13-9,T) | +14.2 | 2.8e-4 | unusual |
| 8 kilobytes | DC6-9x1Bytes-1 | +6.7 | 2.9e-3 | unusual |
| 8 kilobytes | [Low1/8]DC6-9x1Bytes-1 | +7.2 | 7.2e-3 | unusual |
| 16 kilobytes | BCFN(2+0,13-9,T) | +33.3 | 9.1e-9 | VERY SUSPICIOUS |
| 16 kilobytes | DC6-9x1Bytes-1 | +10.5 | 2.5e-5 | suspicious |
| 16 kilobytes | [Low1/8]DC6-9x1Bytes-1 | +8.5 | 1.9e-3 | unusual |
| 32 kilobytes | BCFN(2+0,13-9,T) | +35.9 | 2.3e-9 | VERY SUSPICIOUS |
| 64 kilobytes | BCFN(2+0,13-9,T) | +38.1 | 1.1e-9 | VERY SUSPICIOUS |
| 64 kilobytes | BCFN(2+1,13-9,T) | +46.4 | 1.5e-11 | FAIL |
| 64 kilobytes | BCFN(2+2,13-9,T) | +44.6 | 2.1e-11 | FAIL |
| 64 kilobytes | FPF-14+6/16:all | +6.0 | 4.8e-4 | unusual |
| 64 kilobytes | FPF-14+6/16:cross | +4.6 | 6.2e-4 | unusual |

About 180 test results were evaluated across checkpoints (checkpoints re-test overlapping data, so they are not independent). An isolated 'unusual' (about p = 0.01) is expected by chance; a 'suspicious' or 'FAIL' that persists at larger lengths is the real signal.

---

## 8. TestU01 (small)

Not run: skipped (insufficient data: 0.2 MB, needs about 944 MB).

---

## 9. What these results do and do not show

1. **Raw data is not expected to look full-entropy.** Bias and correlation are normal in an unconditioned noise source; the question is how much min-entropy remains, which is what SP 800-90B measures.
2. **An entropy claim needs more than one number:** the restart test, health tests at runtime, and a documented conditioning and DRBG design (SP 800-90A/B/C).
3. **Statistical tests cannot prove physical origin.** They can detect defects; a quantum origin is argued from the device physics and the 90B assessment of the raw readout.

## 10. Limitations of this run

- No restart test was run, so the entropy assessment is incomplete (SP 800-90B 3.1.4)
- NIST SP 800-22: only 17 sequences (NIST recommends about 100 at alpha = 0.01); the pass-proportion results are noisy
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
python3 qrng_raw_entropy_tests.py sonicium-q135-channel134-bin.bin --out raw_results --sample-bits 1 --packed --seq-len 100000
```

Per-tool outputs in this folder: `ea_non_iid_chunk*.txt`, `ea_iid_chunk*.txt`, `ea_restart.txt`, `nist_summary.csv`, `nist_pvalues.csv`, `dieharder_report.txt`, `practrand_report.txt`, `testu01_*_report.txt`, `raw_summary.json`.
