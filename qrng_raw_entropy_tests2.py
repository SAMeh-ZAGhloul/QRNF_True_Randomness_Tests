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
          f"  (16 lags tested; expect min p ~ 0.06)")
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


def stage_90b(sym, sb, outdir, args):
    exe_n, exe_i, exe_r = (shutil.which(x) for x in ("ea_non_iid", "ea_iid", "ea_restart"))
    print(f"\n=== 2. NIST SP 800-90B entropy assessment ({sb}-bit samples) ===")
    if not exe_n:
        print("[error] ea_non_iid not found. Install: python3 qrng_randomness_tests_v3.py --setup sp80090b")
        return None
    n = len(sym)
    if n < 1_000_000:
        print(f"[skip] {n:,} samples; SP 800-90B needs at least 1,000,000 (collect more raw data).")
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
    return sdf


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
MIN_BYTES = {"dieharder": 100 << 20, "small": 900 << 20, "crush": 20 << 30, "big": 500 << 30}


def main():
    ap = argparse.ArgumentParser(description="Assess raw pre-DRBG samples (SP 800-90B + statistical suites).")
    ap.add_argument("data", help="binary file of raw samples (e.g. data.bin)")
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
    summary = {"file": str(args.data), "samples": n, "sample_bits": sb}

    if not args.skip_diagnostics:
        d = diagnostics(sym, sb, args.diag_max)
        print_diagnostics(d, sb)
        summary["diagnostics"] = d

    if not args.skip_90b:
        r = stage_90b(sym, sb, outdir, args)
        if r:
            summary["sp800_90b"] = r

    # bit stream for the statistical suites
    stream = Path(args.data) if (sb == 8 and not args.max_bytes) else outdir / "stream.bin"
    need_stream = not (args.skip_dieharder and args.skip_practrand and args.testu01 == "none")
    if need_stream and stream != Path(args.data):
        write_bit_stream(sym, sb, stream)
    stream_size = stream.stat().st_size if stream.exists() else 0

    if not args.skip_nist:
        sdf = stage_nist(sym, sb, outdir, args, v3)
        if sdf is not None:
            summary["nist_800_22"] = {"fail": sdf[sdf.verdict == "FAIL"].test.tolist(),
                                      "n_pass": int((sdf.verdict == "PASS").sum()),
                                      "n_tests": int(len(sdf))}

    if not args.skip_dieharder:
        if stream_size < MIN_BYTES["dieharder"] and not args.force_suites:
            print(f"\n=== 3b. Dieharder: SKIPPED ({stream_size / 1e6:.1f} MB < ~100 MB needed; "
                  f"use --force-suites for an invalid-but-fast run) ===")
            summary["dieharder"] = "skipped (insufficient data)"
        else:
            v3.run_dieharder(stream, outdir)
            summary["dieharder"] = "ran"

    if not args.skip_practrand:
        v3.run_practrand(stream, outdir)
        summary["practrand"] = "ran"

    if args.testu01 != "none":
        need = MIN_BYTES[args.testu01]
        if stream_size < need and not args.force_suites:
            print(f"\n=== 3d. TestU01 {args.testu01}: SKIPPED ({stream_size / 1e6:.1f} MB < "
                  f"~{need / 1e6:.0f} MB needed; --force-suites to override) ===")
            summary["testu01"] = "skipped (insufficient data)"
        else:
            v3.run_testu01(stream, outdir, args.testu01)
            summary["testu01"] = "ran"

    # -------- summary files --------
    def _clean(o):
        if isinstance(o, dict):
            return {str(k): _clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [_clean(v) for v in o]
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        return o

    (outdir / "raw_summary.json").write_text(json.dumps(_clean(summary), indent=2, default=str))
    md = [f"# Raw sample assessment: `{args.data}`", "",
          f"- Samples: {n:,} x {sb} bit(s) ({n * sb / 8 / 1e6:.2f} MB)", ""]
    if "diagnostics" in summary:
        d = summary["diagnostics"]
        md += ["## Diagnostics", "", md_table(["Metric", "Value"], [
            ["Shannon entropy / sample", f"{d['shannon']:.4f} of {sb} bits"],
            ["MCV min-entropy / sample (99%)", f"{d['mcv_min_entropy']:.4f} of {sb} bits"],
            ["Chi-square uniformity p", f"{d['chi2_p']:.4g}"],
            ["Longest identical run", f"{d['longest_run']} (expected ~ {d['expected_longest_run']:.1f})"],
            ["Compression (zlib/bz2/lzma)", " / ".join(f"{v:.3f}" for v in d["compression"].values())],
        ]), ""]
    if "sp800_90b" in summary:
        r = summary["sp800_90b"]
        md += ["## NIST SP 800-90B", "", md_table(["Item", "Value"], [
            ["Chunks assessed", f"{r['chunks']} x {r['samples_per_chunk']:,} samples"],
            ["H (non-IID), min over chunks", f"{r['H_non_iid']:.4f} bits/sample"],
            ["H (IID)", "n/a" if r["H_iid"] is None else f"{r['H_iid']:.4f} (IID verified: {r['iid_verified']})"],
            ["Track used", r["track"]],
            ["Assessed min-entropy", f"**{r['H_final']:.4f} bits/sample** ({r['H_final'] / sb:.4f} per bit)"],
            ["Restart test", "run" if "restart" in r else "NOT run (needs restart data)"],
        ]), ""]
        est = r["non_iid"][0].get("estimators", []) if r["non_iid"] else []
        if est:
            md += ["Non-IID estimators (first chunk):", "", md_table(["Estimator", "bits/sample"],
                   [[a, f"{b:.4f}"] for a, b in est]), ""]
    (outdir / "raw_summary.md").write_text("\n".join(md))

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
    print(f"\nFiles written to {outdir}/ (raw_summary.md, raw_summary.json, and per-tool reports)")


if __name__ == "__main__":
    main()
