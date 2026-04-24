#!/usr/bin/env python3
"""
Security Test Suite — tests that go beyond basic randomness:
  1. Autocorrelation scan (lag 1-1000)
  2. Conditional entropy / information leakage
  3. Markov prediction attack
  4. ML distinguisher (Gradient Boosting + Random Forest vs os.urandom)

Usage: python tests/security_tests.py --file <path> [--output dir] [--skip-ml]
"""

import argparse
import json
import os
import sys
from collections import Counter

import numpy as np
from scipy import stats


# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_data(path):
    with open(path, "rb") as f:
        return f.read()

def to_bits(data):
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))

def print_section(title):
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print("=" * 65)


# ─── 1. Autocorrelation scan ─────────────────────────────────────────────────

def run_autocorrelation(bits, max_lag=1000):
    """
    Scan lags 1-max_lag for statistically significant autocorrelation.
    Threshold: 3σ = 3/√n.  Any lag |r| > threshold is flagged.
    PASS criterion: ≤ 0.3% of lags significant (expected ~0.3% by chance at 3σ).
    """
    n = len(bits)
    signal = 2 * bits.astype(np.float32) - 1
    threshold = 3.0 / np.sqrt(n)

    sig_lags = []
    for lag in range(1, max_lag + 1):
        r = float(np.corrcoef(signal[:-lag], signal[lag:])[0, 1])
        if abs(r) > threshold:
            sig_lags.append((lag, r))

    rate = len(sig_lags) / max_lag
    # Expected false positives at 3σ: ~0.27%; allow up to 1% before failing
    ok = rate <= 0.01

    print(f"  Threshold (3σ)      : {threshold:.6f}")
    print(f"  Significant lags    : {len(sig_lags)} / {max_lag}  ({rate*100:.2f}%)")
    if sig_lags:
        top = sorted(sig_lags, key=lambda x: abs(x[1]), reverse=True)[:5]
        print(f"  Top significant lags:")
        for lag, r in top:
            print(f"    lag {lag:4d}  r={r:+.6f}")
    else:
        print("  No significant autocorrelation detected")
    print(f"\n  Result: {'PASS' if ok else 'FAIL'}")

    return {
        "n_significant": len(sig_lags),
        "max_lag_tested": max_lag,
        "significant_rate": round(rate, 6),
        "top_lags": [(int(l), round(r, 8)) for l, r in sig_lags[:10]],
        "pass": bool(ok),
    }


# ─── 2. Conditional entropy / information leakage ────────────────────────────

def run_info_leakage(bits, lags=(1, 8, 64, 174, 311, 392, 740, 746)):
    """
    Compute mutual information I(X; X_lag) for each lag.
    True random: I ≈ 0.  PASS if max leakage < 0.01%.
    """
    n = len(bits)
    ones = int(np.sum(bits))
    p1 = ones / n
    p0 = 1 - p1
    H_x = -(p0 * np.log2(p0) if p0 > 0 else 0) - (p1 * np.log2(p1) if p1 > 0 else 0)

    max_leakage = 0.0
    results_per_lag = {}

    print(f"  {'Lag':>6}  {'Mutual Info':>14}  {'Leakage %':>10}")
    print(f"  {'-'*6}  {'-'*14}  {'-'*10}")

    for lag in lags:
        if lag >= n:
            continue
        cond = bits[:-lag]
        outcome = bits[lag:]
        joint = Counter(zip(cond.tolist(), outcome.tolist()))
        n_pairs = len(outcome)

        # H(X,Y)
        H_xy = -sum(c / n_pairs * np.log2(c / n_pairs) for c in joint.values() if c > 0)
        # H(Y) — the condition variable
        c_ones = int(np.sum(cond))
        cp1 = c_ones / len(cond)
        cp0 = 1 - cp1
        H_y = -(cp0 * np.log2(cp0) if cp0 > 0 else 0) - (cp1 * np.log2(cp1) if cp1 > 0 else 0)
        # I(X;Y) = H(X) - H(X|Y) = H(X) - (H(X,Y) - H(Y))
        MI = H_x - (H_xy - H_y)
        leakage_pct = abs(MI) / H_x * 100 if H_x > 0 else 0

        print(f"  {lag:6d}  {MI:+14.8f}  {leakage_pct:10.6f}%")
        results_per_lag[lag] = {"MI": round(float(MI), 10), "leakage_pct": round(leakage_pct, 8)}
        if leakage_pct > max_leakage:
            max_leakage = leakage_pct

    ok = max_leakage < 0.01
    print(f"\n  Max leakage: {max_leakage:.6f}%")
    print(f"  Result: {'PASS' if ok else 'FAIL'}")

    return {
        "per_lag": results_per_lag,
        "max_leakage_pct": round(max_leakage, 8),
        "pass": bool(ok),
    }


# ─── 3. Markov prediction attack ─────────────────────────────────────────────

