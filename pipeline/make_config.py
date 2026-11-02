"""Step 5: place the model for the viewer using the real camera path.

Usage: python pipeline/make_config.py <colmap_model_dir> <cleaned.ply> viewer/assets/config.json [--phone-height 1.4]

The phone's own trajectory is the best evidence of where a person can stand, so we use it to
  * set scale: phone height above the estimated floor is assumed to be --phone-height metres,
  * put the floor at y = 0 and the first camera at the origin, facing the way it was filmed,
  * bound walking to the filmed path plus a margin.
COLMAP is y-down, so the viewer flips the splat 180 degrees about X (x, -y, -z).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pycolmap
from plyfile import PlyData


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model", type=Path)
    ap.add_argument("ply", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--phone-height", type=float, default=1.4, help="assumed camera height above floor, metres")
    ap.add_argument("--margin", type=float, default=0.8, help="metres beyond the filmed path")
    ap.add_argument("--speed", type=float, default=1.3, help="walking speed, m/s")
    args = ap.parse_args()

    rec = pycolmap.Reconstruction(str(args.model))
    ims = sorted(rec.images.values(), key=lambda i: i.name)
    C = np.array([i.projection_center() for i in ims])
    D = np.array([i.viewing_direction() for i in ims])

    pts = np.array([p.xyz for p in rec.points3D.values()])
    # drop cameras that drifted far outside the reconstructed structure
    plo, phi = np.percentile(pts[:, [0, 2]], 3, axis=0), np.percentile(pts[:, [0, 2]], 97, axis=0)
    margin = 0.25 * (phi - plo)
    ok = np.all((C[:, [0, 2]] > plo - margin) & (C[:, [0, 2]] < phi + margin), axis=1)
    print(f"cameras kept {int(ok.sum())} of {len(C)} (outliers dropped)")
    C, D = C[ok], D[ok]
    lo, hi = C[:, [0, 2]].min(0) - 1.5, C[:, [0, 2]].max(0) + 1.5
    near = pts[(pts[:, 0] > lo[0]) & (pts[:, 0] < hi[0]) & (pts[:, 2] > lo[1]) & (pts[:, 2] < hi[1])]
    floor_y = float(np.percentile(near[:, 1], 95))          # y is down, floor is the largest y
    h_units = floor_y - float(np.median(C[:, 1]))
    if h_units <= 0:
        raise SystemExit("floor estimate is above the cameras; calibrate by hand with the C panel")
    s = args.phone_height / h_units                        # model units -> metres

    c0, d0 = C[0], D[0]
    off = np.array([-s * c0[0], s * floor_y, s * c0[2]])
    f = np.array([d0[0], -d0[1], -d0[2]])
    yaw = float(np.degrees(np.arctan2(-f[0], -f[2])))
    cam_v = np.stack([s * C[:, 0] + off[0], s * -C[:, 2] + off[2]], 1)   # viewer x, z of every camera
    bounds = [float(cam_v[:, 0].min() - args.margin), float(cam_v[:, 0].max() + args.margin),
              float(cam_v[:, 1].min() - args.margin), float(cam_v[:, 1].max() + args.margin)]

    cfg = {
        "rotation": [180, 0, 0],
        "scale": float(s),
        "offset": [float(v) for v in off],
        "eyeY": args.phone_height,
        "start": [0.0, 0.0],
        "startYaw": yaw,
        "speed": args.speed,
        "bounds": bounds,
        "cameras": int(len(C)),
        "assumedPhoneHeightM": args.phone_height,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(cfg, indent=2))
    print(json.dumps({k: (v if not isinstance(v, float) else round(v, 3)) for k, v in cfg.items()}))
    print(f"floor y={floor_y:.2f}, camera height={h_units:.2f} units -> scale {s:.3f} m/unit; path "
          f"{bounds[1]-bounds[0]-2*args.margin:.1f} x {bounds[3]-bounds[2]-2*args.margin:.1f} m")


if __name__ == "__main__":
    main()
