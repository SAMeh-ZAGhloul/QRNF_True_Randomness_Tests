# QRNG Randomness and Entropy Assessment Toolkit

Two Python scripts that assess random-number data from a (quantum) entropy source:

| Script | Use it for |
|---|---|
| `qrng_raw_entropy_tests.py` | **Raw, pre-DRBG noise samples** in a binary file (e.g. `data.bin`). Centred on NIST SP 800-90B min-entropy. Writes a detailed `raw_report.md`. |
| `qrng_randomness_tests_v3.py` | **Post-DRBG / conditioned output** in XLS/XLSX/CSV (hex strings). Also the **installer** for every external tool (`--setup`) and the runners the raw script reuses. |

Keep both files in the same folder.

> **Key idea.** A DRBG such as CTR-DRBG-AES-256 makes any seed look random to statistical suites, so tests on DRBG output cannot show that the *source* is quantum. The meaningful check is SP 800-90B on **raw** samples. The general statistical suites (NIST SP 800-22, Dieharder, PractRand, TestU01) are diagnostics on raw data and checks on conditioned data.

---

## 1. Quick start

```bash
# 1. Install the external tools once (builds from source into ~/.local, no sudo on macOS)
python3 qrng_randomness_tests_v3.py --setup
python3 qrng_randomness_tests_v3.py --list          # check status

# 2a. Raw samples (packed 1-bit samples, e.g. 1,000,000 bits = 125,000 bytes)
python3 qrng_raw_entropy_tests.py data.bin --sample-bits 1 --packed --out raw_results

# 2b. Raw samples (one 8-bit sample per byte; this is the default layout)
python3 qrng_raw_entropy_tests.py data.bin --out raw_results

# 2c. Post-DRBG hex strings in a spreadsheet (2nd column = hex)
python3 qrng_randomness_tests_v3.py data.xlsx --out results --seq-len 100000 --practrand
```

Do not type the square brackets that appear in usage text: zsh treats `[...]` as a file pattern.

---

## 2. What it does

```
 data.bin ──► load samples ──► 1. diagnostics
 (raw)        (--sample-bits,   2. SP 800-90B  (ea_non_iid, ea_iid, ea_restart)
               --packed)        3. bit stream ─► NIST SP 800-22 (parallel, pure Python)
                                               ─► Dieharder   (needs ≥ ~100 MB)
                                               ─► PractRand   (any size, weak below ~1 GB)
                                               ─► TestU01     (SmallCrush needs ~1 GB)
                                4. raw_summary.json ─► raw_report.md
```

| Stage | What you get |
|---|---|
| **Diagnostics** | Symbol histogram, Shannon and most-common-value (MCV) min-entropy, chi-square, serial correlation (lags 1 to 16), stationarity over 10 slices, longest identical run, compressibility, ones/zeros count for 1-bit data. |
| **SP 800-90B** | Non-IID min-entropy (headline), IID estimate and IID checks (supplementary), optional restart test, optional claimed-entropy check, optional multi-chunk stability check, optional ideal-random calibration baseline. |
| **NIST SP 800-22** | All 15 tests with the standard's pass-proportion and uniformity criteria, run in parallel across CPU cores. |
| **Dieharder, PractRand, TestU01** | Run through the shared runners; skipped automatically when the data is too small to give a valid result (`--force-suites` overrides, but results are then invalid because the input is re-used). |
| **Report** | `raw_report.md`: executive summary, per-suite sections, statistical analysis of flagged results, limitations, next steps, reproduction command. Regenerate any time with `--report-only DIR`. |

### Design decisions worth knowing

- **Non-IID is the default track** (`--track non-iid`). The IID track needs a design-level justification that samples are independent and identically distributed; passing the permutation tests alone does not establish it. `ea_iid` still runs for information.
- **Sample layout is explicit.** `--sample-bits N` (1 to 8) and `--packed` describe how samples are stored. A wrong layout is the most common cause of a skipped 90B stage (1,000,000 packed bits read as 125,000 bytes).
- **Correlated tests are not double-counted.** Monobit and Cumulative Sums measure the same imbalance; the analysis treats them as one finding.
- **Calibration** (`--calibrate N`) runs the same estimator on N freshly generated ideal-random datasets of the same size, because the non-IID estimators are conservative and never reach the full symbol size at 1M samples.

---

## 3. Sample data and results (high level)

Two datasets were assessed on 12 October 2026. The figures illustrate what the output looks like; they are not a certification of any device.

### 3.1 Raw samples: `data.bin` (1,000,000 one-bit samples, 125 KB)