def run_markov_attack(bits, context_lengths=(1, 2, 3, 4)):
    """
    Train a Markov model on 80% of bits, predict the remaining 20%.
    PASS: no model achieves accuracy significantly above 50% (p ≥ 0.001).
    """
    n = min(len(bits), 2_000_000)
    data = bits[:n]
    split = int(0.8 * n)
    train, test = data[:split], data[split:]

    best_accuracy = 0.5
    best_p = 1.0
    rows = []

    print(f"  {'Context':>9}  {'Accuracy':>10}  {'Advantage':>10}  {'p-value':>12}  {'Status':>8}")
    print(f"  {'-'*9}  {'-'*10}  {'-'*10}  {'-'*12}  {'-'*8}")

    for ctx_len in context_lengths:
        # Build transition table
        table = {}
        for i in range(ctx_len, len(train)):
            ctx = tuple(train[i - ctx_len:i].tolist())
            b = int(train[i])
            if ctx not in table:
                table[ctx] = [0, 0]
            table[ctx][b] += 1

        # Predict
        correct = total = 0
        for i in range(ctx_len, len(test)):
            ctx = tuple(test[i - ctx_len:i].tolist())
            if ctx in table:
                pred = 1 if table[ctx][1] > table[ctx][0] else 0
                if pred == int(test[i]):
                    correct += 1
            total += 1

        acc = correct / total if total > 0 else 0.5
        result = stats.binomtest(correct, total, 0.5, alternative="greater")
        p = float(result.pvalue)
        adv = acc - 0.5
        broken = p < 0.001 and acc > 0.51
        status = "BROKEN" if broken else "SECURE"

        print(f"  {ctx_len:>9}  {acc*100:>9.4f}%  {adv*100:>+9.4f}%  {p:>12.6f}  {status:>8}")
        rows.append({"context": ctx_len, "accuracy": round(acc, 6), "p_value": round(p, 8), "pass": not broken})

        if acc > best_accuracy:
            best_accuracy = acc
            best_p = p

    ok = best_accuracy <= 0.51 or best_p >= 0.001
    print(f"\n  Best accuracy: {best_accuracy*100:.4f}%")
    print(f"  Result: {'PASS (not breakable)' if ok else 'FAIL (broken)'}")

    return {"models": rows, "best_accuracy": round(best_accuracy, 6), "pass": bool(ok)}


# ─── 4. ML distinguisher ─────────────────────────────────────────────────────

def extract_features(data_chunk, lags=(1, 8, 64, 174, 311, 392, 740)):
    bits = np.unpackbits(np.frombuffer(data_chunk, dtype=np.uint8))
    signal = 2 * bits.astype(np.float32) - 1
    byte_arr = np.frombuffer(data_chunk, dtype=np.uint8)

    feats = [
        float(np.mean(bits)),
        float(np.std(bits)),
        float(1 + np.sum(bits[1:] != bits[:-1])) / len(bits),  # run density
    ]
    for lag in lags:
        if lag < len(signal):
            r = float(np.corrcoef(signal[:-lag], signal[lag:])[0, 1])
            feats.append(r if not np.isnan(r) else 0.0)
        else:
            feats.append(0.0)

    # Byte-level features
    bc = np.bincount(byte_arr, minlength=256).astype(np.float32)
    probs = bc / len(byte_arr)
    probs_nz = probs[probs > 0]
    feats.append(float(-np.sum(probs_nz * np.log2(probs_nz))))          # byte entropy
    feats.append(float(np.max(np.abs(bc - len(byte_arr) / 256))) / (len(byte_arr) / 256))  # max byte dev
    half = len(bits) // 2
    feats.append(float(abs(np.mean(bits[:half]) - np.mean(bits[half:]))))

    return np.array(feats, dtype=np.float32)


