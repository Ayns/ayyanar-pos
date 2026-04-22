#!/bin/sh
# AYY-27 — Build script: compile critical modules with Nuitka
#
# Usage:
#   ./build.sh              # Build all critical modules
#   ./build.sh drainer      # Build only the drainer module
#   ./build.sh --help
#
# Output: .so extensions in the module directory alongside the Python source.
# The compiled modules are drop-in replacements for their .py counterparts.

set -eu

cd "$(dirname "$0")/.."

MODULES="${1:-all}"
PYTHON="${PYTHON:-python3}"

echo "=== AYY-27 Nuitka Build Pipeline ==="
echo "Python:  $($PYTHON --version 2>&1)"
echo "Nuitka:  $($PYTHON -m nuitka --version 2>&1)"
echo ""

NUITKA_FLAGS="
    --module
    --strip-so
    --without-pyc
    --output-dir=.
    --enable-plugin=django
"

compile_module() {
    local module="$1"
    local src_path="$2"
    echo "Compiling: $module ($src_path)"
    $PYTHON -m nuitka $NUITKA_FLAGS "$src_path" && echo "  OK" || echo "  FAILED"
}

case "$MODULES" in
    drainer)
        compile_module sync_core/drainer pos_spike/sync_core/drainer.py
        ;;
    cloud)
        compile_module sync_core/cloud pos_spike/sync_core/cloud.py
        ;;
    license)
        compile_module license_server irp_spike/license_server.py 2>/dev/null || echo "  SKIPPED (no license_server module)"
        ;;
    all)
        # Core: outbox drainer (most latency-sensitive)
        compile_module sync_core/drainer pos_spike/sync_core/drainer.py

        # Cloud ingest (frequent calls during replay)
        compile_module sync_core/cloud pos_spike/sync_core/cloud.py

        # E-invoice client (complex state machine, worth compiling)
        compile_module irp_client/client irp_spike/irp_client/client.py

        # Tally XML generator (deterministic output requirement)
        compile_module tally_client/xml_generator tally_spike/tally_client/xml_generator.py

        echo ""
        echo "=== Build complete ==="

        # Show compiled .so files
        echo "Compiled extensions:"
        find . -name "*.so" -type f 2>/dev/null | head -20
        ;;
    --help)
        echo "Usage: ./build.sh [module]"
        echo ""
        echo "Modules:"
        echo "  drainer   — Sync outbox drainer (Celery worker)"
        echo "  cloud     — Cloud ingest endpoint"
        echo "  license   — License server prototype"
        echo "  all       — All critical modules (default)"
        exit 0
        ;;
    *)
        echo "Unknown module: $MODULES"
        echo "Run './build.sh --help' for usage"
        exit 1
        ;;
esac
