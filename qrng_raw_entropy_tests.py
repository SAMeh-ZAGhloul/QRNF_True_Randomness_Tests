#!/usr/bin/env python3
"""
qrng_raw_entropy_tests.py - assess RAW (pre-DRBG) noise-source samples in a binary file
========================================================================================

Input: a binary file (e.g. data.bin) of raw samples straight from the entropy source,
before any conditioning or DRBG.

What it runs
------------
 1. Quick diagnostics (numpy): symbol histogram, Shannon and MCV min-entropy, chi-square,
    serial correlation (lags 1-16), stationarity across 10 slices, longest identical run,
    compressibility.
 2. NIST SP 800-90B entropy assessment (ea_non_iid, ea_iid, optional ea_restart). THIS IS
    THE STANDARD ASSESSMENT FOR A RAW NOISE SOURCE: it yields min-entropy per sample.
 3. Statistical batteries on the bit stream: NIST SP 800-22 (parallel), Dieharder,
    PractRand, TestU01. These are diagnostics here: raw noise is normally biased or
    correlated and is NOT expected to look full-entropy until it has been conditioned.

A detailed Markdown report (raw_report.md) is written to the output folder at the end of the run;
regenerate it later with  --report-only DIR.

It re-uses the runners and installer in qrng_randomness_tests_v3.py (keep it in the same
folder, or pass --v3 PATH).  Install the external tools with:

    python3 qrng_randomness_tests_v3.py --setup

Sample layout (IMPORTANT, set it correctly)
-------------------------------------------
  --sample-bits N   bits per raw sample, 1..8   (default 8: one byte = one sample)
  --packed          samples are packed back-to-back in the file, MSB first (needed to
                    describe e.g. 1-bit samples stored 8 per byte).  Without --packed,
                    each byte holds ONE sample in its low N bits (the layout the NIST
                    tools themselves use).
  Samples wider than 8 bits (e.g. 12-bit ADC words) are not supported by the 90B tools;
  reduce them first (e.g. keep the low 8 bits) and say so when you interpret the result.

Examples
--------
  python3 qrng_raw_entropy_tests.py data.bin --out raw_results
  python3 qrng_raw_entropy_tests.py data.bin --sample-bits 1 --packed --out raw_results
  python3 qrng_raw_entropy_tests.py data.bin --restart-file restart.bin --claimed-h 7.0
"""
from __future__ import annotations

import argparse
import bz2
import importlib.util
import json
import lzma
import math
import os
import re
import shutil
import subprocess
import sys
import time
import zlib
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCAL = Path.home() / ".local"

try:
    import numpy as np
    from scipy import special, stats
except ImportError:
    _vpy = LOCAL / "venv" / "bin" / "python"
    if _vpy.exists() and not os.environ.get("QRNG_IN_VENV"):
        os.environ["QRNG_IN_VENV"] = "1"
        os.execv(str(_vpy), [str(_vpy)] + sys.argv)
    sys.exit("numpy/scipy are missing. Run: python3 qrng_randomness_tests_v3.py --setup python")


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def load_v3(explicit=None):
    cands = [Path(explicit)] if explicit else [HERE / "qrng_randomness_tests_v3.py",
                                              Path.cwd() / "qrng_randomness_tests_v3.py"]
    for c in cands:
        if c.exists():
            spec = importlib.util.spec_from_file_location("qrng_v3", c)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    sys.exit("qrng_randomness_tests_v3.py not found next to this script (it provides the "
             "NIST/Dieharder/PractRand/TestU01 runners). Put it in the same folder or use --v3 PATH.")


def symbols_to_bits(sym: "np.ndarray", sb: int) -> "np.ndarray":
    if sb == 8:
        return np.unpackbits(sym)
    shifts = np.arange(sb - 1, -1, -1, dtype=np.uint8)
    return ((sym[:, None] >> shifts) & 1).astype(np.uint8).ravel()


def load_samples(path, sb, packed, max_bytes=None) -> "np.ndarray":
    raw = np.fromfile(path, dtype=np.uint8, count=-1 if not max_bytes else int(max_bytes))
    if sb == 8:
        return raw
    if packed:
        bits = np.unpackbits(raw)
        usable = len(bits) - len(bits) % sb
        sym = bits[:usable].reshape(-1, sb)
        weights = (1 << np.arange(sb - 1, -1, -1)).astype(np.uint16)
        return (sym.astype(np.uint16) * weights).sum(axis=1).astype(np.uint8)
    mask = (1 << sb) - 1
    if (raw > mask).any():
        print(f"[warn] some bytes exceed {sb}-bit values; masking to the low {sb} bits "
              f"(is --packed missing?)")
    return raw & mask


def write_bit_stream(sym, sb, path: Path):
    """Write the sample stream as a packed bit stream (MSB first), in chunks."""
    step = 16_000_000
    carry = np.zeros(0, dtype=np.uint8)
    with open(path, "wb") as f:
        for i in range(0, len(sym), step):
            bits = np.concatenate([carry, symbols_to_bits(sym[i:i + step], sb)])
            usable = len(bits) - len(bits) % 8
            np.packbits(bits[:usable]).tofile(f)
            carry = bits[usable:]


def run_cmd(cmd, outfile: Path, cwd=None):
    with open(outfile, "w") as f:
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=cwd)
    return r.returncode, outfile.read_text(errors="replace")


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


