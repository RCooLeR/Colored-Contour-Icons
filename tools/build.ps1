param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,
    [string]$Python = 'python',
    [string]$Python2 = '',
    [switch]$IncludeAtlases
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
$Arguments = @(
    '-m', 'colored_contour_icons.build',
    '--game-root', $GameRoot,
    '--output', (Join-Path $ProjectRoot 'build')
)
if ($IncludeAtlases) {
    $Arguments += '--include-atlases'
}
if ($Python2) {
    $Arguments += @('--python2', $Python2)
}
& $Python @Arguments
