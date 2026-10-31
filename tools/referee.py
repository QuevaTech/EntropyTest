#!/usr/bin/env python3
"""Referee harness for Level 1 (Predictor) and Level 2 (Distinguisher).

The whole point of a public challenge is that acceptance is not a matter of
opinion. This script is the arbiter: it takes a frozen prediction file and a
held-out stream, recomputes the statistic and writes results.json.

Level 1 — Predictor
    The challenger submits one file of predicted bits, aligned so that byte 0
    bit 0 is a prediction for bit 0 of the held-out stream.

        python tools/referee.py l1 --predictions sub.bin --stream eval.bin

Level 2 — Distinguisher
    The challenger submits a JSONL dump of per-sample scores for the held-out
    file, computed by their frozen model.

        python tools/referee.py l2 --scores sub.jsonl --stream eval.bin

Exit code 0 = challenge succeeded (the generator lost), 1 = failed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from math import erfc, sqrt

import numpy as np

ALPHA = 0.001  # two-sided significance
MIN_BITS = 100_000
MIN_L2_PER_CLASS = 100_000


def binomial_z(k: int, n: int) -> float:
    """z-score of k successes in n Bernoulli(0.5) trials."""
    return abs(2 * k - n) / sqrt(n)


def p_two_sided(z: float) -> float:
    return erfc(z / sqrt(2))


def required_accuracy(n: int, alpha: float = ALPHA) -> float:
    """Accuracy that gives p < alpha (two-sided) for exactly n trials."""
    from statistics import NormalDist

    z = NormalDist().inv_cdf(1 - alpha / 2)
    return 0.5 + z * sqrt(0.25 / n)


def level1(pred_path: str, stream_path: str) -> dict:
    pred = np.unpackbits(np.fromfile(pred_path, dtype=np.uint8))
    truth = np.unpackbits(np.fromfile(stream_path, dtype=np.uint8))
    n = min(pred.size, truth.size)
    if n < MIN_BITS:
        return {
            "level": "L1",
            "error": f"at least {MIN_BITS:,} predictions required, got {n:,}",
        }
    hits = int((pred[:n] == truth[:n]).sum())
    acc = hits / n
    z = binomial_z(hits, n)
    p = p_two_sided(z)
    return {
        "level": "L1",
        "n": n,
        "hits": hits,
        "accuracy": round(acc, 6),
        "required_accuracy": round(required_accuracy(n), 6),
        "z": round(z, 4),
        "p_value": p,
        "passed": bool(p < ALPHA and acc > 0.5),
    }


def level2(scores_path: str, stream_path: str, sample_size: int = 32) -> dict:
    """Expect JSONL: {"sample_index": i, "score": x}, higher score = "from us".

    Ordering contract of the held-out file: the first half of the samples is
    generator output (label 0), the second half is os.urandom (label 1).
    """
    with open(scores_path) as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    if not rows:
        return {"level": "L2", "error": "empty score file"}
    idx = np.array([r["sample_index"] for r in rows], dtype=np.int64)
    total = int(np.fromfile(stream_path, dtype=np.uint8).size)
    nsamples = total // sample_size
    half = nsamples / 2
    if idx.max() >= nsamples:
        return {
            "level": "L2",
            "error": f"sample_index out of range: stream holds {nsamples:,} samples of {sample_size} bytes",
        }
    if len(set(idx.tolist())) != len(rows):
        return {"level": "L2", "error": "duplicate sample_index values"}
    labels = (idx >= half).astype(np.int8)
    s = np.array([r["score"] for r in rows], dtype=np.float64)
    # advantage = |2*AUC - 1|
    pos, neg = s[labels == 0], s[labels == 1]
    if pos.size == 0 or neg.size == 0:
        return {"level": "L2", "error": "both classes must be present"}
    if min(pos.size, neg.size) < MIN_L2_PER_CLASS:
        return {
            "level": "L2",
            "error": f"at least {MIN_L2_PER_CLASS:,} scored samples per class required, got {min(pos.size, neg.size):,}",
        }
    # Mann-Whitney U -> AUC, via ranks (O(n log n), no n^2 matrix)
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(s.size, dtype=np.float64)
    ranks[order] = np.arange(1, s.size + 1)
    # average ranks for ties
    uniq, inv, counts = np.unique(s, return_inverse=True, return_counts=True)
    if (counts > 1).any():
        sums = np.zeros(uniq.size)
        np.add.at(sums, inv, ranks)
        ranks = (sums / counts)[inv]
    rank_pos = ranks[labels == 0].sum()
    auc = float((rank_pos - pos.size * (pos.size + 1) / 2) / (pos.size * neg.size))
    adv = abs(2 * auc - 1)
    return {
        "level": "L2",
        "n_per_class": int(min(pos.size, neg.size)),
        "auc": round(auc, 6),
        "advantage": round(adv, 6),
        "threshold": 0.01,
        "passed": bool(adv > 0.01),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="level", required=True)

    a = sub.add_parser("l1", help="predictor referee")
    a.add_argument("--predictions", required=True)
    a.add_argument("--stream", required=True)
    a.add_argument("--out", default="results.json", help="where to write the verdict")

    b = sub.add_parser("l2", help="distinguisher referee")
    b.add_argument("--scores", required=True)
    b.add_argument("--stream", required=True)
    b.add_argument(
        "--sample-size",
        type=int,
        default=32,
        help="bytes per scored sample (default 32)",
    )
    b.add_argument("--out", default="results.json", help="where to write the verdict")

    args = ap.parse_args()
    if args.level == "l1":
        verdict = level1(args.predictions, args.stream)
    else:
        verdict = level2(args.scores, args.stream, args.sample_size)
    verdict["evaluated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    verdict["alpha"] = ALPHA

    with open(args.out, "w") as fh:
        json.dump(verdict, fh, indent=2)

    print(json.dumps(verdict, indent=2))
    if "error" in verdict:
        return 1
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
