#!/usr/bin/env python3
"""
Entropy Test Suite — NIST SP 800-22 | NIST SP 800-90B | Dieharder | AIS 31
Usage: python tests/entropy_tests.py --file <path> [--streams N] [--output dir]
"""

import argparse
import gzip
import json
import os
import sys
from collections import Counter

import numpy as np
from scipy import special, stats
from scipy.fft import fft


# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_data(path):
    with open(path, "rb") as f:
        return f.read()


def to_bits(data):
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


# ─── NIST SP 800-22 ──────────────────────────────────────────────────────────

def nist_frequency(bits):
    n = len(bits)
    s = np.sum(2 * bits.astype(np.int8) - 1)
    return float(special.erfc(abs(s) / np.sqrt(2 * n)))


def nist_block_frequency(bits, M=128):
    n = len(bits)
    N = n // M
    pis = np.array([np.sum(bits[i * M:(i + 1) * M]) / M for i in range(N)])
    chi_sq = 4 * M * np.sum((pis - 0.5) ** 2)
    return float(special.gammaincc(N / 2, chi_sq / 2))


def nist_runs(bits):
    n = len(bits)
    pi = np.sum(bits) / n
    if abs(pi - 0.5) >= 2 / np.sqrt(n):
        return 0.0
    v_obs = 1 + int(np.sum(bits[1:] != bits[:-1]))
    num = abs(v_obs - 2 * n * pi * (1 - pi))
    den = 2 * np.sqrt(2 * n) * pi * (1 - pi)
    return float(special.erfc(num / den)) if den > 0 else 0.0


def nist_longest_run(bits):
    """NIST SP 800-22 §2.4 with official probability tables."""
    n = len(bits)
    if n < 128:
        return 0.0

    if n < 6272:
        M, K = 8, 3
        pi = [0.2148, 0.3672, 0.2305, 0.1875]
        v_min = 1
    elif n < 750_000:
        M, K = 128, 5
        pi = [0.1174, 0.2430, 0.2493, 0.1752, 0.1027, 0.1124]
        v_min = 4
    else:
        M, K = 10_000, 6
        pi = [0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727]
        v_min = 10

    N = n // M
    freqs = [0] * (K + 1)
    for i in range(N):
        block = bits[i * M:(i + 1) * M]
        max_run = cur = 0
        for b in block:
            if b:
                cur += 1
                if cur > max_run:
                    max_run = cur
            else:
                cur = 0
        idx = min(K, max(0, max_run - v_min))
        freqs[idx] += 1

    chi_sq = sum(
        (freqs[i] - N * pi[i]) ** 2 / (N * pi[i])
        for i in range(K + 1) if N * pi[i] > 0
    )
    return float(special.gammaincc((K + 1) / 2, chi_sq / 2))


