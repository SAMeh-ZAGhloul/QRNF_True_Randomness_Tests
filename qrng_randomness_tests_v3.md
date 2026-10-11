# Randomness Test Report: Q135 Quantum RNG Sample

**Report date:** 11 October 2026
**Tool:** `qrng_randomness_tests_v3.py` (NIST SP 800-22, PractRand 0.95, Dieharder)
**Dataset:** `data.xlsx` (10,200 hex strings of 32 bytes)

---

## 1. Executive summary

| Suite | Outcome | Confidence in the result |
|---|---|---|
| **NIST SP 800-22** (own Python implementation) | 12 of 14 testable tests passed; 2 flagged on the pass-proportion criterion (Binary Matrix Rank, Linear Complexity) | **Low**: only 26 sequences of 100,000 bits |
| **PractRand 0.95** | No failures, no "suspicious" results; 1 "unusual" result at 16 KB that did not recur | **Very low**: only 256 KB evaluated |
| **Dieharder** | **No result**: run aborted on end-of-file | None |
| **NIST SP 800-90B** | Not run (needs raw pre-DRBG samples, at least 1,000,000) | n/a |

**Bottom line.** No test showed a reproducible statistical defect. The two NIST flags are about what chance produces with 26 sequences (section 4), and an independent self-check of the implementation on known-good random data found no bias. But the sample is too small for any strong claim, and these tests cannot show that the numbers are *quantum* in origin (section 7).

---

## 2. Dataset and configuration

| Item | Value |
|---|---|
| Hex strings loaded | 10,200 |
| Total size | 326,400 bytes (2,611,200 bits) |
| Ones ratio (all bits) | 0.499758 (z ≈ −0.78, no bias at this scale) |
| Source metadata (first 10 rows inspected) | register `Q135`, entropy source `superconducting_qubit_q135`, `CTR-DRBG-AES-256`, health tests (RCT, APT) passed, one `seed_id` (epoch 4), served 2026-10-07 |
| NIST sequence length | 100,000 bits, inferred from 26 sequences over 2.6 M bits |
| Significance level α | 0.01 |

Provenance caveat: only the first 10 rows were inspected. The full file may span several seeds or epochs. If so, the tests below do not separate them.

---

## 3. NIST SP 800-22 results

### 3.1 Pass-proportion criterion

With 26 sequences at α = 0.01, the acceptable pass proportion is **0.9315 to 1.0**, so **at least 25 of 26** sequences must pass each test.

| Test | Passed | Proportion | Uniformity P | Lowest p | Script verdict |
|---|---|---|---|---|---|
| 01 Frequency (Monobit) | 25/26 | 0.962 | 0.995 | 0.00150 | PASS |
| 02 Block Frequency | 26/26 | 1.000 | 0.709 | 0.07235 | PASS |
| 03 Runs | 26/26 | 1.000 | 0.231 | 0.01188 | PASS |
| 04 Longest Run of Ones | 26/26 | 1.000 | 0.854 | 0.05421 | PASS |
| 05 Binary Matrix Rank | **24/26** | 0.923 | 0.629 | 0.00036 | **FAIL** (proportion) |
| 06 DFT (Spectral) | 26/26 | 1.000 | 0.785 | 0.04846 | PASS |
| 07 Non-overlapping Template¹ | 25/26 | 0.962 | 0.474 | 0.00068 | PASS |
| 08 Overlapping Template | 25/26 | 0.962 | 0.403 | 0.00843 | PASS |
| 09 Maurer's Universal | n/a | n/a | n/a | n/a | N/A (needs ≥ 387,840 bits per sequence) |
| 10 Linear Complexity | **24/26** | 0.923 | 0.474 | 0.00351 | **FAIL** (proportion) |
| 11 Serial #1 | 25/26 | 0.962 | 0.281 | 0.00848 | PASS |
| 11 Serial #2 | 26/26 | 1.000 | 0.854 | 0.03176 | PASS |
| 12 Approximate Entropy | 25/26 | 0.962 | 0.338 | 0.00990 | PASS |
| 13 Cumulative Sums (forward) | 25/26 | 0.962 | 0.629 | 0.00254 | PASS |
| 13 Cumulative Sums (reverse) | 25/26 | 0.962 | 0.629 | 0.00137 | PASS |

