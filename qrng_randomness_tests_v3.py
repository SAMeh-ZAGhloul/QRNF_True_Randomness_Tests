#!/usr/bin/env python3
"""
QRNG randomness test pipeline
-----------------------------
1. Reads an XLS/XLSX/CSV file (column 2 = `data_hex`).
2. Converts every hex string to bits and concatenates them.
3. Writes the stream in the formats the test suites need:
      - <out>/stream.bin   raw binary   (Dieharder, `-g 201`)
      - <out>/stream.txt   ASCII '0'/'1' (NIST STS 'ASCII' input mode)
      - <out>/stream.bits  packed binary (NIST STS 'binary' input mode)
4. Runs:
      a) Full NIST SP 800-22 rev1a suite (15 tests) - pure-Python implementation
         (no external binary needed), applied per-sequence and then aggregated
         exactly as the standard prescribes (proportion + uniformity of P-values).
      b) Dieharder full battery (-a) via the `dieharder` CLI.

v3 adds an automatic prerequisite installer (section 7):

    python qrng_randomness_tests_v3.py --setup            # install everything
    python qrng_randomness_tests_v3.py --setup dieharder testu01   # only some
    python qrng_randomness_tests_v3.py --setup --list     # show what is installed

Components: python packages, dieharder, practrand, testu01, sp80090b.
Everything is built from source into ~/.local (override with --prefix), so no
sudo is needed on macOS. Build logs go to ~/.local/src/_logs/. Already-installed
components are skipped.

Usage
-----
    python qrng_randomness_tests_v3.py data.xls --out results \
           --seq-len 1000000 --alpha 0.01 \
           [--practrand] [--testu01 small] [--sp80090b]

IMPORTANT - sample size
-----------------------
NIST SP 800-22 recommends >= 1,000,000 bits per sequence and >= 55-1000
sequences (alpha=0.01 -> min. ~55 sequences for the proportion test to be
meaningful). That is >= 55 Mbit (~7 MB, ~215,000 rows of 32 bytes).
Dieharder needs hundreds of MB to GBs for the full battery; with less, it
"rewinds" the file and the results are invalid. The script warns you.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

# Heavy scientific imports are optional at start-up so that `--setup` can
# install them first (see section 7).
try:
    import numpy as np
    import pandas as pd
    from scipy import special, stats
    from scipy.fft import fft
    _HAVE_PY_DEPS = True
except ImportError:
    _HAVE_PY_DEPS = False


# ----------------------------------------------------------------------------
# 1. Load + convert
# ----------------------------------------------------------------------------
def load_hex_column(path: str, col_index: int = 1, sheet=0) -> list[str]:
    """Read the 2nd column (index 1) regardless of its header name."""
    ext = Path(path).suffix.lower()
    if ext == ".xls":
        df = pd.read_excel(path, sheet_name=sheet, engine="xlrd", dtype=str)
    elif ext in (".xlsx", ".xlsm"):
        df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl", dtype=str)
    elif ext in (".csv", ".tsv", ".txt"):
        df = pd.read_csv(path, sep=None, engine="python", dtype=str)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    col = df.iloc[:, col_index].dropna().astype(str).str.strip().str.lower()
    col = col.str.replace(r"^0x", "", regex=True)
    bad = ~col.str.fullmatch(r"[0-9a-f]+")
    if bad.any():
        print(f"[warn] dropping {bad.sum()} non-hex rows", file=sys.stderr)
        col = col[~bad]
    return col.tolist()


def hex_to_bits(hex_strings: list[str]) -> np.ndarray:
    """Concatenate all hex strings -> numpy uint8 array of 0/1 (MSB first)."""
    raw = bytes.fromhex("".join(h if len(h) % 2 == 0 else "0" + h for h in hex_strings))
    return np.unpackbits(np.frombuffer(raw, dtype=np.uint8))


def write_streams(bits: np.ndarray, outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    usable = len(bits) - (len(bits) % 8)
    packed = np.packbits(bits[:usable])
    paths = {
        "bin": outdir / "stream.bin",
        "txt": outdir / "stream.txt",
    }
    packed.tofile(paths["bin"])
    with open(paths["txt"], "w") as f:
        f.write("".join(map(str, bits.tolist())))
    return paths


# ----------------------------------------------------------------------------
# 2. NIST SP 800-22 rev1a - the 15 tests
#    Each returns a P-value (float) or a list of P-values.
# ----------------------------------------------------------------------------
def _erfc(x):
    return math.erfc(x)


def _igamc(a, x):
    return special.gammaincc(a, x)


def t01_frequency(b):
    n = len(b)
    s = np.sum(2 * b.astype(np.int64) - 1)
    return _erfc(abs(s) / math.sqrt(n) / math.sqrt(2))


def t02_block_frequency(b, M=128):
    n = len(b)
    N = n // M
    if N == 0:
        return float("nan")
    pi = b[: N * M].reshape(N, M).mean(axis=1)
    chi2 = 4.0 * M * np.sum((pi - 0.5) ** 2)
    return _igamc(N / 2.0, chi2 / 2.0)


def t03_runs(b):
    n = len(b)
    pi = b.mean()
    if abs(pi - 0.5) >= 2.0 / math.sqrt(n):
        return 0.0
    vobs = 1 + np.count_nonzero(b[1:] != b[:-1])
    return _erfc(abs(vobs - 2 * n * pi * (1 - pi)) /
                 (2 * math.sqrt(2 * n) * pi * (1 - pi)))


def t04_longest_run(b):
    n = len(b)
    if n < 128:
        return float("nan")
    if n < 6272:
        M, K, v_lo, v_hi = 8, 3, 1, 4
        pis = [0.2148, 0.3672, 0.2305, 0.1875]
    elif n < 750000:
        M, K, v_lo, v_hi = 128, 5, 4, 9
        pis = [0.1174, 0.2430, 0.2493, 0.1752, 0.1027, 0.1124]
    else:
        M, K, v_lo, v_hi = 10000, 6, 10, 16
        pis = [0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727]
    N = n // M
    blocks = b[: N * M].reshape(N, M)
    counts = np.zeros(K + 1, dtype=np.int64)
    for blk in blocks:
        # longest run of ones
        d = np.diff(np.concatenate(([0], blk, [0])))
        starts = np.where(d == 1)[0]
        ends = np.where(d == -1)[0]
        longest = int((ends - starts).max()) if len(starts) else 0
        idx = min(max(longest, v_lo), v_hi) - v_lo
        counts[idx] += 1
    chi2 = np.sum((counts - N * np.array(pis)) ** 2 / (N * np.array(pis)))
    return _igamc(K / 2.0, chi2 / 2.0)


def _gf2_rank(mat):
    m = mat.copy()
    rows, cols = m.shape
    rank = 0
    for c in range(cols):
        pivot = None
        for r in range(rank, rows):
            if m[r, c]:
                pivot = r
                break
        if pivot is None:
            continue
        m[[rank, pivot]] = m[[pivot, rank]]
        for r in range(rows):
            if r != rank and m[r, c]:
                m[r] ^= m[rank]
        rank += 1
        if rank == rows:
            break
    return rank


def t05_binary_matrix_rank(b, Q=32, M=32):
    n = len(b)
    N = n // (M * Q)
    if N < 38:
        return float("nan")
    ranks = [_gf2_rank(b[i * M * Q:(i + 1) * M * Q].reshape(M, Q).astype(np.uint8))
             for i in range(N)]
    ranks = np.array(ranks)
    Fm = np.sum(ranks == M)
    Fm1 = np.sum(ranks == M - 1)
    Fr = N - Fm - Fm1
    p_full, p_m1, p_rest = 0.2888, 0.5776, 0.1336
    chi2 = ((Fm - p_full * N) ** 2 / (p_full * N) +
            (Fm1 - p_m1 * N) ** 2 / (p_m1 * N) +
            (Fr - p_rest * N) ** 2 / (p_rest * N))
    return math.exp(-chi2 / 2.0)


def t06_dft_spectral(b):
    n = len(b)
    x = 2 * b.astype(np.float64) - 1
    S = np.abs(fft(x))[: n // 2]
    T = math.sqrt(math.log(1 / 0.05) * n)
    N0 = 0.95 * n / 2
    N1 = np.count_nonzero(S < T)
    d = (N1 - N0) / math.sqrt(n * 0.95 * 0.05 / 4)
    return _erfc(abs(d) / math.sqrt(2))


def _bits_to_str(b):
    return "".join(map(str, b.tolist()))


def t07_non_overlapping_template(b, m=9, B=None, N=8):
    """Runs a single template by default (B=000000001) to keep it tractable;
    see `all_aperiodic_templates` if you want the full 148-template run."""
    n = len(b)
    M = n // N
    if B is None:
        B = np.array([0] * (m - 1) + [1], dtype=np.uint8)
    B = np.asarray(B, dtype=np.uint8)
    W = []
    for i in range(N):
        blk = b[i * M:(i + 1) * M]
        cnt, j = 0, 0
        while j <= M - m:
            if np.array_equal(blk[j:j + m], B):
                cnt += 1
                j += m
            else:
                j += 1
        W.append(cnt)
    W = np.array(W)
    mu = (M - m + 1) / 2 ** m
    var = M * (1 / 2 ** m - (2 * m - 1) / 2 ** (2 * m))
    chi2 = np.sum((W - mu) ** 2 / var)
    return _igamc(N / 2.0, chi2 / 2.0)


def all_aperiodic_templates(m=9):
    out = []
    for v in range(2 ** m):
        t = [(v >> (m - 1 - i)) & 1 for i in range(m)]
        ok = True
        for p in range(1, m):
            if t[: m - p] == t[p:]:
                ok = False
                break
        if ok:
            out.append(t)
    return out


def t08_overlapping_template(b, m=9, M=1032, K=5):
    n = len(b)
    N = n // M
    if N == 0:
        return float("nan")
    B = np.ones(m, dtype=np.uint8)
    nu = np.zeros(K + 1, dtype=np.int64)
    for i in range(N):
        blk = b[i * M:(i + 1) * M]
        w = np.lib.stride_tricks.sliding_window_view(blk, m)
        cnt = int(np.sum(np.all(w == B, axis=1)))
        nu[min(cnt, K)] += 1
    # NIST-corrected theoretical probabilities for m=9, M=1032
    pi = np.array([0.364091, 0.185659, 0.139381, 0.100571, 0.0704323, 0.139865])
    chi2 = np.sum((nu - N * pi) ** 2 / (N * pi))
    return _igamc(K / 2.0, chi2 / 2.0)


def t09_universal(b):
    n = len(b)
    if n < 387840:
        return float("nan")
    L_table = [(904960, 7), (2068480, 8), (4654080, 9), (10342400, 10),
               (22753280, 11), (49643520, 12), (107560960, 13),
               (231669760, 14), (496435200, 15), (1059061760, 16)]
    L = 6
    for thr, l in L_table:
        if n >= thr:
            L = l
    expected = {6: (5.2177052, 2.954), 7: (6.1962507, 3.125), 8: (7.1836656, 3.238),
                9: (8.1764248, 3.311), 10: (9.1723243, 3.356), 11: (10.170032, 3.384),
                12: (11.168765, 3.401), 13: (12.168070, 3.410), 14: (13.167693, 3.416),
                15: (14.167488, 3.419), 16: (15.167379, 3.421)}
    ev, var = expected[L]
    Q = 10 * 2 ** L
    K = n // L - Q
    p = 2 ** L
    table = np.zeros(p, dtype=np.int64)
    pw = 1 << np.arange(L - 1, -1, -1)
    blocks = b[: (Q + K) * L].reshape(Q + K, L) @ pw
    for i in range(Q):
        table[blocks[i]] = i + 1
    s = 0.0
    for i in range(Q, Q + K):
        s += math.log2(i + 1 - table[blocks[i]])
        table[blocks[i]] = i + 1
    fn = s / K
    c = 0.7 - 0.8 / L + (4 + 32 / L) * K ** (-3 / L) / 15
    sigma = c * math.sqrt(var / K)
    return _erfc(abs((fn - ev) / (math.sqrt(2) * sigma)))


def _berlekamp_massey(s):
    n = len(s)
    c = np.zeros(n, dtype=np.uint8)
    bb = np.zeros(n, dtype=np.uint8)
    c[0] = bb[0] = 1
    L, m = 0, -1
    for N in range(n):
        d = s[N]
        for i in range(1, L + 1):
            d ^= c[i] & s[N - i]
        if d:
            t = c.copy()
            shift = N - m
            c[shift:] ^= bb[: n - shift]
            if L <= N // 2:
                L = N + 1 - L
                m = N
                bb = t
    return L


def t10_linear_complexity(b, M=500, K=6):
    n = len(b)
    N = n // M
    if N < 200:
        return float("nan")
    mu = M / 2 + (9 + (-1) ** (M + 1)) / 36 - (M / 3 + 2 / 9) / 2 ** M
    pi = np.array([0.010417, 0.03125, 0.125, 0.5, 0.25, 0.0625, 0.020833])
    nu = np.zeros(K + 1, dtype=np.int64)
    for i in range(N):
        L = _berlekamp_massey(b[i * M:(i + 1) * M])
        T = (-1) ** M * (L - mu) + 2 / 9
        if T <= -2.5: nu[0] += 1
        elif T <= -1.5: nu[1] += 1
        elif T <= -0.5: nu[2] += 1
        elif T <= 0.5: nu[3] += 1
        elif T <= 1.5: nu[4] += 1
        elif T <= 2.5: nu[5] += 1
        else: nu[6] += 1
    chi2 = np.sum((nu - N * pi) ** 2 / (N * pi))
    return _igamc(K / 2.0, chi2 / 2.0)


def _psi2(b, m):
    if m == 0:
        return 0.0
    n = len(b)
    ext = np.concatenate([b, b[: m - 1]])
    pw = 1 << np.arange(m - 1, -1, -1)
    idx = np.lib.stride_tricks.sliding_window_view(ext, m)[:n] @ pw
    counts = np.bincount(idx, minlength=2 ** m)
    return (2 ** m / n) * np.sum(counts.astype(np.float64) ** 2) - n


def t11_serial(b, m=None):
    n = len(b)
    if m is None:
        m = max(2, int(math.floor(math.log2(n))) - 5 - 1)
        m = min(m, 16)
    p1 = _psi2(b, m)
    p2 = _psi2(b, m - 1)
    p3 = _psi2(b, m - 2)
    d1 = p1 - p2
    d2 = p1 - 2 * p2 + p3
    return [_igamc(2 ** (m - 2), d1 / 2.0), _igamc(2 ** (m - 3), d2 / 2.0)]


def _phi(b, m):
    n = len(b)
    ext = np.concatenate([b, b[: m - 1]])
    pw = 1 << np.arange(m - 1, -1, -1)
    idx = np.lib.stride_tricks.sliding_window_view(ext, m)[:n] @ pw
    c = np.bincount(idx, minlength=2 ** m) / n
    c = c[c > 0]
    return np.sum(c * np.log(c))


def t12_approximate_entropy(b, m=None):
    n = len(b)
    if m is None:
        m = max(2, int(math.floor(math.log2(n))) - 5 - 1)
        m = min(m, 14)
    ap_en = _phi(b, m) - _phi(b, m + 1)
    chi2 = 2.0 * n * (math.log(2) - ap_en)
    return _igamc(2 ** (m - 1), chi2 / 2.0)


def t13_cumulative_sums(b):
    n = len(b)
    x = 2 * b.astype(np.int64) - 1
    res = []
    for seq in (x, x[::-1]):
        S = np.cumsum(seq)
        z = int(np.max(np.abs(S)))
        k1 = np.arange(int((-n / z + 1) // 4), int((n / z - 1) // 4) + 1)
        k2 = np.arange(int((-n / z - 3) // 4), int((n / z - 1) // 4) + 1)
        sn = math.sqrt(n)
        cdf = stats.norm.cdf
        s1 = np.sum(cdf((4 * k1 + 1) * z / sn) - cdf((4 * k1 - 1) * z / sn))
        s2 = np.sum(cdf((4 * k2 + 3) * z / sn) - cdf((4 * k2 + 1) * z / sn))
        res.append(1.0 - s1 + s2)
    return res


def _excursions(b):
    x = 2 * b.astype(np.int64) - 1
    S = np.concatenate(([0], np.cumsum(x), [0]))
    zero_idx = np.where(S == 0)[0]
    J = len(zero_idx) - 1
    return S, zero_idx, J


def t14_random_excursions(b):
    S, zi, J = _excursions(b)
    if J < 500:
        return [float("nan")] * 8
    states = [-4, -3, -2, -1, 1, 2, 3, 4]
    nu = {x: np.zeros(6, dtype=np.int64) for x in states}
    for a, c in zip(zi[:-1], zi[1:]):
        cyc = S[a:c + 1]
        for x in states:
            nu[x][min(int(np.count_nonzero(cyc == x)), 5)] += 1
    out = []
    for x in states:
        ax = abs(x)
        pi = [1 - 1 / (2 * ax)] + \
             [(1 / (4 * ax ** 2)) * (1 - 1 / (2 * ax)) ** (k - 1) for k in range(1, 5)] + \
             [(1 / (2 * ax)) * (1 - 1 / (2 * ax)) ** 4]
        pi = np.array(pi)
        chi2 = np.sum((nu[x] - J * pi) ** 2 / (J * pi))
        out.append(_igamc(5 / 2.0, chi2 / 2.0))
    return out


def t15_random_excursions_variant(b):
    S, zi, J = _excursions(b)
    if J < 500:
        return [float("nan")] * 18
    out = []
    for x in list(range(-9, 0)) + list(range(1, 10)):
        xi = int(np.count_nonzero(S == x))
        out.append(_erfc(abs(xi - J) / math.sqrt(2 * J * (4 * abs(x) - 2))))
    return out


NIST_TESTS = [
    ("01 Frequency (Monobit)", t01_frequency),
    ("02 Block Frequency", t02_block_frequency),
    ("03 Runs", t03_runs),
    ("04 Longest Run of Ones", t04_longest_run),
    ("05 Binary Matrix Rank", t05_binary_matrix_rank),
    ("06 DFT (Spectral)", t06_dft_spectral),
    ("07 Non-overlapping Template", t07_non_overlapping_template),
    ("08 Overlapping Template", t08_overlapping_template),
    ("09 Maurer's Universal", t09_universal),
    ("10 Linear Complexity", t10_linear_complexity),
    ("11 Serial", t11_serial),
    ("12 Approximate Entropy", t12_approximate_entropy),
    ("13 Cumulative Sums", t13_cumulative_sums),
    ("14 Random Excursions", t14_random_excursions),
    ("15 Random Excursions Variant", t15_random_excursions_variant),
]


def run_nist(bits: np.ndarray, seq_len: int, alpha: float, outdir: Path):
    n_seq = len(bits) // seq_len
    print(f"\n=== NIST SP 800-22: {n_seq} sequences x {seq_len} bits ===")
    if n_seq < 55:
        print(f"[warn] only {n_seq} sequences; NIST recommends >= ~55 for alpha={alpha}. "
              f"Pass/fail proportion results are NOT statistically meaningful.")
    if n_seq == 0:
        print("[error] not enough bits for even one sequence; "
              "lower --seq-len (min useful ~ 10^3-10^5, less valid) or add data.")
        return None

    rows = []  # (test, sequence, p)
    for s in range(n_seq):
        seq = bits[s * seq_len:(s + 1) * seq_len]
        for name, fn in NIST_TESTS:
            try:
                p = fn(seq)
            except Exception as e:  # keep going on failures
                print(f"[warn] {name} seq {s}: {e}", file=sys.stderr)
                p = float("nan")
            plist = p if isinstance(p, list) else [p]
            for k, pv in enumerate(plist):
                label = name if len(plist) == 1 else f"{name} #{k + 1}"
                rows.append((label, s, float(pv)))
        print(f"  sequence {s + 1}/{n_seq} done", end="\r")
    print()

    df = pd.DataFrame(rows, columns=["test", "seq", "p"])
    df.to_csv(outdir / "nist_pvalues.csv", index=False)

    summary = []
    for test, g in df.groupby("test", sort=True):
        p = g["p"].dropna().values
        m = len(p)
        if m == 0:
            summary.append((test, 0, np.nan, np.nan, "N/A (seq too short / n/a)"))
            continue
        # (a) proportion of passing sequences
        prop = np.mean(p >= alpha)
        phat = 1 - alpha
        lo = phat - 3 * math.sqrt(phat * alpha / m)
        hi = phat + 3 * math.sqrt(phat * alpha / m)
        prop_ok = lo <= prop <= hi
        # (b) uniformity of p-values (10 bins chi-square)
        counts, _ = np.histogram(p, bins=10, range=(0, 1))
        chi2 = np.sum((counts - m / 10) ** 2 / (m / 10))
        p_unif = _igamc(9 / 2.0, chi2 / 2.0)
        unif_ok = p_unif >= 0.0001
        verdict = "PASS" if (prop_ok and (unif_ok or m < 55)) else "FAIL"
        summary.append((test, m, prop, p_unif, verdict))

    sdf = pd.DataFrame(summary, columns=["test", "n_p", "proportion", "uniformity_P", "verdict"])
    sdf.to_csv(outdir / "nist_summary.csv", index=False)
    with pd.option_context("display.max_rows", None, "display.width", 140):
        print(sdf.to_string(index=False))
    return sdf


# ----------------------------------------------------------------------------
# 3. Dieharder
# ----------------------------------------------------------------------------
def run_dieharder(bin_path: Path, outdir: Path):
    exe = shutil.which("dieharder")
    if not exe:
        print("\n[error] `dieharder` not found. Install it with: python3 " + Path(sys.argv[0]).name + " --setup dieharder")
        return
    size = bin_path.stat().st_size
    print(f"\n=== Dieharder (-a) on {size:,} bytes ===")
    if size < 100 * 1024 * 1024:
        print("[warn] file < ~100 MB: Dieharder will rewind the file and re-use "
              "the same data; many tests will be INVALID or flag false failures. "
              "Collect far more data for a conclusive result (full -a can consume GBs).")
    out_txt = outdir / "dieharder_report.txt"
    cmd = [exe, "-a", "-g", "201", "-f", str(bin_path)]
    print("running:", " ".join(cmd))
    with open(out_txt, "w") as f:
        subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=False)
    text = out_txt.read_text()
    if "Cannot open" in text:
        print("[info] this dieharder build ignored -f; retrying via stdin (-g 200). "
              "Note: stdin cannot rewind, so dieharder stops when the data runs out.")
        with open(bin_path, "rb") as fin, open(out_txt, "w") as f:
            subprocess.run([exe, "-a", "-g", "200"], stdin=fin, stdout=f,
                           stderr=subprocess.STDOUT, check=False)
        text = out_txt.read_text()
    print(text[-3000:])
    n_pass = text.count("PASSED")
    n_weak = text.count("WEAK")
    n_fail = text.count("FAILED")
    print(f"\nDieharder summary: PASSED={n_pass}  WEAK={n_weak}  FAILED={n_fail}")
    print(f"Full report: {out_txt}")


# ----------------------------------------------------------------------------
def _summarize_failures(text: str, markers):
    return {m: text.count(m) for m in markers}


# ----------------------------------------------------------------------------
# 4. PractRand  (binary: RNG_test)
#    Build: download PractRand from SourceForge, then in its folder:
#      g++ -std=c++14 -O3 -Iinclude tools/RNG_test.cpp src/*.cpp \
#          src/RNGs/*.cpp src/RNGs/other/*.cpp -o RNG_test -pthread
#    and put RNG_test on your PATH (or pass --practrand-exe).
# ----------------------------------------------------------------------------
def run_practrand(bin_path: Path, outdir: Path, exe: str = "RNG_test"):
    exe_path = shutil.which(exe) or (exe if os.path.isfile(exe) else None)
    if not exe_path:
        print("\n[error] PractRand `RNG_test` not found. Install it with: python3 " + Path(sys.argv[0]).name + " --setup practrand")
        return
    size = bin_path.stat().st_size
    print(f"\n=== PractRand on {size:,} bytes ===")
    if size < 64 << 20:
        print("[warn] < 64 MB: PractRand reports from 1 KB upward here (-tlmin 1KB), but "
              "small samples give weak evidence; use hundreds of MB to GBs for a real test.")
    out_txt = outdir / "practrand_report.txt"
    # -tlmin 1KB: by default PractRand prints nothing until much larger sizes.
    # "error reading standard input" at the end is just EOF and is normal.
    cmd = [exe_path, "stdin", "-multithreaded", "-tlmin", "1KB"]
    print("running:", " ".join(cmd), f"< {bin_path}")
    with open(bin_path, "rb") as fin, open(out_txt, "w") as fout:
        subprocess.run(cmd, stdin=fin, stdout=fout, stderr=subprocess.STDOUT, check=False)
    text = out_txt.read_text()
    print(text[-2500:])
    fails = [ln for ln in text.splitlines() if "FAIL" in ln]
    suspicious = [ln for ln in text.splitlines() if "suspicious" in ln.lower()]
    print(f"PractRand summary: FAIL lines={len(fails)}  suspicious lines={len(suspicious)}")
    print(f"Full report: {out_txt}")


# ----------------------------------------------------------------------------
# 5. TestU01  (SmallCrush / Crush / BigCrush) via a small C harness
#    Install: `brew install testu01` (if the formula is available) or build
#    from source; set TESTU01_PREFIX if it lives in a custom prefix.
#    Data needs: SmallCrush ~ 1 GB (measured: a 300 MB file was rewound 3
#    times), Crush ~ tens of GB, BigCrush ~ on the order of 1 TB (rough). A short file is rewound and re-used,
#    which makes results invalid (the harness reports the rewind count).
# ----------------------------------------------------------------------------
TESTU01_C = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "unif01.h"
#include "bbattery.h"

static FILE *fp;
static unsigned long rewinds = 0;

static unsigned int next32(void) {
    uint32_t v;
    if (fread(&v, sizeof v, 1, fp) != 1) {
        rewind(fp);
        rewinds++;
        if (fread(&v, sizeof v, 1, fp) != 1) { fprintf(stderr, "empty file\n"); exit(1); }
    }
    return v;
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s file small|crush|big\n", argv[0]); return 2; }
    fp = fopen(argv[1], "rb");
    if (!fp) { perror("open"); return 1; }
    unif01_Gen *gen = unif01_CreateExternGenBits("qrng-file", next32);
    if (argv[2][0] == 's')      bbattery_SmallCrush(gen);
    else if (argv[2][0] == 'c') bbattery_Crush(gen);
    else                        bbattery_BigCrush(gen);
    unif01_DeleteExternGenBits(gen);
    fflush(stdout);
    fprintf(stderr, "\nFILE REWINDS: %lu (must be 0 for a valid run)\n", rewinds);
    return 0;
}
'''


def _testu01_prefix() -> str:
    prefix = os.environ.get("TESTU01_PREFIX")
    local = Path.home() / ".local"
    if not prefix and (local / "include" / "unif01.h").exists():
        prefix = str(local)
    if not prefix and shutil.which("brew"):
        r = subprocess.run(["brew", "--prefix", "testu01"], capture_output=True, text=True)
        if r.returncode == 0:
            prefix = r.stdout.strip()
    return prefix or "/usr/local"


def run_testu01(bin_path: Path, outdir: Path, battery: str = "small"):
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        print("\n[error] no C compiler found (install Xcode CLT: xcode-select --install)")
        return
    prefix = _testu01_prefix()
    src = outdir / "testu01_runner.c"
    exe = outdir / "testu01_runner"
    src.write_text(TESTU01_C)
    cmd = [cc, "-O2", str(src), "-o", str(exe),
           f"-I{prefix}/include", f"-I{prefix}/include/TestU01",
           f"-L{prefix}/lib", f"-Wl,-rpath,{prefix}/lib",
           "-ltestu01", "-lprobdist", "-lmylib", "-lm"]
    print(f"\n=== TestU01 {battery.upper()} ===")
    comp = subprocess.run(cmd, capture_output=True, text=True)
    if comp.returncode != 0:
        print("[error] compiling TestU01 harness failed (is TestU01 installed? run "
              "--setup testu01, or set TESTU01_PREFIX):\n", comp.stderr[-1500:])
        return
    size = bin_path.stat().st_size
    print(f"input: {size:,} bytes. Running (this can take a long time)...")
    out_txt = outdir / f"testu01_{battery}_report.txt"
    with open(out_txt, "w") as f:
        subprocess.run([str(exe), str(bin_path), battery], stdout=f,
                       stderr=subprocess.STDOUT, check=False)
    text = out_txt.read_text()
    print(text[-2500:])
    if "All tests were passed" in text:
        print("TestU01 verdict: ALL TESTS PASSED")
    elif "outside" in text:
        print("TestU01 verdict: SOME p-values outside [0.001, 0.999] - see report")
    if "FILE REWINDS: 0" not in text:
        print("[warn] input was rewound/reused: result is INVALID. Provide more data.")
    print(f"Full report: {out_txt}")


# ----------------------------------------------------------------------------
# 6. NIST SP 800-90B entropy assessment (ea_non_iid from usnistgov/SP800-90B_EntropyAssessment)
#    ONLY meaningful on RAW noise-source samples taken BEFORE any DRBG/conditioning.
#    Pointing it at DRBG output just reports ~8 bits/byte and says nothing about
#    the entropy source.
# ----------------------------------------------------------------------------
def run_sp80090b(bin_path: Path, outdir: Path, exe: str = "ea_non_iid",
                 bits_per_symbol: int = 8, force: bool = False):
    exe_path = shutil.which(exe) or (exe if os.path.isfile(exe) else None)
    if not exe_path:
        print("\n[error] `ea_non_iid` not found. Install it with: python3 " + Path(sys.argv[0]).name + " --setup sp80090b "
              "(or pass --ea-non-iid /path/to/ea_non_iid)")
        return
    # The NIST tools expect ONE SYMBOL PER BYTE (low bits_per_symbol bits used).
    raw = np.fromfile(bin_path, dtype=np.uint8)
    if bits_per_symbol < 8:
        bits = np.unpackbits(raw)
        usable = len(bits) - len(bits) % bits_per_symbol
        sym = bits[:usable].reshape(-1, bits_per_symbol)
        weights = 1 << np.arange(bits_per_symbol - 1, -1, -1)
        raw = (sym * weights).sum(axis=1).astype(np.uint8)
    sample_file = outdir / f"samples_{bits_per_symbol}bit.bin"
    raw.tofile(sample_file)
    n_samples = len(raw)
    print(f"\n=== SP 800-90B non-IID assessment ({n_samples:,} samples of {bits_per_symbol} bits) ===")
    print("[note] valid only for RAW pre-DRBG noise samples; DRBG output will show ~full entropy.")
    if n_samples < 1_000_000 and not force:
        print("[skip] SP 800-90B needs >= 1,000,000 samples. Use --force-90b to try anyway.")
        return
    out_txt = outdir / "sp800_90b_report.txt"
    with open(out_txt, "w") as f:
        subprocess.run([exe_path, "-v", str(sample_file), str(bits_per_symbol)],
                       stdout=f, stderr=subprocess.STDOUT, check=False)
    print(out_txt.read_text()[-2500:])
    print(f"Full report: {out_txt}")


# ----------------------------------------------------------------------------
# 7. Automatic prerequisite installation (--setup)
#    Builds everything from source into ~/.local (no sudo on macOS).
#    macOS needs Homebrew + Xcode command line tools (xcode-select --install).
#    Debian/Ubuntu uses apt (sudo) for build dependencies.
#    Build logs: <prefix>/src/_logs/<component>.log
# ----------------------------------------------------------------------------
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"
COMPONENTS = ["python", "dieharder", "practrand", "testu01", "sp80090b"]
PY_PACKAGES = {  # import name -> pip name
    "numpy": "numpy", "scipy": "scipy", "pandas": "pandas",
    "xlrd": "xlrd", "openpyxl": "openpyxl",
}


def add_prefix_to_path(prefix: Path):
    b = str(prefix / "bin")
    parts = os.environ.get("PATH", "").split(os.pathsep)
    if b not in parts:
        os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")


def component_status(prefix: Path) -> dict:
    py_ok = all(importlib.util.find_spec(m) is not None for m in PY_PACKAGES)
    vpy = prefix / "venv" / "bin" / "python"
    if not py_ok and vpy.exists():
        r = subprocess.run([str(vpy), "-c", "import " + ",".join(PY_PACKAGES)],
                           capture_output=True)
        py_ok = r.returncode == 0
    tu_ok = any((Path(p) / "include" / "unif01.h").exists()
                for p in (os.environ.get("TESTU01_PREFIX", str(prefix)), str(prefix)))
    return {
        "python": py_ok,
        "dieharder": bool(shutil.which("dieharder")),
        "practrand": bool(shutil.which("RNG_test")),
        "testu01": tu_ok,
        "sp80090b": bool(shutil.which("ea_non_iid")),
    }


class Installer:
    def __init__(self, prefix: Path):
        self.prefix = prefix
        self.src = prefix / "src"
        self.logs = self.src / "_logs"
        self.logs.mkdir(parents=True, exist_ok=True)
        (prefix / "bin").mkdir(parents=True, exist_ok=True)
        add_prefix_to_path(prefix)
        self.brew = shutil.which("brew")
        self.env = self._build_env()

    # -- helpers ----------------------------------------------------------
    def brew_prefix(self, pkg=None):
        if not self.brew:
            return None
        cmd = [self.brew, "--prefix"] + ([pkg] if pkg else [])
        r = subprocess.run(cmd, capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None

    def _build_env(self):
        env = os.environ.copy()
        inc = [str(self.prefix / "include")]
        lib = [str(self.prefix / "lib")]
        pkgcfg = [str(self.prefix / "lib" / "pkgconfig")]
        for pkg in (None, "openssl@3"):
            p = self.brew_prefix(pkg)
            if p:
                inc.append(p + "/include")
                lib.append(p + "/lib")
                pkgcfg.append(p + "/lib/pkgconfig")
        sep = os.pathsep
        # CPATH / LIBRARY_PATH are honoured by gcc and clang even when a
        # Makefile hard-codes its own CXXFLAGS.
        env["CPATH"] = sep.join(inc + [env.get("CPATH", "")]).strip(sep)
        env["LIBRARY_PATH"] = sep.join(lib + [env.get("LIBRARY_PATH", "")]).strip(sep)
        env["CPPFLAGS"] = (" ".join(f"-I{i}" for i in inc) + " " + env.get("CPPFLAGS", "")).strip()
        env["LDFLAGS"] = (" ".join(f"-L{l}" for l in lib) + " " + env.get("LDFLAGS", "")).strip()
        env["PKG_CONFIG_PATH"] = sep.join(pkgcfg + [env.get("PKG_CONFIG_PATH", "")]).strip(sep)
        return env

    def run(self, cmd, name, cwd=None, shell=False) -> bool:
        log = self.logs / f"{name}.log"
        shown = cmd if isinstance(cmd, str) else " ".join(map(str, cmd))
        print(f"    $ {shown}")
        with open(log, "a") as lf:
            lf.write(f"\n$ {shown}\n")
            lf.flush()
            try:
                r = subprocess.run(cmd, cwd=cwd, env=self.env, shell=shell,
                                   stdout=lf, stderr=subprocess.STDOUT)
            except FileNotFoundError as e:
                lf.write(f"command not found: {e}\n")
                return False
        return r.returncode == 0

    def fail(self, name, msg="") -> bool:
        log = self.logs / f"{name}.log"
        print(f"  [FAILED] {name}. {msg}".rstrip())
        if log.exists():
            tail = log.read_text(errors="replace").splitlines()[-15:]
            print(f"  --- last lines of {log} ---")
            for ln in tail:
                print("  | " + ln)
        return False

    def sys_pkgs(self, name, brew_pkgs, apt_pkgs) -> bool:
        if IS_MAC:
            if not self.brew:
                print("  [error] Homebrew is required on macOS: https://brew.sh")
                return False
            ok = True
            for p in brew_pkgs:
                have = subprocess.run([self.brew, "list", "--versions", p],
                                      capture_output=True, text=True).stdout.strip()
                if not have:
                    if not self.run([self.brew, "install", p], name):
                        print(f"  [warn] `brew install {p}` failed")
                        ok = False
            return ok
        if IS_LINUX and shutil.which("apt-get"):
            sudo = [] if os.geteuid() == 0 else ["sudo"]
            self.run(sudo + ["apt-get", "update", "-qq"], name)
            return self.run(sudo + ["apt-get", "install", "-y", *apt_pkgs], name)
        print("  [error] unsupported platform: install build tools manually")
        return False

    def need_tools(self) -> bool:
        if not shutil.which("git"):
            print("  [error] git not found" +
                  (" - run: xcode-select --install" if IS_MAC else ""))
            return False
        if not (shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")):
            print("  [error] no C compiler" +
                  (" - run: xcode-select --install" if IS_MAC else ""))
            return False
        return True

    def clone(self, name, url, dest: Path):
        if (dest / ".git").exists():
            return dest
        if dest.exists():
            shutil.rmtree(dest)
        return dest if self.run(["git", "clone", "--depth", "1", url, str(dest)], name) else None

    def refresh_config_scripts(self, srcdir: Path):
        """Old autotools trees do not know Apple Silicon: copy fresh
        config.sub / config.guess from Homebrew's automake over the old ones."""
        p = self.brew_prefix("automake")
        if not p:
            return
        cands = sorted((Path(p) / "share").glob("automake-*"))
        if not cands:
            return
        for f in ("config.sub", "config.guess"):
            s = cands[-1] / f
            if s.exists():
                for target in srcdir.rglob(f):
                    shutil.copy(s, target)

    def install_bins(self, files):
        n = 0
        for f in files:
            f = Path(f)
            if f.is_file() and os.access(f, os.X_OK):
                shutil.copy(f, self.prefix / "bin" / f.name)
                n += 1
        return n

    # -- components -------------------------------------------------------
    def python(self) -> bool:
        vpy = self.prefix / "venv" / "bin" / "python"
        if component_status(self.prefix)["python"]:
            print("  python packages: already installed")
            return True
        missing = [pip for imp, pip in PY_PACKAGES.items()
                   if importlib.util.find_spec(imp) is None]
        print(f"  installing python packages: {' '.join(missing)}")
        if self.run([sys.executable, "-m", "pip", "install", *missing], "python"):
            return True
        log = (self.logs / "python.log").read_text(errors="replace")
        if "externally-managed" in log or "externally managed" in log:
            print("  system Python is locked (PEP 668); creating a private virtualenv "
                  f"at {self.prefix / 'venv'}")
            ok = (self.run([sys.executable, "-m", "venv", str(self.prefix / "venv")], "python")
                  and self.run([str(vpy), "-m", "pip", "install", *PY_PACKAGES.values()],
                               "python"))
            if ok:
                print("  OK. This script re-launches itself inside that venv automatically.")
                return True
        return self.fail("python")

    def dieharder(self) -> bool:
        if shutil.which("dieharder"):
            print(f"  dieharder: already installed ({shutil.which('dieharder')})")
            return True
        if IS_LINUX and shutil.which("apt-get"):
            return self.sys_pkgs("dieharder", [], ["dieharder"]) or self.fail("dieharder")
        if not self.need_tools():
            return False
        self.sys_pkgs("dieharder", ["gsl", "autoconf", "automake", "libtool", "pkg-config"], [])
        d = self.clone("dieharder", "https://github.com/eddelbuettel/dieharder.git",
                       self.src / "dieharder")
        if not d:
            return self.fail("dieharder", "git clone failed")
        ok = self.run(["autoreconf", "-i"], "dieharder", cwd=d)
        self.refresh_config_scripts(d)
        ok = (ok and self.run(["./configure", f"--prefix={self.prefix}"], "dieharder", cwd=d)
              and self.run(["make", "-j4"], "dieharder", cwd=d)
              and self.run(["make", "install"], "dieharder", cwd=d))
        return ok or self.fail("dieharder")

    def _practrand_root(self, base: Path):
        for p in base.rglob("RNG_test.cpp"):
            root = p.parent.parent
            if (root / "src").is_dir() and (root / "include").is_dir():
                return root
        return None

    def _practrand_build(self, root: Path) -> bool:
        cxx = shutil.which("g++") or shutil.which("c++") or shutil.which("clang++")
        if not cxx:
            return False
        flags = "-O3 -Iinclude -pthread -std=gnu++11"
        steps = [
            f"{cxx} -c src/*.cpp src/RNGs/*.cpp src/RNGs/other/*.cpp {flags}",
            "ar rcs libPractRand.a *.o",
            f"{cxx} -o RNG_test tools/RNG_test.cpp libPractRand.a {flags}",
        ]
        for s in steps:
            if not self.run(s, "practrand", cwd=root, shell=True):
                return False
        return self.install_bins([root / "RNG_test"]) == 1

    def practrand(self) -> bool:
        if shutil.which("RNG_test"):
            print(f"  practrand: already installed ({shutil.which('RNG_test')})")
            return True
        if IS_LINUX and shutil.which("apt-get"):
            self.sys_pkgs("practrand", [], ["build-essential", "git"])
        if not self.need_tools():
            return False
        base = self.src / "PractRand"
        # 1) official SourceForge zip
        try:
            base.mkdir(parents=True, exist_ok=True)
            z = self.src / "PractRand-pre0.95.zip"
            url = "https://downloads.sourceforge.net/project/pracrand/PractRand-pre0.95.zip"
            print(f"    downloading {url}")
            urllib.request.urlretrieve(url, z)
            if zipfile.is_zipfile(z):
                with zipfile.ZipFile(z) as zf:
                    zf.extractall(base)
                root = self._practrand_root(base)
                if root and self._practrand_build(root):
                    return True
            else:
                print("    download was not a zip file (SourceForge redirect page?)")
        except Exception as e:
            print(f"    SourceForge download failed: {e}")
        # 2) GitHub mirror
        print("  trying GitHub mirror MartyMacGyver/PractRand")
        d = self.clone("practrand", "https://github.com/MartyMacGyver/PractRand.git",
                       self.src / "PractRand-git")
        if d and self._practrand_build(d):
            return True
        return self.fail("practrand",
                         "On Apple Silicon this old C++ code may not build natively; "
                         "try running this script under Rosetta: arch -x86_64 python3 ...")

    def testu01(self) -> bool:
        if component_status(self.prefix)["testu01"]:
            print("  testu01: already installed")
            return True
        if IS_LINUX and shutil.which("apt-get"):
            self.sys_pkgs("testu01", [], ["build-essential", "autoconf", "automake",
                                          "libtool", "git"])
        else:
            self.sys_pkgs("testu01", ["autoconf", "automake", "libtool"], [])
        if not self.need_tools():
            return False
        # Unofficial GitHub mirror of TestU01 1.2.3 (the official zip URL is unreliable).
        d = self.clone("testu01", "https://github.com/blep/TestU01.git", self.src / "TestU01")
        if not d:
            return self.fail("testu01", "git clone failed")
        self.refresh_config_scripts(d)

        def build():
            return (self.run(["./configure", f"--prefix={self.prefix}"], "testu01", cwd=d)
                    and self.run(["make", "-j4"], "testu01", cwd=d)
                    and self.run(["make", "install"], "testu01", cwd=d))

        if build():
            return True
        print("  retrying after regenerating the autotools files ...")
        self.run(["glibtoolize" if IS_MAC else "libtoolize", "--force", "--copy"],
                 "testu01", cwd=d)
        self.run(["autoreconf", "-fi"], "testu01", cwd=d)
        self.refresh_config_scripts(d)
        return build() or self.fail("testu01")

    def sp80090b(self) -> bool:
        import re
        if shutil.which("ea_non_iid"):
            print(f"  sp800-90b: already installed ({shutil.which('ea_non_iid')})")
            return True
        if IS_LINUX and shutil.which("apt-get"):
            self.sys_pkgs("sp80090b", [], ["build-essential", "git", "libbz2-dev",
                                           "libdivsufsort-dev", "libjsoncpp-dev",
                                           "libssl-dev", "libmpfr-dev", "libgmp-dev"])
        else:
            # GCC (OpenMP) is the only compiler NIST tests; Apple clang has no -fopenmp.
            self.sys_pkgs("sp80090b", ["gcc", "libdivsufsort", "jsoncpp", "openssl@3",
                                       "mpfr", "gmp"], [])
        if not self.need_tools():
            return False
        d = self.clone("sp80090b", "https://github.com/usnistgov/SP800-90B_EntropyAssessment.git",
                       self.src / "SP800-90B")
        if not d:
            return self.fail("sp80090b", "git clone failed")
        cpp = d / "cpp"
        cxx = None
        if IS_MAC:
            bp = self.brew_prefix()
            gpp = sorted(Path(bp or "/opt/homebrew").glob("bin/g++-[0-9]*"))
            cxx = str(gpp[-1]) if gpp else None
            if not cxx:
                print("  [warn] Homebrew g++ not found; falling back to the default compiler "
                      "(OpenMP may fail)")
        mk = cpp / "Makefile"
        if mk.exists():
            t = mk.read_text()
            t2 = t.replace("-march=native", "")  # not supported on Apple Silicon gcc
            if cxx:
                t2 = re.sub(r"(?<![\w-])g\+\+(?![\w+-])", cxx, t2)
            if t2 != t:
                mk.write_text(t2)
        cmd = ["make", "-j4", "iid", "non_iid", "restart"]
        if cxx:
            cmd.append(f"CXX={cxx}")
        if not self.run(cmd, "sp80090b", cwd=cpp):
            return self.fail("sp80090b",
                             "Paste the log tail above if you want help; the NIST "
                             "Makefile is only tested by NIST on GCC/Linux.")
        n = self.install_bins(sorted(cpp.glob("ea_*")))
        return n > 0 or self.fail("sp80090b", "build produced no ea_* binaries")