def nist_spectral(bits):
    n = len(bits)
    x = 2 * bits.astype(np.float64) - 1
    s = np.abs(fft(x))[:n // 2]
    t = np.sqrt(np.log(1 / 0.05) * n)
    n0 = 0.95 * n / 2
    n1 = float(np.sum(s < t))
    d = (n1 - n0) / np.sqrt(n * 0.95 * 0.05 / 4)
    return float(special.erfc(abs(d) / np.sqrt(2)))


def nist_serial(bits, m=2):
    n = len(bits)

    def psi_sq(m):
        if m == 0:
            return 0.0
        c = Counter(tuple(bits[i:i + m].tolist()) for i in range(n - m + 1))
        total = sum(c.values())
        return sum(v ** 2 for v in c.values()) * (2 ** m) / total - total

    pm, pm1 = psi_sq(m), psi_sq(m - 1)
    pm2 = psi_sq(m - 2) if m > 2 else 0.0
    p1 = float(special.gammaincc(2 ** (m - 2), (pm - pm1) / 2))
    p2 = float(special.gammaincc(2 ** (m - 3), (pm - 2 * pm1 + pm2) / 2)) if m > 2 else 1.0
    return min(p1, p2)


def nist_approx_entropy(bits, m=2):
    n = len(bits)

    def phi(m):
        ext = np.concatenate([bits, bits[:m - 1]])
        c = Counter(tuple(ext[i:i + m].tolist()) for i in range(n))
        return sum(v / n * np.log(v / n) for v in c.values())

    apen = phi(m) - phi(m + 1)
    chi_sq = 2 * n * (np.log(2) - apen)
    return float(special.gammaincc(2 ** (m - 1), chi_sq / 2))


NIST_800_22_TESTS = {
    "Frequency":          nist_frequency,
    "Block Frequency":    lambda b: nist_block_frequency(b, 128),
    "Runs":               nist_runs,
    "Longest Run":        nist_longest_run,
    "Spectral (DFT)":     nist_spectral,
    "Serial":             lambda b: nist_serial(b, 2),
    "Approx Entropy":     lambda b: nist_approx_entropy(b, 2),
}


def run_nist_800_22(data, n_streams, bits_per_stream=1_000_000):
    available = len(data) * 8 // bits_per_stream
    n_streams = min(n_streams, available)
    if n_streams == 0:
        return {}, False

    acc = {name: {"pass": 0, "fail": 0} for name in NIST_800_22_TESTS}

    for i in range(n_streams):
        offset = i * (bits_per_stream // 8)
        bits = to_bits(data[offset:offset + bits_per_stream // 8])[:bits_per_stream]
        for name, fn in NIST_800_22_TESTS.items():
            try:
                p = fn(bits)
                if p >= 0.01:
                    acc[name]["pass"] += 1
                else:
                    acc[name]["fail"] += 1
            except Exception:
                acc[name]["fail"] += 1

    # Adaptive threshold: NIST standard is 96% at ≥55 streams.
    # For fewer streams, allow at most max(1, floor(5% of n)) failures.
    def _pass_threshold(n):
        max_fail = max(1, int(n * 0.05))
        return (n - max_fail) / n

    all_pass = all(
        r["pass"] / (r["pass"] + r["fail"]) >= _pass_threshold(r["pass"] + r["fail"])
        for r in acc.values() if r["pass"] + r["fail"] > 0
    )
    return acc, bool(all_pass)


# ─── NIST SP 800-90B ─────────────────────────────────────────────────────────

def run_nist_800_90b(data):
    sample = data[:1_000_000]
    samples = np.frombuffer(sample, dtype=np.uint8)
    n = len(samples)
    counts = Counter(int(b) for b in samples)

    p_max = max(counts.values()) / n
    H_mcv = min(-np.log2(p_max), 8.0)

    # Collision estimator (SP 800-90B simplified)
    collisions, i = 0, 0
    while i < n - 1:
        j = i + 1
        while j < n and samples[j] != samples[i]:
            j += 1
        if j < n:
            collisions += 1
        i = j
    H_collision = min(np.log2(n / collisions), 8.0) if collisions > 0 else 8.0

    # Markov estimate
    trans = np.zeros((256, 256), dtype=np.float64)
    for a, b in zip(samples[:-1], samples[1:]):
        trans[a, b] += 1
    row_sums = trans.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    trans /= row_sums
    H_markov = min(-np.log2(np.max(trans)), 8.0)

    H_compression = min(8 * len(gzip.compress(sample)) / len(sample), 8.0)

    min_entropy = min(H_mcv, H_collision, H_markov, H_compression)

    # IID chi-square
    expected = n / 256
    chi_sq = sum((counts.get(v, 0) - expected) ** 2 / expected for v in range(256))
    p_iid = float(1 - stats.chi2.cdf(chi_sq, 255))

    # Min-entropy ≥ 6.5 bits/byte is the threshold (Markov estimator is conservative)
    return {
        "H_mcv": round(H_mcv, 4),
        "H_collision": round(H_collision, 4),
        "H_markov": round(H_markov, 4),
        "H_compression": round(H_compression, 4),
        "min_entropy": round(min_entropy, 4),
        "iid_p_value": round(p_iid, 6),
        "is_iid": bool(p_iid >= 0.001),
        "pass": bool(min_entropy >= 6.5 and p_iid >= 0.001),
    }


# ─── Dieharder-style ─────────────────────────────────────────────────────────

def dieharder_birthday(data, n=512):
    if len(data) < n * 4:
        return 0.5
    samples = np.sort(np.frombuffer(data[:n * 4], dtype=np.uint32))
    spacings = np.diff(samples)
    sc = Counter(spacings.tolist())
    # Total extra occurrences of repeated spacing values
    collisions = sum(c - 1 for c in sc.values() if c > 1)
    expected = n * (n - 1) / (2 * 2 ** 32)
    # sf(k-1, λ) = P(X >= k); k=-1 gives P(X >= 0) = 1.0 when collisions=0
    return float(stats.poisson.sf(collisions - 1, expected)) if expected > 0 else 0.5


def dieharder_operm5(data):
    samples = np.frombuffer(data[:100_000], dtype=np.uint8)
    n = len(samples)
    if n < 5:
        return 0.5
    c = Counter(
        tuple(np.argsort(np.argsort(samples[i:i + 5])).tolist())
        for i in range(n - 4)
    )
    expected = (n - 4) / 120
    chi_sq = sum((v - expected) ** 2 / expected for v in c.values())
    return float(1 - stats.chi2.cdf(chi_sq, 119))


def dieharder_dna(data):
    bits = to_bits(data[:100_000])
    letters = bits[::2] * 2 + bits[1::2]
    n = len(letters)
    if n < 10:
        return 0.5
    c = Counter(tuple(letters[i:i + 10].tolist()) for i in range(n - 9))
    n_words = n - 9
    expected_unique = 4 ** 10 * (1 - np.exp(-n_words / 4 ** 10))
    z = (len(c) - expected_unique) / np.sqrt(expected_unique) if expected_unique > 0 else 0
    return float(2 * stats.norm.sf(abs(z)))


def run_dieharder(data):
    results = {
        "Birthday Spacings":        dieharder_birthday(data),
        "Overlapping 5-Permutation": dieharder_operm5(data),
        "DNA Test":                  dieharder_dna(data),
    }
    all_pass = all(p >= 0.01 for p in results.values())
    return results, all_pass


# ─── AIS 31 ──────────────────────────────────────────────────────────────────

def run_ais31(data):
    """AIS 31 PTG.2 tests on exactly 20 000 bits per the standard."""
    bits = to_bits(data[:2500])[:20_000]
    n = len(bits)
    ones = int(np.sum(bits))

    # T1 – Monobit: AIS 31 Table requires 9654 < ones < 10346
    t1 = 9654 < ones < 10346

    # T2 – Poker (4-bit nibbles): 1.03 < X < 57.4
    n_nibbles = n // 4
    nibbles = [
        bits[i * 4] * 8 + bits[i * 4 + 1] * 4 + bits[i * 4 + 2] * 2 + bits[i * 4 + 3]
        for i in range(n_nibbles)
    ]
    c = Counter(nibbles)
    poker_x = (16 / n_nibbles) * sum(v ** 2 for v in c.values()) - n_nibbles
    t2 = 1.03 < poker_x < 57.4

    # T3 – Runs: AIS 31 Table 7 limits for 20 000 bits (per run type, per length)
    AIS31_T3 = {1: (2267, 2733), 2: (1079, 1421), 3: (502, 748),
                4: (223, 402),  5: (90, 223),   6: (90, 223)}  # 6 = length ≥ 6

    runs_0, runs_1 = Counter(), Counter()
    cur, length = bits[0], 1
    for b in bits[1:]:
        if b == cur:
            length += 1
        else:
            bucket = min(length, 6)
            (runs_1 if cur else runs_0)[bucket] += 1
            cur, length = b, 1
    (runs_1 if cur else runs_0)[min(length, 6)] += 1

    t3 = True
    for bit_runs in (runs_0, runs_1):
        for k, (lo, hi) in AIS31_T3.items():
            observed = bit_runs.get(k, 0)
            if not (lo < observed < hi):
                t3 = False
                break

    # T4 – Long Run: AIS 31 requires max run < 34 for 20000 bits
    max_run = cur = 1
    for i in range(1, n):
        if bits[i] == bits[i - 1]:
            cur += 1
            if cur > max_run:
                max_run = cur
        else:
            cur = 1
    t4 = max_run < 34  # AIS 31 hard limit

    all_pass = bool(t1 and t2 and t3 and t4)
    return {
        "T1_Monobit": {"pass": bool(t1), "ones": ones, "bounds": [9654, 10346]},
        "T2_Poker":   {"pass": bool(t2), "chi_sq": round(poker_x, 4), "bounds": [1.03, 57.4]},
        "T3_Runs":    {"pass": bool(t3)},
        "T4_LongRun": {"pass": bool(t4), "max_run": int(max_run), "limit": 34},
        "overall": all_pass,
    }


# ─── Main ────────────────────────────────────────────────────────────────────

def print_section(title):
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print('=' * 65)


def run_all(data_path, n_streams, output_dir):
    data = load_data(data_path)
    size_mb = len(data) / 1024 / 1024
    print(f"\nFile : {data_path}")
    print(f"Size : {len(data):,} bytes ({size_mb:.2f} MB)")
    print(f"Bits : {len(data) * 8:,}")

    all_results = {}
    exit_ok = True

    # ── NIST SP 800-22 ────────────────────────────────────────────────────
    print_section(f"NIST SP 800-22  ({n_streams} streams × 1 000 000 bits)")
    nist_res, nist_ok = run_nist_800_22(data, n_streams)
    all_results["nist_800_22"] = {"tests": nist_res, "overall": nist_ok}
    for name, r in nist_res.items():
        total = r["pass"] + r["fail"]
        rate = r["pass"] / total * 100 if total else 0
        icon = "✓" if rate >= 96 else "✗"
        print(f"  {icon} {name:<22}  {r['pass']}/{total}  ({rate:.1f}%)")
    print(f"\n  Overall: {'PASS' if nist_ok else 'FAIL'}")
    if not nist_ok:
        exit_ok = False

    # ── NIST SP 800-90B ───────────────────────────────────────────────────
    print_section("NIST SP 800-90B  (Entropy Estimation)")
    ent = run_nist_800_90b(data)
    all_results["nist_800_90b"] = ent
    for k in ("H_mcv", "H_collision", "H_markov", "H_compression"):
        print(f"  {k:<18}  {ent[k]:.4f} bits/byte")
    print(f"  {'min_entropy':<18}  {ent['min_entropy']:.4f} bits/byte")
    print(f"  IID p-value        {ent['iid_p_value']:.6f}  ({'IID' if ent['is_iid'] else 'NON-IID'})")
    print(f"\n  Overall: {'PASS' if ent['pass'] else 'FAIL'}")
    if not ent["pass"]:
        exit_ok = False

    # ── Dieharder ─────────────────────────────────────────────────────────
    print_section("Dieharder-style Tests")
    dh_res, dh_ok = run_dieharder(data)
    all_results["dieharder"] = {"p_values": dh_res, "overall": dh_ok}
    for name, p in dh_res.items():
        icon = "✓" if p >= 0.01 else "✗"
        print(f"  {icon} {name:<30}  p={p:.6f}")
    print(f"\n  Overall: {'PASS' if dh_ok else 'FAIL'}")
    if not dh_ok:
        exit_ok = False

    # ── AIS 31 ────────────────────────────────────────────────────────────
    print_section("AIS 31 (BSI Germany) PTG.2")
    ais = run_ais31(data)
    all_results["ais31"] = ais
    for t in ("T1_Monobit", "T2_Poker", "T3_Runs", "T4_LongRun"):
        icon = "✓" if ais[t]["pass"] else "✗"
        detail = {k: v for k, v in ais[t].items() if k != "pass"}
        print(f"  {icon} {t:<14}  {detail}")
    print(f"\n  Overall: {'PASS' if ais['overall'] else 'FAIL'}")
    if not ais["overall"]:
        exit_ok = False

    # ── Summary ───────────────────────────────────────────────────────────
    print_section("SUMMARY")
    suites = [
        ("NIST SP 800-22",  nist_ok),
        ("NIST SP 800-90B", ent["pass"]),
        ("Dieharder",       dh_ok),
        ("AIS 31",          ais["overall"]),
    ]
    for name, ok in suites:
        icon = "✓" if ok else "✗"
        print(f"  {icon} {name}")

    if exit_ok:
        print("\n  RESULT: ALL SUITES PASSED")
    else:
        print("\n  RESULT: ONE OR MORE SUITES FAILED")

    # ── Save results ──────────────────────────────────────────────────────
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, "results.json")
        with open(out_path, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\n  Results saved → {out_path}")

    return exit_ok


def main():
    parser = argparse.ArgumentParser(description="Entropy randomness test suite")
    parser.add_argument("--file",    required=True, help="Path to binary data file")
    parser.add_argument("--streams", type=int, default=80,
                        help="NIST 800-22 stream count (default 80; use 20 for faster CI)")
    parser.add_argument("--output",  default="", help="Directory to save results JSON")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"ERROR: file not found: {args.file}", file=sys.stderr)
        sys.exit(2)

    ok = run_all(args.file, args.streams, args.output)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
