param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,

    [string]$Package,

    [string]$BattleAtlasPackage,

    [switch]$SkipBattleAtlasAddon,

    [switch]$InstallXvmDirectAdapter,

    [switch]$IncludeXvmNames,

    [string]$Python = 'py',

    [string[]]$PythonArguments = @('-3')
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ResolvedGameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$ModsRoot = Join-Path $ResolvedGameRoot 'mods'
if (-not (Test-Path -LiteralPath $ModsRoot -PathType Container)) {
    throw "World of Tanks mods directory not found: $ModsRoot"
}

$VersionDirectories = Get-ChildItem -LiteralPath $ModsRoot -Directory | Where-Object {
    $_.Name -match '^2(?:\.\d+){3}$'
}
if (-not $VersionDirectories) {
    throw 'No World of Tanks 2.x mod directory was found.'
}

$ActiveVersion = $VersionDirectories | Sort-Object {
    [version]$_.Name
} -Descending | Select-Object -First 1

if (-not $Package) {
    $Package = Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'build') `
        -Filter 'com.rcooler.colored_contour_icons_*.wotmod' | Where-Object {
            $_.Name -match '^com\.rcooler\.colored_contour_icons_\d+\.\d+\.\d+\.wotmod$'
        } | Sort-Object LastWriteTime -Descending | Select-Object -First 1 `
        -ExpandProperty FullName
}
if (-not $Package) {
    throw 'No version-independent coloured icon package was found.'
}

$ResolvedPackage = (Resolve-Path -LiteralPath $Package).Path
$Target = Join-Path $ActiveVersion.FullName (Split-Path $ResolvedPackage -Leaf)
Get-ChildItem -LiteralPath $ActiveVersion.FullName `
    -Filter 'com.rcooler.colored_contour_icons_*.wotmod' | Where-Object {
        $_.Name -notmatch '_battle_atlas_' -and
        $_.FullName -ne $Target
    } | Remove-Item -Force
Copy-Item -LiteralPath $ResolvedPackage -Destination $Target -Force
Write-Output "Installed to World of Tanks $($ActiveVersion.Name): $Target"

if (-not $SkipBattleAtlasAddon) {
    if (-not $BattleAtlasPackage) {
        $AtlasPattern = "com.rcooler.colored_contour_icons_battle_atlas_*_wg$($ActiveVersion.Name).wotmod"
        $BattleAtlasPackage = Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'build') `
            -Filter $AtlasPattern | Sort-Object LastWriteTime -Descending | Select-Object -First 1 `
            -ExpandProperty FullName
    }
    if (-not $BattleAtlasPackage) {
        throw "No battleAtlas add-on built for World of Tanks $($ActiveVersion.Name) was found."
    }
    $ResolvedAtlasPackage = (Resolve-Path -LiteralPath $BattleAtlasPackage).Path
    $env:PYTHONPATH = Join-Path $ProjectRoot 'src'
    & $Python @PythonArguments -m colored_contour_icons.verify_atlas `
        --game-root $ResolvedGameRoot --package $ResolvedAtlasPackage
    if ($LASTEXITCODE -ne 0) {
        throw 'The battleAtlas add-on does not match this client installation.'
    }
    $AtlasTarget = Join-Path $ActiveVersion.FullName (Split-Path $ResolvedAtlasPackage -Leaf)
    $ConflictJson = & $Python @PythonArguments -m colored_contour_icons.find_conflicts `
        --mods-directory $ActiveVersion.FullName --target $AtlasTarget
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not scan installed mods for battleAtlas conflicts.'
    }
    $AtlasConflicts = $ConflictJson | ConvertFrom-Json
    if ($AtlasConflicts) {
        Write-Warning ("Other packages also provide battleAtlas; only one can win: " +
            ($AtlasConflicts -join ', '))
    }
    Get-ChildItem -LiteralPath $ActiveVersion.FullName `
        -Filter 'com.rcooler.colored_contour_icons_battle_atlas_*.wotmod' | Where-Object {
            $_.FullName -ne $AtlasTarget
        } | Remove-Item -Force
    Copy-Item -LiteralPath $ResolvedAtlasPackage -Destination $AtlasTarget -Force
    Write-Output "Installed classic ears battleAtlas: $AtlasTarget"
}

