param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$Version,
    [string]$ReportDirectory = "$PWD\artifacts\installer-smoke"
)
$ErrorActionPreference = 'Stop'
$expected = [IO.Path]::GetFullPath($Installer)
if ((Split-Path -Leaf $expected) -ne "WhisperDesk-$Version-Setup.exe") { throw 'Installer filename does not match the tag version.' }
$report = [ordered]@{version=$Version; installer=$expected; steps=@()}
New-Item -ItemType Directory -Path $ReportDirectory -Force | Out-Null
$setupLog = Join-Path $ReportDirectory 'setup.log'
$args = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CPU=1',"/LOG=$setupLog")
$setup = Start-Process -FilePath $expected -ArgumentList $args -Wait -PassThru
if ($setup.ExitCode -ne 0) {
    $diagnostics = if (Test-Path -LiteralPath $setupLog) {
        (Get-Content -LiteralPath $setupLog -Tail 40) -join [Environment]::NewLine
    } else { 'No Inno Setup log was created.' }
    throw "Unattended installer exited with $($setup.ExitCode). Inno Setup log tail:`n$diagnostics"
}
$keyPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{EF14A980-E239-414E-A6F4-ABAB4AF008F2}_is1'
$entry = Get-ItemProperty -LiteralPath $keyPath
if ($entry.DisplayName -ne 'WhisperDesk' -or $entry.DisplayVersion -ne $Version -or $entry.Publisher -ne 'DotSam') {
    throw "Apps & Features metadata mismatch: $($entry.DisplayName) $($entry.DisplayVersion) $($entry.Publisher)"
}
$app = Join-Path $env:LOCALAPPDATA 'Programs\WhisperDesk\WhisperDesk.exe'
$versionOutput = Join-Path $ReportDirectory 'app-version.stdout.txt'
$versionError = Join-Path $ReportDirectory 'app-version.stderr.txt'
$versionProcess = Start-Process -FilePath $app -ArgumentList @('--version') -Wait -PassThru `
    -RedirectStandardOutput $versionOutput -RedirectStandardError $versionError
$actualVersion = if (Test-Path -LiteralPath $versionOutput) {
    (Get-Content -LiteralPath $versionOutput -Raw).Trim()
} else { '' }
if ($versionProcess.ExitCode -ne 0 -or $actualVersion -ne "WhisperDesk $Version") {
    $versionErrorText = if (Test-Path -LiteralPath $versionError) { Get-Content -LiteralPath $versionError -Raw } else { '' }
    throw "Executable version mismatch (exit $($versionProcess.ExitCode)): '$actualVersion'. $versionErrorText"
}
$data = Join-Path $env:LOCALAPPDATA 'WhisperDesk'
$verified = Get-Content (Join-Path $data 'setup-verification.json') -Raw | ConvertFrom-Json
if ($verified.exit_code -ne 0 -or $verified.device -ne 'cpu') { throw 'CPU setup did not complete actual local Whisper inference.' }
$report.steps += [ordered]@{stage='unattended install'; exit_code=$setup.ExitCode; display_name=$entry.DisplayName; display_version=$entry.DisplayVersion; publisher=$entry.Publisher; app_version=$actualVersion; backend=$verified.device; inference_ms=$verified.elapsed_ms}
$uninstallLog = Join-Path $ReportDirectory 'uninstall.log'
$uninstaller = Join-Path (Split-Path $app) 'unins000.exe'
$remove = Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/LOG=$uninstallLog") -Wait -PassThru
if ($remove.ExitCode -ne 0) { throw "Unattended uninstaller exited with $($remove.ExitCode). Inspect $uninstallLog" }
if ((Test-Path -LiteralPath $app) -or (Test-Path -LiteralPath $keyPath)) { throw 'Uninstall left application files or Apps & Features registration behind.' }
if (!(Test-Path (Join-Path $data 'models')) -or !(Test-Path (Join-Path $data 'setup-cache'))) { throw 'Uninstall did not retain model/cache data as designed.' }
$report.steps += [ordered]@{stage='unattended uninstall'; exit_code=$remove.ExitCode; retained_model_cache=$true}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $ReportDirectory 'report.json') -Encoding utf8
Write-Output "Installer unattended install, CPU inference, Apps & Features metadata and uninstall passed. Report: $ReportDirectory\report.json"
