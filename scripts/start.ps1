$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:MIDIMCP_UPSTREAM_ROOT = Join-Path $projectRoot ".dependencies\serum-mcp"
if (-not $env:MIDIMCP_OUTPUT_DIR) { $env:MIDIMCP_OUTPUT_DIR = Join-Path $projectRoot "local-output" }
& (Join-Path $projectRoot ".venv\Scripts\python.exe") -m midimcp.server
exit $LASTEXITCODE
