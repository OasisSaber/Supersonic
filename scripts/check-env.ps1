$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$tools = @("node", "pnpm", "uv", "git", "ffmpeg", "nvidia-smi")
foreach ($tool in $tools) {
  $command = Get-Command $tool -ErrorAction SilentlyContinue
  if ($command) { Write-Host "[OK] $tool -> $($command.Source)" }
  else { Write-Host "[--] $tool is not installed or is not on PATH" }
}

Write-Host "OS: $([System.Environment]::OSVersion.VersionString)"
Write-Host "Arch: $([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture)"
Write-Host "Logical processors: $([System.Environment]::ProcessorCount)"
