"""Step 4: remove floaters, shrink the file, and write walking bounds for the viewer.

Usage: python pipeline/clean_splat.py in.ply out.ply [--config viewer/assets/config.json]
Keeps splats that are opaque enough, not huge, and inside a robust box around the
dense core of the scene. Drops the higher-order spherical harmonics (f_rest) so the
web file is about a quarter of the size; view-dependent shine is lost, colour stays.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from plyfile import PlyData, PlyElement


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--min-opacity", type=float, default=0.15)
    ap.add_argument("--lo", type=float, default=3.0, help="percentile for the core box")
    ap.add_argument("--pad", type=float, default=0.25, help="box padding as a fraction of its size")
    ap.add_argument("--max-scale-frac", type=float, default=0.08, help="max splat size / box diagonal")
    args = ap.parse_args()

    ply = PlyData.read(args.src)
    v = ply["vertex"].data
    names = v.dtype.names
    xyz = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float64)
    opacity = 1 / (1 + np.exp(-v["opacity"].astype(np.float64)))
    scale = np.exp(np.stack([v["scale_0"], v["scale_1"], v["scale_2"]], 1).astype(np.float64))
    n0 = len(v)

    solid = opacity > args.min_opacity
    lo = np.percentile(xyz[solid], args.lo, axis=0)
    hi = np.percentile(xyz[solid], 100 - args.lo, axis=0)
    size = hi - lo
    lo -= args.pad * size
    hi += args.pad * size
    diag = float(np.linalg.norm(hi - lo))

    keep = (
        solid
        & np.all((xyz >= lo) & (xyz <= hi), axis=1)
        & (scale.max(1) < args.max_scale_frac * diag)
    )
    keep_cols = [n for n in names if not n.startswith("f_rest")]
    kept_rows = v[keep]
    out = np.empty(len(kept_rows), dtype=[(c, "<f4") for c in keep_cols])
    for c in keep_cols:
        out[c] = kept_rows[c]
    args.dst.parent.mkdir(parents=True, exist_ok=True)
    PlyData([PlyElement.describe(out, "vertex")], text=False).write(args.dst)
    print(f"{n0} -> {int(keep.sum())} splats; box lo={lo.round(2)} hi={hi.round(2)}; "
          f"{args.src.stat().st_size / 1e6:.1f} MB -> {args.dst.stat().st_size / 1e6:.1f} MB")

    if args.config:
        # bounds are x/z extents after the viewer's default 180 degree flip about X (x stays, z negates)
        kept = xyz[keep]
        zx = kept[:, 0]
        zz = -kept[:, 2]
        cfg = json.loads(args.config.read_text()) if args.config.exists() else {}
        cfg["bounds"] = [float(np.percentile(zx, 5)), float(np.percentile(zx, 95)),
                         float(np.percentile(zz, 5)), float(np.percentile(zz, 95))]
        args.config.parent.mkdir(parents=True, exist_ok=True)
        args.config.write_text(json.dumps(cfg, indent=2))
        print("wrote", args.config, cfg["bounds"])


if __name__ == "__main__":
    main()
