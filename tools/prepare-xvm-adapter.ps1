param(
    [Parameter(Mandatory = $true)]
    [string]$PlayersPanel,

    [string]$Output,

    [string]$Python = 'py',

    [string[]]$PythonArguments = @('-3'),

    [switch]$IncludeNames
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
if (-not $Output) {
    $Output = Join-Path $ProjectRoot 'build\xvm-adapter-preview'
}

$Arguments = @(
    '-m', 'colored_contour_icons.xvm_adapter',
    '--players-panel', $PlayersPanel,
    '--output', $Output
)
if ($IncludeNames) {
    $Arguments += '--include-names'
}
& $Python @PythonArguments @Arguments