def run_setup(components, prefix: Path, list_only=False) -> bool:
    status = component_status(prefix)
    print(f"\n=== Prerequisite status (prefix: {prefix}) ===")
    for c in COMPONENTS:
        print(f"  {c:<10} {'installed' if status[c] else 'MISSING'}")
    if list_only:
        return all(status.values())
    inst = Installer(prefix)
    results = {}
    for c in COMPONENTS:  # fixed order: python first
        if c not in components:
            continue
        print(f"\n--- {c} ---")
        try:
            results[c] = getattr(inst, c)()
        except Exception as e:  # never let one component abort the rest
            print(f"  [error] {c}: {e}")
            results[c] = False
    print("\n=== Setup summary ===")
    for c, ok in results.items():
        print(f"  {c:<10} {'OK' if ok else 'FAILED (see log above)'}")
    print(f"\nBinaries are in {prefix}/bin (this script adds it to PATH automatically). "
          f"To use them in your shell too:\n  export PATH=\"{prefix}/bin:$PATH\"\n"
          f"  export TESTU01_PREFIX=\"{prefix}\"")
    return all(results.values())


def main():
    ap = argparse.ArgumentParser(
        description="QRNG randomness test pipeline (NIST SP 800-22, Dieharder, PractRand, "
                    "TestU01, SP 800-90B) with automatic prerequisite installation.")
    ap.add_argument("xls", nargs="?",
                    help="input .xls/.xlsx/.csv (2nd column = hex data); "
                         "omit when only using --setup")
    ap.add_argument("--setup", nargs="*", metavar="COMPONENT",
                    help="install prerequisites (default: all of "
                         + ", ".join(COMPONENTS) + ") and exit")
    ap.add_argument("--list", action="store_true",
                    help="show which prerequisites are installed and exit")
    ap.add_argument("--prefix", default=None,
                    help="install prefix for --setup (default ~/.local)")
    ap.add_argument("--out", default="results")
    ap.add_argument("--sheet", default=0)
    ap.add_argument("--seq-len", type=int, default=1_000_000,
                    help="bits per NIST sequence (default 1,000,000)")
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--skip-nist", action="store_true")
    ap.add_argument("--skip-dieharder", action="store_true")
    ap.add_argument("--practrand", action="store_true", help="run PractRand")
    ap.add_argument("--practrand-exe", default="RNG_test")
    ap.add_argument("--testu01", choices=["small", "crush", "big"],
                    help="run a TestU01 battery (SmallCrush/Crush/BigCrush)")
    ap.add_argument("--sp80090b", action="store_true",
                    help="run NIST SP 800-90B ea_non_iid (RAW pre-DRBG samples only)")
    ap.add_argument("--ea-non-iid", default="ea_non_iid")
    ap.add_argument("--bits-per-symbol", type=int, default=8)
    ap.add_argument("--force-90b", action="store_true",
                    help="run 90B even with < 1,000,000 samples")
    args = ap.parse_args()

    prefix = Path(args.prefix).expanduser() if args.prefix else Path.home() / ".local"
    add_prefix_to_path(prefix)          # tools installed by --setup are found automatically
    if "TESTU01_PREFIX" not in os.environ and (prefix / "include" / "unif01.h").exists():
        os.environ["TESTU01_PREFIX"] = str(prefix)

    vpy = prefix / "venv" / "bin" / "python"
    if (not _HAVE_PY_DEPS and vpy.exists() and not os.environ.get("QRNG_IN_VENV")
            and args.setup is None and not args.list):
        os.environ["QRNG_IN_VENV"] = "1"
        os.execv(str(vpy), [str(vpy)] + sys.argv)

    if args.setup is not None or args.list:
        comps = args.setup if args.setup else COMPONENTS
        bad = [c for c in comps if c not in COMPONENTS]
        if bad:
            ap.error(f"unknown component(s): {', '.join(bad)} "
                     f"(choose from {', '.join(COMPONENTS)})")
        ok = run_setup(comps, prefix, list_only=args.list or args.setup is None)
        if not args.xls:
            sys.exit(0 if (ok or args.list) else 1)
        if not _HAVE_PY_DEPS:
            print("\nPython packages were just installed: re-run the command "
                  "(without --setup) to run the tests.")
            sys.exit(0 if ok else 1)

    if not _HAVE_PY_DEPS:
        sys.exit("Required Python packages (numpy, scipy, pandas, xlrd, openpyxl) are "
                 "missing.\nInstall them with:  python3 "
                 f"{Path(sys.argv[0]).name} --setup python")
    if not args.xls:
        ap.error("input file is required (or use --setup / --list)")

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    hexes = load_hex_column(args.xls, col_index=1, sheet=args.sheet)
    print(f"Loaded {len(hexes):,} hex strings")
    bits = hex_to_bits(hexes)
    print(f"Total bits: {len(bits):,}  ({len(bits) / 8:,.0f} bytes)  "
          f"ones-ratio = {bits.mean():.6f}")
    paths = write_streams(bits, outdir)

    if not args.skip_nist:
        run_nist(bits, args.seq_len, args.alpha, outdir)
    if not args.skip_dieharder:
        run_dieharder(paths["bin"], outdir)
    if args.practrand:
        run_practrand(paths["bin"], outdir, args.practrand_exe)
    if args.testu01:
        run_testu01(paths["bin"], outdir, args.testu01)
    if args.sp80090b:
        run_sp80090b(paths["bin"], outdir, args.ea_non_iid,
                     args.bits_per_symbol, args.force_90b)

    print("\nNOTE: passing these tests is necessary, not sufficient, for 'true' randomness. "
          "This data is CTR-DRBG output, so the tests see the DRBG, not the qubit entropy. "
          "Use NIST SP 800-90B on raw (pre-DRBG) noise samples to assess the entropy source.")


if __name__ == "__main__":
    main()
