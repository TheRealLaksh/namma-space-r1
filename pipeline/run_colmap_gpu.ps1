# Step 2 (GPU): COLMAP 4.2.1 CUDA build. Same output as run_colmap.py, much faster feature extraction and matching.
# Usage: .\pipeline\run_colmap_gpu.ps1 data\work [-Matcher sequential|exhaustive] [-Overlap 40] [-Mapper mapper|global_mapper]
param(
  [Parameter(Mandatory=$true)][string]$Work,
  [ValidateSet('sequential','exhaustive')][string]$Matcher = 'sequential',
  [int]$Overlap = 40,
  [ValidateSet('mapper','global_mapper')][string]$Mapper = 'mapper'
)
$ErrorActionPreference = 'Stop'
$colmap = Join-Path $PSScriptRoot '..\tools\colmap\app\bin\colmap.exe'
$images = Join-Path $Work 'images'
$dir    = Join-Path $Work 'colmap'
$sparse = Join-Path $dir 'sparse'
$db     = Join-Path $dir 'database.db'
$ds     = Join-Path $Work 'brush_dataset'
if (-not (Test-Path "$images\*.jpg")) { throw "no .jpg frames in $images; run extract_frames.py first" }
if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
New-Item -ItemType Directory -Force $sparse | Out-Null
function Step($name, [scriptblock]$b) { $t = Get-Date; & $b; if ($LASTEXITCODE -ne 0) { throw "$name failed ($LASTEXITCODE)" }; "{0}: {1:n0}s" -f $name, ((Get-Date) - $t).TotalSeconds }

Step 'features' { & $colmap feature_extractor --database_path $db --image_path $images `
  --ImageReader.single_camera 1 --ImageReader.camera_model SIMPLE_RADIAL --SiftExtraction.max_num_features 12000 | Out-Null }
if ($Matcher -eq 'sequential') {
  Step 'matching' { & $colmap sequential_matcher --database_path $db `
    --SequentialMatching.overlap $Overlap --SequentialMatching.loop_detection 0 | Out-Null }
} else {
  Step 'matching' { & $colmap exhaustive_matcher --database_path $db | Out-Null }
}
Step 'mapping' { & $colmap $Mapper --database_path $db --image_path $images --output_path $sparse | Out-Null }

# pick the model with most registered images
$best = Get-ChildItem $sparse -Directory | Sort-Object { (Get-Item "$($_.FullName)\images.bin").Length } -Descending | Select-Object -First 1
if (-not $best) { throw "COLMAP produced no model; recapture with more overlap" }
$ErrorActionPreference = 'Continue'  # COLMAP logs to stderr; that is not a failure
$stats = & $colmap model_analyzer --path $best.FullName 2>&1 | ForEach-Object { "$_" } | Select-String 'Registered images|Points|Mean reprojection|Mean track' | ForEach-Object { $_.Line -replace '^.*?\] ','' }
$stats
$ErrorActionPreference = 'Stop'
$nImg = (Get-ChildItem "$images\*.jpg").Count
if (($stats -join ' ') -match 'Registered images:\s*(\d+)') {
  $reg = [int]$Matches[1]
  if ($reg -lt 0.6 * $nImg) { "WARNING: only {0:n0}% of frames registered. Recapture the weak section: slower, more overlap, fewer plain-wall views." -f (100 * $reg / $nImg) }
}

if (Test-Path $ds) { Remove-Item $ds -Recurse -Force }
Step 'undistort' { & $colmap image_undistorter --image_path $images --input_path $best.FullName --output_path $ds --output_type COLMAP | Out-Null }
$s0 = Join-Path $ds 'sparse\0'
if (-not (Test-Path $s0) -and (Test-Path "$ds\sparse\cameras.bin")) { New-Item -ItemType Directory $s0 | Out-Null; Copy-Item "$ds\sparse\*.bin" $s0 }
"dataset ready: $ds"
