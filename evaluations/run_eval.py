"""Run the local evaluation suite and emit a machine-readable scorecard."""
import json
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
started = time.perf_counter()
proc = subprocess.run(
    [sys.executable, "-m", "pytest", "evaluations/test_core.py", "-q"],
    cwd=root, text=True, capture_output=True,
)
print(proc.stdout, end="")
if proc.stderr:
    print(proc.stderr, file=sys.stderr, end="")
elapsed = round(time.perf_counter() - started, 3)
summary = {
    "passed": proc.returncode == 0,
    "returncode": proc.returncode,
    "test_file": "evaluations/test_core.py",
    "tests": 30,
    "elapsed_seconds": elapsed,
}
(root / "evaluations" / "latest_result.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
raise SystemExit(proc.returncode)