# Older test builds patched the default XVM profile directly.  The atlas add-on
# makes those duplicate fields unnecessary, so remove only our exact references
# and preserve every unrelated byte of the user's profile.
if (-not $InstallXvmDirectAdapter) {
    $DefaultPlayersPanel = Join-Path $ResolvedGameRoot 'res_mods\configs\xvm\default\playersPanel.xc'
    if (Test-Path -LiteralPath $DefaultPlayersPanel -PathType Leaf) {
        $CleanupDirectory = Join-Path $ProjectRoot 'build\xvm-adapter-cleanup'
        $CleanPanelPath = Join-Path $CleanupDirectory 'playersPanel.xc'
        $env:PYTHONPATH = Join-Path $ProjectRoot 'src'
        & $Python @PythonArguments -m colored_contour_icons.xvm_uninstall `
            --source $DefaultPlayersPanel --output $CleanPanelPath
        if ($LASTEXITCODE -ne 0) {
            throw 'Could not remove the obsolete XVM direct adapter.'
        }
        $OriginalPanelHash = (Get-FileHash -LiteralPath $DefaultPlayersPanel -Algorithm SHA256).Hash
        $CleanPanelHash = (Get-FileHash -LiteralPath $CleanPanelPath -Algorithm SHA256).Hash
        if ($CleanPanelHash -ne $OriginalPanelHash) {
            $Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
            $Backup = "$DefaultPlayersPanel.rcooler-before-atlas-$Timestamp"
            Copy-Item -LiteralPath $DefaultPlayersPanel -Destination $Backup
            Copy-Item -LiteralPath $CleanPanelPath -Destination $DefaultPlayersPanel -Force
            Write-Output "Removed obsolete XVM overlay. Backup: $Backup"
        }
        $AdapterFragment = Join-Path (Split-Path $DefaultPlayersPanel -Parent) '_rcooler_colored_contour_icons.xc'
        if (Test-Path -LiteralPath $AdapterFragment -PathType Leaf) {
            Remove-Item -LiteralPath $AdapterFragment -Force
        }
    }
}

# The current-client battleAtlas already supplies coloured icons to stock panels
# and XVM's default iconset.  Direct XVM fields remain opt-in for custom iconsets.
if ($InstallXvmDirectAdapter) {
    $XvmBoot = Join-Path $ResolvedGameRoot 'res_mods\configs\xvm\xvm.xc'
    $DefaultPlayersPanel = Join-Path $ResolvedGameRoot 'res_mods\configs\xvm\default\playersPanel.xc'
    if ((Test-Path -LiteralPath $XvmBoot -PathType Leaf) -and
        (Test-Path -LiteralPath $DefaultPlayersPanel -PathType Leaf)) {
        $XvmBootText = Get-Content -LiteralPath $XvmBoot -Raw -Encoding UTF8
        if ($XvmBootText -match 'default[/\\]@xvm\.xc') {
            $Staging = Join-Path $ProjectRoot 'build\xvm-adapter-install'
            $env:PYTHONPATH = Join-Path $ProjectRoot 'src'
            $AdapterArguments = @(
                '-m', 'colored_contour_icons.xvm_adapter',
                '--players-panel', $DefaultPlayersPanel,
                '--output', $Staging
            )
            if ($IncludeXvmNames) {
                $AdapterArguments += '--include-names'
            }
            & $Python @PythonArguments @AdapterArguments
            if ($LASTEXITCODE -ne 0) {
                throw 'Could not prepare the XVM players-panel adapter.'
            }
            $PreparedPlayersPanel = Join-Path $Staging 'playersPanel.xc'
            $SourceHash = (Get-FileHash -LiteralPath $DefaultPlayersPanel -Algorithm SHA256).Hash
            $PreparedHash = (Get-FileHash -LiteralPath $PreparedPlayersPanel -Algorithm SHA256).Hash
            if ($SourceHash -ne $PreparedHash) {
                $Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
                $Backup = "$DefaultPlayersPanel.rcooler-backup-$Timestamp"
                Copy-Item -LiteralPath $DefaultPlayersPanel -Destination $Backup
                Copy-Item -LiteralPath $PreparedPlayersPanel -Destination $DefaultPlayersPanel -Force
                Write-Output "Installed XVM ears adapter. Backup: $Backup"
            } else {
                Write-Output 'XVM ears adapter is already installed.'
            }
            Copy-Item -LiteralPath (Join-Path $Staging '_rcooler_colored_contour_icons.xc') `
                -Destination (Join-Path (Split-Path $DefaultPlayersPanel -Parent) '_rcooler_colored_contour_icons.xc') -Force
        } else {
            Write-Warning 'XVM uses a custom profile; the XVM ears adapter was not applied automatically.'
        }
    }
}