| Item | Result |
|---|---|
| Ones / zeros | 50.16% ones (z = +3.1, chi-square p = 0.0018): small but statistically significant bias |
| MCV min-entropy (99% bound) | 0.9918 per bit |
| Serial correlation, stationarity, compressibility | Clean (smallest lag p = 0.076, slices p = 0.81, incompressible) |
| **SP 800-90B, non-IID** | **0.8717 bits/sample**, limited by the Compression estimator (all others 0.93 to 0.997) |
| SP 800-90B, IID | 0.9918 (IID checks passed; supplementary only) |
| Calibration on 20 ideal-random 1M-bit datasets | 0.816 / 0.850 / 0.902 (min / median / max), so 0.8717 is typical for perfect randomness at this size |
| NIST SP 800-22 (1 sequence) | 12 rows pass; Monobit (p = 0.0018) and both Cumulative Sums (p = 0.0027, 0.0031) flagged, which is one bias finding (about 2.3% chance after multiplicity adjustment); Random Excursions not applicable |
| PractRand | No anomalies up to 64 KB (the file's whole length) |
| Dieharder, TestU01 | Skipped: data too small |
| Still missing | Restart test, second chunk for stability |

### 3.2 Post-DRBG output: 10,200 hex strings (326,400 bytes)

| Item | Result |
|---|---|
| NIST SP 800-22 (26 sequences x 100,000 bits) | 12 of 14 testable tests pass; Binary Matrix Rank and Linear Complexity flagged at 24/26. About a 6% chance of two such tests by chance; the implementation showed no bias on `os.urandom` data |
| PractRand | One isolated "unusual" at 16 KB that did not recur; clean to 256 KB |
| Dieharder | No result (input too small, end of file) |
| SP 800-90B | Not applicable: DRBG output, not raw samples |

**Takeaway:** neither dataset shows a reproducible defect, but both are far too small for strong conclusions, which is the main limitation below.

---

## 4. Sample data size recommendations

Sizes are the main limit on what these tools can tell you. Numbers marked *measured* come from runs of this toolkit; *rough* means approximate.

| Goal | Minimum | Recommended | 1-bit packed | 8-bit |
|---|---|---|---|---|
| **SP 800-90B initial estimate** | 1,000,000 consecutive samples (hard requirement, tools refuse less) | 3 or more chunks of 1,000,000 (`--chunks 3`) to see stability | 375 KB | 3 MB |
| **SP 800-90B restart test** | 1000 restarts x 1000 samples = 1,000,000 samples (separate file, re-initialise the source before each row) | same | 125 KB | 1 MB |
| **NIST SP 800-22** | 1 sequence of 1 Mbit (p-values only) | at least 100 sequences x 1 Mbit; 1000 for a thorough run | 12.5 MB (125 MB) | 12.5 MB (125 MB) |
| **PractRand** | any size (reports from 1 KB) | 1 GB (2^30 bytes) or more | 1 GB | 1 GB |
| **Dieharder** | about 100 MB (script guard) | several GB for the full `-a` battery *(rough)* | | |
| **TestU01 SmallCrush** | about 1 GB (*measured*: a 300 MB file was re-read 3 times) | 1 to 2 GB | | |
| **TestU01 Crush / BigCrush** | tens of GB / about 1 TB *(rough)* | | | |

Notes:

- **One chunk is a snapshot.** A single 1M-sample estimate can sit anywhere in the estimator's natural spread (0.82 to 0.90 for ideal 1-bit data). Several chunks, ideally from separate captures, show whether the figure is stable.
- **Re-used data gives false failures.** If a suite has to rewind the file (Dieharder and TestU01 report this), its results are invalid. The report marks them INVALID.
- **Spreadsheets cap at 1,048,576 rows**, about 33 MB at 32 bytes per row. For anything larger, export binary or CSV.
- **Pure-Python NIST speed:** about 30 s for one 1-Mbit sequence on an Apple-silicon Mac (*measured*, including Linear Complexity). 100 sequences take roughly 7 minutes on 8 cores. `--skip-linear-complexity` drops the slowest test.
- **SP 800-90B speed:** 1 to 10 seconds per 1M 1-bit samples; about 30 to 75 seconds per 1M 8-bit samples (*measured*, slower on one core).

### Suggested collection plan

1. **Tier 1: defensible entropy assessment (under 1 MB for 1-bit data).** 3M raw samples plus 1M restart samples. Run SP 800-90B with `--chunks 3 --restart-file restart.bin`.
2. **Tier 2: proper SP 800-22 (about 13 MB).** Add 100 x 1 Mbit.
3. **Tier 3: large-scale suites (1 GB or more).** Enables PractRand at scale, Dieharder and SmallCrush with valid results.
4. **Repeat across conditions:** temperature, time, each device or register, to show the estimate holds.

---

## 5. Reading the results

- **Headline number:** the SP 800-90B non-IID min-entropy per sample, with its limiting estimator and, when `--calibrate` is used, its position against ideal random data.
- **A non-IID value below the symbol size is not a defect.** At 1M samples even ideal data assesses well below the symbol size (about 0.82 to 0.90 for 1-bit samples; about 6.6 to 6.9 for 8-bit samples in earlier tests).
- **Raw data failing the general suites** usually means bias or correlation that the conditioner must remove.
- **An entropy claim also needs** the restart test, runtime health tests, and a documented conditioning and DRBG design (SP 800-90A/B/C).
- **Statistical tests cannot prove physical origin.** A quantum origin is argued from the device physics plus the raw-data assessment.

---

## 6. Output files

| File | Content |
|---|---|
| `raw_report.md` | Detailed report (regenerate with `--report-only DIR`) |
| `raw_summary.json` | All parsed results; the report is built from this |
| `ea_non_iid_chunk*.txt`, `ea_iid_chunk*.txt`, `ea_restart.txt` | Raw tool output |
| `nist_summary.csv`, `nist_pvalues.csv` | SP 800-22 aggregate and per-sequence p-values |
| `dieharder_report.txt`, `practrand_report.txt`, `testu01_<battery>_report.txt` | Suite output |
| `calibration/` | Baseline runs (only with `--calibrate`) |
| `stream.bin` | Bit stream written for the suites when the samples are not 8-bit |

---

## 7. Option reference (`qrng_raw_entropy_tests.py`)

| Option | Meaning |
|---|---|
| `--sample-bits N`, `--packed` | Sample width (1 to 8) and layout |
| `--chunks K`, `--samples-per-chunk M` | Number and size of 90B chunks (default 1 x 1,000,000) |
| `--restart-file F` | Restart data, 1000 x 1000 samples, same layout |
| `--claimed-h X` | Claimed entropy per sample; H_I = min(claimed, estimate) |
| `--track non-iid/auto/iid` | Headline track (default `non-iid`) |
| `--calibrate N` | Ideal-random baseline with N datasets; works with `--report-only` too |
| `--no-iid` | Skip `ea_iid` |
| `--seq-len L`, `--nist-max-seq K`, `--skip-linear-complexity`, `--workers W` | SP 800-22 setup |
| `--skip-diagnostics`, `--skip-90b`, `--skip-nist`, `--skip-dieharder`, `--skip-practrand`, `--testu01 none/small/crush/big` | Choose stages |
| `--force-suites` | Run Dieharder/TestU01 on too little data (results invalid) |
| `--report-only DIR`, `--no-report` | Rebuild or suppress the Markdown report |

`qrng_randomness_tests_v3.py`: `--setup [python dieharder practrand testu01 sp80090b]`, `--list`, `--prefix DIR`, plus the analysis options for spreadsheet input (`--seq-len`, `--practrand`, `--testu01`, `--sp80090b`, and so on).

---

## 8. Verification status and limitations

- **Tested on Linux:** installers for PractRand, TestU01 and SP 800-90B; the full pipeline on synthetic data; the report parsers against real PractRand 0.95, Dieharder and TestU01 output. **Run by the user on an Apple-silicon Mac:** the diagnostics, SP 800-90B, NIST and PractRand stages on `data.bin`.
- **SP 800-22 is a pure-Python implementation, not the official NIST STS.** Cross-check any flagged test with the official suite before a formal claim. Non-overlapping Template runs one template (`000000001`), not all 148.
- **Unofficial sources:** TestU01 is built from a GitHub mirror (the official download URL is unreliable); PractRand from SourceForge with a GitHub mirror fallback.
- **SP 800-90B on macOS** needs Homebrew GCC and a statically built jsoncpp (the installer does both) because Homebrew's jsoncpp uses a C++ library that GCC cannot link. A Docker fallback is possible.
- **Samples wider than 8 bits** are not supported by the NIST 90B tools; reduce them first and state how.
- **The restart test needs separately collected data** and is not generated by this toolkit.
- **Baselines are for ideal data.** A biased source is expected to assess slightly lower than the calibration range.

---

## 9. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `zsh: no matches found: [--flag]` | You typed the brackets from a usage line. Remove them. |
| SP 800-90B skipped, "only N samples" | Wrong layout or too little data. Check the `Loaded N samples` line; use `--sample-bits` / `--packed`; need 1,000,000. |
| SP 800-90B skipped, "tool not found" | `ea_non_iid` not on `PATH`. Run `qrng_randomness_tests_v3.py --setup sp80090b`. |
| `restart file not found` | The path is a placeholder or wrong. Omit `--restart-file` until you have restart data. |
| Dieharder `Error: EOF` or `Cannot open ,` | Input too small, or this Dieharder build ignores `-f`. Use enough data; the Docker build (`apt install dieharder`) handles `-f`. |
| Link errors about `Json::...` building 90B | Fixed by the installer's static jsoncpp step; re-run `--setup sp80090b`. |
| `externally-managed-environment` from pip | The installer creates `~/.local/venv`; the scripts re-launch inside it automatically. |
| NIST stage very slow | Use `--skip-linear-complexity`, `--nist-max-seq`, or more `--workers`. |
