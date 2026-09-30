param(
    [Parameter(Mandatory=$true)][string]$ContextPath,
    [Parameter(Mandatory=$true)][string]$InstallerHash
)
$ErrorActionPreference = 'Stop'
$context = Get-Content -LiteralPath $ContextPath -Raw | ConvertFrom-Json
$manifestRoot = 'manifests/d/DotSam/WhisperDesk'
$listing = & gh api "repos/microsoft/winget-pkgs/contents/$manifestRoot?ref=master" --jq '.[].name' 2>&1
if ($LASTEXITCODE -ne 0) {
    if (($listing -join "`n") -notmatch 'Not Found|HTTP 404') { throw "Could not confirm WinGet package identity status: $($listing -join ' ')" }
    Write-Warning 'DotSam.WhisperDesk is not yet registered in microsoft/winget-pkgs. Generate and submit the initial reviewed manifests using packaging/winget/bootstrap/README.md; subsequent tag releases will update it automatically.'
    exit 0
}
$versionPath = "$manifestRoot/$($context.version)/DotSam.WhisperDesk.installer.yaml"
$existing = & gh api "repos/microsoft/winget-pkgs/contents/$versionPath?ref=master" --jq '.content' 2>&1
if ($LASTEXITCODE -eq 0 -and $existing) {
    $yaml = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(($existing -join '').Trim()))
    if (!$yaml.Contains($context.installer_url) -or !$yaml.Contains($InstallerHash)) {
        throw "WinGet version $($context.version) already exists with different installer metadata."
    }
    Write-Output "WinGet $($context.version) already references the expected immutable installer; skipping duplicate submission."
    exit 0
}
if ($LASTEXITCODE -ne 0 -and ($existing -join "`n") -notmatch 'Not Found|HTTP 404') { throw "Could not check whether WinGet version $($context.version) already exists." }
if (!$env:WINGET_CREATE_GITHUB_TOKEN) { throw 'WINGET_CREATE_GITHUB_TOKEN is required to submit WinGet updates.' }
$tool = Join-Path $env:RUNNER_TEMP 'wingetcreate.exe'
Invoke-WebRequest 'https://aka.ms/wingetcreate/latest' -OutFile $tool -MaximumRedirection 10
$signature = Get-AuthenticodeSignature -FilePath $tool
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') {
    throw 'Downloaded WinGetCreate CLI does not have a valid Microsoft signature.'
}
& $tool update $context.winget_id --urls "$($context.installer_url)|x64|user" --version $context.version --display-version $context.version --submit --no-open
if ($LASTEXITCODE -ne 0) { throw 'Microsoft WinGetCreate failed to submit the package update.' }
Write-Output "Submitted $($context.winget_id) $($context.version) update pull request to microsoft/winget-pkgs."
