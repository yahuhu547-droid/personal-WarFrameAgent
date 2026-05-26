$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$CacheRoot = Join-Path $Root "local-cache"
$TempRoot = Join-Path $CacheRoot "tmp"

New-Item -ItemType Directory -Force -Path $CacheRoot | Out-Null
New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null

$env:PIP_CACHE_DIR = Join-Path $CacheRoot "pip"
$env:UV_CACHE_DIR = Join-Path $CacheRoot "uv"
$env:NPM_CONFIG_CACHE = Join-Path $CacheRoot "npm"
$env:PNPM_HOME = Join-Path $CacheRoot "pnpm-home"
$env:PNPM_STORE_DIR = Join-Path $CacheRoot "pnpm-store"
$env:YARN_CACHE_FOLDER = Join-Path $CacheRoot "yarn"
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $CacheRoot "ms-playwright"
$env:CARGO_HOME = Join-Path $CacheRoot "cargo-home"
$env:RUSTUP_HOME = Join-Path $CacheRoot "rustup-home"
$env:HF_HOME = Join-Path $CacheRoot "huggingface"
$env:TRANSFORMERS_CACHE = Join-Path $CacheRoot "huggingface\transformers"
$env:TORCH_HOME = Join-Path $CacheRoot "torch"
$env:PYTHONUSERBASE = Join-Path $CacheRoot "python-userbase"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:TEMP = $TempRoot
$env:TMP = $TempRoot
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"

$paths = @(
  $env:PIP_CACHE_DIR,
  $env:UV_CACHE_DIR,
  $env:NPM_CONFIG_CACHE,
  $env:PNPM_HOME,
  $env:PNPM_STORE_DIR,
  $env:YARN_CACHE_FOLDER,
  $env:PLAYWRIGHT_BROWSERS_PATH,
  $env:CARGO_HOME,
  $env:RUSTUP_HOME,
  $env:HF_HOME,
  $env:TRANSFORMERS_CACHE,
  $env:TORCH_HOME,
  $env:PYTHONUSERBASE,
  $env:TEMP
)

foreach ($path in $paths) {
  New-Item -ItemType Directory -Force -Path $path | Out-Null
}

Write-Host "Local package/cache root: $CacheRoot"
Write-Host "PIP_CACHE_DIR=$env:PIP_CACHE_DIR"
Write-Host "UV_CACHE_DIR=$env:UV_CACHE_DIR"
Write-Host "NPM_CONFIG_CACHE=$env:NPM_CONFIG_CACHE"
Write-Host "PNPM_STORE_DIR=$env:PNPM_STORE_DIR"
Write-Host "PLAYWRIGHT_BROWSERS_PATH=$env:PLAYWRIGHT_BROWSERS_PATH"
Write-Host "PYTHONUSERBASE=$env:PYTHONUSERBASE"
Write-Host "TMP=$env:TMP"
