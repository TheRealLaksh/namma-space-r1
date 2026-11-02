"""Step 2: camera poses with pycolmap (CPU), then undistort for Brush.

Usage: python pipeline/run_colmap.py data/work [--matcher sequential|exhaustive]
Expects data/work/images/*.jpg. Writes data/work/colmap/{database.db,sparse/}
and data/work/brush_dataset/{images,sparse}.
"""
import argparse
import shutil
from pathlib import Path

import pycolmap


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("work", type=Path)
    ap.add_argument("--matcher", choices=["sequential", "exhaustive"], default="sequential")
    ap.add_argument("--overlap", type=int, default=20, help="sequential neighbours matched")
    args = ap.parse_args()

    images = args.work / "images"
    if not list(images.glob("*.jpg")):
        raise SystemExit(f"no .jpg frames in {images}; run extract_frames.py first")
    colmap = args.work / "colmap"
    sparse = colmap / "sparse"
    dataset = args.work / "brush_dataset"
    if colmap.exists():
        shutil.rmtree(colmap)
    sparse.mkdir(parents=True)
    db = colmap / "database.db"

    n = len(list(images.glob("*.jpg")))
    print(f"{n} images, matcher={args.matcher}, cuda={pycolmap.has_cuda}")

    reader = pycolmap.ImageReaderOptions()
    reader.camera_model = "SIMPLE_RADIAL"
    pycolmap.extract_features(
        db, images, camera_mode=pycolmap.CameraMode.SINGLE, reader_options=reader
    )
    if args.matcher == "sequential":
        pairing = pycolmap.SequentialPairingOptions()
        pairing.overlap = args.overlap
        if hasattr(pairing, "loop_detection"):
            pairing.loop_detection = False  # needs a vocab tree download
        pycolmap.match_sequential(db, pairing_options=pairing)
    else:
        pycolmap.match_exhaustive(db)

    maps = pycolmap.incremental_mapping(db, images, sparse)
    if not maps:
        raise SystemExit("COLMAP produced no reconstruction; recapture with more overlap")
    best = max(maps, key=lambda k: maps[k].num_reg_images())
    rec = maps[best]
    print(f"model {best}: {rec.num_reg_images()}/{n} images registered, "
          f"{rec.num_points3D()} points, mean reproj error {rec.compute_mean_reprojection_error():.2f}px")

    if rec.num_reg_images() < 0.6 * n:
        print(f"WARNING: only {100 * rec.num_reg_images() / n:.0f}% of frames registered. "
              "Recapture the weak section: slower, more overlap, fewer plain-wall views.")

    if dataset.exists():
        shutil.rmtree(dataset)
    pycolmap.undistort_images(dataset, sparse / str(best), images)
    # Brush looks for sparse/0; undistort writes sparse/ directly in COLMAP output.
    d0 = dataset / "sparse" / "0"
    if not d0.exists() and (dataset / "sparse" / "cameras.bin").exists():
        d0.mkdir()
        for f in (dataset / "sparse").glob("*.bin"):
            shutil.copy2(f, d0 / f.name)
    print("dataset ready:", dataset)


if __name__ == "__main__":
    main()
