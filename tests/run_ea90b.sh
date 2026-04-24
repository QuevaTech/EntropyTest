#!/usr/bin/env bash
# Run official NIST SP 800-90B ea_iid and ea_non_iid tools.
# Local macOS : uses Docker image nist-ea90b (keeps Mac clean)
# CI Linux    : builds natively with apt-get
#
# Usage: bash tests/run_ea90b.sh <data_file> [bits_per_symbol] [output_dir]
set -euo pipefail

DATA_FILE="${1:?Usage: run_ea90b.sh <data_file> [bits_per_symbol] [output_dir]}"
BITS="${2:-8}"
OUT_DIR="${3:-ea90b_results}"
mkdir -p "$OUT_DIR"

IID_LOG="$OUT_DIR/ea_iid.txt"
NON_IID_LOG="$OUT_DIR/ea_non_iid.txt"

# ── Locate or build the tools ─────────────────────────────────────────────────
USE_DOCKER=false

if command -v ea_iid &>/dev/null; then
    : # already on PATH — use directly

elif [[ "$(uname)" == "Linux" ]]; then
    echo "[EA90B] Building from source (Linux CI)..."
    if [[ ! -d ea-src ]]; then
        git clone --depth=1 https://github.com/usnistgov/SP800-90B_EntropyAssessment ea-src
    fi
    (cd ea-src/cpp && make iid non_iid 2>&1)
    export PATH="$(pwd)/ea-src/cpp:$PATH"

else
    # macOS: run inside Docker (Mac stays clean)
    USE_DOCKER=true
    IMAGE="nist-ea90b"
    if ! docker image inspect "$IMAGE" &>/dev/null 2>&1; then
        echo "[EA90B] Building Docker image $IMAGE ..."
        docker build -t "$IMAGE" -f Dockerfile.ea90b . 2>&1
    fi
fi

run_tool() {
    local tool="$1" args="${@:2}"
    if $USE_DOCKER; then
        local abs_data
        abs_data="$(cd "$(dirname "$DATA_FILE")" && pwd)/$(basename "$DATA_FILE")"
        docker run --rm \
            -v "${abs_data}:/data/data.bin:ro" \
            nist-ea90b \
            "${tool} -v /data/data.bin ${BITS}"
    else
        "$tool" -v "$DATA_FILE" "$BITS"
    fi
}

# ── Run ea_iid ────────────────────────────────────────────────────────────────
echo ""
echo "================================================================="
echo "  NIST SP 800-90B — IID Tests"
echo "================================================================="
run_tool ea_iid 2>&1 | tee "$IID_LOG"

# ── Run ea_non_iid ────────────────────────────────────────────────────────────
echo ""
echo "================================================================="
echo "  NIST SP 800-90B — Non-IID Entropy Estimators"
echo "================================================================="
run_tool ea_non_iid 2>&1 | tee "$NON_IID_LOG"

# ── Parse and summarise ───────────────────────────────────────────────────────
python3 - "$IID_LOG" "$NON_IID_LOG" <<'PYEOF'
import sys, re

def extract(text, pattern, default="N/A"):
    m = re.search(pattern, text)
    return m.group(1) if m else default

iid_out     = open(sys.argv[1]).read()
non_iid_out = open(sys.argv[2]).read()

print("\n" + "=" * 65)
print("  NIST SP 800-90B  —  FINAL SUMMARY")
print("=" * 65)

iid_passed  = "Passed IID permutation tests" in iid_out
print(f"\n  IID Test              : {'PASS' if iid_passed else 'FAIL'}")

h_orig_iid = extract(iid_out,     r'H_original:\s+([\d.]+)')
h_bits_iid = extract(iid_out,     r'H_bitstring:\s+([\d.]+)')
h_min_iid  = extract(iid_out,     r'min\(H_original.*?\):\s+([\d.]+)')
print(f"  H_original (IID)      : {h_orig_iid} bits/byte")
print(f"  H_bitstring (IID)     : {h_bits_iid} bits/bit")
print(f"  Min-Entropy (IID)     : {h_min_iid} bits/byte")

# Non-IID results (conservative bound)
h_orig_niid = extract(non_iid_out, r'H_original:\s+([\d.]+)')
h_bits_niid = extract(non_iid_out, r'H_bitstring:\s+([\d.]+)')
h_min_niid  = extract(non_iid_out, r'min\(H_original.*?\):\s+([\d.]+)')
print(f"\n  H_original (non-IID)  : {h_orig_niid} bits/byte")
print(f"  H_bitstring (non-IID) : {h_bits_niid} bits/bit")
print(f"  Min-Entropy (non-IID) : {h_min_niid} bits/byte")

try:
    min_e = float(h_min_niid if h_min_niid != "N/A" else h_min_iid)
    entropy_ok = min_e >= 7.0
except ValueError:
    entropy_ok = False

ok = iid_passed and entropy_ok
print(f"\n  Min-entropy ≥ 7.0     : {'PASS' if entropy_ok else 'FAIL'}")
print(f"\n  OVERALL               : {'PASS' if ok else 'FAIL'}")
print("=" * 65)

sys.exit(0 if ok else 1)
PYEOF
