# Tests for tools/windows/check-ready.ps1: the edition picked for graphics cards,
# and a full read-only run on this machine.
$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot '..\..\tools\windows\check-ready.ps1'

$expected = [ordered]@{
    'NVIDIA GeForce GTX 1650 Ti'         = 'nvidia'
    'NVIDIA GeForce RTX 4070 Laptop GPU' = 'nvidia'
    'NVIDIA GeForce MX450'               = 'nvidia'
    'NVIDIA T600 Laptop GPU'             = 'nvidia'
    'NVIDIA RTX A2000'                   = 'nvidia'
    'NVIDIA GeForce GTX 1060 6GB'        = 'nvidia-legacy'
    'NVIDIA GeForce GTX 750 Ti'          = 'nvidia-legacy'
    'NVIDIA GeForce GTX 980M'            = 'nvidia-legacy'
    'NVIDIA GeForce 940MX'               = 'nvidia-legacy'
    'NVIDIA GeForce MX250'               = 'nvidia-legacy'
    'NVIDIA GeForce GT 1030'             = 'nvidia-legacy'
    'NVIDIA Quadro P2000'                = 'nvidia-legacy'
    'NVIDIA Quadro K2200'                = 'nvidia-legacy'
    'NVIDIA GeForce GTX TITAN X'         = 'nvidia-legacy'
    'NVIDIA GeForce GTX 680'             = 'main'
    'NVIDIA GeForce GTX TITAN Black'     = 'main'
    'NVIDIA Quadro K4000'                = 'main'
    'AMD Radeon RX 6600'                 = 'main'
    'Intel(R) Arc(TM) A770 Graphics'     = 'main'
    'Intel(R) UHD Graphics'              = 'main'
}

$failures = 0
$output = & $script -GpuName ([string[]]$expected.Keys)
foreach ($line in $output) {
    $name, $edition = $line -split ' => '
    if ($expected[$name] -eq $edition) {
        Write-Host "PASS: $name => $edition"
    } else {
        Write-Host "FAIL: $name => $edition (expected $($expected[$name]))"
        $failures++
    }
}
if (@($output).Count -ne $expected.Count) {
    Write-Host "FAIL: $(@($output).Count) results for $($expected.Count) cards"
    $failures++
}

$run = & powershell -NoProfile -ExecutionPolicy Bypass -File $script 2>&1 | Out-String
Write-Host $run
foreach ($needle in 'Edition:', 'Memory:', 'processor') {
    if ($run -match [regex]::Escape($needle)) { Write-Host "PASS: full run shows '$needle'" }
    else { Write-Host "FAIL: full run does not show '$needle'"; $failures++ }
}
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: full run exited with $LASTEXITCODE"; $failures++ }

Write-Host "$failures failure(s)"
exit [int]($failures -gt 0)
