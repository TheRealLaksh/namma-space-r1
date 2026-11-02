# Namma Space: phone video to a walkable 3D web twin

Round 1 entry for Namma Space (Techfest IIT Bombay 2026, Juspay), Team Claudus. A smartphone walkthrough video of an indoor space becomes a photorealistic 3D Gaussian-splat model that anyone can walk through in a browser with WASD and the mouse. No manual 3D modelling at any step.

**Live viewer:** https://namma-space-viewer-eosin.vercel.app

## Pipeline

| Step | Script / tool | What it does |
|---|---|---|
| 1 | `pipeline/extract_frames.py` | Oversamples the video with ffmpeg, tone-maps HDR (HLG/PQ) phone video to SDR, keeps the sharpest frame per time window (variance of the Laplacian). |
| 2 | `pipeline/run_colmap_gpu.ps1` (GPU) or `pipeline/run_colmap.py` (CPU, pycolmap) | SIFT features, sequential matching, incremental mapping, undistortion into a dataset Brush reads. Warns if fewer than 60% of frames register. |
| 3 | [Brush](https://github.com/ArthurBrussee/brush) | Trains the 3D Gaussian splat on the GPU through Vulkan (no CUDA toolkit needed) and exports a `.ply`. |
| 4 | `pipeline/clean_splat.py` | Drops translucent, oversized and out-of-box splats (floaters) and the higher-order colour bands, so the web file is small. |
| 5 | `pipeline/make_config.py` | Places the model from the real camera path: floor at y = 0, scale from an assumed 1.4 m phone height, start pose = first camera, walking bounds = filmed path plus a margin. |
| 5b | `pipeline/ply_to_spz.mjs` | Packs the `.ply` into Spark's compact `.spz` with Spark's own encoder (50 MB to 15 MB, no visible change). |
| 6 | `viewer/` | Static web page using [Spark](https://sparkjs.dev) on [three.js](https://threejs.org): first-person roaming, calibration panel, touch controls. Dependencies are bundled, no CDN. |

If COLMAP splits the video into disconnected pieces (low overlap between frames), run an exhaustive matcher on the same database and map again; this merged our capture from 196 to 306 registered frames.

## Setup (Windows, Python 3.11, ffmpeg on PATH)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pycolmap numpy opencv-python-headless plyfile
# Brush v0.3.0 Windows build:  https://github.com/ArthurBrussee/brush/releases  -> tools\brush\app\brush_app.exe
# optional, GPU poses: COLMAP 4.2.1 CUDA build https://github.com/colmap/colmap/releases -> tools\colmap\app\bin\colmap.exe
```

## Reconstruct a space

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py pipeline\extract_frames.py data\room.mov data\work\images --target 480 --width 1600
& $py pipeline\run_colmap.py data\work                       # or: .\pipeline\run_colmap_gpu.ps1 data\work
tools\brush\app\brush_app.exe data\work\brush_dataset --total-steps 30000 --max-splats 3000000 --max-resolution 1600 --export-path data\work\out --export-name scene.ply
& $py pipeline\clean_splat.py data\work\out\scene.ply viewer\assets\scene.ply
& $py pipeline\make_config.py data\work\brush_dataset\sparse\0 viewer\assets\scene.ply viewer\assets\config.json
node pipeline\ply_to_spz.mjs viewer\assets\scene.ply viewer\assets\scene.spz   # 3x smaller; needs: npm i playwright && npx playwright install chromium
python -m http.server 8088 --directory viewer                # open http://localhost:8088
```

`viewer/assets/` already contains the model (`scene.spz`, 15 MB) and config produced from our capture, so `python -m http.server 8088 --directory viewer` shows the result without running anything else. The viewer loads `assets/scene.spz`; use `?splat=assets/scene.ply` for a raw `.ply`. If your copy of this code came without `viewer/assets/scene.spz` (for example the Drive zip, which leaves it out because of the upload limit), download it from https://namma-space-viewer-eosin.vercel.app/assets/scene.spz into `viewer/assets/`, together with https://namma-space-viewer-eosin.vercel.app/assets/config.json.

## Test

```powershell
python test/run_test.py
```

Registers the 36 sample frames in `test/sample_frames/` with COLMAP and passes when at least 80% register with a reprojection error under 1 px (about 4 minutes on a laptop CPU; we measured 35 of 36 frames, 0.55 px). The full-model result for these frames is the model in `viewer/assets/`.

## Viewer controls

W A S D or arrow keys walk, the mouse looks (click to capture it), Shift sprints, `C` opens a calibration panel (rotation, scale, eye height, speed) and copies a `config.json` for `viewer/assets/`. On a phone: drag the left half to walk, the right half to look. Add `?splat=assets/other.ply` to load a different model.

## Capture SOP (summary)

Slow continuous walk, phone at chest height, landscape, exposure and focus locked, all lights on, two laps (along the walls, then a metre inside, lens tilted slightly down and up), pause at doorways, no spinning in place, finish at the start point, nobody moving through the scene. The full procedure and a description of how well our footage followed it are in the technical abstract.

## Licences and credits

Our code is MIT-licensed (see `LICENSE`). Third-party: COLMAP / pycolmap (BSD-style licence), Brush (Apache-2.0), Spark (MIT), three.js (MIT), OpenCV (Apache-2.0), NumPy (BSD), plyfile (GPL-3.0), FFmpeg (LGPL/GPL build).
