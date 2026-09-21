param([string]$Python = "python", [string]$Git = "git")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$environmentPath = Join-Path $projectRoot ".venv"
$upstreamPath = Join-Path $projectRoot ".dependencies\serum-mcp"
$revision = "6c471bb8424f3f06f16f5b9fc5bfab244fd11384"
if (-not (Test-Path -LiteralPath $upstreamPath)) {
    & $Git clone https://github.com/Celian-mrc/serum-mcp.git $upstreamPath
    if ($LASTEXITCODE -ne 0) { throw "Upstream clone failed" }
    & $Git -C $upstreamPath checkout --detach $revision
    if ($LASTEXITCODE -ne 0) { throw "Upstream checkout failed" }
}
$actual = & $Git -C $upstreamPath rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $actual.Trim() -ne $revision) { throw "Upstream revision mismatch" }
$modified = & $Git -C $upstreamPath status --porcelain --untracked-files=no
if ($modified) { throw "Upstream tracked files were modified; use a clean pinned checkout" }
& $Python -m venv $environmentPath
if ($LASTEXITCODE -ne 0) { throw "Python 3.12+ is required" }
$venvPython = Join-Path $environmentPath "Scripts\python.exe"
& $venvPython -m pip install -e $upstreamPath -e "$projectRoot[test]"
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
$config = @{ mcpServers = @{ midimcp = @{
    command = $venvPython
    args = @("-m", "midimcp.server")
    env = @{ MIDIMCP_UPSTREAM_ROOT = $upstreamPath; MIDIMCP_OUTPUT_DIR = (Join-Path $projectRoot "local-output") }
}}}
$config | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $projectRoot "mcp.local.json") -Encoding UTF8
Write-Output "Setup complete. MCP client configuration: $projectRoot\mcp.local.json"