¹ One template only (`000000001`), not the full set of 148.

### 3.2 Random Excursions tests (14 and 15)

Only **4 of 26 sequences** (indices 1, 8, 13, 25) had the 500 or more cycles these tests require. The other 22 are not applicable under the standard.

| Test | States | Sequences used | Proportion | Lowest p | Highest p |
|---|---|---|---|---|---|
| 14 Random Excursions | 8 (−4…−1, 1…4) | 4 | 1.0 in all states | 0.0657 | 0.9879 |
| 15 Random Excursions Variant | 18 (−9…−1, 1…9) | 4 | 1.0 in all states | 0.0606 | 0.9927 |

With only 4 p-values per state, the uniformity P-values are not meaningful and should be ignored. For example, state #5 of test 14 shows 0.0127, which is not a finding.

---

## 4. Interpretation of the two flagged tests

Both flags come from the proportion rule alone. Their uniformity P-values are healthy (0.63 and 0.47).

| Flagged test | Failing sequences | p-values |
|---|---|---|
| 05 Binary Matrix Rank | #0, #7 | 0.00176, 0.00036 |
| 10 Linear Complexity | #8, #13 | 0.00351, 0.00824 |

**How unusual is this?**

| Question | Probability |
|---|---|
| One test, 26 sequences, 2 or more failures at α = 0.01 | 2.8 % |
| At least one of the 14 testable rows shows that | 33 % |
| At least two of the 14 rows show that | 5.6 % |

Two such tests are mildly unusual, not alarming.

**Sequence #23 clusters four low p-values:**

| Test | p-value |
|---|---|
| Frequency (Monobit) | 0.0015 |
| Cumulative Sums (forward) | 0.0025 |
| Cumulative Sums (reverse) | 0.0014 |
| Non-overlapping Template | 0.00068 |

Monobit and the two cumulative-sums tests all measure ones/zeros imbalance, so the first three are effectively one event, not three. The chance that the lowest of 26 monobit p-values is 0.0015 or smaller is about 3.8 %.

**Overall tail count.** 11 of 468 valid p-values are below 0.01, against about 4.7 expected.

| Counting method | Probability of this much excess |
|---|---|
| Naive count | 0.8 % |
| Correlated trio counted once (8 events) | about 10 % |

The pooled p-values (364, excluding tests 14 and 15) are consistent with uniform: Kolmogorov–Smirnov p = 0.77, mean p = 0.488.

**Implementation self-check.** The two flagged tests are the most intricate to implement (GF(2) matrix rank and Berlekamp–Massey), so I ran them on 100,000-bit sequences from `os.urandom`:

| Test | Sequences | Below 0.01 (expected) | KS vs uniform |
|---|---|---|---|
| Binary Matrix Rank | 300 | 4 (3.0) | p = 0.35 |
| Linear Complexity | 83 | 1 (0.8) | p = 0.60 |

The implementation shows no bias on known-good data. **Assessment:** the flags are most plausibly chance. They need a larger sample to settle.

---

## 5. PractRand 0.95

| Item | Value |
|---|---|
| Input | 326,400 bytes via stdin |
| Reported checkpoints | 1 KB to 256 KB (2¹⁰ to 2¹⁸), 9 checkpoints |
| Bytes beyond the last checkpoint | about 64 KB not reported (the next checkpoint is 512 KB) |
| Test results evaluated (all checkpoints) | about 314 |
| Failures | 0 |
| "Suspicious" | 0 |
| "Unusual" | 1: `[Low4/32]DC6-9x1Bytes-1`, R = +6.5, p = 9.1 × 10⁻³, at 16 KB |

The single "unusual" result did not recur at 32 KB or any later checkpoint. One such result among about 300 is expected by chance. Checkpoints re-test overlapping data, so they are not independent.

The final line, `error reading standard input`, is just end of file and is normal.

**Power.** PractRand's sensitivity grows with length. Weak generators typically fail at MB to GB scales, so at 256 KB this only rules out gross defects.

---

## 6. Dieharder