# ----------------------------------------------------------------------------
# 1. diagnostics
# ----------------------------------------------------------------------------
def diagnostics(sym, sb, max_n):
    s = sym[:max_n]
    n = len(s)
    k = 1 << sb
    counts = np.bincount(s, minlength=k).astype(np.float64)
    p = counts / n
    nz = p[p > 0]
    shannon = float(-(nz * np.log2(nz)).sum())
    pmax = float(p.max())
    pu = min(1.0, pmax + 2.576 * math.sqrt(pmax * (1 - pmax) / (n - 1)))
    mcv = -math.log2(pu)
    exp = n / k
    chi2 = float(((counts - exp) ** 2 / exp).sum())
    chi_p = float(special.gammaincc((k - 1) / 2, chi2 / 2))

    x = s.astype(np.float64)
    x -= x.mean()
    den = float((x * x).sum())
    lags = []
    for L in range(1, 17):
        r = float((x[:-L] * x[L:]).sum() / den) if den > 0 else 0.0
        z = r * math.sqrt(n)
        lags.append((L, r, math.erfc(abs(z) / math.sqrt(2))))

    ch = np.flatnonzero(np.diff(s) != 0)
    runs = np.diff(np.concatenate(([-1], ch, [n - 1])))
    longest = int(runs.max())
    exp_longest = math.log(n * (k - 1) / k) / math.log(k) + 1 if k > 1 else float("nan")

    parts = np.array_split(s, 10)
    tbl = np.array([np.bincount(pt, minlength=k) for pt in parts])
    tbl = tbl[:, tbl.sum(axis=0) > 0]
    homog_p = None
    low_expected = n / (10 * k) < 5
    if tbl.shape[1] > 1:
        homog_p = float(stats.chi2_contingency(tbl)[1])

    nbytes = 2_000_000
    sample = s[: max(1, (nbytes * 8) // sb)]
    packed = np.packbits(symbols_to_bits(sample, sb)).tobytes()
    comp = {"zlib-9": len(zlib.compress(packed, 9)) / len(packed),
            "bz2": len(bz2.compress(packed)) / len(packed),
            "lzma": len(lzma.compress(packed)) / len(packed)}
    return {
        "n": n, "k": k, "shannon": shannon, "shannon_eff": shannon / sb,
        "pmax": pmax, "mcv_min_entropy": mcv, "mcv_per_bit": mcv / sb,
        "chi2": chi2, "chi2_p": chi_p, "lags": lags,
        "longest_run": longest, "expected_longest_run": exp_longest,
        "homogeneity_p": homog_p, "homogeneity_low_expected": low_expected,
        "compression": comp,
    }


def print_diagnostics(d, sb):
    print(f"\n=== 1. Diagnostics ({d['n']:,} samples of {sb} bit(s)) ===")
    print(f"  Shannon entropy        : {d['shannon']:.4f} / {sb} bits  ({d['shannon_eff']:.4f} per bit)")
    print(f"  MCV min-entropy (99%)  : {d['mcv_min_entropy']:.4f} / {sb} bits  ({d['mcv_per_bit']:.4f} per bit)")
    print(f"  Most common value freq : {d['pmax']:.6f}  (uniform = {1 / d['k']:.6f})")
    print(f"  Chi-square uniformity  : chi2={d['chi2']:.1f}  p={d['chi2_p']:.4g}")
    worst = min(d["lags"], key=lambda t: t[2])
    print(f"  Serial correlation     : most extreme lag {worst[0]}: r={worst[1]:+.5f}  p={worst[2]:.4g}"
          f"  (16 lags tested; expect min p ~ 0.06; flagged only below {0.001 / 16:.2g})")
    print(f"  Longest identical run  : {d['longest_run']}  (uniform-source expectation ~ {d['expected_longest_run']:.1f})")
    if d["homogeneity_p"] is not None:
        extra = "  [low expected counts: unreliable]" if d["homogeneity_low_expected"] else ""
        print(f"  Stationarity (10 slices): chi-square homogeneity p={d['homogeneity_p']:.4g}{extra}")
    print("  Compression ratio      : " + "  ".join(f"{k}={v:.4f}" for k, v in d["compression"].items())
          + "   (1.00 = incompressible)")


# ----------------------------------------------------------------------------
# 2. SP 800-90B
# ----------------------------------------------------------------------------
EST_RE = re.compile(r"^\s*(.+?Estimate)\s*=\s*([0-9.]+)\s*/\s*(\d+)\s*bit", re.M)


def parse_90b(text):
    out = {}
    for key in ("H_original", "H_bitstring"):
        m = re.search(rf"^{key}:\s*([0-9.]+)", text, re.M)
        if m:
            out[key] = float(m.group(1))
    m = re.search(r"^min\(H_original,\s*\d+\s*X\s*H_bitstring\):\s*([0-9.]+)", text, re.M)
    if m:
        out["final"] = float(m.group(1))
    elif "H_original" in out:
        out["final"] = out["H_original"]
    out["estimators"] = [(a.strip(), float(b)) for a, b, _ in EST_RE.findall(text)]
    checks = re.findall(r"\*\* (Passed|Failed) ([^\n.]+)", text)
    if checks:
        out["iid_checks"] = [(v, w.strip()) for v, w in checks]
        out["iid_ok"] = all(v == "Passed" for v, _ in checks)
    return out


def parse_restart(text):
    out = {}
    for key in ("H_r", "H_c", "H_I"):
        m = re.search(rf"^{key}:\s*([0-9.]+)", text, re.M)
        if m:
            out[key] = float(m.group(1))
    m = re.search(r"^min\(H_r, H_c, H_I\):\s*([0-9.]+)", text, re.M)
    if m:
        out["final"] = float(m.group(1))
    out["sanity_failed"] = "Sanity Check Failed" in text
    out["validation_passed"] = "Validation Test Passed" in text
    return out


_REASON = {}


def stage_90b(sym, sb, outdir, args):
    exe_n, exe_i, exe_r = (shutil.which(x) for x in ("ea_non_iid", "ea_iid", "ea_restart"))
    print(f"\n=== 2. NIST SP 800-90B entropy assessment ({sb}-bit samples) ===")
    if not exe_n:
        print("[error] ea_non_iid not found on PATH. Install: python3 qrng_randomness_tests_v3.py --setup sp80090b")
        _REASON["90b"] = "tool not found: ea_non_iid is not on PATH (run --setup sp80090b)"
        return None
    n = len(sym)
    if n < 1_000_000:
        print(f"[skip] only {n:,} samples of {sb} bit(s) ({n * sb / 8 / 1e6:.2f} MB). SP 800-90B needs at least "
              f"1,000,000 consecutive samples. If your file holds {sb}-bit samples packed back-to-back, "
              f"check --sample-bits / --packed.")
        _REASON["90b"] = (f"only {n:,} samples; SP 800-90B requires at least 1,000,000 "
                          f"(check --sample-bits / --packed if the layout is wrong)")
        return None
    csz = args.samples_per_chunk
    chunks = max(1, min(args.chunks, n // csz))
    res = {"bits_per_sample": sb, "chunks": chunks, "samples_per_chunk": csz,
           "non_iid": [], "iid": []}
    for c in range(chunks):
        fname = f"samples_chunk{c}.bin"
        sym[c * csz:(c + 1) * csz].tofile(outdir / fname)
        print(f"  chunk {c + 1}/{chunks}: ea_non_iid ...")
        t = time.time()
        _, txt = run_cmd([exe_n, "-v", fname, str(sb)], outdir / f"ea_non_iid_chunk{c}.txt", cwd=outdir)
        p = parse_90b(txt)
        res["non_iid"].append(p)
        print(f"    H (non-IID) = {p.get('final', float('nan')):.4f} bits/sample  ({time.time() - t:.0f}s)")
        if exe_i and not args.no_iid:
            print(f"  chunk {c + 1}/{chunks}: ea_iid ...")
            t = time.time()
            _, txt = run_cmd([exe_i, fname, str(sb)], outdir / f"ea_iid_chunk{c}.txt", cwd=outdir)
            p = parse_90b(txt)
            res["iid"].append(p)
            verdict = "passed" if p.get("iid_ok") else "FAILED"
            print(f"    H (IID) = {p.get('final', float('nan')):.4f}; IID checks {verdict}  ({time.time() - t:.0f}s)")

    h_non = min((p.get("final", float("nan")) for p in res["non_iid"]), default=float("nan"))
    res["H_non_iid"] = h_non
    iid_ok = bool(res["iid"]) and all(p.get("iid_ok") for p in res["iid"])
    res["iid_verified"] = iid_ok
    res["H_iid"] = min((p.get("final", float("nan")) for p in res["iid"]), default=None)
    h_est = res["H_iid"] if iid_ok else h_non
    res["track"] = "IID" if iid_ok else "non-IID"
    h_i = min(h_est, args.claimed_h) if args.claimed_h is not None else h_est
    res["H_I"] = h_i

    if args.restart_file:
        if not exe_r:
            print("[error] ea_restart not found")
        else:
            rsym = load_samples(args.restart_file, sb, args.packed)
            if len(rsym) < 1_000_000:
                print(f"[error] restart file has {len(rsym):,} samples; need 1,000,000 "
                      f"(1000 restarts x 1000 samples, one restart per row)")
            else:
                rsym[:1_000_000].tofile(outdir / "restart_samples.bin")
                flag = "-i" if iid_ok else "-n"
                print(f"  ea_restart {flag} (H_I = {h_i:.4f}) ...")
                _, txt = run_cmd([exe_r, flag, "restart_samples.bin", str(sb), f"{h_i:.6f}"],
                                 outdir / "ea_restart.txt", cwd=outdir)
                rp = parse_restart(txt)
                res["restart"] = rp
                if rp.get("sanity_failed"):
                    print("    RESTART SANITY CHECK FAILED: the source does not restart independently "
                          "or H_I is overstated; no valid entropy claim.")
                elif "final" in rp:
                    print(f"    H_r={rp.get('H_r')}  H_c={rp.get('H_c')}  min(H_r,H_c,H_I)={rp['final']:.4f}")
                    res["H_final"] = rp["final"]
    res.setdefault("H_final", h_i)
    print(f"\n  >> Assessed min-entropy: {res['H_final']:.4f} bits/sample "
          f"= {res['H_final'] / sb:.4f} per bit  (track: {res['track']}"
          f"{', restart-validated' if 'restart' in res and 'final' in res['restart'] else ', NO restart test'})")
    if args.claimed_h is not None:
        ok = h_est >= args.claimed_h
        print(f"  >> Claimed {args.claimed_h} bits/sample: "
              f"{'SUPPORTED' if ok else 'NOT SUPPORTED'} by the estimators (estimate {h_est:.4f})")
    if chunks > 1:
        vals = [p.get("final", float("nan")) for p in res["non_iid"]]
        print(f"  >> Per-chunk non-IID estimates: " + ", ".join(f"{v:.3f}" for v in vals)
              + "  (large spread = unstable source)")
    return res


# ----------------------------------------------------------------------------
# 3. NIST SP 800-22 in parallel
# ----------------------------------------------------------------------------
_V3 = None


def _nist_worker(job):
    v3path, idx, seq, skip_lc = job
    global _V3
    if _V3 is None:
        _V3 = load_v3(v3path)
    rows = []
    for name, fn in _V3.NIST_TESTS:
        if skip_lc and name.startswith("10"):
            continue
        try:
            p = fn(seq)
        except Exception:
            p = float("nan")
        plist = p if isinstance(p, list) else [p]
        for k, pv in enumerate(plist):
            label = name if len(plist) == 1 else f"{name} #{k + 1}"
            rows.append((label, idx, float(pv)))
    return rows


def stage_nist(sym, sb, outdir, args, v3):
    import pandas as pd
    print("\n=== 3a. NIST SP 800-22 (pure-Python implementation, parallel) ===")
    L = args.seq_len
    max_bits = args.nist_max_seq * L
    need_sym = min(len(sym), -(-max_bits // sb))
    bits = symbols_to_bits(sym[:need_sym], sb)[:max_bits]
    n_seq = len(bits) // L
    if n_seq == 0:
        print(f"[skip] fewer than {L:,} bits available")
        return None
    if n_seq < 55:
        print(f"[warn] only {n_seq} sequences: pass-proportion results are weak (NIST: ~100 at alpha=0.01)")
    if not args.skip_linear_complexity:
        print(f"  note: Linear Complexity is slow in pure Python (~minutes per 1M-bit sequence per core); "
              f"use --skip-linear-complexity to omit it")
    workers = args.workers or os.cpu_count() or 1
    print(f"  {n_seq} sequences x {L:,} bits on {workers} workers")
    jobs = [(str(v3.__file__), i, bits[i * L:(i + 1) * L].copy(), args.skip_linear_complexity)
            for i in range(n_seq)]
    rows = []
    t = time.time()
    with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as ex:
        for i, r in enumerate(ex.map(_nist_worker, jobs), 1):
            rows += r
            print(f"  sequence {i}/{n_seq} done ({time.time() - t:.0f}s)", end="\r")
    print()
    df = pd.DataFrame(rows, columns=["test", "seq", "p"])
    df.to_csv(outdir / "nist_pvalues.csv", index=False)
    alpha = args.alpha
    summ = []
    for test, g in df.groupby("test", sort=True):
        p = g["p"].dropna().values
        m = len(p)
        if m == 0:
            summ.append((test, 0, float("nan"), float("nan"), "N/A"))
            continue
        prop = float(np.mean(p >= alpha))
        phat = 1 - alpha
        half = 3 * math.sqrt(phat * alpha / m)
        prop_ok = (phat - half) <= prop <= (phat + half)
        counts, _ = np.histogram(p, bins=10, range=(0, 1))
        chi2 = np.sum((counts - m / 10) ** 2 / (m / 10))
        punif = float(special.gammaincc(4.5, chi2 / 2.0))
        unif_ok = punif >= 0.0001 or m < 55
        summ.append((test, m, prop, punif, "PASS" if (prop_ok and unif_ok) else "FAIL"))
    sdf = pd.DataFrame(summ, columns=["test", "n_p", "proportion", "uniformity_P", "verdict"])
    sdf.to_csv(outdir / "nist_summary.csv", index=False)
    with pd.option_context("display.max_rows", None, "display.width", 140):
        print(sdf.to_string(index=False))
    return sdf, n_seq


# ----------------------------------------------------------------------------
# 4. Detailed Markdown report  (raw_report.md)
#    Built from raw_summary.json + the per-tool report files in the output folder,
#    so it can be regenerated later with:  --report-only <outdir>
# ----------------------------------------------------------------------------
def _fx(x, nd=4):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def _fp(x):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.4g}"


def _mb(nbytes):
    return f"{nbytes / 1e6:,.2f} MB" if nbytes < 1e9 else f"{nbytes / 1e9:,.2f} GB"


def parse_practrand(text):
    res = {"version": None, "checkpoints": [], "anomalies": [],
           "eof": "error reading standard input" in text}
    m = re.search(r"PractRand version\s*([0-9.]+)", text)
    if m:
        res["version"] = m.group(1)
    cur = None
    for line in text.splitlines():
        m = re.match(r"\s*length=\s*(.+?)\s*\(2\^(\d+) bytes\)", line)
        if m:
            cur = {"length": m.group(1), "exp": int(m.group(2)), "status": "no anomalies", "n": None}
            res["checkpoints"].append(cur)
            continue
        if cur is None:
            continue
        m = re.search(r"no anomalies in (\d+) test result", line)
        if m:
            cur["n"] = int(m.group(1))
            continue
        m = re.search(r"\.\.\.and (\d+) test result\(s\) without anomalies", line)
        if m:
            cur["n"] = (cur["n"] or 0) + int(m.group(1))
            continue
        m = re.match(r"^\s*(\S.*?)\s+R\s*=\s*([+\-]?[0-9.eE+\-]+)\s+p\s*[=<~]+\s*(\S+)\s+(\S.*?)\s*$", line)
        if m:
            ev = m.group(4).strip()
            cur["status"] = ev if cur["status"] == "no anomalies" else (
                cur["status"] if ev in cur["status"] else cur["status"] + "; " + ev)
            cur["n"] = (cur["n"] or 0) + 1
            res["anomalies"].append({"length": cur["length"], "test": m.group(1),
                                     "R": m.group(2), "p": m.group(3), "eval": ev})
    return res


DH_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*"
                   r"([0-9.eE+\-]+)\s*\|\s*(PASSED|WEAK|FAILED)\s*$", re.M)


def parse_dieharder(text):
    rows = [(a, int(b), int(c), int(d), float(e), f) for a, b, c, d, e, f in DH_RE.findall(text)]
    m = re.search(r"dieharder version\s+([0-9.]+)", text)
    return {"rows": rows, "version": m.group(1) if m else None,
            "eof": "Error: EOF" in text,
            "rewinds": [int(x) for x in re.findall(r"rewound\s+(\d+)\s+times", text)]}


def parse_testu01(text):
    out = {"all_passed": "All tests were passed" in text, "bad": []}
    m = re.search(r"FILE REWINDS:\s*(\d+)", text)
    out["rewinds"] = int(m.group(1)) if m else None
    m = re.search(r"Number of statistics:\s*(\d+)", text)
    out["n_stats"] = int(m.group(1)) if m else None
    m = re.search(r"Total CPU time:\s*(\S+)", text)
    out["cpu"] = m.group(1) if m else None
    i = text.find("The following tests gave")
    if i >= 0:
        out["bad"] = [(a, b.strip(), c) for a, b, c in
                      re.findall(r"^\s*(\d+)\s+(\S.*?)\s{2,}(\S.*?)\s*$", text[i:], re.M)]
    return out


def nist_analysis(outdir, nist):
    """Returns (table_rows, analysis_lines, flagged, notes) for the SP 800-22 section."""
    import pandas as pd
    alpha, m = nist["alpha"], nist["n_seq"]
    rec = pd.DataFrame(nist["records"])
    pv = pd.read_csv(outdir / "nist_pvalues.csv").dropna()
    phat = 1 - alpha
    lo = phat - 3 * math.sqrt(phat * alpha / m)
    min_pass = math.ceil(lo * m - 1e-9)
    lines = [f"With {m} sequences at alpha = {alpha}, the acceptable pass proportion is "
             f"**{lo:.4f} to 1.0**, so at least **{min_pass} of {m}** sequences must pass each test."]
    lowest = pv.groupby("test")["p"].min()
    rows, rex = [], {"14": [], "15": []}
    for _, r in rec.iterrows():
        t = r["test"]
        if t[:2] in rex:
            rex[t[:2]].append(r)
            continue
        if r["n_p"] == 0:
            rows.append([t, "n/a", "n/a", "n/a", "n/a", "N/A (not applicable at this sequence length)"])
            continue
        passed = int(round(r["proportion"] * r["n_p"]))
        rows.append([t, f"{passed}/{int(r['n_p'])}", _fx(r["proportion"], 3), _fx(r["uniformity_P"], 3),
                     _fp(float(lowest.get(t, float('nan')))), r["verdict"]])
    for g, lst in rex.items():
        if not lst:
            continue
        napp = int(max(x["n_p"] for x in lst))
        name = "14 Random Excursions" if g == "14" else "15 Random Excursions Variant"
        if napp == 0:
            rows.append([f"{name} ({len(lst)} states)", "n/a", "n/a", "n/a", "n/a",
                         "N/A (fewer than 500 cycles in every sequence)"])
        else:
            lp = min(float(lowest.get(x["test"], float("nan"))) for x in lst if x["n_p"] > 0)
            worst = min(x["proportion"] for x in lst if x["n_p"] > 0)
            rows.append([f"{name} ({len(lst)} states)", f"{napp} sequences applicable",
                         f"min {worst:.3f}", "not meaningful (n < 55)", _fp(lp),
                         "FAIL" if any(x["verdict"] == "FAIL" for x in lst) else "PASS"])
    # --- statistical context ---
    full = rec[rec["n_p"] == m]
    T = len(full)
    flagged = [r["test"] for _, r in full.iterrows() if r["verdict"] == "FAIL"]
    notes = []
    if flagged:
        lines.append("")
        lines.append("**Tests flagged on the pass-proportion rule:**")
        lines.append("")
        frows = []
        kmax = 0
        for t in flagged:
            f = pv[(pv.test == t) & (pv.p < alpha)]
            k = len(f)
            kmax = max(kmax, k)
            tail = float(1 - stats.binom.cdf(k - 1, m, alpha))
            frows.append([t, k, ", ".join(f"#{int(s)} (p={p:.4g})" for s, p in zip(f.seq, f.p)),
                          f"{tail:.3g}"])
        lines.append(md_table(["Test", "Failing sequences", "Sequence (p-value)",
                               f"P(>= that many failures | {m} seq, alpha={alpha})"], frows))
        pk = float(1 - stats.binom.cdf(kmax - 1, m, alpha))
        p_any = 1 - (1 - pk) ** T
        lines += ["", f"Across the {T} full-length test rows, the chance that at least one row shows "
                      f"{kmax} or more failures purely by chance is about **{p_any:.1%}**."]
        if len(flagged) > 1:
            p_two = float(1 - stats.binom.cdf(len(flagged) - 1, T, pk))
            lines.append(f"The chance that at least {len(flagged)} rows do is about **{p_two:.1%}**.")
    # overall tail count
    N = len(pv)
    L = int((pv.p < alpha).sum())
    if N:
        tail = float(1 - stats.binom.cdf(L - 1, N, alpha)) if L else 1.0
        lines += ["", f"**Overall:** {L} of {N} valid p-values are below {alpha} "
                      f"(expected about {N * alpha:.1f}; naive binomial tail probability {tail:.3g})."]
    core = pv[pv.test.isin(full["test"])]
    if len(core) >= 20:
        ks = stats.kstest(core.p, "uniform")
        lines.append(f"Pooled p-values of the full-length tests ({len(core)}) vs uniform: "
                     f"Kolmogorov-Smirnov p = {ks.pvalue:.3g}, mean p = {core.p.mean():.3f}.")
    # clusters
    low = pv[pv.p < alpha]
    clusters = low.groupby("seq").filter(lambda g: len(g) >= 3)
    if len(clusters):
        lines += ["", "**Clusters (3 or more low p-values in one sequence):**", ""]
        for s, g in clusters.groupby("seq"):
            lines.append(f"- Sequence #{int(s)}: " + ", ".join(f"{t} (p={p:.4g})" for t, p in zip(g.test, g.p)))
        names = " ".join(clusters.test)
        if "Frequency" in names and "Cumulative Sums" in names:
            lines.append("")
            lines.append("Monobit and Cumulative Sums all measure ones/zeros imbalance, so they are strongly "
                         "correlated: treat those as one event, not several.")
    if m < 55:
        notes.append(f"only {m} sequences (NIST recommends about {int(1 / alpha)} at alpha = {alpha}); "
                     f"the pass-proportion results are noisy")
    return rows, lines, flagged, notes, low


def build_report(outdir: Path):
    import pandas as pd  # noqa: F401  (used inside nist_analysis)
    outdir = Path(outdir)
    S = json.loads((outdir / "raw_summary.json").read_text())
    cfg = S.get("config", {})
    sb = S["sample_bits"]
    n = S["samples"]
    stages = S.get("stages", {})
    stream_size = S.get("stream_size", 0)
    findings, limits, recs = [], [], []
    summ_rows = []
    md = []

    # ------- 90B -------
    r = S.get("sp800_90b")
    # ------- NIST -------
    nist = S.get("nist_800_22")
    nist_block = None
    if nist and (outdir / "nist_pvalues.csv").exists():
        nist_block = nist_analysis(outdir, nist)
    # ------- tool reports -------
    def _read(name):
        p = outdir / name
        return p.read_text(errors="replace") if p.exists() else None

    pr_txt = _read("practrand_report.txt")
    dh_txt = _read("dieharder_report.txt")
    tu_name = f"testu01_{cfg.get('testu01', 'small')}_report.txt"
    tu_txt = _read(tu_name)
    pr = parse_practrand(pr_txt) if pr_txt and stages.get("practrand", "").startswith("ran") else None
    dh = parse_dieharder(dh_txt) if dh_txt and stages.get("dieharder", "").startswith("ran") else None
    tu = parse_testu01(tu_txt) if tu_txt and stages.get("testu01", "").startswith("ran") else None

    # ---------------- executive summary rows ----------------
    d = S.get("diagnostics")
    if d:
        flags = []
        if d["chi2_p"] < 0.001:
            flags.append("non-uniform symbol distribution")
        if min(x[2] for x in d["lags"]) < 0.001 / 16:
            flags.append("serial correlation")
        if d.get("homogeneity_p") is not None and d["homogeneity_p"] < 0.001 and not d["homogeneity_low_expected"]:
            flags.append("non-stationary across slices")
        if min(d["compression"].values()) < 0.99:
            flags.append("compressible")
        summ_rows.append(["Diagnostics", "Flags: " + (", ".join(flags) if flags else "none"),
                          f"Shannon {d['shannon']:.3f} / {sb} bits; MCV min-entropy {d['mcv_min_entropy']:.3f} / {sb} bits"])
        if flags:
            findings.append("Basic diagnostics flag: " + ", ".join(flags) + ".")
    if r:
        track = r["track"]
        restart = r.get("restart")
        rtxt = ("restart test PASSED" if restart and "final" in restart else
                "restart SANITY CHECK FAILED" if restart and restart.get("sanity_failed") else
                "restart test NOT run")
        summ_rows.append(["SP 800-90B", f"**{r['H_final']:.4f} bits/sample** ({r['H_final'] / sb:.4f} per bit)",
                          f"{r['chunks']} x {r['samples_per_chunk']:,} samples, {track} track, {rtxt}"])
        findings.append(f"Assessed min-entropy: **{r['H_final']:.4f} bits per {sb}-bit sample "
                        f"({r['H_final'] / sb:.1%} of nominal)**, {track} track.")
        if restart and restart.get("sanity_failed"):
            findings.append("**The restart sanity check FAILED**: the source does not restart independently "
                            "or H_I is overstated, so no valid entropy claim exists.")
        if cfg.get("claimed_h") is not None:
            h_est = r["H_iid"] if r["iid_verified"] else r["H_non_iid"]
            ok = h_est >= cfg["claimed_h"]
            findings.append(f"Claimed {cfg['claimed_h']} bits/sample is **{'supported' if ok else 'NOT supported'}** "
                            f"by the estimators (estimate {h_est:.4f}).")
        if not restart:
            limits.append("No restart test was run, so the entropy assessment is incomplete (SP 800-90B 3.1.4)")
            recs.append("Collect restart data (1000 restarts x 1000 samples, one restart per row) and rerun with "
                        "`--restart-file`.")
    else:
        summ_rows.append(["SP 800-90B", "not run", stages.get("sp800_90b", "skipped")])
        limits.append("SP 800-90B did not run (needs at least 1,000,000 raw samples)")
        recs.append("Collect at least 1,000,000 raw samples to enable the SP 800-90B assessment.")
    if nist_block:
        rows_n, _, flagged, notes, _ = nist_block
        m = nist["n_seq"]
        adequacy = "adequate" if m >= 100 else "marginal" if m >= 55 else "weak"
        _v = [x["verdict"] for x in nist["records"]]
        _np_, _nf_ = sum(v == "PASS" for v in _v), sum(v == "FAIL" for v in _v)
        summ_rows.append(["NIST SP 800-22", f"{_np_} PASS, {_nf_} FAIL, {len(_v) - _np_ - _nf_} N/A (of {len(_v)} test rows)"
                          + (f"; flagged: {', '.join(flagged)}" if flagged else ""),
                          f"{m} sequences x {nist['seq_len']:,} bits ({adequacy} sample)"])
        if flagged:
            findings.append("SP 800-22 flags (pass-proportion rule): " + ", ".join(flagged) +
                            ". See section 6 for how likely that is by chance.")
        limits += [f"NIST SP 800-22: {x}" for x in notes]
        if m < 100:
            recs.append(f"Provide at least {int(1 / nist['alpha'])} sequences x 1 Mbit "
                        f"({int(1 / nist['alpha']) * 125000 / 1e6:.1f} MB) for SP 800-22.")
    else:
        summ_rows.append(["NIST SP 800-22", "not run", stages.get("nist", "skipped")])
    if dh is not None:
        c = {k: sum(1 for x in dh["rows"] if x[5] == k) for k in ("PASSED", "WEAK", "FAILED")}
        invalid = bool(dh["rewinds"]) and max(dh["rewinds"]) > 0
        txt = ("no result (end-of-file)" if dh["eof"] and not dh["rows"] else
               f"PASSED {c['PASSED']}, WEAK {c['WEAK']}, FAILED {c['FAILED']}")
        summ_rows.append(["Dieharder", txt, "INVALID: input was rewound" if invalid else "input not re-used"])
        if invalid:
            limits.append("Dieharder input was rewound, so Dieharder results are not valid")
    else:
        summ_rows.append(["Dieharder", "not run", stages.get("dieharder", "skipped")])
        if str(stages.get("dieharder", "")).startswith("skipped"):
            recs.append("Dieharder needs at least ~100 MB (several GB for the full `-a` battery).")
    if pr is not None:
        top = max((c_["exp"] for c_ in pr["checkpoints"]), default=None)
        bad = [a for a in pr["anomalies"] if a["eval"].upper().startswith(("FAIL", "VERY", "SUSP"))]
        unusual = [a for a in pr["anomalies"] if a not in bad]
        summ_rows.append(["PractRand", f"{len(bad)} failure/suspicious, {len(unusual)} unusual",
                          f"evaluated up to 2^{top} bytes" if top is not None else "no checkpoints"])
        if bad:
            findings.append(f"PractRand reported {len(bad)} suspicious/failing result(s); see section 8.")
        if top is not None and top < 30:
            limits.append(f"PractRand only reached 2^{top} bytes (its power grows with length; "
                          f"weak sources typically fail at MB to GB scales)")
            recs.append("Provide at least 1 GB of raw data so PractRand can reach 2^30 bytes.")
    else:
        summ_rows.append(["PractRand", "not run", stages.get("practrand", "skipped")])
    if tu is not None:
        invalid = tu["rewinds"] not in (None, 0)
        summ_rows.append(["TestU01 " + cfg.get("testu01", "small"),
                          "all tests passed" if tu["all_passed"] else f"{len(tu['bad'])} test(s) outside [0.001, 0.999]",
                          "INVALID: input was rewound" if invalid else "input not re-used"])
        if tu["bad"] and not invalid:
            findings.append("TestU01 flagged: " + ", ".join(b[1] for b in tu["bad"]) + ".")
    else:
        summ_rows.append(["TestU01", "not run", stages.get("testu01", "skipped")])
        if str(stages.get("testu01", "")).startswith("skipped"):
            recs.append("TestU01 SmallCrush needs about 1 GB of data (Crush tens of GB, BigCrush about 1 TB, rough).")

    # ---------------- assemble ----------------
    md += [f"# Raw Entropy Source Assessment: `{Path(S['file']).name}`", "",
           f"**Generated:** {time.strftime('%d %B %Y %H:%M')}  ",
           f"**Data:** {n:,} samples of {sb} bit(s) ({_mb(n * sb / 8)})  ",
           "**Tool:** `qrng_raw_entropy_tests.py`", "", "---", "",
           "## 1. Executive summary", "",
           md_table(["Suite", "Outcome", "Detail"], summ_rows), "", "**Key findings**", ""]
    md += [f"- {x}" for x in (findings or ["No anomalies were flagged by the suites that ran."])]
    md += ["", "This is a raw noise-source assessment. The headline number is the SP 800-90B min-entropy; "
               "verdicts of the general statistical suites on unconditioned data are diagnostics only "
               "(raw noise is normally biased or correlated).", "", "---", ""]

    # 2. dataset & config
    md += ["## 2. Dataset and configuration", "", md_table(["Item", "Value"], [
        ["File", f"`{S['file']}`"],
        ["Samples", f"{n:,}"],
        ["Sample width", f"{sb} bit(s), {'packed back-to-back' if cfg.get('packed') else 'one sample per byte'}"],
        ["Raw data size", _mb(n * sb / 8)],
        ["SP 800-90B chunks", f"{cfg.get('chunks', 1)} x {cfg.get('samples_per_chunk', 1000000):,} samples"],
        ["Claimed entropy", "none given" if cfg.get("claimed_h") is None else f"{cfg['claimed_h']} bits/sample"],
        ["Restart file", cfg.get("restart_file") or "none"],
        ["NIST sequence length / alpha", f"{cfg.get('seq_len', 1000000):,} bits / {cfg.get('alpha', 0.01)}"],
    ]), "", "---", ""]

    # 3. diagnostics
    md += ["## 3. Diagnostics", ""]
    if d:
        md += [md_table(["Metric", "Value"], [
            ["Shannon entropy / sample", f"{d['shannon']:.4f} of {sb} bits ({d['shannon_eff']:.4f} per bit)"],
            ["MCV min-entropy / sample (99% bound)", f"{d['mcv_min_entropy']:.4f} of {sb} bits ({d['mcv_per_bit']:.4f} per bit)"],
            ["Most common value frequency", f"{d['pmax']:.6f} (uniform = {1 / d['k']:.6f})"],
            ["Chi-square uniformity", f"chi2 = {d['chi2']:.1f}, p = {_fp(d['chi2_p'])}"],
            ["Longest identical-symbol run", f"{d['longest_run']} (uniform-source expectation about {d['expected_longest_run']:.1f})"],
            ["Stationarity (10 slices, chi-square homogeneity)", _fp(d.get("homogeneity_p")) +
             (" (low expected counts: unreliable)" if d.get("homogeneity_low_expected") else "")],
            ["Compression ratio zlib-9 / bz2 / lzma", " / ".join(f"{v:.4f}" for v in d["compression"].values()) +
             " (1.0 = incompressible)"],
        ]), "", "**Serial correlation (lags 1 to 16)**", "",
            md_table(["Lag", "r", "p-value"], [[L, f"{rr:+.5f}", _fp(p)] for L, rr, p in d["lags"]]), "",
            f"With 16 lags the smallest p-value is expected to be about 0.06 by chance. A lag is flagged only "
            f"below {0.001 / 16:.2g} (0.1% family-wise level, Bonferroni). The smallest observed is "
            f"{_fp(min(x[2] for x in d['lags']))}.", ""]
    else:
        md += ["Not run.", ""]
    md += ["---", ""]

    # 4. 90B
    md += ["## 4. NIST SP 800-90B entropy assessment", ""]
    if r:
        rows90 = []
        for i, p in enumerate(r["non_iid"]):
            q = r["iid"][i] if i < len(r["iid"]) else {}
            rows90.append([i + 1, _fx(p.get("H_original")), _fx(p.get("H_bitstring")) if "H_bitstring" in p else "n/a",
                           _fx(p.get("final")), _fx(q.get("final")) if q else "not run",
                           ("passed" if q.get("iid_ok") else "FAILED") if q else "n/a"])
        md += ["**Per chunk**", "", md_table(["Chunk", "H_original (non-IID)", "H_bitstring", "non-IID result",
                                            "IID result", "IID checks"], rows90), ""]
        names = []
        for p in r["non_iid"]:
            for nme, _ in p.get("estimators", []):
                if nme not in names:
                    names.append(nme)
        if names:
            erows = []
            for nme in names:
                vals = [dict(p.get("estimators", [])).get(nme) for p in r["non_iid"]]
                vv = [v for v in vals if v is not None]
                erows.append([nme] + [_fx(v) for v in vals] + [_fx(min(vv)) if vv else "n/a"])
            md += ["**Non-IID estimators (bits per sample)**", "", md_table(
                ["Estimator"] + [f"Chunk {i + 1}" for i in range(len(r["non_iid"]))] + ["Min"], erows), ""]
        if r["iid"] and r["iid"][0].get("iid_checks"):
            md += ["**IID checks (chunk 1)**", "", md_table(["Check", "Result"],
                   [[w, v] for v, w in r["iid"][0]["iid_checks"]]), ""]
        md += ["**Result**", "", md_table(["Item", "Value"], [
            ["H (non-IID), minimum over chunks", f"{r['H_non_iid']:.4f} bits/sample"],
            ["H (IID)", "not run" if r["H_iid"] is None else f"{r['H_iid']:.4f} bits/sample (IID verified: {r['iid_verified']})"],
            ["Track used", r["track"]],
            ["H_I after claim", f"{r['H_I']:.4f} bits/sample"],
            ["Final assessed min-entropy", f"**{r['H_final']:.4f} bits/sample** ({r['H_final'] / sb:.4f} per bit)"],
        ]), ""]
        rs = r.get("restart")
        if rs:
            md += ["**Restart test**", "", md_table(["Item", "Value"], [
                ["Sanity check", "FAILED" if rs.get("sanity_failed") else "passed"],
                ["Validation test", "passed" if rs.get("validation_passed") else "not passed / not reached"],
                ["H_r (rows)", _fx(rs.get("H_r"))], ["H_c (columns)", _fx(rs.get("H_c"))],
                ["H_I", _fx(rs.get("H_I"))], ["min(H_r, H_c, H_I)", _fx(rs.get("final"))],
            ]), ""]
        _cap = ([f"- A claimed entropy of {cfg['claimed_h']} bits/sample was supplied, so H_I = min(claimed, estimate) "
                 f"and the final value is capped at the claim (SP 800-90B 3.1.3). The estimators' own value is "
                 f"{(r['H_iid'] if r['iid_verified'] else r['H_non_iid']):.4f}."]
                if cfg.get("claimed_h") is not None else [])
        md += ["**Reading these numbers**", ""] + _cap + [
               "- The non-IID track is deliberately conservative. Even ideal uniform 8-bit data typically assesses "
               "well below 8 bits per sample at 1M samples (about 6.6 to 6.9 in tests), while the IID track gives "
               "about 7.9. A non-IID value below the symbol size is not a defect by itself.",
               "- The assessed value is the minimum over all estimators and chunks, so a single conservative "
               "estimator (e.g. the Compression or MultiMMC estimator on biased data) can dominate.",
               "- When raw samples feed a conditioning function and DRBG, the usable entropy rate "
               "must be justified under SP 800-90C using this min-entropy figure.", ""]
    else:
        md += [f"Not run: {stages.get('sp800_90b', 'skipped')}.", ""]
    md += ["---", ""]

    # 5. NIST 800-22
    md += ["## 5. NIST SP 800-22 statistical tests", ""]
    if nist_block:
        rows_n, alines, flagged, notes, low = nist_block
        md += [f"Pure-Python implementation, {nist['n_seq']} sequences x {nist['seq_len']:,} bits, alpha = {nist['alpha']}"
               + (", Linear Complexity omitted" if cfg.get("skip_linear_complexity") else "")
               + ". Non-overlapping Template runs one template (`000000001`), not all 148. "
               "Not the official NIST STS; cross-check before any formal claim.", "",
               md_table(["Test", "Passed", "Proportion", "Uniformity P", "Lowest p", "Verdict"], rows_n), "",
               "### Analysis", ""] + alines + [""]
        if len(low):
            md += ["**All p-values below alpha**", "", md_table(["Sequence", "Test", "p-value"],
                   [[int(s), t, f"{p:.6f}"] for s, t, p in zip(low.seq, low.test, low.p)]), ""]
        md += ["On unconditioned raw data, failures here point to bias or correlation the conditioner must remove."
               if flagged else "", ""]
    else:
        md += [f"Not run: {stages.get('nist', 'skipped')}.", ""]
    md += ["---", ""]

    # 6. Dieharder
    md += ["## 6. Dieharder", ""]
    if dh is not None:
        if dh["eof"] and not dh["rows"]:
            md += ["**No result.** Dieharder hit end-of-file before completing its first test: the input is "
                   "too small, or this Dieharder build ignored `-f` and fell back to stdin.", ""]
        else:
            c = {k: sum(1 for x in dh["rows"] if x[5] == k) for k in ("PASSED", "WEAK", "FAILED")}
            md += [f"Dieharder {dh['version'] or ''}: **{c['PASSED']} PASSED, {c['WEAK']} WEAK, {c['FAILED']} FAILED** "
                   f"of {len(dh['rows'])} tests."
                   + (" With a full battery of this size, 1 to 2 WEAK results are expected by chance."
                      if len(dh["rows"]) >= 50 else ""), ""]
            if dh["rewinds"] and max(dh["rewinds"]) > 0:
                md += [f"**Invalid:** the input file was rewound (up to {max(dh['rewinds'])} times in one test), "
                       f"so data was re-used and FAILED/WEAK results are not meaningful.", ""]
            bad = [x for x in dh["rows"] if x[5] != "PASSED"]
            if bad:
                md += [md_table(["Test", "ntup", "tsamples", "psamples", "p-value", "Assessment"],
                                [[a, b, c_, d_, f"{e:.6f}", f] for a, b, c_, d_, e, f in bad]), ""]
            md += [f"Full table: `dieharder_report.txt`.", ""]
    else:
        md += [f"Not run: {stages.get('dieharder', 'skipped')}.", ""]
    md += ["---", ""]

    # 7. PractRand
    md += ["## 7. PractRand", ""]
    if pr is not None:
        md += [f"PractRand {pr['version'] or ''}, `-tlmin 1KB`. The final line `error reading standard input` "
               f"is just end of file.", "",
               md_table(["Length", "Test results", "Status"],
                        [[c_["length"], c_["n"] if c_["n"] is not None else "?", c_["status"]] for c_ in pr["checkpoints"]]), ""]
        if pr["anomalies"]:
            md += ["**Anomalies**", "", md_table(["At length", "Test", "R", "p", "Evaluation"],
                   [[a["length"], a["test"], a["R"], a["p"], a["eval"]] for a in pr["anomalies"]]), ""]
        tot = sum(c_["n"] or 0 for c_ in pr["checkpoints"])
        md += [f"About {tot} test results were evaluated across checkpoints (checkpoints re-test overlapping data, so "
               f"they are not independent). An isolated 'unusual' (about p = 0.01) is expected by chance; a "
               f"'suspicious' or 'FAIL' that persists at larger lengths is the real signal.", ""]
    else:
        md += [f"Not run: {stages.get('practrand', 'skipped')}.", ""]
    md += ["---", ""]

    # 8. TestU01
    md += [f"## 8. TestU01 ({cfg.get('testu01', 'small')})", ""]
    if tu is not None:
        if tu["rewinds"] not in (None, 0):
            md += [f"**Invalid:** the input was rewound {tu['rewinds']} time(s); the data was re-used.", ""]
        if tu["all_passed"]:
            md += [f"All tests were passed ({tu['n_stats']} statistics, CPU {tu['cpu']}).", ""]
        elif tu["bad"]:
            md += [md_table(["#", "Test", "p-value"], [list(b) for b in tu["bad"]]), "",
                   "p-values outside [0.001, 0.999]. `eps` means below 1e-300; `eps1` below 1e-15.", ""]
        else:
            md += ["No summary found in the report (run incomplete?). See `" + tu_name + "`.", ""]
    else:
        md += [f"Not run: {stages.get('testu01', 'skipped')}.", ""]
    md += ["---", ""]

    # 9. what it means / limitations / next steps
    md += ["## 9. What these results do and do not show", "",
           "1. **Raw data is not expected to look full-entropy.** Bias and correlation are normal in an "
           "unconditioned noise source; the question is how much min-entropy remains, which is what SP 800-90B measures.",
           "2. **An entropy claim needs more than one number:** the restart test, health tests at runtime, and a "
           "documented conditioning and DRBG design (SP 800-90A/B/C).",
           "3. **Statistical tests cannot prove physical origin.** They can detect defects; a quantum origin "
           "is argued from the device physics and the 90B assessment of the raw readout.", ""]
    if limits:
        md += ["## 10. Limitations of this run", ""] + [f"- {x}" for x in limits] + [""]
    recs += ["Run `--chunks 3` or more to check that the min-entropy estimate is stable across the dataset.",
             "Cross-check any flagged SP 800-22 test with the official NIST STS.",
             "Repeat the assessment across operating conditions (temperature, time of day, each device/register) "
             "to show the estimate holds."]
    md += ["## 11. Recommended next steps", ""] + [f"{i}. {x}" for i, x in enumerate(recs, 1)] + [""]
    cmd = f"python3 qrng_raw_entropy_tests.py {S['file']} --out {outdir}"
    if sb != 8:
        cmd += f" --sample-bits {sb}" + (" --packed" if cfg.get("packed") else "")
    if cfg.get("chunks", 1) != 1:
        cmd += f" --chunks {cfg['chunks']}"
    if cfg.get("restart_file"):
        cmd += f" --restart-file {cfg['restart_file']}"
    if cfg.get("claimed_h") is not None:
        cmd += f" --claimed-h {cfg['claimed_h']}"
    if cfg.get("seq_len", 1000000) != 1000000:
        cmd += f" --seq-len {cfg['seq_len']}"
    if cfg.get("nist_max_seq", 50) != 50:
        cmd += f" --nist-max-seq {cfg['nist_max_seq']}"
    if cfg.get("skip_linear_complexity"):
        cmd += " --skip-linear-complexity"
    md += ["---", "", "## Appendix: reproduction", "", "```bash", cmd, "```", "",
           "Per-tool outputs in this folder: `ea_non_iid_chunk*.txt`, `ea_iid_chunk*.txt`, `ea_restart.txt`, "
           "`nist_summary.csv`, `nist_pvalues.csv`, `dieharder_report.txt`, `practrand_report.txt`, "
           "`testu01_*_report.txt`, `raw_summary.json`.", ""]
    path = outdir / "raw_report.md"
    path.write_text("\n".join(md))
    return path


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
MIN_BYTES = {"dieharder": 100 << 20, "small": 900 << 20, "crush": 20 << 30, "big": 500 << 30}


def main():
    ap = argparse.ArgumentParser(description="Assess raw pre-DRBG samples (SP 800-90B + statistical suites).")
    ap.add_argument("data", nargs="?", help="binary file of raw samples (e.g. data.bin)")
    ap.add_argument("--report-only", metavar="DIR", default=None,
                    help="regenerate raw_report.md from an existing results folder and exit")
    ap.add_argument("--no-report", action="store_true", help="do not write raw_report.md")
    ap.add_argument("--out", default="raw_results")
    ap.add_argument("--v3", default=None, help="path to qrng_randomness_tests_v3.py")
    ap.add_argument("--sample-bits", type=int, default=8, choices=range(1, 9), metavar="1-8")
    ap.add_argument("--packed", action="store_true", help="samples packed back-to-back, MSB first")
    ap.add_argument("--max-bytes", type=int, default=None, help="read only the first N bytes")
    # stage switches
    ap.add_argument("--skip-diagnostics", action="store_true")
    ap.add_argument("--skip-90b", action="store_true")
    ap.add_argument("--skip-nist", action="store_true")
    ap.add_argument("--skip-dieharder", action="store_true")
    ap.add_argument("--skip-practrand", action="store_true")
    ap.add_argument("--testu01", choices=["none", "small", "crush", "big"], default="small")
    ap.add_argument("--force-suites", action="store_true",
                    help="run Dieharder/TestU01 even when the data is smaller than they need "
                         "(results will be INVALID: the file is re-used)")
    # 90B
    ap.add_argument("--chunks", type=int, default=1, help="number of 1M-sample chunks to assess with 90B")
    ap.add_argument("--samples-per-chunk", type=int, default=1_000_000)
    ap.add_argument("--no-iid", action="store_true", help="skip ea_iid")
    ap.add_argument("--restart-file", default=None,
                    help="restart data: 1000 restarts x 1000 samples, one restart per row, same sample layout")
    ap.add_argument("--claimed-h", type=float, default=None,
                    help="entropy per sample claimed by the source (bits); H_I = min(claimed, estimated)")
    # NIST 800-22
    ap.add_argument("--seq-len", type=int, default=1_000_000)
    ap.add_argument("--nist-max-seq", type=int, default=50)
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--skip-linear-complexity", action="store_true")
    ap.add_argument("--diag-max", type=int, default=50_000_000)
    args = ap.parse_args()

    if args.report_only:
        print(f"Report written: {build_report(Path(args.report_only))}")
        return
    if not args.data:
        ap.error("the data file is required (or use --report-only DIR)")

    v3 = load_v3(args.v3)
    v3.add_prefix_to_path(LOCAL)
    if "TESTU01_PREFIX" not in os.environ and (LOCAL / "include" / "unif01.h").exists():
        os.environ["TESTU01_PREFIX"] = str(LOCAL)

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    sb = args.sample_bits
    sym = load_samples(args.data, sb, args.packed, args.max_bytes)
    n = len(sym)
    print(f"Loaded {n:,} samples of {sb} bit(s) from {args.data} "
          f"({'packed' if args.packed and sb < 8 else 'one sample per byte' if sb < 8 else '8-bit'} layout) "
          f"= {n * sb / 8 / 1e6:.2f} MB of raw data")
    summary = {"file": str(args.data), "samples": n, "sample_bits": sb,
               "config": {k: v for k, v in vars(args).items()}, "stages": {}}
    st = summary["stages"]

    if not args.skip_diagnostics:
        d = diagnostics(sym, sb, args.diag_max)
        print_diagnostics(d, sb)
        summary["diagnostics"] = d
        st["diagnostics"] = "ran"
    else:
        st["diagnostics"] = "skipped (--skip-diagnostics)"

    if not args.skip_90b:
        r = stage_90b(sym, sb, outdir, args)
        if r:
            summary["sp800_90b"] = r
            st["sp800_90b"] = "ran"
        else:
            st["sp800_90b"] = "skipped (" + _REASON.get("90b", "unknown reason") + ")"
    else:
        st["sp800_90b"] = "skipped (--skip-90b)"

    # bit stream for the statistical suites
    stream = Path(args.data) if (sb == 8 and not args.max_bytes) else outdir / "stream.bin"
    need_stream = not (args.skip_dieharder and args.skip_practrand and args.testu01 == "none")
    if need_stream and stream != Path(args.data):
        write_bit_stream(sym, sb, stream)
    stream_size = stream.stat().st_size if stream.exists() else 0
    summary["stream_size"] = stream_size

    if not args.skip_nist:
        res = stage_nist(sym, sb, outdir, args, v3)
        if res is not None:
            sdf, n_seq = res
            summary["nist_800_22"] = {
                "records": sdf.to_dict("records"), "n_seq": n_seq, "seq_len": args.seq_len,
                "alpha": args.alpha, "n_pass": int((sdf.verdict == "PASS").sum()),
                "n_tests": int(len(sdf)), "fail": sdf[sdf.verdict == "FAIL"].test.tolist()}
            st["nist"] = "ran"
        else:
            st["nist"] = f"skipped (fewer than {args.seq_len:,} bits)"
    else:
        st["nist"] = "skipped (--skip-nist)"

    if not args.skip_dieharder:
        if stream_size < MIN_BYTES["dieharder"] and not args.force_suites:
            print(f"\n=== 3b. Dieharder: SKIPPED ({stream_size / 1e6:.1f} MB < ~100 MB needed; "
                  f"use --force-suites for an invalid-but-fast run) ===")
            st["dieharder"] = f"skipped (insufficient data: {stream_size / 1e6:.1f} MB, needs about 100 MB)"
        else:
            v3.run_dieharder(stream, outdir)
            st["dieharder"] = "ran"
    else:
        st["dieharder"] = "skipped (--skip-dieharder)"

    if not args.skip_practrand:
        v3.run_practrand(stream, outdir)
        st["practrand"] = "ran"
    else:
        st["practrand"] = "skipped (--skip-practrand)"

    if args.testu01 != "none":
        need = MIN_BYTES[args.testu01]
        if stream_size < need and not args.force_suites:
            print(f"\n=== 3d. TestU01 {args.testu01}: SKIPPED ({stream_size / 1e6:.1f} MB < "
                  f"~{need / 1e6:.0f} MB needed; --force-suites to override) ===")
            st["testu01"] = f"skipped (insufficient data: {stream_size / 1e6:.1f} MB, needs about {need / 1e6:.0f} MB)"
        else:
            v3.run_testu01(stream, outdir, args.testu01)
            st["testu01"] = "ran"
    else:
        st["testu01"] = "skipped (--testu01 none)"

    # -------- summary + detailed report --------
    def _clean(o):
        if isinstance(o, dict):
            return {str(k): _clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [_clean(v) for v in o]
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
            return None
        return o

    (outdir / "raw_summary.json").write_text(json.dumps(_clean(summary), indent=2, default=str))
    report_path = None
    if not args.no_report:
        try:
            report_path = build_report(outdir)
        except Exception as e:  # never lose the run because of a report bug
            print(f"[warn] could not build the detailed report: {e!r}  "
                  f"(retry later with --report-only {outdir})")

    print("\n=== Interpretation notes ===")
    print("  * For raw noise, the headline number is the SP 800-90B min-entropy per sample, "
          "not the NIST 800-22 / Dieharder verdicts.")
    print("  * Failures of the statistical suites on UNCONDITIONED data usually indicate bias or "
          "correlation that conditioning must remove; they do not by themselves mean a faulty source.")
    print("  * The non-IID track is deliberately conservative: even ideal uniform 8-bit data typically "
          "assesses well below 8 bits/sample at 1M samples (about 6.6-6.9 in my tests; the IID track gave ~7.9). "
          "Do not read a non-IID value below the symbol size as a defect by itself.")
    print("  * A valid entropy claim also needs the restart test and a documented conditioning design "
          "(SP 800-90C / 90A).")
    print(f"\nFiles written to {outdir}/")
    if report_path:
        print(f"Detailed report: {report_path}")


if __name__ == "__main__":
    main()
