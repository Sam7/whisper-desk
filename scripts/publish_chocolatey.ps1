param(
    [Parameter(Mandatory=$true)][string]$ContextPath,
    [Parameter(Mandatory=$true)][string]$Package,
    [Parameter(Mandatory=$true)][string]$InstallerHash
)
$ErrorActionPreference = 'Stop'
$context = Get-Content -LiteralPath $ContextPath -Raw | ConvertFrom-Json
$base = 'https://community.chocolatey.org/api/v2'
$metadataUrl = "$base/Packages(Id='$($context.chocolatey_id)',Version='$($context.version)')"
$alreadyPublished = $false
try {
    $response = Invoke-WebRequest -Uri $metadataUrl -MaximumRedirection 5
    $alreadyPublished = $response.StatusCode -eq 200
} catch {
    $status = [int]$_.Exception.Response.StatusCode
    if ($status -ne 404) { throw "Could not check Chocolatey version status (HTTP $status)." }
}
if ($alreadyPublished) {
    $publishedPackage = Join-Path $env:TEMP "$($context.chocolatey_id)-$($context.version)-published.nupkg"
    Invoke-WebRequest -Uri "$base/package/$($context.chocolatey_id)/$($context.version)" -OutFile $publishedPackage -MaximumRedirection 5
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($publishedPackage)
    try {
        $nuspecEntry = $zip.Entries | Where-Object { $_.FullName -match '\.nuspec$' } | Select-Object -First 1
        $scriptEntry = $zip.GetEntry('tools/chocolateyinstall.ps1')
        if (!$nuspecEntry -or !$scriptEntry) { throw 'Existing Chocolatey version is missing package metadata.' }
        $reader = [IO.StreamReader]::new($nuspecEntry.Open())
        try { [xml]$nuspec = $reader.ReadToEnd() } finally { $reader.Dispose() }
        $reader = [IO.StreamReader]::new($scriptEntry.Open())
        try { $installScript = $reader.ReadToEnd() } finally { $reader.Dispose() }
        $metadata = $nuspec.package.metadata
        if ($metadata.id -ne $context.chocolatey_id -or $metadata.version -ne $context.version -or $metadata.title -ne 'WhisperDesk' -or $metadata.authors -ne 'DotSam' -or
            !$installScript.Contains($context.installer_url) -or !$installScript.Contains($InstallerHash)) {
            throw 'That Chocolatey ID/version already exists with different installer metadata. Refusing to publish or overwrite it.'
        }
    } finally {
        $zip.Dispose()
        Remove-Item -LiteralPath $publishedPackage -Force -ErrorAction SilentlyContinue
    }
    Write-Output "Chocolatey $($context.chocolatey_id) $($context.version) already contains the expected immutable installer; skipping duplicate publication."
    exit 0
}
if (!(Test-Path -LiteralPath $Package)) { throw "Chocolatey package is missing: $Package" }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\smoke_chocolatey.ps1" -Package $Package -Version $context.version
if ($LASTEXITCODE -ne 0) { throw 'Local Chocolatey install/uninstall verification failed.' }
if (!$env:CHOCOLATEY_API_KEY) { throw 'CHOCOLATEY_API_KEY is required to publish the Chocolatey package.' }
& choco.exe push $Package --source 'https://push.chocolatey.org/' "--api-key=$env:CHOCOLATEY_API_KEY" --no-progress
if ($LASTEXITCODE -ne 0) { throw 'Chocolatey Community Repository rejected the package upload.' }
Write-Output "Submitted $($context.chocolatey_id) $($context.version) to the Chocolatey Community Repository."
