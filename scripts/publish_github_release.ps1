param(
    [Parameter(Mandatory=$true)][string]$ContextPath,
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$ChecksumFile,
    [string]$Directory = "$PWD\artifacts\release"
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$context = Get-Content -LiteralPath $ContextPath -Raw | ConvertFrom-Json
$installer = (Resolve-Path -LiteralPath $Installer).Path
$checksumFile = (Resolve-Path -LiteralPath $ChecksumFile).Path
if ((Split-Path -Leaf $installer) -ne $context.installer_name) { throw 'Installer filename differs from the validated release tag.' }
$expectedHash = (Get-Content -LiteralPath $checksumFile -Raw).Trim().Split()[0].ToLowerInvariant()
$localHash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
if ($localHash -ne $expectedHash) { throw 'Installer SHA-256 sidecar does not match the built file.' }
if ($env:GITHUB_SHA -and $env:GITHUB_SHA -ne (git rev-parse "$($context.tag)^{commit}")) { throw 'Tag commit differs from the workflow source commit.' }
$repo = $context.repository
$tag = $context.tag
$existingText = & gh release view $tag --repo $repo --json tagName,targetCommitish,isDraft,assets 2>$null
$exists = $LASTEXITCODE -eq 0
$release = $null
if ($exists) {
    $release = ($existingText -join "`n") | ConvertFrom-Json
    if ($release.targetCommitish -ne $env:GITHUB_SHA) { throw 'This tag already has a release built from a different commit.' }
    if (!$release.isDraft -and !$release.assets) { throw 'Published release has no assets; refusing to mutate it.' }
} else {
    & gh release create $tag --repo $repo --verify-tag --target $env:GITHUB_SHA --draft --title "$($context.product) $($context.version)" --notes "WhisperDesk $($context.version) for Windows 11 x64.`n`nLocal Whisper Turbo transcription with optional NVIDIA GPU acceleration. After the one-time dependency download, transcription runs offline.`n`nSee the repository README for installation and system requirements." | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the draft GitHub Release.' }
    $release = (& gh release view $tag --repo $repo --json tagName,targetCommitish,isDraft,assets | ConvertFrom-Json)
}
$expectedFiles = @($installer, $checksumFile)
New-Item -ItemType Directory -Path $Directory -Force | Out-Null
foreach ($file in $expectedFiles) {
    $name = Split-Path -Leaf $file
    $asset = @($release.assets | Where-Object { $_.name -eq $name }) | Select-Object -First 1
    if ($asset) {
        $downloadDirectory = Join-Path $Directory "existing-$name"
        New-Item -ItemType Directory -Path $downloadDirectory -Force | Out-Null
        & gh release download $tag --repo $repo --pattern $name --dir $downloadDirectory
        if ($LASTEXITCODE -ne 0) { throw "Could not verify existing release asset $name." }
        $existingFile = Join-Path $downloadDirectory $name
        $actual = (Get-FileHash -LiteralPath $existingFile -Algorithm SHA256).Hash.ToLowerInvariant()
        $expected = if ($name -eq (Split-Path -Leaf $installer)) { $expectedHash } else { (Get-FileHash -LiteralPath $checksumFile -Algorithm SHA256).Hash.ToLowerInvariant() }
        if ($actual -ne $expected) { throw "Existing release asset $name differs from this build; refusing to replace a versioned asset." }
    } elseif ($release.isDraft) {
        & gh release upload $tag $file --repo $repo
        if ($LASTEXITCODE -ne 0) { throw "Could not upload release asset $name." }
    } else {
        throw "Published release is missing $name; refusing to modify an existing release."
    }
}
if ($release.isDraft) {
    & gh release edit $tag --repo $repo --draft=false
    if ($LASTEXITCODE -ne 0) { throw 'Could not publish the GitHub Release.' }
}
$temporary = Join-Path $Directory $context.installer_name
try {
    Invoke-WebRequest -Uri $context.installer_url -OutFile $temporary -MaximumRedirection 10
    $remoteHash = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($remoteHash -ne $expectedHash) { throw 'Published GitHub Release download SHA-256 does not match the built installer.' }
    $remoteChecksum = (Invoke-WebRequest -Uri ($context.installer_url + '.sha256') -MaximumRedirection 10).Content.Trim().Split()[0].ToLowerInvariant()
    if ($remoteChecksum -ne $expectedHash) { throw 'Published SHA-256 sidecar does not match the installer.' }
} finally {
    Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
}
Write-Output "Published and remotely verified $($context.installer_url) ($expectedHash)."