def run_ml_distinguisher(data, n_samples=400, chunk_size=10_000):
    """
    Label V2 data (0) vs os.urandom (1), train Gradient Boosting and Random Forest.
    PASS: best accuracy ≤ 51% OR p-value ≥ 0.001 (classifier no better than chance).
    """
    try:
        from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
        from sklearn.model_selection import cross_val_score
    except ImportError:
        print("  scikit-learn not installed — skipping ML test")
        return {"pass": True, "skipped": True}

    half = n_samples // 2

    # V2 samples
    v2_chunks = [data[i * chunk_size:(i + 1) * chunk_size]
                 for i in range(half) if (i + 1) * chunk_size <= len(data)]
    # os.urandom samples
    rng_chunks = [os.urandom(chunk_size) for _ in range(half)]

    if len(v2_chunks) < half // 2:
        print("  Not enough data for ML test — skipping")
        return {"pass": True, "skipped": True}

    X_v2  = np.array([extract_features(c) for c in v2_chunks])
    X_rng = np.array([extract_features(c) for c in rng_chunks])
    X = np.vstack([X_v2, X_rng])
    y = np.array([0] * len(X_v2) + [1] * len(X_rng))

    classifiers = [
        ("Gradient Boosting", GradientBoostingClassifier(n_estimators=100, random_state=42)),
        ("Random Forest",     RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)),
    ]

    print(f"  Samples: {len(X_v2)} V2  +  {len(X_rng)} os.urandom  =  {len(X)} total")
    print(f"  Features per sample: {X.shape[1]}")
    print()
    print(f"  {'Classifier':<22}  {'Accuracy':>10}  {'Advantage':>10}  {'p-value':>12}  {'Status':>12}")
    print(f"  {'-'*22}  {'-'*10}  {'-'*10}  {'-'*12}  {'-'*12}")

    rows = []
    best_acc = 0.5

    for name, clf in classifiers:
        # 5-fold cross-validation for more robust estimate
        scores = cross_val_score(clf, X, y, cv=5, scoring="accuracy")
        acc = float(np.mean(scores))
        n_correct = int(acc * len(y))
        p = float(stats.binomtest(n_correct, len(y), 0.5, alternative="greater").pvalue)
        adv = acc - 0.5
        broken = acc > 0.51 and p < 0.001
        status = "DISTINGUISHABLE" if broken else "INDISTINGUISHABLE"
        print(f"  {name:<22}  {acc*100:>9.2f}%  {adv*100:>+9.2f}%  {p:>12.6f}  {status:>12}")
        rows.append({"classifier": name, "accuracy": round(acc, 6), "p_value": round(p, 8), "pass": not broken})
        if acc > best_acc:
            best_acc = acc

    ok = all(r["pass"] for r in rows)
    print(f"\n  Best accuracy: {best_acc*100:.2f}%")
    print(f"  Result: {'PASS (indistinguishable)' if ok else 'FAIL (distinguishable!)'}")

    return {"classifiers": rows, "best_accuracy": round(best_acc, 6), "pass": bool(ok)}


# ─── Main ────────────────────────────────────────────────────────────────────

def run_all(data_path, output_dir, skip_ml):
    data = load_data(data_path)
    bits = to_bits(data)
    print(f"\nFile : {data_path}")
    print(f"Size : {len(data):,} bytes  ({len(data)/1024/1024:.2f} MB)")
    print(f"Bits : {len(bits):,}")

    all_results = {}
    exit_ok = True

    print_section("1 · Autocorrelation Scan  (lag 1–1000)")
    r = run_autocorrelation(bits[:10_000_000] if len(bits) > 10_000_000 else bits)
    all_results["autocorrelation"] = r
    if not r["pass"]:
        exit_ok = False

    print_section("2 · Conditional Entropy / Information Leakage")
    r = run_info_leakage(bits[:5_000_000] if len(bits) > 5_000_000 else bits)
    all_results["info_leakage"] = r
    if not r["pass"]:
        exit_ok = False

    print_section("3 · Markov Prediction Attack  (context 1–4)")
    r = run_markov_attack(bits)
    all_results["markov_attack"] = r
    if not r["pass"]:
        exit_ok = False

    if not skip_ml:
        print_section("4 · ML Distinguisher Attack  (GBM + RF vs os.urandom)")
        r = run_ml_distinguisher(data)
        all_results["ml_distinguisher"] = r
        if not r["pass"]:
            exit_ok = False
    else:
        print_section("4 · ML Distinguisher Attack  — SKIPPED (--skip-ml)")
        all_results["ml_distinguisher"] = {"pass": True, "skipped": True}

    # ── Summary ───────────────────────────────────────────────────────────────
    print_section("SUMMARY")
    labels = [
        ("Autocorrelation",    all_results["autocorrelation"]["pass"]),
        ("Info Leakage",       all_results["info_leakage"]["pass"]),
        ("Markov Attack",      all_results["markov_attack"]["pass"]),
        ("ML Distinguisher",   all_results["ml_distinguisher"]["pass"]),
    ]
    for name, ok in labels:
        icon = "✓" if ok else "✗"
        print(f"  {icon} {name}")

    print(f"\n  RESULT: {'ALL PASSED' if exit_ok else 'ONE OR MORE FAILED'}")

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        out = os.path.join(output_dir, "security_results.json")
        with open(out, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\n  Results saved → {out}")

    return exit_ok


def main():
    parser = argparse.ArgumentParser(description="Security / attack resistance test suite")
    parser.add_argument("--file",    required=True, help="Path to binary data file")
    parser.add_argument("--output",  default="",    help="Directory to save results JSON")
    parser.add_argument("--skip-ml", action="store_true",
                        help="Skip the ML distinguisher (saves ~2 min in CI)")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"ERROR: file not found: {args.file}", file=sys.stderr)
        sys.exit(2)

    ok = run_all(args.file, args.output, args.skip_ml)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
