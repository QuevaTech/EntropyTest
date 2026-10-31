#!/usr/bin/env python3
"""Independent sanity check of the published sample.

Reproduces the headline numbers of TEST_REPORT.md without any proprietary
tooling: file integrity, bit balance, byte uniformity, serial correlation,
run length, block repetition and a compression bound.

    python tools/verify_sample.py
    python tools/verify_sample.py --file path/to/sample.bin --json

Exit code 0 = every check passed, 1 = at least one check failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zlib
from math import erfc, sqrt

import numpy as np

DEFAULT_FILE = "v2_submission/data/v2_random_sample.bin"
EXPECTED_SHA256 = "9e78d28edfe7fe1e1a76a3da5eee805c2a472fe43d0abfe873b170a5453dacd1"
EXPECTED_BYTES = 11_702_528


def chi2_sf(x: float, df: int) -> float:
    """Survival function for chi-square, with a normal approximation fallback."""
    try:
        from scipy.stats import chi2  # type: ignore

        return float(chi2.sf(x, df))
    except ImportError:  # pragma: no cover - scipy is optional
        # Wilson-Hilferty approximation; good enough for a pass/fail gate
        z = ((x / df) ** (1 / 3) - (1 - 2 / (9 * df))) / sqrt(2 / (9 * df))
        return 0.5 * erfc(z / sqrt(2))


def analyse(path: str) -> dict:
    data = np.fromfile(path, dtype=np.uint8)
    n = int(data.size)
    bits = np.unpackbits(data)
    nbits = int(bits.size)

    ones = int(bits.sum())
    monobit_z = abs(2 * ones - nbits) / sqrt(nbits)
    monobit_p = erfc(monobit_z / sqrt(2))

    counts = np.bincount(data, minlength=256)
    expected = n / 256
    chi = float(((counts - expected) ** 2 / expected).sum())
    chi_p = chi2_sf(chi, 255)

    x = data.astype(np.float64)
    x -= x.mean()
    var = float(x.var())
    corr = [float((x[:-k] * x[k:]).mean() / var) for k in range(1, 9)]
    corr_limit = 3 / sqrt(n)

    edges = np.flatnonzero(np.diff(bits) != 0)
    longest = int(np.diff(edges).max()) + 1 if edges.size > 1 else nbits

    blocks = data[: (n // 16) * 16].reshape(-1, 16)
    duplicates = int(
        blocks.shape[0] - np.unique(blocks.view([("", blocks.dtype)] * 16)).size
    )

    compressed_bits = len(zlib.compress(data.tobytes(), 9)) * 8

    checks = {
        "sha256": hashlib.sha256(data.tobytes()).hexdigest() == EXPECTED_SHA256,
        "size": n == EXPECTED_BYTES,
        "monobit": monobit_p > 0.01,
        "byte_uniformity": chi_p > 0.01,
        "serial_correlation": all(abs(c) < corr_limit for c in corr),
        "no_duplicate_16B_blocks": duplicates == 0,
        "incompressible": compressed_bits / n > 7.99,
    }

    return {
        "file": path,
        "bytes": n,
        "bits": nbits,
        "sha256": hashlib.sha256(data.tobytes()).hexdigest(),
        "bit_ones": ones,
        "bit_balance_pct": round(ones / nbits * 100, 4),
        "monobit_p": round(monobit_p, 4),
        "byte_chi2": round(chi, 2),
        "byte_chi2_p": round(chi_p, 4),
        "byte_mean": round(float(data.mean()), 2),
        "byte_std": round(float(data.std()), 3),
        "serial_corr_lag1_8": [round(c, 6) for c in corr],
        "serial_corr_limit_3sigma": round(corr_limit, 6),
        "longest_identical_run_bits": longest,
        "duplicate_16B_blocks": duplicates,
        "zlib_bits_per_byte": round(compressed_bits / n, 4),
        "checks": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Independent sanity check of the sample.")
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--json", action="store_true", help="emit JSON only")
    args = ap.parse_args()

    r = analyse(args.file)
    if args.json:
        print(json.dumps(r, indent=2))
        return 0 if r["verdict"] == "PASS" else 1

    width = 34
    rows = [
        ("file", r["file"]),
        ("bytes / bits", f"{r['bytes']:,} / {r['bits']:,}"),
        ("sha256 (matches report)", r["sha256"]),
        ("bit balance", f"{r['bit_balance_pct']} % ones"),
        ("monobit p-value", r["monobit_p"]),
        ("byte chi-square", f"{r['byte_chi2']} (p={r['byte_chi2_p']})"),
        (
            "byte mean / std",
            f"{r['byte_mean']} / {r['byte_std']} (ideal 127.5 / 73.90)",
        ),
        (
            "serial corr lag 1..8",
            " ".join(f"{c:+.5f}" for c in r["serial_corr_lag1_8"]),
        ),
        ("serial corr 3-sigma limit", r["serial_corr_limit_3sigma"]),
        ("longest identical run", f"{r['longest_identical_run_bits']} bit"),
        ("duplicate 16-byte blocks", r["duplicate_16B_blocks"]),
        ("zlib bits/byte", f"{r['zlib_bits_per_byte']} (ideal 8.0000)"),
    ]
    for k, v in rows:
        print(f"{k:<{width}} {v}")
    print()
    for name, ok in r["checks"].items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"\nVERDICT: {r['verdict']}")
    return 0 if r["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
