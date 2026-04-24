#!/usr/bin/env bash
# Run the official NIST STS and parse results.
# Usage: bash tests/run_sts.sh <data_file> [sts_binary] [iterations] [work_dir]
set -euo pipefail

DATA_FILE="${1:?Usage: run_sts.sh <data_file> [sts_binary] [iterations] [work_dir]}"
STS_BIN="${2:-sts_legacy_fft}"
ITERATIONS="${3:-89}"
WORK_DIR="${4:-sts_results}"

# ── Locate or build sts_legacy_fft ───────────────────────────────────────────
if ! command -v "$STS_BIN" &>/dev/null && [[ ! -x "$STS_BIN" ]]; then
    echo "[STS] Binary '$STS_BIN' not found — building from source..."

    if [[ ! -d sts-src ]]; then
        git clone --depth=1 https://github.com/arcetri/sts sts-src
    fi

    # 'make legacy' needs only gcc + make (no fftw3 dependency)
    (cd sts-src && make legacy 2>&1)
    STS_BIN="sts-src/sts_legacy_fft"
    echo "[STS] Build complete: $STS_BIN"
fi

# ── Run sts ──────────────────────────────────────────────────────────────────
mkdir -p "$WORK_DIR"
WORK_DIR="$(cd "$WORK_DIR" && pwd)"   # normalize: remove trailing slash / relative refs

echo "[STS] Running: $STS_BIN -i $ITERATIONS -w $WORK_DIR -s -F r $DATA_FILE"
"$STS_BIN" -v 1 -i "$ITERATIONS" -I 20 -w "$WORK_DIR" -s -F r "$DATA_FILE"

RESULT_FILE="$WORK_DIR/result.txt"

if [[ ! -f "$RESULT_FILE" ]]; then
    echo "[STS] ERROR: result.txt not found in $WORK_DIR" >&2
    exit 1
fi

# ── Parse result.txt ─────────────────────────────────────────────────────────
python3 - "$RESULT_FILE" <<'PYEOF'
import sys, re

result_file = sys.argv[1]
text = open(result_file).read()

# Extract overall counts
m = re.search(r'(\d+)/(\d+) tests passed', text)
if not m:
    print("[STS] ERROR: could not parse result.txt")
    sys.exit(1)

passed, total = int(m.group(1)), int(m.group(2))
failed = total - passed
rate = passed / total * 100

print("\n" + "=" * 65)
print("  OFFICIAL NIST STS (SP 800-22) RESULTS")
print("=" * 65)
print(f"  Streams tested : {total}")
print(f"  Tests passed   : {passed}/{total}  ({rate:.1f}%)")
print(f"  Tests failed   : {failed}")

# List failures — lines like "6/148 of the ... tests FAILED ..."
# The leading number IS the failure count, not the pass count.
failures = re.findall(r'(\d+)/(\d+)[^\n]+FAILED[^\n]+', text)
if failures:
    print("\n  Failed sub-tests:")
    for f_count, f_total in failures:
        print(f"    {f_count}/{f_total} failed")

# NIST guidance: proportion failures are expected at ~1% per sub-test;
# a pass rate ≥ 95% (179/188) is generally acceptable.
THRESHOLD = 0.95
ok = (passed / total) >= THRESHOLD
print(f"\n  Threshold : ≥{THRESHOLD*100:.0f}%")
print(f"  Result    : {'PASS' if ok else 'FAIL'}")
print("=" * 65)

sys.exit(0 if ok else 1)
PYEOF