**No result.** The report file contains only:

```
# stdin_input_raw(): Error: EOF
```

**Cause.**
- The local Dieharder build ignored the `-f <file>` option, so the script fell back to reading stdin.
- A pipe cannot be rewound, and 326 KB is too small for even the first test, so the run aborted immediately.

**File mode would not help either.** In a separate test on a 326 KB random file with a working Dieharder, the first test re-read the file 169 times and reported a false `FAILED`. Re-used data produces false failures, so a small file can never give a valid Dieharder result.

---

## 7. What these tests do and do not show

1. **The tested data is DRBG output.** The rows are labelled `CTR-DRBG-AES-256`. A DRBG seeded from any source, even a constant, produces output that passes NIST, Dieharder, PractRand and TestU01. These suites can show that the output has no detectable statistical defect. They cannot show that the seed came from a qubit.
2. **Entropy-source assessment needs raw data.** The correct tool is NIST SP 800-90B on raw pre-conditioning samples (at least 1,000,000 samples, plus restart tests). Request those from the provider.
3. **The provider's health tests are not an independent check.** `health_rct` and `health_apt` are SP 800-90B-style continuous tests on the source. They suggest the service monitors its source but do not verify it.

---

## 8. Limitations of this run

| Limitation | Effect |
|---|---|
| 26 NIST sequences (roughly 100 recommended at α = 0.01) | Pass/fail proportions are very noisy |
| 100,000-bit sequences | Maurer's Universal not applicable; Random Excursions mostly not applicable |
| Own NIST implementation | Not the official STS; cross-check before any formal claim |
| Single template in test 07 | Not the full 148-template test |
| 326 KB total | PractRand evaluated only to 256 KB; Dieharder and TestU01 not usable |
| Mixed seeds not examined | Cross-epoch correlations would not be visible |

---

## 9. Recommended next steps

1. **Collect more data** into CSV or binary, since Excel is capped at 1,048,576 rows (about 33 MB at 32 bytes per row).

   | Target | Volume |
   |---|---|
   | NIST SP 800-22, 100+ sequences of 1 Mbit | about 12.5 MB (about 390,000 rows) |
   | PractRand | at least 1 GB, ideally several GB |
   | TestU01 SmallCrush | about 1 GB (measured) |
   | Dieharder `-a` | several GB (approximate) |

2. **Cross-check the two flagged tests** with the official NIST STS (`sts-2.1.2`) on `results/stream.txt`.
3. **Stratify by `seed_id` and `seed_epoch`** and test per seed and across seeds.
4. **Request raw pre-DRBG qubit samples** and run `ea_non_iid` (SP 800-90B). This is the only test in this list that speaks to the source.
5. **Fix Dieharder** by running the packaged build in Docker:

   ```bash
   docker run --rm -v "$PWD/results":/data ubuntu:24.04 bash -c \
     "apt-get update -qq && apt-get install -y -qq dieharder && \
      dieharder -a -g 201 -f /data/stream.bin > /data/dieharder_report.txt"
   ```

---

## Appendix A: all NIST p-values below 0.01

| Sequence | Test | p-value |
|---|---|---|
| 0 | 05 Binary Matrix Rank | 0.001759 |
| 4 | 11 Serial #1 | 0.008480 |
| 7 | 05 Binary Matrix Rank | 0.000360 |
| 8 | 10 Linear Complexity | 0.003510 |
| 12 | 12 Approximate Entropy | 0.009901 |
| 13 | 10 Linear Complexity | 0.008243 |
| 21 | 08 Overlapping Template | 0.008426 |
| 23 | 01 Frequency (Monobit) | 0.001499 |
| 23 | 07 Non-overlapping Template | 0.000678 |
| 23 | 13 Cumulative Sums #1 | 0.002543 |
| 23 | 13 Cumulative Sums #2 | 0.001366 |

## Appendix B: reproduction

```bash
python3 qrng_randomness_tests_v3.py data.xlsx --out results \
    --seq-len 100000 --alpha 0.01 --practrand
```

Output files: `results/nist_summary.csv`, `results/nist_pvalues.csv`, `results/practrand_report.txt`, `results/dieharder_report.txt`.
