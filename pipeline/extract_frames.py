"""Step 1: pick sharp, evenly spaced frames from a phone video.

Usage: python pipeline/extract_frames.py data/room.mp4 data/work/images [--target 220] [--width 1600]
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np


def probe(video: Path) -> tuple[float, float]:
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return fps, n / fps


TONEMAP = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
           "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def is_hdr(video: Path) -> bool:
    """iPhone video is often HLG HDR; frames must be tone-mapped to SDR or colours wash out."""
    ffprobe = Path(shutil.which("ffprobe") or "ffprobe")
    out = subprocess.run(
        [str(ffprobe), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=color_transfer", "-of", "default=nw=1:nk=1", str(video)],
        capture_output=True, text=True,
    ).stdout.strip()
    return out in ("arib-std-b67", "smpte2084")


def sharpness(img: np.ndarray) -> float:
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(grey, cv2.CV_64F).var())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--target", type=int, default=220, help="frames to keep")
    ap.add_argument("--width", type=int, default=1600, help="output width in px")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    fps, duration = probe(args.video)
    # Oversample 3x, then keep the sharpest frame in each window.
    sample_fps = min(fps, max(1.0, 3.0 * args.target / duration))
    tmp = args.out.parent / "_candidates"
    tmp.mkdir(exist_ok=True)
    hdr = is_hdr(args.video)
    vf = f"fps={sample_fps:.4f}" + ("," + TONEMAP if hdr else "") + f",scale={args.width}:-2"
    print(f"hdr={hdr}, sampling {sample_fps:.2f} fps")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(args.video),
         "-vf", vf,
         "-qmin", "1", "-q:v", "2", str(tmp / "c_%05d.jpg")],
        check=True,
    )
    cands = sorted(tmp.glob("c_*.jpg"))
    if not cands:
        sys.exit("ffmpeg produced no frames")
    group = max(1, round(len(cands) / args.target))
    kept = 0
    for i in range(0, len(cands), group):
        window = cands[i:i + group]
        best = max(window, key=lambda p: sharpness(cv2.imread(str(p))))
        best.replace(args.out / f"frame_{kept:05d}.jpg")
        kept += 1
    for p in tmp.glob("c_*.jpg"):
        p.unlink()
    tmp.rmdir()
    print(f"video {duration:.1f}s @ {fps:.1f} fps -> {kept} frames in {args.out}")


if __name__ == "__main__":
    main()
