$ErrorActionPreference = 'Stop'
$uninstaller = Join-Path $env:LOCALAPPDATA 'Programs\WhisperDesk\unins000.exe'
if (Test-Path -LiteralPath $uninstaller) {
    $process = Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "WhisperDesk uninstaller exited with code $($process.ExitCode)."
    }
}
