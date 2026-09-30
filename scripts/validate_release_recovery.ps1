param(
    [Parameter(Mandatory=$true)][string]$SourceRunId,
    [Parameter(Mandatory=$true)][string]$Tag,
    [Parameter(Mandatory=$true)][string]$Repository,
    [string]$ArtifactRoot = 'release-artifacts'
)
$ErrorActionPreference = 'Stop'

if ($SourceRunId -notmatch '^\d+$') { throw 'Recovery requires a numeric source Actions run ID.' }
if ($Tag -notmatch '^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$') {
    throw 'Recovery requires a release tag in vMAJOR.MINOR.PATCH format.'
}
if ($Repository -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') { throw 'Invalid repository identity.' }

$runText = & gh run view $SourceRunId --repo $Repository --json workflowName,event,headBranch,headSha,jobs 2>&1
if ($LASTEXITCODE -ne 0) { throw "Could not inspect source Actions run $SourceRunId." }
$run = ($runText -join "`n") | ConvertFrom-Json
if ($run.workflowName -ne 'Tagged Windows release' -or $run.event -ne 'push' -or $run.headBranch -ne $Tag) {
    throw 'Source run is not the tagged Windows release run for the requested tag.'
}
if ($run.headSha -notmatch '^[0-9a-f]{40}$') { throw 'Source run does not contain a valid commit SHA.' }
$build = @($run.jobs | Where-Object { $_.name -eq 'Test and build versioned Windows installer' }) | Select-Object -First 1
if (!$build -or $build.conclusion -ne 'success') { throw 'Source run did not pass its complete build and installer validation job.' }

$tagText = & gh api "repos/$Repository/git/ref/tags/$Tag" 2>&1
if ($LASTEXITCODE -ne 0) { throw "Could not verify the current $Tag Git reference." }
$tagObject = (($tagText -join "`n") | ConvertFrom-Json).object
for ($depth = 0; $tagObject.type -eq 'tag' -and $depth -lt 4; $depth++) {
    $annotatedText = & gh api "repos/$Repository/git/tags/$($tagObject.sha)" 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Could not resolve annotated tag $Tag." }
    $tagObject = (($annotatedText -join "`n") | ConvertFrom-Json).object
}
if ($tagObject.type -ne 'commit' -or $tagObject.sha -ne $run.headSha) {
    throw 'The current release tag no longer points to the validated source commit; recovery is refused.'
}

$root = [IO.Path]::GetFullPath($ArtifactRoot)
$contextPath = Join-Path $root 'build\release\release.json'
if (!(Test-Path -LiteralPath $contextPath)) { throw 'Validated release metadata is missing from the source artifact.' }
$context = Get-Content -LiteralPath $contextPath -Raw | ConvertFrom-Json
$version = ($Tag -split '^v')[1]
$installerName = "WhisperDesk-$version-Setup.exe"
$installerUrl = "https://github.com/$Repository/releases/download/$Tag/$installerName"
if ($context.tag -ne $Tag -or $context.version -ne $version -or $context.repository -ne $Repository -or
    $context.product -ne 'WhisperDesk' -or $context.publisher -ne 'DotSam' -or
    $context.winget_id -ne 'DotSam.WhisperDesk' -or $context.chocolatey_id -ne 'whisperdesk' -or
    $context.installer_name -ne $installerName -or $context.installer_url -ne $installerUrl) {
    throw 'Release artifact metadata does not match the requested tag, repository, and package identities.'
}

$installer = Join-Path $root "dist\installer\$installerName"
$checksumFile = "$installer.sha256"
if (!(Test-Path -LiteralPath $installer) -or !(Test-Path -LiteralPath $checksumFile)) {
    throw 'The versioned installer or checksum sidecar is missing from the validated artifact.'
}
$expectedHash = ([string]$context.sha256).ToLowerInvariant()
if ($expectedHash -notmatch '^[0-9a-f]{64}$') { throw 'Release metadata does not contain a valid SHA-256.' }
$actualHash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
$sidecar = [IO.File]::ReadAllText($checksumFile, [Text.Encoding]::ASCII)
if ($actualHash -ne $expectedHash -or $sidecar -notmatch "^$expectedHash\s+$([regex]::Escape($installerName))(\s|$)") {
    throw 'Installer bytes, metadata SHA-256, and checksum sidecar do not agree.'
}

$package = Join-Path $root "build\chocolatey\whisperdesk.$version.nupkg"
if (!(Test-Path -LiteralPath $package) -or (Get-Item -LiteralPath $package).Length -eq 0) {
    throw 'The validated Chocolatey package is missing or empty.'
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$packageArchive = [IO.Compression.ZipFile]::OpenRead($package)
try {
    $nuspecEntry = $packageArchive.Entries | Where-Object { $_.FullName -match '\.nuspec$' } | Select-Object -First 1
    $installEntry = $packageArchive.GetEntry('tools/chocolateyinstall.ps1')
    if (!$nuspecEntry -or !$installEntry) { throw 'Chocolatey package metadata or installer script is missing.' }
    $reader = [IO.StreamReader]::new($nuspecEntry.Open())
    try { [xml]$nuspec = $reader.ReadToEnd() } finally { $reader.Dispose() }
    $reader = [IO.StreamReader]::new($installEntry.Open())
    try { $installScript = $reader.ReadToEnd() } finally { $reader.Dispose() }
    $metadata = $nuspec.package.metadata
    if ($metadata.id -ne 'whisperdesk' -or $metadata.version -ne $version -or
        $metadata.title -ne 'WhisperDesk' -or $metadata.authors -ne 'DotSam' -or
        !$installScript.Contains($installerUrl) -or !$installScript.Contains($expectedHash) -or
        !$installScript.Contains('/VERYSILENT /SUPPRESSMSGBOXES /NORESTART')) {
        throw 'Chocolatey package metadata, immutable installer URL, hash, or silent arguments do not match the release.'
    }
} finally {
    $packageArchive.Dispose()
}
$manifestDirectory = Join-Path $root "build\winget-bootstrap\$version"
$manifests = @(Get-ChildItem -LiteralPath $manifestDirectory -Filter '*.yaml' -File)
if ($manifests.Count -ne 3) { throw 'The three validated initial WinGet manifests are missing.' }
$manifestText = ($manifests | ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw }) -join "`n"
foreach ($required in @('PackageIdentifier: DotSam.WhisperDesk', "PackageVersion: $version", $installerUrl,
        "InstallerSha256: $expectedHash", 'DisplayName: WhisperDesk', 'Publisher: DotSam')) {
    if (!$manifestText.Contains($required)) { throw "WinGet release metadata is missing: $required" }
}

if ($env:GITHUB_ENV) {
    [IO.File]::AppendAllText($env:GITHUB_ENV, "RELEASE_SOURCE_SHA=$($run.headSha)`n", [Text.UTF8Encoding]::new($false))
}
$global:LASTEXITCODE = 0
Write-Output "Validated recovery artifact for $Tag from successful run $SourceRunId at $($run.headSha)."
