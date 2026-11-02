"""Smoke test: reconstruct camera poses from the sample frames in test/sample_frames.

Usage: python test/run_test.py
Passes when at least 80 percent of the sample frames register in COLMAP. A full model (training and the web viewer)
needs Brush and a GPU, see the README; the expected result for these frames is in test/expected/.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRAMES = ROOT / "test" / "sample_frames"


def main() -> int:
    frames = sorted(FRAMES.glob("*.jpg"))
    if not frames:
        print("no sample frames found in", FRAMES)
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        (work / "images").mkdir(parents=True)
        for f in frames:
            shutil.copy2(f, work / "images" / f.name)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "pipeline" / "run_colmap.py"), str(work)],
            capture_output=True, text=True,
        )
        out = proc.stdout + proc.stderr
        m = re.search(r"model \d+: (\d+)/(\d+) images registered, (\d+) points, mean reproj error ([\d.]+)px", out)
        if proc.returncode != 0 or not m:
            print(out[-1500:])
            print("FAIL: pose estimation did not produce a model")
            return 1
        reg, n, pts, err = int(m[1]), int(m[2]), int(m[3]), float(m[4])
        ok = reg >= 0.8 * n and err < 1.0
        print(f"{'PASS' if ok else 'FAIL'}: {reg}/{n} frames registered, {pts} points, reprojection error {err}px")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
